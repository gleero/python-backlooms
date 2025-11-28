"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter
from starlette.middleware.cors import CORSMiddleware

from backlooms.server.adapters import FastAPIServerAdapter


@pytest.fixture()
def router():
    yield APIRouter()


def test_init(router):
    adapter = FastAPIServerAdapter(router=router, host="127.0.0.1", port=9000)
    assert adapter._router is router
    assert adapter._host == "127.0.0.1"
    assert adapter._port == 9000
    assert adapter._cors is None
    assert adapter._fastapi_extra_args == {}


def test_start_requires_setup(router):
    adapter = FastAPIServerAdapter(router=router, host="127.0.0.1", port=9000)
    with pytest.raises(RuntimeError, match="required"):
        adapter.start([])


def test_start(router, config, monkeypatch):
    container = MagicMock()
    registry = MagicMock()
    uvicorn_run = MagicMock()
    router_mock = MagicMock()
    router_mock.include_router = MagicMock()
    fastapi_mock = MagicMock(return_value=router_mock)

    monkeypatch.setattr("backlooms.server.adapters.fastapi.uvicorn.run", uvicorn_run)
    monkeypatch.setattr("backlooms.server.adapters.fastapi.FastAPI", fastapi_mock)

    adapter = FastAPIServerAdapter(
        router=router,
        host="127.0.0.1",
        port=9000,
        fastapi_extra_args={"docs_url": "/api-docs"},
    )
    adapter.setup(config=config, workers=registry, container=container)
    adapter.start([])

    fastapi_mock.assert_called_once()
    assert fastapi_mock.call_args[1]["title"] == config.PROJECT_NAME
    assert fastapi_mock.call_args[1]["version"] == config.VERSION
    assert fastapi_mock.call_args[1]["docs_url"] == "/api-docs"

    uvicorn_run.assert_called_once_with(
        fastapi_mock.return_value,
        host="127.0.0.1",
        port=9000,
    )

    router_mock.include_router.assert_called_once_with(router)


@pytest.mark.parametrize(
    "cors,expected_present",
    [
        (None, False),
        (["*"], True),
    ],
)
def test_start_with_cors(router, config, monkeypatch, cors, expected_present):
    fastapi_ret = MagicMock()
    fastapi_ret.add_middleware = MagicMock()

    monkeypatch.setattr("backlooms.server.adapters.fastapi.uvicorn.run", MagicMock())
    monkeypatch.setattr(
        "backlooms.server.adapters.fastapi.FastAPI", MagicMock(return_value=fastapi_ret)
    )

    adapter = FastAPIServerAdapter(
        router=router,
        host="127.0.0.1",
        port=9000,
        cors=cors,
        fastapi_extra_args={"docs_url": "/api-docs"},
    )
    adapter.setup(config=config, workers=MagicMock(), container=MagicMock())
    adapter.start([])

    if expected_present:
        fastapi_ret.add_middleware.assert_called_once_with(
            CORSMiddleware,
            allow_credentials=True,
            allow_origins=cors,
            allow_methods=cors,
            allow_headers=cors,
        )
    else:
        fastapi_ret.add_middleware.assert_not_called()


async def test_lifespan_requires_setup(router):
    adapter = FastAPIServerAdapter(router=router, host="127.0.0.1", port=8003)
    with pytest.raises(RuntimeError):
        async with adapter._fastapi_lifespan(None, workers_to_run=[]):
            pass  # pragma: nocover


async def test_lifespan(router, config, monkeypatch):

    class RecordingController:
        def __init__(self, workers):
            self.workers = workers
            self.entered = False
            self.exited = False

        @asynccontextmanager
        async def runner(self):
            self.entered = True
            try:
                yield self
            finally:
                self.exited = True

    container_mock = MagicMock()
    workers_mock = MagicMock()
    workers_mock.get_workers = MagicMock(return_value=["ret1", "ret2"])
    recording_controller = RecordingController([])
    workerctl = MagicMock(return_value=recording_controller)

    adapter = FastAPIServerAdapter(router=router, host="127.0.0.1", port=8003)
    adapter.setup(config=config, workers=workers_mock, container=container_mock)

    monkeypatch.setattr(
        "backlooms.server.adapters.fastapi.WorkerController",
        workerctl,
    )

    async with adapter._fastapi_lifespan(None, workers_to_run=["w1", "w2"]):
        pass

    workers_mock.get_workers.assert_called_once_with(
        ["w1", "w2"], container=container_mock
    )

    workerctl.assert_called_once_with(["ret1", "ret2"])

    assert recording_controller.entered is True
    assert recording_controller.exited is True
