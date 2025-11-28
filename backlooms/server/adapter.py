"""
Server adapter base interface.

This module defines `ServerAdapter`, an abstract adapter that encapsulates
how a concrete server (e.g., FastAPI/Uvicorn or another HTTP/WS stack) is
started and how it cooperates with Backlooms workers.

Expected usage:
- The `Application` creates an adapter instance (supplied by the user), calls
  `setup(...)` to inject the framework context, and invokes `start(...)` when
  the `start` CLI command is executed.

Notes:
- Adapterss should not perform heavy work on import or during construction;
  all runtime initialization should happen inside `start(...)`.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from abc import ABCMeta, abstractmethod

from backlooms.config import BaseConfig
from backlooms.di import DIContainer
from backlooms.workers import WorkerRegistry


class ServerAdapter(metaclass=ABCMeta):
    """
    Abstract server adapter for Backlooms.

    Purpose:
    - Provide a uniform contract to start a server alongside selected workers.

    Behavior:
    - Receives the configuration, worker registry, and DI container via
      `setup(...)` prior to being started.
    - Exposes a single `start(workers_to_run)` entrypoint that implementations
      use to spawn the server and coordinate worker lifecycle as needed.

    Notes:
    - Implementations must be reusable and free of side effects before `setup`.
    """

    _config: BaseConfig | None
    _workers: WorkerRegistry | None
    _container: DIContainer | None

    def __init__(self, *args, **kwargs):
        """
        Initialize the adapter instance.

        Notes:
        - No framework context is available at this point. The instance becomes
          ready only after `setup(...)` is called by the `Application`.
        """
        self._config = None
        self._workers = None
        self._container = None

    def setup(
        self,
        *,
        config: BaseConfig,
        workers: WorkerRegistry,
        container: DIContainer,
    ):
        """
        Inject framework context required by the adapter.

        Parameters:
        - config (BaseConfig): Active application configuration instance.
        - workers (WorkerRegistry): Registry with all available worker classes.
        - container (DIContainer): Instantiated DI container for constructing
          workers and resolving dependencies.

        Behavior:
        - Stores the provided objects for use during `start(...)`.
        """
        self._config = config
        self._workers = workers
        self._container = container

    @abstractmethod
    def start(self, workers_to_run: list[str]):
        """
        Start the server runtime and optionally selected workers.

        Parameters:
        - workers_to_run (list[str]): Names of workers to run alongside the
          server, in desired startup order. May be empty to run server only if
          supported by the implementation.

        Behavior:
        - Implementations should block until server shutdown, ensuring workers
          are started and stopped gracefully as part of the server lifecycle.

        Possible errors:
        - RuntimeError: Implementations may raise if `setup(...)` was not
          called prior to `start(...)`.
        - Other exceptions specific to the underlying server stack may be
          propagated to the caller.
        """
        ...
