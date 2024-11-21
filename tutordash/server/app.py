import asyncio
import os

# import sys
# import time
import typing as t

import aiofiles

# from contextlib import contextmanager

import tutor.env
from quart import Quart, render_template, request, websocket
from tutor import hooks

# from tutor.commands.cli import cli
from tutor.types import Config


class TutorProject:
    """
    TODO This big god class is not very elegant.
    """

    CONFIG: dict[str, t.Any] = {}
    ROOT: str = ""

    @staticmethod
    def installed_plugins() -> list[str]:
        return sorted(set(hooks.Filters.PLUGINS_INSTALLED.iterate()))

    @staticmethod
    def enabled_plugins() -> list[str]:
        return sorted(set(hooks.Filters.PLUGINS_LOADED.iterate()))

    @hooks.Actions.CONFIG_LOADED.add()
    @staticmethod
    def _dash_update_tutor_config(config: Config) -> None:
        TutorProject.CONFIG = config

    @hooks.Actions.PROJECT_ROOT_READY.add()
    @staticmethod
    def _dash_update_tutor_root(root: str) -> None:
        TutorProject.ROOT = root

    @classmethod
    def tutor_stdout_path(cls):
        return tutor.env.data_path(cls.ROOT, "dash", "tutor.log")


app = Quart(
    __name__,
    static_url_path="/static",
    static_folder="static",
)


def run(root: str, **app_kwargs: t.Any) -> None:
    hooks.Actions.CORE_READY.do()  # discover plugins
    hooks.Actions.PROJECT_ROOT_READY.do(root)
    app.logger.info("Dash tutor logs location: %s", TutorProject.tutor_stdout_path())
    app.run(**app_kwargs)


@app.get("/")
async def home():
    return await render_template("index.html")


@app.get("/sidebar/plugins")
async def sidebar_plugins():
    return await render_template(
        "sidebar/_plugins.html",
        installed_plugins=sorted(set(hooks.Filters.PLUGINS_INSTALLED.iterate())),
    )


@app.get("/plugin/<name>")
async def plugin(name: str):
    # TODO check that plugin exists
    is_enabled = name in TutorProject.enabled_plugins()
    return await render_template("plugin.html", plugin_name=name, is_enabled=is_enabled)


@app.post("/plugin/<name>/toggle")
async def toggle_plugin(name: str):
    # TODO check plugin exists
    form = await request.form
    enabled = form.get("enabled")
    if enabled not in ["on", "off"]:
        # TODO request validation. Can't we validate requests with a proper tool, such
        # as pydantic or a rest framework?
        return {}

    return {}


# @app.post("/tutor")
# async def run_tutor():
#     """
#     Run an arbitrary tutor command.
#     """
#     try:
#         with capture_stdout() as stdout:
#             # pylint: disable=no-value-for-parameter
#             cli(["config", "printvalue", "DOCKER_IMAGE_OPENEDX"])
#     except SystemExit as e:
#         if e.code == 0:
#             # success!
#             return {}
#         else:
#             # TODO Return 500?
#             return {}
#     # TODO


@app.get("/tutor/logs")
async def tutor_logs():
    return await render_template("tutor_logs.html")


@app.websocket("/tutor/logs/stream")
async def tutor_logs_stream():
    while True:
        async for content in stream_file(TutorProject.tutor_stdout_path()):
            try:
                await websocket.send(content)
            except asyncio.CancelledError:
                return
        # Exiting the loop means that the file no longer exists, so we wait a little
        await asyncio.sleep(0.1)


async def stream_file(path: str) -> t.Iterator[str]:
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


# @contextmanager
# def capture_stdout():
#     sys_stdout = sys.stdout
#     try:
#         while os.path.exists(TutorProject.tutor_stdout_path()):
#             # TODO thread-safe, lock-based implementation that does not use sleep()
#             await asyncio.sleep(0.1)
#         with open(TutorProject.tutor_stdout_path(), "wb", encoding="utf8") as stdout:
#             sys.stdout = stdout
#             sys.stderr = stdout
#             yield stdout
#     finally:
#         if os.path.exists(TutorProject.tutor_stdout_path()):
#             # TODO more reliable implementation
#             os.remove(TutorProject.tutor_stdout_path())
#         sys.stdout = sys_stdout
