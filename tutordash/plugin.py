from __future__ import annotations

import os

import click
import uvicorn

from tutor import hooks
from tutor.commands.context import Context

from .__about__ import __version__

########################################
# CONFIGURATION
########################################

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("DASH_VERSION", __version__),
    ]
)


@click.group()
@click.pass_obj
def dash(obj: Context) -> None:
    # Pass project root to dash. This is the only way we have to pass data to the
    # fastapi app.
    os.environ["DASH_TUTOR_ROOT"] = obj.root


@dash.command(name="run")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("-p", "--port", default=3274, type=int, show_default=True)
@click.option("--reload/--no-reload", help="Enable auto-reload.")
def dash_run(host: str, port: int, reload: bool) -> None:
    """
    Run the dash server.
    """
    uvicorn.run("tutordash.server.app:app", host=host, port=port, reload=reload)


hooks.Filters.CLI_COMMANDS.add_item(dash)
