"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator, Self
from unittest.mock import MagicMock

import pytest

from backlooms.workers import BaseWorker, WorkerController, WorkerRegistry


class RecordingWorker(BaseWorker):
    NAME = "rec"
    DESCRIPTION = "rec"

    def __init__(
        self,
        *,
        container,
        name: str,
        events: list[tuple[str, str]],
        raise_err: bool = False,
    ):
        super().__init__(container=container)
        self.name = name
        self.events = events
        self.raise_err = raise_err

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[Self]:
        self.events.append(("enter", self.name))
        if self.raise_err:
            raise RuntimeError("boom")
        try:
            yield self
        finally:
            self.events.append(("exit", self.name))


def test_base_worker_no_lifespan():

    class WorkerWithoutLifespan(BaseWorker):  # noqa
        NAME = "my-worker"
        DESCRIPTION = "My worker description"

    with pytest.raises(TypeError):
        WorkerWithoutLifespan(container=None)  # type: ignore  # noqa


async def test_base_worker():

    class WorkerWithoutLifespan(BaseWorker):
        @asynccontextmanager
        async def lifespan(self) -> AsyncIterator[Self]:
            yield self

        NAME = "my-worker"
        DESCRIPTION = "My worker description"

    container_mock = MagicMock()
    worker = WorkerWithoutLifespan(container=container_mock)

    assert worker.NAME == "my-worker"
    assert worker.DESCRIPTION == "My worker description"
    assert worker._container is container_mock

    async with worker.lifespan() as ret:
        assert ret is worker


def test_worker_controller_init():
    ctl = WorkerController([])
    assert ctl._workers == []


async def test_worker_controller_no_workers():
    ctl = WorkerController([])

    async with ctl.runner() as stack:
        assert isinstance(stack, AsyncExitStack)


async def test_worker_controller_run_and_cleanup():
    events: list[tuple[str, str]] = []
    container = MagicMock()

    w1 = RecordingWorker(container=container, name="w1", events=events)
    w2 = RecordingWorker(container=container, name="w2", events=events)

    ctl = WorkerController([w1, w2])

    async with ctl.runner():
        assert events == [("enter", "w1"), ("enter", "w2")]

    # On exit, workers should be cleaned up in reverse order
    assert events == [
        ("enter", "w1"),
        ("enter", "w2"),
        ("exit", "w2"),
        ("exit", "w1"),
    ]


async def test_worker_controller_run_error():
    container = MagicMock()
    events: list[tuple[str, str]] = []

    good = RecordingWorker(container=container, name="good", events=events)
    bad = RecordingWorker(
        container=container, name="bad", events=events, raise_err=True
    )

    ctl = WorkerController([good, bad])

    with pytest.raises(RuntimeError, match="boom"):
        async with ctl.runner():
            pass  # pragma: nocover

    # The first worker should have been entered and then exited due to unwind.
    # The failing worker recorded only its attempted enter.
    assert events == [  # noqa
        ("enter", "good"),
        ("enter", "bad"),
        ("exit", "good"),
    ]


def test_worker_registry_init():
    reg = WorkerRegistry()
    assert reg._workers == {}
    assert reg.workers == []


def test_worker_registry_add():
    reg = WorkerRegistry()
    reg.add(RecordingWorker)

    assert "rec" in reg._workers
    assert reg._workers["rec"] == RecordingWorker
    assert reg.workers == [("rec", "rec")]


def test_worker_registry_add_duplicate():
    reg = WorkerRegistry()
    reg.add(RecordingWorker)
    with pytest.raises(ValueError, match="already registered"):
        reg.add(RecordingWorker)


def test_worker_registry_get_workers_not_exists():
    reg = WorkerRegistry()
    with pytest.raises(ValueError, match="not registered"):
        reg.get_workers(["foo"])


def test_worker_registry_get_workers_invalid_args():
    reg = WorkerRegistry()
    reg.add(RecordingWorker)
    with pytest.raises(TypeError):
        reg.get_workers(["rec"])


def test_worker_registry_get_workers():
    reg = WorkerRegistry()
    reg.add(RecordingWorker)
    ret = reg.get_workers(["rec"], container=MagicMock(), name="w1", events=[])
    assert isinstance(ret, list)
    assert len(ret) == 1
    assert isinstance(ret[0], RecordingWorker)
