import asyncio
import importlib_metadata
import json
import logging
import sys
import typing as t

from markdown import markdown
from quart import (
    Quart,
    make_response,
    render_template,
    request,
    redirect,
    url_for,
)
from quart.helpers import WerkzeugResponse
from quart.typing import ResponseTypes

from . import constants
from . import tutorclient


app = Quart(
    __name__,
    static_url_path="/static",
    static_folder="static",
)

ONE_MONTH = 60*60*24*30
WARNING_COOKIE_PREFIX = "warning-cookie"

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
    return await render_template("index.html", **shared_template_context())


@app.get("/plugin/store")
async def plugin_store() -> str:
    installed_plugins = tutorclient.Client.installed_plugins()
    plugins: list[dict[str, str]] = [
        {
            "name": p.name,
            "url": p.url,
            "index": p.index,
            "author": p.author.split('<')[0].strip(),
            "description": markdown(p.description.replace("\n", " ")),
            "is_installed": p.name in installed_plugins,
        }
        for p in tutorclient.Client.plugins_in_store()
    ]

    search_query = request.args.get("q", default="", type=str).strip().lower()
    if search_query:
        plugins = [plugin for plugin in plugins if search_query in plugin["name"].lower()]

    page = request.args.get("page", default=1, type=int)
    per_page = 9
    total_pages = (len(plugins) + per_page - 1) // per_page
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    plugins = plugins[start:end]

    return await render_template(
        "plugin_store.html",
        plugins=plugins,
        page_count=total_pages,
        current_page=page,
        **shared_template_context(),
    )


@app.get("/plugin/installed")
async def installed_plugins() -> str:
    installed_plugins = tutorclient.Client.installed_plugins()
    enabled_plugins = tutorclient.Client.enabled_plugins()
    store_plugins: dict[str, dict[str, str]] = {
        p.name: {
            "url": p.url,
            "index": p.index,
            "author": p.author.split('<')[0].strip(),
            "description": markdown(p.description.replace("\n", " ")),
        }
        for p in tutorclient.Client.plugins_in_store()
    }
    plugins: list[dict[str, str]] = [
        {
            "name": plugin_name,
            "url": store_plugins[plugin_name]["url"] if plugin_name in store_plugins else "",
            "index": store_plugins[plugin_name]["index"] if plugin_name in store_plugins else "",
            "author": store_plugins[plugin_name]["author"].split('<')[0].strip() if plugin_name in store_plugins else "",
            "description": markdown(store_plugins[plugin_name]["description"]) if plugin_name in store_plugins else "",
            "is_enabled": plugin_name in enabled_plugins,
        }
        for plugin_name in installed_plugins
    ]

    search_query = request.args.get("q", default="", type=str).strip().lower()
    if search_query:
        plugins = [plugin for plugin in plugins if search_query in plugin["name"].lower()]

    return await render_template(
        "installed_plugins.html",
        plugins=plugins,
        **shared_template_context(),
    )


@app.get("/plugin/<name>")
async def plugin(name: str) -> str:
    # TODO check that plugin exists
    show_logs = request.args.get("show_logs")
    is_enabled = name in tutorclient.Client.enabled_plugins()
    is_installed = name in tutorclient.Client.installed_plugins()
    author = next((p.author.split('<')[0].strip() for p in tutorclient.Client.plugins_in_store() if p.name == name), "")
    description = next((markdown(p.description) for p in tutorclient.Client.plugins_in_store() if p.name == name), "")
    return await render_template(
        "plugin.html",
        plugin_name=name,
        is_enabled=is_enabled,
        is_installed=is_installed,
        author_name=author,
        plugin_description=description,
        plugin_config_unique=tutorclient.Client.plugin_config_unique(name),
        plugin_config_defaults=tutorclient.Client.plugin_config_defaults(name),
        user_config=tutorclient.Project.get_user_config(),
        show_logs=show_logs,
        **shared_template_context(),
    )


@app.post("/plugin/<name>/toggle")
async def plugin_toggle(name: str) -> WerkzeugResponse:
    # TODO check plugin exists
    form = await request.form
    enable_plugin = form.get("checked") == "on"
    command = ["plugins", "enable" if enable_plugin else "disable", name]
    tutorclient.CliPool.run_sequential(command)
    # TODO error management
    response = await make_response(redirect(url_for("plugin", name=name)))
    if enable_plugin:
        response.set_cookie(f"{WARNING_COOKIE_PREFIX}-{name}", "requires launch", max_age=ONE_MONTH)
    else:
        entrypoints = importlib_metadata.entry_points(name=name)
        for entrypoint in entrypoints:
            sys.modules.pop(entrypoint.value)
        response.delete_cookie(f"{WARNING_COOKIE_PREFIX}-{name}")
    return response


@app.post("/plugin/<name>/install")
async def plugin_install(name: str) -> WerkzeugResponse:
    async def bg_install_and_reload():
        tutorclient.CliPool.run_parallel(app, ["plugins", "install", name])
        while tutorclient.CliPool.THREAD and tutorclient.CliPool.THREAD.is_alive():
            await asyncio.sleep(0.1)
        tutorclient.Client.reload_plugins()
    asyncio.create_task(bg_install_and_reload())
    return redirect(url_for("plugin", name=name, show_logs=True))


@app.post("/plugin/<name>/upgrade")
async def plugin_upgrade(name: str) -> WerkzeugResponse:
    tutorclient.CliPool.run_parallel(app, ["plugins", "upgrade", name])
    return redirect(url_for("plugin", name=name, show_logs=True))

@app.post("/plugins/update")
async def plugins_update() -> WerkzeugResponse:
    tutorclient.CliPool.run_parallel(app, ["plugins", "update"])
    return redirect(url_for("cli_logs"))

@app.post("/config/<name>/set")
async def config_set(name: str) -> WerkzeugResponse:
    form = await request.form
    value = form.get("value", "")
    plugin_name = form.get("plugin_name")
    tutorclient.CliPool.run_sequential(["config", "save", "--set", f"{name}={value}"])
    # TODO error management
    response = await make_response(redirect(request.args.get("next", "/")))
    response.set_cookie(f"{WARNING_COOKIE_PREFIX}-{plugin_name}", "requires launch", max_age=ONE_MONTH)
    return response


@app.post("/config/<name>/unset")
async def config_unset(name: str) -> WerkzeugResponse:
    tutorclient.CliPool.run_sequential(["config", "save", f"--unset={name}"])
    # TODO error management
    return redirect(request.args.get("next", "/"))


# def tutor_cli(command: list[str]) -> WerkzeugResponse:
#     # Run command asynchronously
#     # if TutorCli.is_thread_alive():
#     # TODO return 400 if thread is active
#     # TODO parse command from JSON request body
#     tutorclient.CliPool.run_parallel(app, command)
#     return redirect(url_for("cli_logs"))


@app.post("/cli/local/launch")
async def cli_local_launch() -> WerkzeugResponse:
    tutorclient.CliPool.run_parallel(app, ["local", "launch", "--non-interactive"])
    response = await make_response(redirect(url_for("cli_logs")))
    for cookie_name in request.cookies:
        if cookie_name.startswith(WARNING_COOKIE_PREFIX):
            response.delete_cookie(cookie_name)
    return response


@app.get("/cli/logs")
async def cli_logs() -> str:
    name = request.args.get("name")
    return await render_template("cli_logs.html", name=name, **shared_template_context())


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
async def cli_stop() -> WerkzeugResponse:
    tutorclient.CliPool.stop()
    return redirect(url_for("cli_logs"))


def shared_template_context() -> dict[str, t.Any]:
    """
    Common context shared between all views that make use of the base template.

    TODO isn't there a better way to achieve that? Either template variable or Quart feature.
    """
    return {
        "installed_plugins": tutorclient.Client.installed_plugins(),
        "enabled_plugins": tutorclient.Client.enabled_plugins(),
    }
