import asyncio
import contextlib
import os
import shlex
import subprocess
import tempfile
import threading

import typing as t

import aiofiles

import tutor.env
from quart import (
    Quart,
    render_template,
    request,
    websocket,
    redirect,
    url_for,
)
from quart.helpers import WerkzeugResponse
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

    def __init__(self, args: list[str]) -> None:
        self.args = args
        self.log_path = tempfile.mktemp(prefix="tutor-dash-", suffix=".log")
        # TODO how do we ensure that the log file is deleted?
        TutorCli.INSTANCE = self

    @classmethod
    def run_parallel(cls, args: list[str]) -> None:
        """
        Run a command in a separate thread.
        """
        tutor_cli_runner = cls(args)
        thread = threading.Thread(target=tutor_cli_runner.run)
        thread.start()

    def run(self) -> None:
        """
        Execute some arbitrary tutor command.

        Output will be captured in the log file.
        TODO Return the exit code?
        """
        app.logger.info(
            "Running command: tutor %s (logs: %s)", shlex.join(self.args), self.log_path
        )
        with open(self.log_path, "w", encoding="utf8") as stdout:
            # TODO useless because overwritten by Popen
            stdout.write(f"$ tutor {shlex.join(self.args)}\n")

        # TODO refactor this ugly mocking
        def _mock_click_echo(text: str, **_kwargs: t.Any) -> None:
            with open(self.log_path, "a", encoding="utf8") as stdout:
                stdout.write(text)
                stdout.write("\n")

        def _mock_click_style(text: str, **_kwargs: t.Any) -> str:
            """
            Strip ANSI colors

            TODO convert to HTML color codes?
            """
            return text

        def _mock_execute(*command: str) -> int:
            """
            TODO refactor this
            """
            with open(self.log_path, "ab") as stdout:
                with subprocess.Popen(command, stdout=stdout, stderr=stdout) as p:
                    try:
                        result = p.wait(timeout=None)
                    except Exception as e:
                        p.kill()
                        p.wait()
                        raise TutorError(f"Command failed: {' '.join(command)}") from e
                    if result > 0:
                        raise TutorError(
                            f"Command failed with status {result}: {' '.join(command)}"
                        )
            return result

        # Override execute function
        with patch_objects(
            [
                (tutor.utils, "execute", _mock_execute),
                (fmt.click, "echo", _mock_click_echo),
                (fmt.click, "style", _mock_click_style),
            ]
        ):
            try:
                # Call tutor command
                cli(self.args)  # pylint: disable=no-value-for-parameter
            except TutorError as e:
                with open(self.log_path, "a", encoding="utf8") as stdout:
                    stdout.write(e.args[0])
            except SystemExit:
                # TODO what to do with e.code?
                pass

    async def iter_logs(self) -> t.AsyncGenerator[str, None]:
        """
        Async stream content from file.

        This will handle gracefully file deletion. Note however that if the file is
        truncated, all contents added to the beginning until the current position will be
        missed.
        """
        # TODO super ugly. Any way to do better?
        if not os.path.exists(self.log_path):
            return
        async with aiofiles.open(self.log_path, "r", encoding="utf8") as f:
            while True:
                if not os.path.exists(self.log_path):
                    break
                content = await f.read()
                if content:
                    yield content
                else:
                    await asyncio.sleep(0.1)


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
    return await render_template(
        "index.html",
        installed_plugins=sorted(set(hooks.Filters.PLUGINS_INSTALLED.iterate())),
    )


@app.get("/plugin/<name>")
async def plugin(name: str) -> str:
    # TODO check that plugin exists
    is_enabled = name in hooks.Filters.PLUGINS_LOADED.iterate()
    return await render_template("plugin.html", plugin_name=name, is_enabled=is_enabled)


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
    # TODO return 400 if thread is active
    # TODO parse command from JSON request body
    TutorCli.run_parallel(
        # ["dev", "dc", "run", "pouac"],
        # ["config", "printvalue", "DOCKER_IMAGE_OPENEDX"],
        ["config", "printvalue", "POUAC"],
        # ["local", "launch", "--non-interactive"],
    )
    return redirect(url_for("tutor_logs"))


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
    return await render_template("tutor_logs.html")


@app.websocket("/tutor/logs/stream")
async def tutor_logs_stream() -> None:
    while True:
        if TutorCli.INSTANCE:
            async for content in TutorCli.INSTANCE.iter_logs():
                try:
                    await websocket.send(content)
                except asyncio.CancelledError:
                    return
        # Exiting the loop means that the file no longer exists, so we wait a little
        await asyncio.sleep(0.1)
