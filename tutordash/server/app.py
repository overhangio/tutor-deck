import os
import typing as t

from fastapi import FastAPI, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import importlib_resources

from tutor import hooks
from tutor.types import Config


class TutorProject:
    """
    This big god class is not very elegant.
    """

    CONFIG: dict[str, t.Any] = {}

    @classmethod
    def bootstrap(cls):
        # This is how we guarantee that all necessary modules are loaded
        # pylint: disable=import-outside-toplevel,unused-import
        import tutor.commands.cli

        hooks.Actions.CORE_READY.do()  # discover plugins
        # Don't you dare write os.environ.get() here: we want to crash if the
        # environment variable is missing.
        tutor_root = os.environ["DASH_TUTOR_ROOT"]
        hooks.Actions.PROJECT_ROOT_READY.do(tutor_root)

    @staticmethod
    def installed_plugins() -> list[str]:
        return sorted(set(hooks.Filters.PLUGINS_INSTALLED.iterate()))

    @staticmethod
    def enabled_plugins() -> list[str]:
        return sorted(set(hooks.Filters.PLUGINS_LOADED.iterate()))


@hooks.Actions.CONFIG_LOADED.add()
def _dash_update_tutor_config(config: Config):
    TutorProject.CONFIG = config


TutorProject.bootstrap()


app = FastAPI()
app.mount(
    "/static",
    StaticFiles(
        directory=importlib_resources.files("tutordash")
        .joinpath("server")
        .joinpath("static")
    ),
    name="static",
)
templates = Jinja2Templates(
    directory=importlib_resources.files("tutordash")
    .joinpath("server")
    .joinpath("templates")
)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/sidebar/plugins")
def sidebar_plugins(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="sidebar/_plugins.html",
        context={
            "installed_plugins": sorted(set(hooks.Filters.PLUGINS_INSTALLED.iterate())),
        },
    )


@app.get("/plugin/{name}")
def plugin(request: Request, name: str):
    # TODO check that plugin exists
    is_enabled = name in TutorProject.enabled_plugins()
    return templates.TemplateResponse(
        request=request,
        name="plugin.html",
        context={
            "plugin_name": name,
            "is_enabled": is_enabled,
        },
    )


@app.post("/plugin/{name}/toggle")
def toggle_plugin(request: Request, name: str, enabled: t.Annotated[bool, Form]):
    # TODO I am unable to parse the "enabled" form parameter.
    pass
