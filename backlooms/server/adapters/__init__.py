"""
Built-in server adapter implementations.

This subpackage contains ready-to-use `ServerAdapter` implementations. It is
safe to depend on these from applications; each adapter encapsulates a
specific server stack without leaking implementation details to the rest of the
framework.

Currently available:
- `FastAPIServerAdapter` — runs a FastAPI application with optional CORS and
  coordinates Backlooms workers during the server lifespan.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from typing import TYPE_CHECKING


__all__ = [
    "FastAPIServerAdapter",
]


if TYPE_CHECKING:
    from .fastapi import FastAPIServerAdapter


def __getattr__(name: str):
    from importlib import import_module

    if name == "FastAPIServerAdapter":
        try:
            module = import_module(".fastapi", __name__)
        except ImportError as e:
            raise ImportError(
                "fastapi is not installed, run `pip install 'backlooms[fastapi]'`"
            ) from e

        obj = getattr(module, name)

        # Cache the adapter object for future imports
        globals()[name] = obj

        return obj

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
