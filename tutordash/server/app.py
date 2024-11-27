import asyncio
import os
import shlex

# import sys
# import time
import typing as t

import aiofiles

# from contextlib import contextmanager

import tutor.env
from quart import Quart, render_template, request, websocket, redirect, url_for
from tutor import hooks
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
    # import module to trigger all the right imports and hooks
    # TODO how do we handle this now that we call the tutor binary directly? Should we
    # even deal with hooks at all? We have to to figure out plugin configuration,
    # information, etc.
    # pylint: disable=unused-import,import-outside-toplevel
    from tutor.commands.cli import cli

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


@app.post("/tutor/cli")
async def tutor_cli():
    # Run command asynchronously
    # TODO parse command from JSON request body
    # app.add_background_task(subprocess_exec, ["tutor", "config", "printvalue", "DOCKER_IMAGE_OPENEDX"])
    # app.add_background_task(subprocess_exec, ["tutor" "local", "launch"])
    # await subprocess_exec(["tutor", "config", "printvalue", "pouac"])
    await subprocess_exec(["tutor", "dev", "dc", "run", "pouac"])
    return redirect(url_for("tutor_logs"))


async def subprocess_exec(command: list[str]):
    path = TutorProject.tutor_stdout_path()
    # if os.path.exists(path):
    #     # TODO return 400? We can't run two commands at the same time
    #     return {}
    with open(path, "w", encoding="utf8") as stdout:
        # Print command
        # TODO this doesn't seem to work. For some reason, the command is added at the
        # bottom of the file!!!
        stdout.write(f"$ {shlex.join(command)}\n")
        # Run command
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=stdout,
            stderr=stdout,
            stdin=asyncio.subprocess.DEVNULL,
        )
        while proc.returncode is None:
            await proc.communicate()
            await asyncio.sleep(0.1)
    return {}


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
