"""
FastAPI-powered server adapter for Backlooms.

This module implements `FastAPIServerAdapter`, a concrete `ServerAdapter`
that launches a FastAPI application with optional CORS middleware and
coordinates Backlooms workers during the server lifespan.

Behavior overview:
- Builds a `FastAPI` app using project metadata from the active config.
- Wires the provided `APIRouter` into the app and optionally enables CORS.
- Runs the app via `uvicorn.run(...)` and blocks until shutdown.
- Starts selected workers during the FastAPI lifespan and stops them on exit.

Notes:
- Adapter must be `setup(...)` by the `Application` before `start(...)` is
  called; otherwise a runtime error is raised.
- Extra keyword arguments for `FastAPI(...)` can be supplied via the
  `fastapi_extra_args` parameter of the constructor.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from contextlib import asynccontextmanager
from functools import partial
from typing import Any

import uvicorn
from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from backlooms.server.adapter import ServerAdapter
from backlooms.workers import WorkerController


class FastAPIServerAdapter(ServerAdapter):
    """
    Server adapter that runs a FastAPI application via Uvicorn.

    Purpose:
    - Provide a ready-to-use HTTP server integration based on FastAPI while
      remaining compatible with Backlooms' worker lifecycle management.

    Notes:
    - Instances are inert until `setup(...)` is called by the `Application`.
    - CORS configuration is opt-in; when provided, the same origins list is
      applied to allowed methods and headers for simplicity.
    """

    _router: APIRouter
    _fastapi_extra_args: dict[str, Any]
    _host: str
    _port: int
    _cors: list[str] | None

    def __init__(
        self,
        router: APIRouter,
        host: str,
        port: int,
        cors: list[str] | None = None,
        fastapi_extra_args: dict[str, Any] | None = None,
        *args,
        **kwargs,
    ):
        """
        Initialize the FastAPI server adapter.

        Parameters:
        - router (APIRouter): The router to include into the FastAPI app.
        - host (str): Host interface to bind Uvicorn to.
        - port (int): TCP port for the server.
        - cors (list[str] | None): Optional list of allowed origins. When set,
          it is also used for allowed methods and headers.
        - fastapi_extra_args (dict[str, Any] | None): Optional keyword args
          forwarded to the `FastAPI(...)` constructor.

        Notes:
        - This constructor does not start the server. The instance is prepared
          for a later `setup(...)` and `start(...)` sequence.
        """
        super().__init__(*args, **kwargs)
        self._router = router
        self._host = host
        self._port = port
        self._cors = cors

        if fastapi_extra_args is None:
            fastapi_extra_args = {}
        self._fastapi_extra_args = fastapi_extra_args

    def start(self, workers_to_run: list[str]):
        """
        Start FastAPI with Uvicorn and manage workers during app lifespan.

        Parameters:
        - workers_to_run (list[str]): Names of workers to start alongside the
          server. May be empty to run only the HTTP server.

        Behavior:
        - Constructs a FastAPI app with project metadata and a lifespan context
          that starts selected workers and gracefully stops them on shutdown.
        - Includes the provided router and, when configured, adds CORS middleware.
        - Runs the app using `uvicorn.run(...)` and blocks until termination.

        Raises:
        - RuntimeError: If the adapter has not been `setup(...)` with config,
          workers, and container prior to calling this method.
        """
        if self._config is None or self._workers is None or self._container is None:
            raise RuntimeError("ServerAdapter.setup(...) required")

        fastapi = FastAPI(
            title=self._config.PROJECT_NAME,
            version=self._config.VERSION,
            lifespan=partial(self._fastapi_lifespan, workers_to_run=workers_to_run),
            **self._fastapi_extra_args,
        )

        # Add Routers and middlewares
        fastapi.include_router(self._router)

        if self._cors is not None:
            fastapi.add_middleware(
                CORSMiddleware,
                allow_credentials=True,
                allow_origins=self._cors,
                allow_methods=self._cors,
                allow_headers=self._cors,
            )

        uvicorn.run(
            fastapi,
            host=self._host,
            port=self._port,
        )

    @asynccontextmanager
    async def _fastapi_lifespan(self, _, workers_to_run: list[str]):
        """
        Internal FastAPI lifespan context that manages worker lifecycle.

        Parameters:
            _ : Unused positional argument reserved by FastAPI lifespan signature.
            workers_to_run (list[str]): Ordered list of worker names selected to run.

        Behavior:
            - Creates a controller for the selected workers and yields control
              while they remain active. Cleanup occurs on application shutdown.
        """
        if self._workers is None or self._container is None:
            raise RuntimeError("ServerAdapter.setup(...) required")

        workerctl = WorkerController(
            self._workers.get_workers(
                workers_to_run,
                container=self._container,
            )
        )

        async with workerctl.runner():
            yield
