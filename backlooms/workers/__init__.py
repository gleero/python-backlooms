"""
Worker Control Package

This package provides a small framework for registering, building, and running
long-lived background workers inside the application. It exposes three
core components:

- `BaseWorker`: An abstract base class defining the worker interface and
  lifecycle management via an async context manager.
- `WorkerRegistry`: A registry used to collect available worker classes,
  integrate their CLI options, and instantiate selected workers.
- `WorkerController`: A controller that starts and manages the lifespan of the
  instantiated workers using an `AsyncExitStack`.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from .base_worker import BaseWorker
from .controller import WorkerController
from .registry import WorkerRegistry


__all__ = ["BaseWorker", "WorkerController", "WorkerRegistry"]
