import asyncio
import contextlib
import shlex
import subprocess
import tempfile
import threading
import typing as t

import aiofiles
from quart import (
    Quart,
    make_response,
    render_template,
    request,
    redirect,
    url_for,
)
from quart.helpers import WerkzeugResponse

import tutor.env
from tutor.exceptions import TutorError
from tutor import fmt, hooks
from tutor.types import Config
import tutor.utils
from tutor.commands.cli import cli

SHORT_SLEEP_SECONDS = 0.1


class TutorProject:
    """
    Provide access to the current Tutor project root and configuration.
    """

    CONFIG: dict[str, t.Any] = {}
    ROOT: str = ""

    @classmethod
    def connect(cls, root: str) -> None:
        """
        Call whenever we are ready to connect to the Tutor hooks API.
        """
        if not cls.ROOT:
            # Hook up TutorProject with Tutor hooks -- just once
            hooks.Actions.PROJECT_ROOT_READY.add()(cls._dash_on_project_root_ready)
            hooks.Actions.CONFIG_LOADED.add()(cls._dash_on_config_loaded)
        hooks.Actions.CORE_READY.do()  # discover plugins
        hooks.Actions.PROJECT_ROOT_READY.do(root)

    @classmethod
    def _dash_on_project_root_ready(cls, root: str) -> None:
        cls.ROOT = root

    @classmethod
    def _dash_on_config_loaded(cls, config: Config) -> None:
        cls.CONFIG = config


class TutorCli:
    """
    Run Tutor commands and capture the output in a file.

    Output must be a file because subprocess.Popen requires stdout.fileno() to be
    available. We store logs in temporary files.

    Tutor commands are not meant to be run in parallel. Thus, there must be only one
    instance running at any time: calling functions are responsible for calling
    TutorCliPool instead of this class.
    """

    def __init__(self, args: list[str]) -> None:
        """
        Each instance can be interrupted from other threads via the stop flag.
        """
        self.args = args
        self.log_file = tempfile.NamedTemporaryFile(
            "ab", prefix="tutor-dash-", suffix=".log"
        )
        self._stop_flag = threading.Event()

    @property
    def log_path(self) -> str:
        """
        Path to the log file
        """
        return self.log_file.name

    @property
    def command(self) -> str:
        """
        Tutor command executed by this runner.
        """
        return shlex.join(["tutor"] + self.args)

    def run(self) -> None:
        """
        Execute some arbitrary tutor command.

        Output will be captured in the log file.
        """
        app.logger.info(
            "Running command: tutor %s (logs: %s)", self.command, self.log_path
        )

        # Override execute function
        with self.patch_objects():
            try:
                # Call tutor command
                cli(self.args)  # pylint: disable=no-value-for-parameter
            except TutorError as e:
                # This happens for incorrect commands
                self.log_file.write(e.args[0].encode())
            except SystemExit:
                pass
            self.log_file.flush()

    def stop(self) -> None:
        """
        Sets the stop flag, whic is monitored by all subprocess.Popen commands.
        """
        app.logger.info("Stopping Tutor command: %s...", self.command)
        self._stop_flag.set()

    async def iter_logs(self) -> t.AsyncGenerator[str, None]:
        """
        Async stream content from file. Output is prefixed by the running command.

        This will handle gracefully file deletion. Note however that if the file is
        truncated, all contents added to the beginning until the current position will be
        missed.
        """
        yield f"$ {self.command}\n"
        async with aiofiles.open(self.log_path, "rb") as f:
            # Note that file reading needs to happen from the file path, because it maye
            # be done from a separate thread, where the file object is not available.
            while True:
                content = await f.read()
                if content:
                    yield content.decode()
                else:
                    await asyncio.sleep(SHORT_SLEEP_SECONDS)

    # Mocking functions to override tutor functions that write to stdout
    @contextlib.contextmanager
    def patch_objects(self) -> t.Iterator[None]:
        refs = [
            (tutor.utils, "execute", self._mock_execute),
            (fmt.click, "echo", self._mock_click_echo),
            (fmt.click, "style", self._mock_click_style),
        ]
        old_objects = []
        for module, object_name, new_object in refs:
            # backup old object
            old_objects.append((module, object_name, getattr(module, object_name)))
            # override object
            setattr(module, object_name, new_object)
        try:
            yield None
        finally:
            # restore old objects
            for module, object_name, old_object in old_objects:
                setattr(module, object_name, old_object)

    def _mock_click_echo(self, text: str, **_kwargs: t.Any) -> None:
        """
        Mock click.echo to write to log file
        """
        self.log_file.write(text.encode())
        self.log_file.write(b"\n")

    def _mock_click_style(self, text: str, **_kwargs: t.Any) -> str:
        """
        Mock click.style to strip ANSI colors

        TODO convert to HTML color codes?
        """
        return text

    def _mock_execute(self, *command: str) -> int:
        """
        Mock tutor.utils.execute.
        """
        command_string = shlex.join(command)
        with subprocess.Popen(
            command, stdout=self.log_file, stderr=self.log_file
        ) as popen:
            while popen.returncode is None:
                try:
                    popen.wait(timeout=0.5)
                except subprocess.TimeoutExpired as e:
                    # Check every now and then whether we should stop
                    if self._stop_flag.is_set():
                        popen.kill()
                        popen.wait()
                        raise TutorError(
                            f"Stopping child command: {command_string}"
                        ) from e
                except Exception as e:
                    popen.kill()
                    popen.wait()
                    raise TutorError(f"Command failed: {command_string}") from e

            if popen.returncode > 0:
                raise TutorError(
                    f"Command failed with status {popen.returncode}: {command_string}"
                )
            return popen.returncode


class TutorCliPool:
    INSTANCE: t.Optional["TutorCli"] = None
    THREAD: t.Optional[threading.Thread] = None

    @classmethod
    def run_parallel(cls, args: list[str]) -> None:
        """
        Run a command in a separate thread. This command automatically stops any running
        command.
        """
        # Stop any running command
        cls.stop()

        # Start thread
        cls.INSTANCE = TutorCli(args)
        cls.THREAD = threading.Thread(target=cls.INSTANCE.run)
        cls.THREAD.start()

        # Watch for exit
        app.add_background_task(cls.stop_on_exit, cls.INSTANCE, cls.THREAD)

    @classmethod
    def stop(cls) -> None:
        """
        Stop running instance.

        This is a no-op when there is no running thread, so it's safe to call any time.
        """
        if cls.INSTANCE and cls.THREAD:
            cls.stop_runner_thread(cls.INSTANCE, cls.THREAD)

    @staticmethod
    def stop_runner_thread(
        tutor_cli_runner: TutorCli, thread: threading.Thread
    ) -> None:
        """
        Set runner stop flag and wait for thread to complete.
        """
        if thread.is_alive():
            tutor_cli_runner.stop()
            thread.join()

    @classmethod
    async def stop_on_exit(
        cls, tutor_cli_runner: TutorCli, thread: threading.Thread
    ) -> None:
        """
        This background task will stop the runner whenever the Quart app is
        requested to stop/exit/shutdown. This happens for instance on dev reload.
        """
        try:
            while thread.is_alive():
                await asyncio.sleep(SHORT_SLEEP_SECONDS)
        finally:
            cls.stop_runner_thread(tutor_cli_runner, thread)

    @classmethod
    async def iter_logs(cls) -> t.AsyncGenerator[str, None]:
        """
        Iterate indefinitely from any running instance. When an existing instance is
        replaced by another one, previous logs are not deleted. New ones are simply
        appended.
        """
        while cls.INSTANCE:
            async for log in cls.INSTANCE.iter_logs():
                yield log


app = Quart(
    __name__,
    static_url_path="/static",
    static_folder="static",
)


def run(root: str, **app_kwargs: t.Any) -> None:
    """
    Bootstrap the Quart app and run it.
    """
    TutorProject.connect(root)
    app.run(**app_kwargs)


@app.get("/")
async def home() -> str:
    return await render_template("index.html", **shared_template_context())


@app.get("/plugin/<name>")
async def plugin(name: str) -> str:
    # TODO check that plugin exists
    is_enabled = name in hooks.Filters.PLUGINS_LOADED.iterate()
    return await render_template(
        "plugin.html",
        plugin_name=name,
        is_enabled=is_enabled,
        **shared_template_context(),
    )


@app.post("/plugin/<name>/toggle")
async def toggle_plugin(name: str) -> dict[str, str]:
    # TODO check plugin exists
    form = await request.form
    enabled = form.get("enabled")
    if enabled not in ["on", "off"]:
        # TODO request validation. Can't we validate requests with a proper tool, such
        # as pydantic or a rest framework?
        return {}

    # TODO actually toggle plugin
    app.logger.info("Toggling plugin %s", name)

    return {}


@app.post("/tutor/cli")
async def tutor_cli() -> WerkzeugResponse:
    # Run command asynchronously
    # if TutorCli.is_thread_alive():
    # TODO return 400 if thread is active
    # TODO parse command from JSON request body
    TutorCliPool.run_parallel(
        ["dev", "start"],
        # ["dev", "dc", "run", "--no-deps", "lms", "bash"],
        # ["config", "printvalue", "DOCKER_IMAGE_OPENEDX"],
        # ["config", "printvalue", "POUAC"],
        # ["local", "launch", "--non-interactive"],
    )
    return redirect(url_for("tutor_cli_logs"))


@app.post("/tutor/cli/stop")
async def tutor_cli_stop() -> WerkzeugResponse:
    TutorCliPool.stop()
    return redirect(url_for("tutor_cli_logs"))


@app.get("/tutor/logs")
async def tutor_cli_logs() -> str:
    return await render_template("tutor_cli_logs.html", **shared_template_context())


@app.get("/tutor/cli/logs/stream")
async def tutor_cli_logs_stream() -> None:
    # Websockets were not working for us in dev mode, we were unable to stop the server
    # as long as there were open connection. We only need single-direction
    # communication, so we use server-sent events
    # https://github.com/pallets/quart/issues/333
    # https://quart.palletsprojects.com/en/latest/how_to_guides/server_sent_events.html
    async def send_events():
        while True:
            # TODO this is again causing the stream to never stop...
            async for data in TutorCliPool.iter_logs():
                event = f"data: {data}\nevent: logs\n"
                # TODO encode one way or another to be able to send EOL characters and other weird chars
                yield event.encode()
            await asyncio.sleep(SHORT_SLEEP_SECONDS)

    response = await make_response(
        send_events(),
        {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Transfer-Encoding": "chunked",
        },
    )
    response.timeout = None
    return response


def shared_template_context() -> dict[str, t.Any]:
    """
    Common context shared between all views that make use of the base template.

    TODO isn't there a better way to achieve that? Either template variable or Quart feature.
    """
    return {
        "installed_plugins": sorted(set(hooks.Filters.PLUGINS_INSTALLED.iterate())),
    }
