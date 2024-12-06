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
    render_template,
    request,
    websocket,
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
    available. We store This file must be unique because it is accessed from a different thread.
    Basically, the log file is the API between threads.
    """

    INSTANCE: t.Optional["TutorCli"] = None

    @classmethod
    def run_parallel(cls, args: list[str]) -> None:
        """
        Run a command in a separate thread.
        """
        tutor_cli_runner = cls(args)
        thread = threading.Thread(target=tutor_cli_runner.run)
        thread.start()

        async def stop_on_reload() -> None:
            """
            This background task will stop the runner whenever the Quart app is
            requested to stop. This happens for instance on dev reload.
            """
            try:
                while True:
                    await asyncio.sleep(1)
            finally:
                app.logger.info(
                    "#################### thread.is_alive: %s Stopping command: %s...",
                    thread.is_alive(),
                    tutor_cli_runner.tutor_command,
                )
                tutor_cli_runner.stop()
                thread.join()

        app.add_background_task(stop_on_reload)

    @classmethod
    def stop_instance(cls) -> None:
        """
        Stop all running instances
        """
        if cls.INSTANCE:
            # TODO stop only actually running instances
            cls.INSTANCE.stop()

    def __init__(self, args: list[str]) -> None:
        """
        Every created instance is assigned to cls.INSTANCE.
        """
        self.args = args
        self.log_file = tempfile.NamedTemporaryFile(
            "ab", prefix="tutor-dash-", suffix=".log"
        )
        self._stop_flag = threading.Event()
        TutorCli.INSTANCE = self

    @property
    def log_path(self) -> str:
        """
        Path to the log file
        """
        return self.log_file.name

    @property
    def tutor_command(self) -> str:
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
            "Running command: tutor %s (logs: %s)", self.tutor_command, self.log_path
        )

        # Override execute function
        with patch_objects(
            [
                (tutor.utils, "execute", self._mock_execute),
                (fmt.click, "echo", self._mock_click_echo),
                (fmt.click, "style", self._mock_click_style),
            ]
        ):
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
        Stop all subprocess.Popen commands.
        """
        self._stop_flag.set()

    async def iter_logs(self) -> t.AsyncGenerator[str, None]:
        """
        Async stream content from file.

        This will handle gracefully file deletion. Note however that if the file is
        truncated, all contents added to the beginning until the current position will be
        missed.
        """
        async with aiofiles.open(self.log_path, "rb") as f:
            # Note that file reading needs to happen from the file path, because it maye
            # be done from a separate thread, where the file object is not available.
            while True:
                content = await f.read()
                if content:
                    yield content.decode()
                else:
                    await asyncio.sleep(0.1)

    # Mocking functions to override tutor functions that write to stdout
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
                            f"Command interrupted: {command_string}"
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
    # TODO important how to handle different commands? Currently, commands are not killed properly...
    TutorCli.stop_instance()
    # TODO parse command from JSON request body
    TutorCli.run_parallel(
        ["dev", "start"],
        # ["dev", "dc", "run", "--no-deps", "lms", "bash"],
        # ["config", "printvalue", "DOCKER_IMAGE_OPENEDX"],
        # ["config", "printvalue", "POUAC"],
        # ["local", "launch", "--non-interactive"],
    )
    return redirect(url_for("tutor_logs"))


@app.post("/tutor/cli/stop")
async def tutor_cli_stop() -> dict[str, str]:
    # TODO actually use this?
    TutorCli.stop_instance()
    return {}


@contextlib.contextmanager
def patch_objects(
    refs: list[tuple[object, str, t.Callable[[t.Any], t.Any]]]
) -> t.Iterator[None]:
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


@app.get("/tutor/logs")
async def tutor_logs() -> str:
    return await render_template("tutor_logs.html", **shared_template_context())


@app.websocket("/tutor/logs/stream")
async def tutor_logs_stream() -> None:
    while True:
        if TutorCli.INSTANCE:
            await websocket.send(f"$ {TutorCli.INSTANCE.tutor_command}\n")
            async for content in TutorCli.INSTANCE.iter_logs():
                try:
                    await websocket.send(content)
                except asyncio.CancelledError:
                    return
        await asyncio.sleep(0.1)


def shared_template_context() -> dict[str, t.Any]:
    """
    Common context shared between all views that make use of the base template.

    TODO isn't there a better way to achieve that? Either template variable or Quart feature.
    """
    return {
        "installed_plugins": sorted(set(hooks.Filters.PLUGINS_INSTALLED.iterate())),
    }
