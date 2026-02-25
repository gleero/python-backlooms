"""
Worker Base Class Module

This module defines the `BaseWorker` abstract class that standardizes the
interface and lifecycle for long-lived background workers. Workers implement
the async context manager `lifespan` to start and gracefully stop resources.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from abc import ABCMeta, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Generic, Self, TypeVar

from backlooms.di import DIContainer


T_co = TypeVar("T_co", bound="BaseWorker", covariant=True)
W = TypeVar("W", bound="BaseWorker")


@dataclass(frozen=True)
class WorkerSpec(Generic[T_co]):
    cls: type[T_co]
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)

    def build(self, **kwargs) -> T_co:
        return self.cls(*self.args, **self.kwargs, **kwargs)


class BaseWorker(metaclass=ABCMeta):
    """
    Abstract base class for all background workers.

    Attributes:
        NAME (str): A short unique worker identifier, used in CLI flags and registry.
        DESCRIPTION (str): A human-readable description used in help messages.
    """

    _container: DIContainer

    NAME: str
    DESCRIPTION: str
    SHADOW: bool = False

    def __init__(self, *, container: DIContainer):
        """
        Initialize the worker with the application container.

        Args:
            container (Container): The application's dependency injection container
                used to resolve services required by the worker.
        """
        self._container = container

    @abstractmethod
    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[Self]:
        """
        Async context manager that manages the worker's lifecycle.

        Yields:
            Self: The started worker instance that can be used within the context.

        Description:
            - Implementations should start required resources before yielding
              and ensure proper cleanup in the `finally` block.
        """
        try:  # pragma: nocover
            yield self  # pragma: nocover
        finally:  # pragma: nocover
            pass  # pragma: nocover

    @classmethod
    def with_args(cls: type[W], *args: Any, **kwargs: Any) -> WorkerSpec[W]:
        return WorkerSpec(cls=cls, args=args, kwargs=kwargs)
