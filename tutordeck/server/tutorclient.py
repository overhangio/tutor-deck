import asyncio
import contextlib
import datetime
import json
import logging
import os
import shlex
import subprocess
import tempfile
import threading
import traceback
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
        TODO
        Load config dynamically from root anytime it is changed on disk?
        Maybe take the chance to clear sys.modules cache on reload?
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
        # None while the command is running, then "success", "failure" or "cancelled".
        self.result: t.Optional[str] = None

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
        logger.info("Running command: %s (logs: %s)", self.command, self.log_path)

        # Override execute function
        with self.patch_objects():
            try:
                # Call tutor command
                # pylint: disable=no-value-for-parameter
                tutor.commands.cli.cli(self.args)
            except TutorError as e:
                if e.args:
                    self.log_to_file(f"{e.args[0]}\n")
                if self._stop_flag.is_set():
                    # The error was caused by the user cancelling the command
                    self.result = "cancelled"
                    self.log_to_file("\nCancelled!\n")
                else:
                    self.result = "failure"
                    self.log_to_file("\nFailure!\n")
            except SystemExit as e:
                # Click always exits with SystemExit, including on usage errors: the
                # exit code tells failure and success apart. The result is also exposed
                # in the log stream (see app.py), on which the frontend relies to detect
                # command completion.
                code = e.code if isinstance(e.code, int) else 0 if e.code is None else 1
                if code == 0:
                    self.result = "success"
                    self.log_to_file("\nSuccess!")
                else:
                    self.result = "failure"
                    self.log_to_file("\nFailure!\n")
            except Exception:  # pylint: disable=broad-exception-caught
                # Without this, exceptions raised from the worker thread would
                # disappear into the void, and the frontend would report success.
                self.result = "failure"
                self.log_to_file(traceback.format_exc())
                self.log_to_file("\nFailure!\n")
            else:
                self.result = "success"
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
        truncated, all contents added to the beginning until the current position
        will be missed.
        """
        yield f"$ {self.command}\n"
        final_chunk_sent = False
        async with aiofiles.open(self.log_path, "rb") as f:
            # Note that file reading needs to happen from the file path, because it maye
            # be done from a separate thread, where the file object is not available.
            while True:
                content = await f.read()
                if content:
                    yield content.decode()
                elif self.result is not None and not final_chunk_sent:
                    # The command completed and all its output was read: emit one final
                    # (empty) chunk, such that subscribers are notified of the final
                    # command state even when they already read the last output chunk
                    # while the command was still running.
                    final_chunk_sent = True
                    yield ""
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
    def current_command(cls) -> str:
        """
        Return the current or last command that was executed.
        """
        if cls.CLI_INSTANCE is None:
            raise RuntimeError("CLI_INSTANCE is not initialized.")
        return cls.CLI_INSTANCE.command

    @classmethod
    def current_result(cls) -> t.Optional[str]:
        """
        Result of the current or last command: None while it is running, then
        "success", "failure" or "cancelled".
        """
        if cls.CLI_INSTANCE is None:
            return None
        return cls.CLI_INSTANCE.result

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
    def plugin_in_store(cls, name: str) -> t.Optional[tutor.plugins.indexes.IndexEntry]:
        for plugin in cls.plugins_in_store():
            if plugin.name == name:
                return plugin
        return None

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
    def services_status(cls) -> list[dict[str, str]]:
        """
        Status of the platform containers, as reported by docker compose.

        Containers are queried by compose project name, so this works whatever
        directory the platform was launched from. Raises TutorError when docker
        cannot be reached.
        """
        project_name = str(
            Project.get_config().get("LOCAL_PROJECT_NAME", "tutor_local")
        )
        try:
            process = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-p",
                    project_name,
                    "ps",
                    "-a",
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
        except FileNotFoundError as e:
            raise TutorError("The docker binary was not found") from e
        except subprocess.TimeoutExpired as e:
            raise TutorError("Timeout while querying docker") from e
        except subprocess.CalledProcessError as e:
            raise TutorError(f"Failed to query docker: {e.stderr.strip()}") from e

        containers: list[dict[str, t.Any]] = []
        for line in process.stdout.splitlines():
            if not line.strip():
                continue
            # docker compose >= 2.21 prints one JSON object per line, while older
            # versions print a single JSON array.
            parsed = json.loads(line)
            containers.extend(parsed if isinstance(parsed, list) else [parsed])

        # Restart policies tell one-shot jobs from stopped services, restart
        # counts reveal crash loops, and health logs explain failing checks.
        details = inspect_containers(
            [container["Name"] for container in containers if container.get("Name")]
        )

        services = []
        for container in containers:
            name = container.get("Name", "")
            container_details = details.get(name, ContainerDetails())
            level = service_level(
                container.get("State", ""),
                container.get("Health", ""),
                container.get("ExitCode"),
                restart_policy=container_details.restart_policy,
                restart_count=container_details.restart_count,
                recently_started=container_details.recently_started,
                error=container_details.error,
            )
            services.append(
                {
                    "service": container.get("Service", ""),
                    "name": name,
                    "state": container.get("State", ""),
                    "status": container.get("Status", ""),
                    "health": container.get("Health", ""),
                    "ports": container.get("Ports", ""),
                    "level": level,
                    # Failed checks are expected while a container is starting
                    "health_output": (
                        container_details.health_output if level == "unhealthy" else ""
                    ),
                    "error": container_details.error,
                }
            )
        return sorted(services, key=lambda service: service["service"])

    @classmethod
    def running_services(cls) -> list[str]:
        """
        Names of the services that currently have a platform container, running or
        not. Empty when docker cannot be reached: callers are expected to fall back
        to a static list.
        """
        try:
            return [
                service["service"]
                for service in cls.services_status()
                if service["service"]
            ]
        except TutorError:
            return []

    @classmethod
    def plugins_matching_pattern(cls, pattern: str) -> list[str]:
        return [
            plugin.name for plugin in cls.plugins_in_store() if plugin.match(pattern)
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
    def get_plugin_author(cls, index_entry: tutor.plugins.indexes.IndexEntry) -> str:
        return index_entry.author.split("<")[0].strip()

    @classmethod
    def autocomplete(cls, partial_command: str) -> list[dict[str, str]]:
        """
        Handle CLI command completion via click_repl.ClickCompleter
        https://github.com/click-contrib/click-repl/blob/master/click_repl/_completer.py
        """
        cli = tutor.commands.cli.cli
        ctx = click.Context(cli, info_name=cli.name, parent=None)
        completer = click_repl.ClickCompleter(cli, ctx)
        document = Document(partial_command, len(partial_command))
        completions = list(completer.get_completions(document, None))
        return [
            {
                "text": completion.text,
                "display": completion.display_text,
            }
            for completion in completions
        ]


# Restart policies of long-running services: Docker restarts these containers
# whatever their exit code, unless they were stopped on purpose.
LONG_RUNNING_RESTART_POLICIES = ("always", "unless-stopped")

# Automatic restarts that happened less than this number of seconds ago are
# reported to users.
RECENT_RESTART_SECONDS = 60

# A container that was automatically restarted at least this number of times,
# and recently, is considered to be crash-looping.
CRASH_LOOP_RESTART_COUNT = 3


def service_level(
    state: str,
    health: str,
    exit_code: t.Union[int, str, None] = None,
    restart_policy: t.Optional[str] = None,
    restart_count: int = 0,
    recently_started: bool = False,
    error: str = "",
) -> str:
    """
    Summarize the state of a platform container in a single word:

    - "ok": running, and healthy if it defines a health check.
    - "starting": running, but its health check has not passed yet.
    - "unhealthy": running, but its health check is failing.
    - "restarted": automatically restarted in the last minute, for instance
      because it crashed while its dependencies were starting.
    - "restarting": crash-looping, i.e. automatically restarted repeatedly.
    - "paused": paused by the user.
    - "stopped": a long-running service that was stopped, e.g. by `tutor local
      stop`, whatever its exit code, or that was created but never started.
    - "done": a one-shot container, such as the one that sets volume
      permissions, that exited successfully, as expected.
    - "down": a container that could not start, a one-shot container that
      failed, or a dead container.

    The restart policy is None when it is unknown, for instance because docker
    could not be inspected. Exited containers are then reported as stopped: we
    cannot tell whether they failed, or whether they were expected to exit.
    """
    if error and state in ("created", "exited", "dead"):
        # Docker failed to start the container, e.g. because a port is in use
        return "down"
    if state == "restarting":
        return "restarting"
    if state == "running" and recently_started and restart_count > 0:
        if restart_count >= CRASH_LOOP_RESTART_COUNT:
            return "restarting"
        return "restarted"
    if state == "running":
        if health == "starting":
            return "starting"
        if health == "unhealthy":
            return "unhealthy"
        return "ok"
    if state == "paused":
        return "paused"
    if state == "created":
        return "stopped"
    if state == "exited":
        if restart_policy is None or restart_policy in LONG_RUNNING_RESTART_POLICIES:
            return "stopped"
        if not isinstance(exit_code, (int, str)):
            return "down"
        try:
            return "done" if int(exit_code) == 0 else "down"
        except ValueError:
            return "down"
    return "down"


class ContainerDetails(t.NamedTuple):
    """
    Container attributes that are not part of the docker compose ps output.
    """

    restart_policy: t.Optional[str] = None
    health_output: str = ""
    restart_count: int = 0
    recently_started: bool = False
    error: str = ""


# Maximum length of the outputs that are displayed to users
HEALTH_OUTPUT_MAX_LENGTH = 300


def inspect_containers(container_names: list[str]) -> dict[str, ContainerDetails]:
    """
    Fetch the details of multiple containers with a single docker call.
    Containers that cannot be inspected are silently skipped: this information
    is only a hint.
    """
    if not container_names:
        return {}
    try:
        process = subprocess.run(
            [
                "docker",
                "inspect",
                "--type",
                "container",
                "--format",
                "{{ json .Name }}\t{{ json .HostConfig.RestartPolicy.Name }}"
                "\t{{ json .RestartCount }}\t{{ json .State.StartedAt }}"
                "\t{{ json .State.Error }}\t{{ json .State.Health }}",
                *container_names,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            # Exits with 1 when any container is missing, but still prints the
            # others: for instance, when one was removed in the meantime.
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}

    now = datetime.datetime.now(datetime.timezone.utc)
    details = {}
    for line in process.stdout.splitlines():
        try:
            name, restart_policy, restart_count, started_at, error, health = (
                json.loads(field) for field in line.split("\t")
            )
            # Docker prints timestamps with nanoseconds, which Python < 3.11
            # cannot parse: seconds are precise enough.
            started = datetime.datetime.strptime(
                str(started_at)[:19], "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=datetime.timezone.utc)
            health_log = (health or {}).get("Log") or []
            output = (
                str(health_log[-1].get("Output") or "").strip() if health_log else ""
            )
            details[str(name).lstrip("/")] = ContainerDetails(
                restart_policy=str(restart_policy or ""),
                health_output=truncate(output),
                restart_count=int(restart_count or 0),
                recently_started=(
                    (now - started).total_seconds() < RECENT_RESTART_SECONDS
                ),
                error=truncate(str(error or "").strip()),
            )
        except (ValueError, TypeError, AttributeError):
            continue
    return details


def truncate(text: str) -> str:
    if len(text) > HEALTH_OUTPUT_MAX_LENGTH:
        return text[:HEALTH_OUTPUT_MAX_LENGTH] + "…"
    return text
