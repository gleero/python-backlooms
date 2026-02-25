"""
Application orchestrator and CLI entrypoint for Backlooms.

This module exposes the `Application` class, a small orchestrator that wires
configuration, dependency injection, background workers, an optional server
adapter, and a unified Typer-based CLI. It provides a black-box interface for
running a single worker or launching a server alongside selected workers.

Usage:
    ```python
    app = Application(
        config=Config,              # Instance of a user-defined BaseConfig subclass
        workers=app_workers,        # WorkerRegistry with all workers registered
        actions=[MigrationAction],  # Optional list of CLI action groups (Typer apps)
        container_cls=Container,    # User DI container class (subclass of DIContainer)
        server_adapter=adapter,     # Optional ServerAdapter implementation
    )

    app.run()
    ```

CLI commands provided by this application:
- run <worker>:
  - Runs a single worker until termination.
  - The positional `<worker>` argument is restricted to registered worker names
    and includes contextual help derived from the registry.
- start [--with-<worker>/--without-<worker> ...] [--server-only | -s]:
  - Starts the configured server adapter and, by default, all registered workers.
  - `--without-<worker>` disables selected workers; `--with-<worker>` re-enables.
  - `--server-only` disables all worker components.
  - This command is registered only if a `server_adapter` is supplied; otherwise
    it is not available in the CLI.
- Any additional action groups passed via `actions` are mounted as Typer
  sub-applications with their own commands.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import asyncio
import signal
from functools import partial
from logging.config import dictConfig

import typer

from ._utils.command_builder import build_run_command, build_start_command
from .action import CLIAction
from .config import BaseConfig
from .di import DIContainer
from .server import ServerAdapter
from .workers import WorkerController, WorkerRegistry


class Application:
    """
    Orchestrates configuration, DI container, workers, optional server adapter, and CLI.

    Purpose:
        - Provide a single entrypoint that initializes logging, builds a Typer
          application, exposes worker-related commands, and optionally delegates
          server startup to a supplied `ServerAdapter`.

    Behavior:
        - Always registers a `run` command to execute exactly one registered
          worker until termination.
        - Registers a `start` command only when a `server_adapter` is supplied.
          This command starts the configured server and, unless disabled via
          flags, the selected workers.
        - Additional Typer action groups provided via `actions` are mounted as
          sub-applications.

    Notes:
        - `config` must be an already-instantiated `BaseConfig` subclass. Its
          `LOG_CONFIG` mapping is applied at construction time.
        - `container_cls` must be a subclass of `DIContainer`.
        - Worker choices and help texts are derived from the passed
          `WorkerRegistry`.
    """

    _config: BaseConfig
    _container: DIContainer
    _typer: typer.Typer
    _workers: WorkerRegistry
    _server_adapter: ServerAdapter | None

    @property
    def config(self) -> BaseConfig:
        """
        Return the active configuration instance.

        Returns:
            BaseConfig: The instantiated configuration passed to the application.
        """
        return self._config

    @property
    def container(self) -> DIContainer:
        """
        Return the application dependency injection container instance.

        Returns:
            DIContainer: An instance of the provided `container_cls` ready for
            use in workers and actions.
        """
        return self._container

    @property
    def typer(self) -> typer.Typer:
        """
        Return the application CLI typer instance.

        Returns:
            typer.Typer: An instance of the CLI typer.
        """
        return self._typer

    def __init__(
        self,
        *,
        config: BaseConfig,
        container_cls: type[DIContainer],
        workers: WorkerRegistry | None = None,
        actions: list[CLIAction] | None = None,
        server_adapter: ServerAdapter | None = None,
    ):
        """
        Create an application instance and assemble the CLI.

        Parameters:
            config (BaseConfig): An already-instantiated configuration object.
            workers (WorkerRegistry | None): Registry containing all available
                workers. If omitted, an empty registry is used.
            container_cls (type[DIContainer]): DI container class to instantiate
                for the application.
            actions (list[CLIAction] | None): Optional list of additional Typer
                action groups to mount as subcommands.
            server_adapter (ServerAdapter | None): Optional server adapter that
                the application will use to implement the `start` command.

        Side effects:
            - Applies logging configuration via `logging.config.dictConfig` using
              `config.LOG_CONFIG`.
            - Constructs the Typer application and registers commands.

        Notes:
            - The `start` command is not registered if `server_adapter` is `None`.
            - Worker choices and help are generated from the `workers` registry.
        """
        self._config = config
        self._container = container_cls(config=config)
        self._server_adapter = server_adapter

        if workers is None:
            workers = WorkerRegistry()
        self._workers = workers

        # Apply basic logging configuration
        dictConfig(config.LOG_CONFIG)

        # Setup server adapter
        if server_adapter is not None:
            server_adapter.setup(
                config=config,
                workers=workers,
                container=self._container,
            )

        # Create and register argument parsers
        self._typer = typer.Typer(
            name=config.PROJECT_NAME,
            help=config.PROJECT_DESCRIPTION,
            context_settings={"help_option_names": ["-h", "--help"]},
        )

        # Register all CLI actions
        if actions:
            for action in actions:
                self._typer.add_typer(action)

        # Prepare 'run' command to run specific worker
        run_command = build_run_command(
            self._run_command,
            workers.workers,
            description="Possible workers:",
            help="Worker to run",
        )
        self._typer.command(name="run", short_help="Run specific worker")(run_command)

        # Prepare 'start' command to run server adapter and all workers
        if server_adapter is not None:
            start_command = build_start_command(
                self._start_command,
                workers.workers,
            )
            self._typer.command(name="start", short_help="Start application")(
                start_command
            )

    def _run_command(self, **kwargs):
        """
        Internal entrypoint for the `run` CLI command.

        Parameters:
            **kwargs: Contains a required key `cmd` with the selected worker name.

        Behavior:
            - Validates the presence of `cmd` and then runs the corresponding
              worker until termination.

        Raises:
            SystemError: If `cmd` is missing. This condition should not occur
            during normal CLI usage since Typer enforces the argument.
        """
        if "cmd" not in kwargs:
            raise SystemError("No worker specified")

        asyncio.run(self._run_worker(kwargs["cmd"]))

    def _start_command(self, server_only: bool, **kwargs):
        """
        Internal entrypoint for the `start` CLI command.

        Parameters:
            server_only (bool): When True, starts only the server without
                launching any workers.
            **kwargs: A mapping of worker-name booleans corresponding to
                `--with-<worker>/--without-<worker>` options; True means the
                worker should be run.

        Behavior:
            - Delegates to the configured server adapter to start the server and,
              unless `server_only` is True, the selected workers alongside it.
            - If the application was constructed without a server adapter, this
              command is a no-op and is not exposed in the CLI.
        """
        if self._server_adapter is None:
            return

        workers_to_run = []
        if not server_only:
            for worker_name, need_to_run in kwargs.items():
                if need_to_run:
                    workers_to_run.append(worker_name)

        self._server_adapter.start(workers_to_run)

    async def _run_worker(self, worker_name: str):
        """
        Run a single worker until a termination signal is received.

        Parameters:
            worker_name (str): The name of the worker to run.

        Behavior:
            - Starts the specified worker and blocks until a termination signal
              is received (e.g., SIGINT/SIGTERM) or the worker completes.

        Possible errors:
            - KeyError: If the requested worker name is not registered.
            - RuntimeError or TypeError: Propagated from worker construction or
              runtime if dependencies are misconfigured.
        """
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        partial(loop.add_signal_handler, signal.SIGINT, lambda: stop_event.set())()
        partial(loop.add_signal_handler, signal.SIGTERM, lambda: stop_event.set())()

        try:
            workers = self._workers.build_workers(
                (worker_name,),
                False,
                container=self._container,
            )
        except ValueError as e:
            raise SystemError(f"Worker {worker_name} not registered") from e

        workerctl = WorkerController(workers)

        try:
            async with workerctl.runner():
                await stop_event.wait()

        except asyncio.CancelledError:
            pass

    def run(self):
        """
        Execute the application's CLI.

        Behavior:
            - Invokes the Typer application, exposing built-in commands (`run`,
              optionally `start`) and any additional action groups provided.
            - Standard help flags (`-h/--help`) are available. Command argument
              validation and parsing are handled by Typer/Click.
        """
        self._typer()
