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
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from quart.typing import ResponseTypes
from werkzeug.sansio.response import Response as BaseResponse
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

    # Configure authentication
    HttpAuthCredentials.load_credentials()

    # TODO app.run() should be called only in development
    app.run(**app_kwargs)


class HttpAuthCredentials:
    USERNAME: str = ""
    PASSWORD: str = ""

    @classmethod
    def load_credentials(cls) -> None:
        """
        Load config and fetch credentials.

        This method should be called every time the configuration is updated.
        """
        config = tutorclient.Project.get_config()
        cls.USERNAME = t.cast(str, config.get("DECK_AUTH_USERNAME", ""))
        cls.PASSWORD = t.cast(str, config.get("DECK_AUTH_PASSWORD", ""))

    @classmethod
    def is_auth_success(cls) -> bool:
        """
        Returns True if the current request has the right HTTP basic auth credentials.
        """
        if not cls.USERNAME or not cls.PASSWORD:
            # No credential required
            return True

        if not request.authorization:
            # No credential was provided
            return False

        # Check provided credentials
        username = request.authorization.parameters.get("username")
        password = request.authorization.parameters.get("password")
        return username == cls.USERNAME and password == cls.PASSWORD


@app.before_request
def http_basic_auth() -> t.Optional[tuple[str, int, dict[str, str]]]:
    """
    Check authentication headers if necessary.
    """
    if not HttpAuthCredentials.is_auth_success():
        # https://quart.palletsprojects.com/en/latest/reference/response_values/#tuple-str-int-dict-str-str
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/401
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Authentication#authentication_schemes
        return "", 401, {"WWW-Authenticate": "basic"}

    return None


@app.before_request
async def before_request() -> None:
    """
    Store installed and enabled plugins as global attributes.
    """
    # Shared views and template context
    g.installed_plugins = tutorclient.Client.installed_plugins()
    g.enabled_plugins = tutorclient.Client.enabled_plugins()


@app.get("/")
async def home() -> BaseResponse:
    """
    Home redirects to the list of installed plugins
    """
    return redirect(url_for("plugin_installed"))


@app.get("/configuration")
async def configuration() -> str:
    config = tutorclient.Project.get_config()

    # Load base config with essential settings
    base_settings = [
        "LMS_HOST",
        "CMS_HOST",
        "LANGUAGE_CODE",
        "ENABLE_HTTPS",
    ]
    base_config = {key: config.pop(key) for key in base_settings}

    # User-saved configuration
    user_config = tutorclient.Project.get_user_config()

    return await render_template(
        "configuration.html",
        base_config=base_config,
        user_config=user_config,
        config=dict(sorted(config.items())),
    )


@app.post("/configuration")
async def configuration_update() -> BaseResponse:
    """
    Update configuration settings.

    TODO IMPORTANT display "need to run launch".
    """
    await process_config_update_request()

    response: BaseResponse
    if next_url := request.args.get("next", ""):
        # Handle non-ajax call
        response = redirect(next_url)
    else:
        # Handle ajax call
        response = Response("", status=200, content_type="text/html")
        response.headers["HX-Redirect"] = url_for("configuration")

    notify_run_sequential(response)
    return response


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
            "author": tutorclient.Client.get_plugin_author(p),
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
    """
    Search for installed plugins that match a certain query.

    Notes:
    - this returns not just the plugins that are in the store. When a plugin
      is installed locally but not in the store, we must display it here anyway.
    - in most cases the search argument is empty.
    - the match method is slightly different than store search. We match just on name.
      That's because some installed plugins don't have any description.
    """
    search_query = request.args.get("search", "").lower()

    # Search for plugins
    # Note that in most cases the search argument is empty.
    # Note also that this is slightly different than store search. That's because some
    # installed plugins may not be present in the store.
    plugins_found = []
    for name in g.installed_plugins:
        # Simple pattern matching
        if search_query in name.lower() or not search_query:
            plugins_found.append(name)

    # Match with plugins in store
    store_plugins = {
        p.name: p
        for p in tutorclient.Client.plugins_in_store()
        if p.name in plugins_found
    }

    # Collect results
    plugins: list[dict[str, t.Any]] = []
    for name in plugins_found:
        result = {
            "name": name,
            "author": "",
            "description": "",
            "is_enabled": name in g.enabled_plugins,
        }
        if store_plugin := store_plugins.get(name):
            result["description"] = store_plugin.short_description
            result["author"] = tutorclient.Client.get_plugin_author(store_plugin)
        plugins.append(result)

    return await render_template(
        "_plugin_installed_list.html",
        plugins=plugins,
    )


@app.get("/plugin/<name>")
async def plugin(name: str) -> Response:
    index_entry = tutorclient.Client.plugin_in_store(name)

    # Plugin must either be installed or available in the store
    if not index_entry and name not in g.installed_plugins:
        return Response("Plugin not found", status=404)

    description = markdown(index_entry.description) if index_entry else ""
    rendered_template = await render_template(
        "plugin.html",
        plugin_name=name,
        is_enabled=name in g.enabled_plugins,
        is_installed=name in g.installed_plugins,
        author_name=(
            tutorclient.Client.get_plugin_author(index_entry) if index_entry else ""
        ),
        plugin_description=description,
        plugin_config_unique=tutorclient.Client.plugin_config_unique(name),
        plugin_config_defaults=tutorclient.Client.plugin_config_defaults(name),
        user_config=tutorclient.Project.get_user_config(),
    )

    # Redirect to plugin page
    response = Response(rendered_template, status=200, content_type="text/html")

    response.headers["HX-Redirect"] = url_for("plugin", name=name)
    return response


@app.get("/plugin/<name>/is-installed")
def plugin_installed_status(name: str) -> Response:
    return jsonify({"installed": name in g.installed_plugins})


@app.post("/plugin/<name>/toggle")
async def plugin_toggle(name: str) -> Response:
    # TODO check plugin exists
    form = await request.form
    enable_plugin = form.get("checked") == "on"
    tutorclient.CliPool.run_sequential(
        ["plugins", "enable" if enable_plugin else "disable", name]
    )
    # TODO error management

    response = t.cast(
        Response,
        await make_response(redirect(url_for("plugin", name=name))),
    )
    notify_run_sequential(response)
    if enable_plugin:
        update_plugins_requiring_launch(response, add=name)
    else:
        update_plugins_requiring_launch(response, remove=name)
    return response


@app.post("/plugin/<name>/install")
async def plugin_install(name: str) -> BaseResponse:
    async def bg_install_and_reload() -> None:
        tutorclient.CliPool.run_parallel(app, ["plugins", "install", name])
        while tutorclient.CliPool.THREAD and tutorclient.CliPool.THREAD.is_alive():
            await asyncio.sleep(0.1)
        # TODO this is hackish. How can we improve?
        discover_package(importlib_metadata.entry_points().__getitem__(name))

    asyncio.create_task(bg_install_and_reload())
    return redirect(
        url_for(
            "plugin",
            name=name,
        )
    )


@app.post("/plugin/<name>/upgrade")
async def plugin_upgrade(name: str) -> BaseResponse:
    tutorclient.CliPool.run_parallel(app, ["plugins", "upgrade", name])
    return redirect(
        url_for(
            "plugin",
            name=name,
        )
    )


@app.post("/plugins/update")
async def plugins_update() -> BaseResponse:
    tutorclient.CliPool.run_sequential(["plugins", "update"])
    return redirect(url_for("plugin_store"))


@app.post("/plugin/<name>/config/update")
async def plugin_config_update(name: str) -> Response:
    await process_config_update_request()
    response = t.cast(
        Response,
        await make_response(redirect(url_for("plugin", name=name))),
    )
    update_plugins_requiring_launch(response, add=name)
    notify_run_sequential(response)
    return response


async def process_config_update_request() -> None:
    """
    Set/Unset config key/values based on request form.
    """

    # Run save command
    # TODO error management
    form = await request.form
    if unset := form.get("unset"):
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

    # Make sure that the configuration is reloaded where needed.
    # Note that this is not very robust. For instance, if the server is running multiple
    # workers, the configuration will only be reloaded for one of them.
    HttpAuthCredentials.load_credentials()


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
                event = f"""data: {
                    json.dumps(
                        {
                            "stdout": data,
                            "command": tutorclient.CliPool.current_command(),
                            "thread_alive": tutorclient.CliPool.is_thread_alive(),
                        }
                    )
                }\nevent: logs\n\n"""
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
    )


@app.post("/suggest")
async def suggest() -> Response:
    data = await request.get_json()
    partial_command = data.get("command", "")
    suggestions = tutorclient.Client.autocomplete(partial_command)
    return jsonify(suggestions)


@app.post("/command")
async def command() -> BaseResponse:
    form = await request.form
    command_string = form.get("command", "")
    command_args = command_string.split()
    tutorclient.CliPool.run_parallel(app, command_args)
    return redirect(url_for("advanced"))


def notify_run_sequential(response: BaseResponse) -> None:
    """
    Notify the frontend that a sequential command was run.
    """
    set_cookie(response, constants.COMMAND_EXECUTED_COOKIE_NAME, "1")


def update_plugins_requiring_launch(
    response: Response, add: t.Optional[str] = None, remove: t.Optional[str] = None
) -> None:
    """
    Store the list of plugins for which a recent set of changes require running "local launch".

    This list is stored as a "+"-separated string in a cookie. Note that flask will automatically put the content in quotes.
    """
    # Note that comma, colon and semi-colon are not supported in cookie values
    separator = "+"

    # Get current plugins
    names = set(
        [
            cookie
            for cookie in request.cookies.get(
                constants.PLUGINS_REQUIRE_LAUNCH_COOKIE_NAME, ""
            ).split(separator)
            if cookie
        ]
    )

    # Add new plugins
    if add:
        names.add(add)

    # Remove plugins
    if remove:
        names.discard(remove)

    # Update the response
    set_cookie(
        response,
        constants.PLUGINS_REQUIRE_LAUNCH_COOKIE_NAME,
        separator.join(sorted(names)),
    )


def set_cookie(response: BaseResponse, name: str, value: str) -> None:
    """
    Set a cookie with a consistent expiry time.
    """
    response.set_cookie(name, value, max_age=60 * 60 * 24 * 30)  # 1 month
