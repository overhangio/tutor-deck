import asyncio
import json
import logging
import re
import sys
import typing as t

import importlib_metadata
from markdown import markdown
from quart import (
    Quart,
    Response,
    abort,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from quart.helpers import WerkzeugResponse
from quart.typing import ResponseTypes
from tutor.plugins.v1 import discover_package

from tutordeck.server.utils import current_page_plugins, pagination_context

from . import constants, tutorclient

app = Quart(
    __name__,
    static_url_path="/static",
    static_folder="static",
)


def run(root: str, **app_kwargs: t.Any) -> None:
    """
    Bootstrap the Quart app and run it.
    """
    tutorclient.Project.connect(root)

    # Configure logging
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    tutorclient.logger.addHandler(handler)
    tutorclient.logger.setLevel(logging.INFO)

    # TODO app.run() should be called only in development
    app.run(**app_kwargs)


@app.before_request
async def before_request() -> None:
    # Shared views and template context
    g.installed_plugins = tutorclient.Client.installed_plugins()
    g.enabled_plugins = tutorclient.Client.enabled_plugins()


@app.get("/")
async def home() -> str:
    return await render_template("plugin_installed.html")


@app.get("/plugin/store")
async def plugin_store() -> str:
    return await render_template("plugin_store.html")


@app.get("/plugin/installed")
async def plugin_installed() -> str:
    return await render_template("plugin_installed.html")


@app.get("/plugin/store/list")
async def plugin_store_list() -> str:
    search_query = request.args.get("search", "")
    plugins: list[dict[str, t.Any]] = [
        {
            "name": p.name,
            "url": p.url,
            "index": p.index,
            "author": p.author.split("<")[0].strip(),
            "description": p.short_description,
            "is_installed": p.name in g.installed_plugins,
            "is_enabled": p.name in g.enabled_plugins,
        }
        for p in tutorclient.Client.plugins_in_store()
        if p.name in tutorclient.Client.plugins_matching_pattern(search_query)
    ]

    current_page = int(request.args.get("page", "1"))
    plugins = current_page_plugins(plugins, current_page)
    pagination = pagination_context(plugins, current_page)

    return await render_template(
        "_plugin_store_list.html",
        plugins=plugins,
        pagination=pagination,
    )


@app.get("/plugin/installed/list")
async def plugin_installed_list() -> str:
    search_query = request.args.get("search", "")
    plugins: list[dict[str, t.Any]] = [
        {
            "name": p.name,
            "url": p.url,
            "index": p.index,
            "author": p.author.split("<")[0].strip(),
            "description": p.short_description,
            "is_enabled": p.name in g.enabled_plugins,
        }
        for p in tutorclient.Client.plugins_in_store()
        if p.name in tutorclient.Client.plugins_matching_pattern(search_query)
        and p.name in g.installed_plugins
    ]

    return await render_template(
        "_plugin_installed_list.html",
        plugins=plugins,
    )


@app.get("/plugin/<name>")
async def plugin(name: str) -> Response:
    # TODO check that plugin exists
    show_logs = request.args.get("show_logs")
    author = next(
        (
            p.author.split("<")[0].strip()
            for p in tutorclient.Client.plugins_in_store()
            if p.name == name
        ),
        "",
    )
    description = next(
        (
            markdown(p.description)
            for p in tutorclient.Client.plugins_in_store()
            if p.name == name
        ),
        "",
    )
    rendered_template = await render_template(
        "plugin.html",
        plugin_name=name,
        is_enabled=name in g.enabled_plugins,
        is_installed=name in g.installed_plugins,
        author_name=author,
        plugin_description=description,
        show_logs=show_logs,
        plugin_config_unique=tutorclient.Client.plugin_config_unique(name),
        plugin_config_defaults=tutorclient.Client.plugin_config_defaults(name),
        user_config=tutorclient.Project.get_user_config(),
    )
    response = Response(rendered_template, status=200, content_type="text/html")
    response.headers["HX-Redirect"] = url_for("plugin", name=name)
    return response


@app.post("/plugin/<name>/toggle")
async def plugin_toggle(name: str) -> Response:
    # TODO check plugin exists
    form = await request.form
    enable_plugin = form.get("checked") == "on"
    command = ["plugins", "enable" if enable_plugin else "disable", name]
    tutorclient.CliPool.run_sequential(command)
    # TODO error management

    response = t.cast(
        Response,
        await make_response(
            redirect(
                url_for(
                    "plugin",
                    name=name,
                )
            )
        ),
    )
    if enable_plugin:
        response.set_cookie(
            f"{constants.WARNING_COOKIE_PREFIX}-{name}",
            "requires launch",
            max_age=constants.ONE_MONTH,
        )
    else:
        response.delete_cookie(f"{constants.WARNING_COOKIE_PREFIX}-{name}")
    return response


@app.post("/plugin/<name>/install")
async def plugin_install(name: str) -> WerkzeugResponse:
    async def bg_install_and_reload() -> None:
        tutorclient.CliPool.run_parallel(app, ["plugins", "install", name])
        while tutorclient.CliPool.THREAD and tutorclient.CliPool.THREAD.is_alive():
            await asyncio.sleep(0.1)
        discover_package(importlib_metadata.entry_points().__getitem__(name))

    asyncio.create_task(bg_install_and_reload())
    return redirect(
        url_for(
            "plugin",
            name=name,
            show_logs=True,
        )
    )


@app.post("/plugin/<name>/upgrade")
async def plugin_upgrade(name: str) -> WerkzeugResponse:
    tutorclient.CliPool.run_parallel(app, ["plugins", "upgrade", name])
    return redirect(
        url_for(
            "plugin",
            name=name,
            show_logs=True,
        )
    )


@app.post("/plugins/update")
async def plugins_update() -> WerkzeugResponse:
    tutorclient.CliPool.run_parallel(app, ["plugins", "update"])
    return redirect(url_for("plugin_store"))


@app.post("/config/<name>/update")
async def config_update(name: str) -> Response:
    form = await request.form

    unset = form.get("unset")
    if unset:
        tutorclient.CliPool.run_sequential(["config", "save", f"--unset={unset}"])
    else:
        cmd = ["config", "save"]
        for key, value in form.items():
            if value.startswith("{{"):
                # Templated values that start with {{ should be explicitely converted to string
                # Otherwise there will be a parsing error because it might be considered a dictionary
                value = f"'{value}'"
            cmd.extend(["--set", f"{key}={value}"])
        tutorclient.CliPool.run_sequential(cmd)
    # TODO error management
    response = t.cast(
        Response,
        await make_response(
            redirect(
                url_for(
                    "plugin",
                    name=name,
                )
            )
        ),
    )
    response.set_cookie(
        f"{constants.WARNING_COOKIE_PREFIX}-{name}",
        "requires launch",
        max_age=constants.ONE_MONTH,
    )
    return response


@app.get("/local/launch")
async def local_launch_view() -> str:
    return await render_template(
        "local_launch.html",
    )


@app.post("/cli/local/launch")
async def cli_local_launch() -> str:
    tutorclient.CliPool.run_parallel(app, ["local", "launch", "--non-interactive"])
    return await render_template(
        "local_launch.html",
        show_logs=True,
    )


@app.get("/cli/logs/stream")
async def cli_logs_stream() -> ResponseTypes:
    """
    We only need single-direction communication, so we use server-sent events, and not
    websockets.
    https://quart.palletsprojects.com/en/latest/how_to_guides/server_sent_events.html

    Note that server interruption with ctrl+c does not work in Python 3.12 and 3.13
    because of this bug:
    https://github.com/pallets/quart/issues/333
    https://github.com/python/cpython/issues/123720

    Events are sent with the following format:

        data: "json-encoded string..."
        event: logs

    Data is JSON-encoded such that we can sent newline characters, etc.
    """

    # TODO check that request accepts event stream (see howto)
    async def send_events() -> t.AsyncIterator[bytes]:
        while True:
            # TODO this is again causing the stream to never stop...
            async for data in tutorclient.CliPool.iter_logs():
                json_data = json.dumps(data)
                event = f"data: {json_data}\nevent: logs\n\n"
                yield event.encode()
            await asyncio.sleep(constants.SHORT_SLEEP_SECONDS)

    response = await make_response(
        send_events(),
        {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Transfer-Encoding": "chunked",
        },
    )
    setattr(response, "timeout", None)
    return response


@app.post("/cli/stop")
async def cli_stop() -> Response:
    tutorclient.CliPool.stop()
    return Response(status=200)


@app.get("/advanced")
async def advanced() -> str:
    return await render_template(
        "advanced.html",
        show_logs=True,
    )


@app.post("/suggest")
async def suggest() -> Response:
    data = await request.get_json()
    partial_command = data.get("command", "")
    suggestions = tutorclient.Client.autocomplete(partial_command)
    return jsonify(suggestions)


@app.post("/command")
async def command() -> WerkzeugResponse:
    form = await request.form
    command_string = form.get("command", "")
    command_args = command_string.split()
    if tutorclient.CliPool.is_thread_alive():
        abort(400, description="Command execution already in progress")
    tutorclient.CliPool.run_parallel(app, command_args)
    return redirect(url_for("advanced"))
