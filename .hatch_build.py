# https://hatch.pypa.io/latest/how-to/config/dynamic-metadata/
import os
import subprocess

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

HERE = os.path.dirname(__file__)


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        # This runs before the build starts
        subprocess.check_call(["make", "scss"])
