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

from .base_worker import BaseWorker


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

    _workers: dict[str, type[BaseWorker]] = {}

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
            ret.append((worker_name, worker.DESCRIPTION))
        return ret

    def __init__(self):
        """
        Initialize an empty registry instance.
        """
        self._workers = {}

    def add(self, worker: type[BaseWorker]):
        """
        Register a worker class under its `NAME`.

        Parameters:
            worker (type[BaseWorker]): The worker class to register. It must
                define a unique `NAME` and a human-readable `DESCRIPTION`.

        Behavior:
            - If a worker with the same name is already registered, it will be
              overwritten by the new class.

        Possible errors:
            - AttributeError: If the provided class does not define `NAME` or
              `DESCRIPTION`.
            - TypeError: If `worker` is not a valid subclass suitable for
              instantiation later on.
        """
        if worker.NAME in self._workers:
            raise ValueError(f"Worker {worker.NAME} already registered")

        self._workers[worker.NAME] = worker

    def get_workers(
        self, to_run: tuple[str, ...] | list[str], **kwargs
    ) -> list[BaseWorker]:
        """
        Construct worker instances by their names.

        Parameters:
            to_run (tuple[str, ...] | list[str]): Ordered collection of worker
                names to instantiate. The resulting list preserves this order.
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
        for worker_name in to_run:
            if worker_name not in self._workers:
                raise ValueError(f"Worker {worker_name} not registered")

            worker = self._workers[worker_name](**kwargs)
            workers.append(worker)

        return workers
