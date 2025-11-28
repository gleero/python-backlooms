"""
Dependency injection integration for Backlooms.

This module provides a minimal adapter around `dependency-injector` to make
container wiring effortless in Backlooms applications.

Key ideas:
- Applications define their own container by subclassing `DIContainer`.
- There is no need to declare `wiring_config = containers.WiringConfiguration(...)`
  on user containers. The base class sets up wiring automatically.
- The base container exposes a default provider `config` that holds the active
  application configuration instance.
- Decorating functions with `@inject` transparently registers the caller's
  module for wiring so dependencies can be resolved via standard
  `dependency-injector` mechanisms.
- The `use_container` hook returns the globally registered container instance
  for convenience in modules that do not receive it explicitly.

Behavior:
- `DIContainer` behaves like a regular `DeclarativeContainer` and can be used
  in the same way for providers, factories, and resources.
- `inject` returns the same callable you pass in, enabling dependency injection
  in its parameters using `dependency-injector.wiring.inject` under the hood.
  The decorator is idempotent per-module and safe to apply to multiple
  functions within the same module.

Notes:
- Any errors related to missing providers or wiring issues are raised by the
  underlying `dependency-injector` library at call or import time.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from typing import Callable, cast, Any, TypeVar

from dependency_injector.wiring import inject as di_inject
from dependency_injector import containers, providers

from backlooms.config import BaseConfig

wiring = containers.WiringConfiguration(modules=[])

REGISTERED_GLOBAL_CONTAINER: object | None = None


class BaseDIContainerMeta(type(containers.DeclarativeContainer)):
    def __new__(cls, name, bases, namespace, **kwargs):
        mcls = super().__new__(cls, name, bases, namespace, **kwargs)
        setattr(mcls, "wiring_config", wiring)
        return mcls


class DIContainer(
    containers.DeclarativeContainer,
    metaclass=BaseDIContainerMeta,
):
    """
    Application DI base container.

    Purpose:
    - Serve as a drop-in base for user containers built with `dependency-injector`.
    - Automatically attaches a wiring configuration so explicit `wiring_config = ...`
      is not required in user subclasses.

    Behavior:
    - Can be used like a normal `DeclarativeContainer` with providers and resources.
    - Exposes a default provider `config` that returns the active `BaseConfig`
      instance passed by the application. This provider is available in all
      user containers derived from this base.
    - Instances created by the framework are ready for wiring of modules decorated
      with `@inject`.

    Notes:
    - The global container instance created by the framework can be retrieved via
      the `use_container(...)` hook when passing the instance explicitly is not
      convenient.
    """

    def __new__(cls, *args, **kwargs):
        ret = super().__new__(cls, *args, **kwargs)
        setattr(ret, "wiring_config", wiring)
        global REGISTERED_GLOBAL_CONTAINER
        REGISTERED_GLOBAL_CONTAINER = ret
        return ret

    config = providers.Object[BaseConfig](None)


F = TypeVar("F", bound=Callable[..., Any])


def inject(fn: F) -> F:
    """
    Decorator that enables dependency injection with automatic module wiring.

    Parameters:
        fn: The target callable (sync or async) whose parameters may declare
            dependencies supported by `dependency-injector.wiring.inject`.

    Returns:
        The same callable `fn` wrapped to resolve dependencies when invoked.

    Behavior:
        - Registers the function's module for wiring so that providers from the
          active `DIContainer` can be injected without manually declaring
          `wiring_config` on user containers.
        - Safe to apply to multiple functions within the same module; repeated
          registrations are ignored.

    Possible errors:
        - Any injection-time errors (e.g., missing providers, incompatible
          signatures) are raised by `dependency-injector` when the function is
          called.
    """
    module_name = getattr(fn, "__module__")
    modules = list(getattr(wiring, "modules", []) or [])

    if module_name not in modules:
        modules.append(module_name)
        wiring.modules = modules

    return cast(F, di_inject(fn))


DI = TypeVar("DI", bound=DIContainer)


def use_container[DI](_: type[DI]) -> DI:
    """
    Retrieve the globally registered DI container instance.

    Parameters:
        _ (type[DI]): Placeholder used only for typing to indicate the expected
            container subtype. The value is ignored at runtime.

    Returns:
        DI: The active container instance created by the framework.

    Raises:
        RuntimeError: If the container has not been initialized yet. Ensure your
        application constructs the container (typically via `Application`).

    Notes:
        - The returned container exposes a default `config` provider that yields
          the active application configuration instance.
        - This hook is convenient in modules where passing the container
          explicitly is impractical; otherwise prefer explicit dependency
          passing for clarity and testability.
    """
    if REGISTERED_GLOBAL_CONTAINER is None:
        raise RuntimeError("Container is not initialized")
    return cast(DI, REGISTERED_GLOBAL_CONTAINER)


__all__ = ["DIContainer", "inject", "use_container"]
