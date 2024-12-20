import asyncio
import json
import typing as t


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


def run(root: str, **app_kwargs: t.Any) -> None:
    """
    Bootstrap the Quart app and run it.
    """
    tutorclient.Project.connect(root)

    # TODO app.run() should be called only in development
    app.run(**app_kwargs)


@app.get("/")
async def home() -> str:
    return await render_template("index.html", **shared_template_context())


@app.get("/plugin/<name>")
async def plugin(name: str) -> str:
    # TODO check that plugin exists
    is_enabled = name in tutorclient.Client.enabled_plugins()
    return await render_template(
        "plugin.html",
        plugin_name=name,
        is_enabled=is_enabled,
        plugin_config_unique=tutorclient.Client.plugin_config_unique(name),
        plugin_config_defaults=tutorclient.Client.plugin_config_defaults(name),
        user_config=tutorclient.Project.get_user_config(),
        **shared_template_context(),
    )


@app.post("/plugin/<name>/toggle")
async def toggle_plugin(name: str) -> WerkzeugResponse:
    # TODO check plugin exists
    form = await request.form
    enable_plugin = form.get("enabled") == "on"
    command = ["plugins", "enable" if enable_plugin else "disable", name]
    tutorclient.CliPool.run_sequential(command)
    # TODO error management
    return redirect(url_for("plugin", name=name))


@app.post("/config/<name>/set")
async def config_set(name: str) -> WerkzeugResponse:
    form = await request.form
    value = form.get("value", "")
    tutorclient.CliPool.run_sequential(["config", "save", "--set", f"{name}={value}"])
    # TODO error management
    return redirect(request.args.get("next", "/"))


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


@app.get("/cli/logs")
async def cli_logs() -> str:
    return await render_template("cli_logs.html", **shared_template_context())


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
