import asyncio
from contextlib import contextmanager
import logging
import os
import shlex
import subprocess
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

logger = logging.getLogger(__name__)


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

    @classmethod
    def tutor_stdout_path(cls) -> str:
        return tutor.env.data_path(cls.ROOT, "dash", "tutor.log")


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
    app.logger.info("Dash tutor logs location: %s", TutorProject.tutor_stdout_path())
    app.run(**app_kwargs)


@app.get("/")
async def home() -> str:
    return await render_template("index.html")


@app.get("/sidebar/plugins")
async def sidebar_plugins() -> str:
    # TODO get rid of this view and render from home()
    return await render_template(
        "sidebar/_plugins.html",
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
    logger.info("Toggling plugin %s", name)

    return {}


@app.post("/tutor/cli")
async def tutor_cli() -> WerkzeugResponse:
    # Run command asynchronously
    # TODO return 400 if thread is active
    # TODO parse command from JSON request body
    thread = threading.Thread(
        target=run_tutor_cli,
        # args=[["dev", "dc", "run", "pouac"]],
        # args=[["config", "printvalue", "DOCKER_IMAGE_OPENEDX"]],
        # args=[["config", "printvalue", "POUAC"]],
        args=[["local", "launch", "--non-interactive"]],
    )
    thread.start()
    return redirect(url_for("tutor_logs"))


def run_tutor_cli(args: list[str]) -> None:
    """
    Execute some arbitrary tutor command. Capture the output in a dedicated file.

    TODO Return the exit code?
    TODO Refactor this
    """
    with open(TutorProject.tutor_stdout_path(), "w", encoding="utf8") as stdout:
        # useless because overwritten by Popen
        stdout.write(f"$ tutor {shlex.join(args)}\n")

    # Override execute function
    with patch_objects(
        [
            (tutor.utils, "execute", execute),
            (fmt.click, "echo", click_echo),
            (fmt.click, "style", click_style),
        ]
    ):
        try:
            # Call tutor command
            cli(args)  # pylint: disable=no-value-for-parameter
        except TutorError as e:
            with open(TutorProject.tutor_stdout_path(), "a", encoding="utf8") as stdout:
                stdout.write(e.args[0])
        except SystemExit:
            # TODO what to do with e.code?
            pass


@contextmanager
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


def click_echo(text: str, **_kwargs: t.Any) -> None:
    with open(TutorProject.tutor_stdout_path(), "a", encoding="utf8") as stdout:
        stdout.write(text)
        stdout.write("\n")


def click_style(text: str, **_kwargs: t.Any) -> str:
    """
    Strip ANSI colors

    TODO convert to HTML color codes?
    """
    return text


def execute(*command: str) -> int:
    """
    TODO refactor this
    """
    with open(TutorProject.tutor_stdout_path(), "ab") as stdout:
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


@app.get("/tutor/logs")
async def tutor_logs() -> str:
    return await render_template("tutor_logs.html")


@app.websocket("/tutor/logs/stream")
async def tutor_logs_stream() -> None:
    while True:
        async for content in stream_file(TutorProject.tutor_stdout_path()):
            try:
                await websocket.send(content)
            except asyncio.CancelledError:
                return
        # Exiting the loop means that the file no longer exists, so we wait a little
        await asyncio.sleep(0.1)


async def stream_file(path: str) -> t.AsyncGenerator[str]:
    """
    Async stream content from file.

    This will handle gracefully file deletion. Note however that if the file is
    truncated, all contents added to the beginning until the current position will be
    missed.
    """
    if not os.path.exists(path):
        return
    async with aiofiles.open(path, "r", encoding="utf8") as f:
        while True:
            if not os.path.exists(path):
                break
            content = await f.read()
            if content:
                yield content
            else:
                await asyncio.sleep(0.1)
