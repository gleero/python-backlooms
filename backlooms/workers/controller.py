"""
Worker Controller Module

This module defines the `WorkerController` which coordinates starting and
stopping multiple workers using an `AsyncExitStack`.

Key Features:
    - Starts all provided workers by entering their `lifespan` context.
    - Ensures graceful shutdown of all workers in reverse order.
    - Exposes a single async context manager `runner` yielding started workers.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from contextlib import AsyncExitStack, asynccontextmanager

from .base_worker import BaseWorker


class WorkerController:
    """
    Coordinates the lifecycle of multiple workers.
    """

    def __init__(self, workers: list[BaseWorker]):
        """
        Initialize the controller with a list of workers.

        Args:
            workers (list[BaseWorker]): Worker instances to manage.
        """
        self._workers = workers

    @asynccontextmanager
    async def runner(self):
        """
        Async context manager that starts all workers and yields them.

        Yields:
            list[BaseWorker]: The list of started worker instances.

        Description:
            - Uses `AsyncExitStack` to enter each worker's `lifespan` context,
              collecting the started instances. Cleanup is handled automatically
              when the context exits.
        """
        async with AsyncExitStack() as stack:
            started_workers = []
            for worker in self._workers:
                started = await stack.enter_async_context(worker.lifespan())
                started_workers.append(started)

            yield stack
