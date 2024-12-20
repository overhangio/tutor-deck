from __future__ import annotations

import click

from tutor import hooks
from tutor.commands.context import Context

from .__about__ import __version__
from .server import app

########################################
# CONFIGURATION
########################################

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("DASH_VERSION", __version__),
    ]
)


@click.group()
def dash() -> None:
    pass


@dash.command(name="run")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("-p", "--port", default=3274, type=int, show_default=True)
@click.option(
    "--dev/--no-dev",
    help="Enable development mode, with auto-reload and debug templates.",
)
@click.pass_obj
def dash_run(obj: Context, host: str, port: int, dev: bool) -> None:
    """
    Run the dash server.
    """
    app.run(obj.root, host=host, port=port, debug=dev, use_reloader=dev)


hooks.Filters.CLI_COMMANDS.add_item(dash)
