"""
Server abstraction layer for Backlooms.

This package defines an adapter interface and concrete implementations that
allow the application to start an HTTP (or any other) server alongside
selected background workers. Adapters are responsible for:
- accepting framework context (configuration, DI container, worker registry),
- exposing a uniform `start(workers_to_run)` entrypoint,
- managing the server runtime and coordinating worker lifecycle as needed.

Notes:
- The `Application` wires an adapter (if supplied) and exposes a `start` CLI
  command that delegates to the adapter's `start` method.
- Different server stacks can be implemented by creating custom adapters that
  subclass `ServerAdapter`.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from .adapter import ServerAdapter


__all__ = ["ServerAdapter"]
