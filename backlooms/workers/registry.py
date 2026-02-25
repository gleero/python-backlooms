"""
Worker Registry Module

Provides a lightweight registry for background worker classes and a factory
method to instantiate selected workers by name. The registry is used by the
application to expose worker choices in the CLI and to construct worker
instances with the application container and other constructor keyword
arguments.

Notes:
- Names and descriptions are taken from each worker class' public attributes
  `NAME` and `DESCRIPTION`.
- Registration order is preserved when listing workers; use this to control
  how choices appear in help output.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from .base_worker import BaseWorker, WorkerSpec


class WorkerRegistry:
    """
    Registry for worker classes with name-based lookup and instantiation.

    Purpose:
        - Collect worker classes keyed by their declared `NAME`.
        - Provide a simple listing of available workers for help/CLI surfaces.
        - Instantiate specific workers by name, forwarding constructor keyword
          arguments.

    Thread-safety:
        - This class is not thread-safe by itself. If used from multiple
          threads, external synchronization is required.
    """

    _workers: dict[str, WorkerSpec[BaseWorker]]
    _shadow_workers: list[str]

    @property
    def workers(self) -> list[tuple[str, str]]:
        """
        Return registered workers as `(name, description)` pairs.

        Returns:
            list[tuple[str, str]]: A list of `(NAME, DESCRIPTION)` tuples for all
            registered workers. The order reflects registration order.
        """
        ret = []
        for worker_name, worker in self._workers.items():
            if not worker.cls.SHADOW:
                ret.append((worker_name, worker.cls.DESCRIPTION))
        return ret

    def __init__(self):
        """
        Initialize an empty registry instance.
        """
        self._workers = {}
        self._shadow_workers = []

    def add(self, worker: type[BaseWorker] | WorkerSpec[BaseWorker]):
        """
        Register a worker class under its `NAME`.

        Parameters:
            worker (type[BaseWorker] | WorkerSpec[BaseWorker]): The worker class
                to register or spec (cls.with_args(...)). It must define
                a unique `NAME` and a human-readable `DESCRIPTION`.

        Behavior:
            - If a worker with the same name is already registered, it will be
              overwritten by the new class.

        Possible errors:
            - AttributeError: If the provided class does not define `NAME` or
              `DESCRIPTION`.
            - TypeError: If `worker` is not a valid subclass suitable for
              instantiation later on.
        """
        if isinstance(worker, WorkerSpec):
            spec = worker
        else:
            spec = WorkerSpec(cls=worker)

        if spec.cls.NAME in self._workers:
            raise ValueError(f"Worker {spec.cls.NAME} already registered")

        self._workers[spec.cls.NAME] = spec

        if spec.cls.SHADOW:
            self._shadow_workers.append(spec.cls.NAME)

    def build_workers(
        self, to_run: tuple[str, ...] | list[str], with_shadow: bool, **kwargs
    ) -> list[BaseWorker]:
        """
        Construct worker instances by their names.

        Parameters:
            to_run (tuple[str, ...] | list[str]): Ordered collection of worker
                names to instantiate. The resulting list preserves this order.
            with_shadow (bool): If True, include the shadow workers to the list.
            **kwargs: Keyword arguments forwarded to each worker's constructor
                (e.g., `container=...`).

        Returns:
            list[BaseWorker]: Instantiated worker objects corresponding to the
            requested names.

        Possible errors:
            - ValueError: If any requested name is not registered.
            - TypeError: Propagated from worker class constructors when provided
              keyword arguments are incompatible.
        """
        workers = []

        if with_shadow:
            to_run = tuple(to_run) + tuple(self._shadow_workers)

        for worker_name in to_run:
            if worker_name not in self._workers:
                raise ValueError(f"Worker {worker_name} not registered")

            worker = self._workers[worker_name].build(**kwargs)
            workers.append(worker)

        return workers
