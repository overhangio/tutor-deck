import asyncio
import contextlib
import logging
import os
import shlex
import subprocess
import tempfile
import threading
import typing as t

import aiofiles
import click
import click_repl
import tutor.commands.cli
import tutor.config
import tutor.env
import tutor.plugins.indexes
import tutor.utils
from prompt_toolkit.document import Document
from quart import Quart
from tutor import fmt, hooks
from tutor.exceptions import TutorError
from tutor.types import Config

from . import constants

logger = logging.getLogger(__name__)


class Project:
    """
    Provide access to the current Tutor project root and configuration.
    """

    # Project root
    ROOT: str = ""

    @classmethod
    def connect(cls, root: str) -> None:
        """
        Call whenever we are ready to connect to the Tutor hooks API.
        """
        cls.ROOT = root

    @classmethod
    def get_config(cls) -> Config:
        # TODO cache?
        return tutor.config.load_full(cls.ROOT)

    @classmethod
    def get_user_config(cls) -> Config:
        """
        TODO load config dynamically from root anytime it is changed on disk? Maybe take the chance to clear sys.modules cache on reload?
        """
        return tutor.config.get_user(cls.ROOT)


class Cli:
    """
    Run Tutor commands and capture the output in a file.

    Output must be a file because subprocess.Popen requires stdout.fileno() to be
    available. We store logs in temporary files.

    Tutor commands are not meant to be run in parallel. Thus, there must be only one
    instance running at any time: calling functions are responsible for calling
    CliPool instead of this class.
    """

    def __init__(self, args: list[str]) -> None:
        """
        Each instance can be interrupted from other threads via the stop flag.
        """
        self.args = args
        self.log_file = tempfile.NamedTemporaryFile(
            "ab", prefix="tutor-deck-", suffix=".log"
        )
        self._stop_flag = threading.Event()

    def log_to_file(self, content: str) -> None:
        with open(self.log_path, mode="ab") as f:
            f.write(content.encode())

    @property
    def log_path(self) -> str:
        """
        Path to the log file
        """
        return self.log_file.name

    @property
    def command(self) -> str:
        """
        Tutor command executed by this runner.
        """
        return shlex.join(["tutor"] + self.args)

    def run(self) -> None:
        """
        Execute some arbitrary tutor command.

        Output will be captured in the log file.
        """
        logger.info("Running command: tutor %s (logs: %s)", self.command, self.log_path)

        # Override execute function
        with self.patch_objects():
            try:
                # Call tutor command
                # pylint: disable=no-value-for-parameter
                tutor.commands.cli.cli(self.args)
            except TutorError as e:
                # This happens for incorrect commands and cancellation
                self.log_to_file(e.args[0])
                self.log_to_file("\nCancelled!\n")
            except SystemExit:
                # TODO Is there a better way to notify command completion???
                self.log_to_file("\nSuccess!")

    def stop(self) -> None:
        """
        Sets the stop flag, which is monitored by all subprocess.Popen commands.
        """
        logger.info("Stopping Tutor command: %s...", self.command)
        self._stop_flag.set()

    async def iter_logs(self) -> t.AsyncGenerator[str, None]:
        """
        Async stream content from file.
        The first item is the log file path. Second item is the running command.

        This will handle gracefully file deletion. Note however that if the file is
        truncated, all contents added to the beginning until the current position will be
        missed.
        """
        yield f"{self.log_path}\n"
        yield f"$ {self.command}\n"
        async with aiofiles.open(self.log_path, "rb") as f:
            # Note that file reading needs to happen from the file path, because it maye
            # be done from a separate thread, where the file object is not available.
            while True:
                content = await f.read()
                if content:
                    yield content.decode()
                else:
                    await asyncio.sleep(constants.SHORT_SLEEP_SECONDS)

    # Mocking functions to override tutor functions that write to stdout
    @contextlib.contextmanager
    def patch_objects(self) -> t.Iterator[None]:
        refs = [
            (tutor.utils, "execute", self._mock_execute),
            (fmt.click, "echo", self._mock_click_echo),
            (fmt.click, "style", self._mock_click_style),
        ]
        old_objects = []
        for module, object_name, new_object in refs:
            # backup old object
            old_objects.append((module, object_name, getattr(module, object_name)))
            # override object
            setattr(module, object_name, new_object)
        try:
            yield None
        finally:
            # restore old objects
            for module, object_name, old_object in old_objects:
                setattr(module, object_name, old_object)

    def _mock_click_echo(self, text: str, **_kwargs: t.Any) -> None:
        """
        Mock click.echo to write to log file
        """
        self.log_to_file(f"{text}\n")

    def _mock_click_style(self, text: str, **_kwargs: t.Any) -> str:
        """
        Mock click.style to strip ANSI colors

        TODO convert to HTML color codes?
        """
        return text

    def _mock_execute(self, *command: str) -> int:
        """
        Mock tutor.utils.execute.
        """
        command_string = shlex.join(command)
        with subprocess.Popen(
            command, stdout=self.log_file, stderr=self.log_file
        ) as popen:
            while popen.returncode is None:
                try:
                    popen.wait(timeout=0.5)
                except subprocess.TimeoutExpired as e:
                    # Check every now and then whether we should stop
                    if self._stop_flag.is_set():
                        popen.kill()
                        popen.wait()
                        raise TutorError(
                            f"Stopping child command: {command_string}"
                        ) from e
                except Exception as e:
                    popen.kill()
                    popen.wait()
                    raise TutorError(f"Command failed: {command_string}") from e

            if popen.returncode > 0:
                raise TutorError(
                    f"Command failed with status {popen.returncode}: {command_string}"
                )
            return popen.returncode


class CliPool:
    CLI_INSTANCE: t.Optional[Cli] = None
    THREAD: t.Optional[threading.Thread] = None

    @classmethod
    def run_sequential(cls, args: list[str]) -> None:
        cls.stop()
        cls.CLI_INSTANCE = Cli(args)
        cls.CLI_INSTANCE.run()

    @classmethod
    def run_parallel(cls, app: Quart, args: list[str]) -> None:
        """
        Run a command in a separate thread. This command automatically stops any running
        command.
        """
        # Stop any running command
        cls.stop()

        # Start thread
        cls.CLI_INSTANCE = Cli(args)
        cls.THREAD = threading.Thread(target=cls.CLI_INSTANCE.run)
        cls.THREAD.start()

        # Watch for exit
        app.add_background_task(cls.stop_on_exit, cls.CLI_INSTANCE, cls.THREAD)

    @classmethod
    def stop(cls) -> None:
        """
        Stop running instance.

        This is a no-op when there is no running thread, so it's safe to call any time.
        """
        if cls.CLI_INSTANCE and cls.THREAD:
            cls.stop_runner_thread(cls.CLI_INSTANCE, cls.THREAD)

    @classmethod
    def is_thread_alive(cls) -> bool:
        """
        Check if the thread is running.

        """
        if cls.CLI_INSTANCE and cls.THREAD:
            return cls.THREAD.is_alive()
        return False

    @staticmethod
    def stop_runner_thread(tutor_cli_runner: Cli, thread: threading.Thread) -> None:
        """
        Set runner stop flag and wait for thread to complete.
        """
        if thread.is_alive():
            tutor_cli_runner.stop()
            thread.join()

    @classmethod
    async def stop_on_exit(
        cls, tutor_cli_runner: Cli, thread: threading.Thread
    ) -> None:
        """
        This background task will stop the runner whenever the Quart app is
        requested to stop/exit/shutdown. This happens for instance on dev reload.
        """
        try:
            while thread.is_alive():
                await asyncio.sleep(constants.SHORT_SLEEP_SECONDS)
        finally:
            cls.stop_runner_thread(tutor_cli_runner, thread)

    @classmethod
    async def iter_logs(cls) -> t.AsyncGenerator[str, None]:
        """
        Iterate indefinitely from any running instance. When an existing instance is
        replaced by another one, previous logs are not deleted. New ones are simply
        appended.
        """
        while cls.CLI_INSTANCE:
            async for log in cls.CLI_INSTANCE.iter_logs():
                yield log


class Client:

    @classmethod
    def plugins_in_store(cls) -> list[tutor.plugins.indexes.IndexEntry]:
        if not os.path.exists(tutor.plugins.indexes.Indexes.CACHE_PATH):
            CliPool.run_sequential(["plugins", "update"])
        return list(tutor.plugins.indexes.iter_cache_entries())

    @classmethod
    def installed_plugins(cls) -> list[str]:
        return sorted(set(hooks.Filters.PLUGINS_INSTALLED.iterate()))

    @classmethod
    def enabled_plugins(cls) -> list[str]:
        return list(hooks.Filters.PLUGINS_LOADED.iterate())

    @classmethod
    def plugins_matching_pattern(cls, pattern: str) -> list[str]:
        return [
            plugin._data["name"]
            for plugin in cls.plugins_in_store()
            if plugin.match(pattern)
        ]

    @classmethod
    def plugin_config_unique(cls, name: str) -> Config:
        plugin_config = hooks.Filters.CONFIG_UNIQUE.iterate_from_context(
            hooks.Contexts.app(name).name
        )
        config = Project.get_config()
        return {key: config.get(key, value) for key, value in plugin_config}

    @classmethod
    def plugin_config_defaults(cls, name: str) -> Config:
        """
        Return the plugin default settings, with values potentially overridden in the
        user configuration.
        """
        config_defaults = dict(
            hooks.Filters.CONFIG_DEFAULTS.iterate_from_context(
                hooks.Contexts.app(name).name
            )
        )
        user_config = Project.get_user_config()
        # TODO render default config values
        return {
            key: user_config.get(key, value) for key, value in config_defaults.items()
        }

    @classmethod
    def autocomplete(cls, partial_command: str) -> list[dict[str, str]]:
        cli = tutor.commands.cli.cli
        ctx = click.Context(cli, info_name=cli.name, parent=None)
        completer = click_repl.ClickCompleter(cli, ctx)
        document = Document(partial_command, len(partial_command))
        completions = list(completer.get_completions(document, None))
        suggestions = []
        for completion in completions:
            suggestions.append(
                {
                    "text": completion.text,
                    "display": completion.display,
                }
            )
        return suggestions
