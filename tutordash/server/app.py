import asyncio
import json
import logging
import sys
import typing as t

import importlib_metadata
from markdown import markdown
from quart import (
    Quart,
    Response,
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


@app.get("/")
async def home() -> str:
    return await render_template("plugin_installed.html", **shared_template_context())


@app.get("/plugin/store")
async def plugin_store() -> str:
    return await render_template("plugin_store.html", **shared_template_context())


@app.get("/plugin/installed")
async def plugin_installed() -> str:
    return await render_template("plugin_installed.html", **shared_template_context())


@app.get("/plugin/store/list")
async def plugin_store_list() -> str:
    search_query = request.args.get("search", "")
    installed_plugins = tutorclient.Client.installed_plugins()
    enabled_plugins = tutorclient.Client.enabled_plugins()
    plugins: list[dict[str, str]] = [
        {
            "name": p.name,
            "url": p.url,
            "index": p.index,
            "author": p.author.split("<")[0].strip(),
            "description": markdown(p.description.replace("\n", " ")),
            "is_installed": p.name in installed_plugins,
            "is_enabled": p.name in enabled_plugins,
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
        **shared_template_context(),
    )


@app.get("/plugin/installed/list")
async def plugin_installed_list() -> str:
    search_query = request.args.get("search", "")
    installed_plugins = tutorclient.Client.installed_plugins()
    enabled_plugins = tutorclient.Client.enabled_plugins()
    plugins: list[dict[str, str]] = [
        {
            "name": p.name,
            "url": p.url,
            "index": p.index,
            "author": p.author.split("<")[0].strip(),
            "description": markdown(p.description.replace("\n", " ")),
            "is_enabled": p.name in enabled_plugins,
        }
        for p in tutorclient.Client.plugins_in_store()
        if p.name in tutorclient.Client.plugins_matching_pattern(search_query)
        and p.name in installed_plugins
    ]

    return await render_template(
        "_plugin_installed_list.html",
        plugins=plugins,
        **shared_template_context(),
    )


@app.get("/plugin/<name>")
async def plugin(name: str) -> str:
    # TODO check that plugin exists
    show_logs = request.args.get("show_logs")
    is_enabled = name in tutorclient.Client.enabled_plugins()
    is_installed = name in tutorclient.Client.installed_plugins()
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
        is_enabled=is_enabled,
        is_installed=is_installed,
        author_name=author,
        plugin_description=description,
        show_logs=show_logs,
        plugin_config_unique=tutorclient.Client.plugin_config_unique(name),
        plugin_config_defaults=tutorclient.Client.plugin_config_defaults(name),
        user_config=tutorclient.Project.get_user_config(),
        **shared_template_context(),
    )
    response = Response(rendered_template, status=200, content_type="text/html")
    response.headers["HX-Redirect"] = url_for("plugin", name=name)
    return response


@app.post("/plugin/<name>/toggle")
async def plugin_toggle(name: str) -> WerkzeugResponse:
    # TODO check plugin exists
    form = await request.form
    enable_plugin = form.get("checked") == "on"
    command = ["plugins", "enable" if enable_plugin else "disable", name]
    tutorclient.CliPool.run_sequential(command)
    # TODO error management

    response = await make_response(
        redirect(
            url_for(
                "plugin",
                name=name,
            )
        )
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
    async def bg_install_and_reload():
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


@app.post("/config/set/multi")
async def config_set_multi() -> WerkzeugResponse:
    form = await request.form
    plugin_name = form.get("plugin_name")

    cmd = ["config", "save"]
    for key, value in form.items():
        if key != "plugin_name":
            cmd.extend(["--set", f"{key}={value}"])
    tutorclient.CliPool.run_sequential(cmd)
    # TODO error management
    response = await make_response(
        redirect(
            url_for(
                "plugin",
                name=plugin_name,
            )
        )
    )
    response.set_cookie(
        f"{constants.WARNING_COOKIE_PREFIX}-{plugin_name}",
        "requires launch",
        max_age=constants.ONE_MONTH,
    )
    return response


@app.post("/config/<name>/unset")
async def config_unset(name: str) -> WerkzeugResponse:
    tutorclient.CliPool.run_sequential(["config", "save", f"--unset={name}"])
    form = await request.form
    plugin_name = form.get("plugin_name")
    # TODO error management
    response = await make_response(
        redirect(
            url_for(
                "plugin",
                name=plugin_name,
            )
        )
    )
    response.set_cookie(
        f"{constants.WARNING_COOKIE_PREFIX}-{plugin_name}",
        "requires launch",
        max_age=constants.ONE_MONTH,
    )
    return response


# def tutor_cli(command: list[str]) -> WerkzeugResponse:
#     # Run command asynchronously
#     # if TutorCli.is_thread_alive():
#     # TODO return 400 if thread is active
#     # TODO parse command from JSON request body
#     tutorclient.CliPool.run_parallel(app, command)
#     return redirect(url_for("cli_logs"))


@app.get("/local/launch")
async def local_launch_view() -> str:
    return await render_template(
        "local_launch.html",
        **shared_template_context(),
    )


@app.post("/cli/local/launch")
async def cli_local_launch() -> WerkzeugResponse:
    tutorclient.CliPool.run_parallel(app, ["local", "launch", "--non-interactive"])
    response = await make_response(
        redirect(
            url_for(
                "cli_logs",
            )
        )
    )
    for cookie_name in request.cookies:
        if cookie_name.startswith(constants.WARNING_COOKIE_PREFIX):
            response.delete_cookie(cookie_name)
    return response


@app.get("/cli/logs")
async def cli_logs() -> str:
    name = request.args.get("name")
    return await render_template(
        "local_launch.html",
        name=name,
        show_logs=True,
        **shared_template_context(),
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
async def cli_stop() -> None:
    tutorclient.CliPool.stop()


@app.get("/advanced")
async def advanced() -> str:
    return await render_template(
        "advanced.html",
        show_logs=True,
        **shared_template_context(),
    )


@app.post("/suggest")
async def suggest():
    data = await request.get_json()
    partial_command = data.get("command", "")
    suggestions = tutorclient.Client.autocomplete(partial_command)
    return jsonify(suggestions)


@app.post("/command")
async def command() -> str:
    form = await request.form
    command_string = form.get("command", "")
    command_args = command_string.split()
    tutorclient.CliPool.run_parallel(app, command_args)
    return await make_response(redirect(url_for("advanced")))


def shared_template_context() -> dict[str, t.Any]:
    """
    Common context shared between all views that make use of the base template.

    TODO isn't there a better way to achieve that? Either template variable or Quart feature.
    """
    return {
        "installed_plugins": tutorclient.Client.installed_plugins(),
        "enabled_plugins": tutorclient.Client.enabled_plugins(),
    }


def pagination_context(
    plugins: list[dict[str, str]], current_page: int
) -> dict[str, t.Any]:
    total_pages = (
        len(plugins) + constants.ITEMS_PER_PAGE - 1
    ) // constants.ITEMS_PER_PAGE
    return {
        "current_page": current_page,
        "total_pages": total_pages,
        "previous_page": current_page - 1 if current_page > 1 else None,
        "next_page": current_page + 1 if current_page < total_pages else None,
    }


def current_page_plugins(
    plugins: list[dict[str, str]], current_page: int
) -> list[dict[str, str]]:
    start_index = (current_page - 1) * constants.ITEMS_PER_PAGE
    end_index = start_index + constants.ITEMS_PER_PAGE
    return plugins[start_index:end_index]
