"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from dependency_injector import containers
from typer.testing import CliRunner

from backlooms import Application, CLIAction
from backlooms.di import DIContainer
from backlooms.workers import BaseWorker, WorkerRegistry


@pytest.fixture
def runner():
    yield CliRunner()


def test_application_init_without_all(config, monkeypatch, runner):
    dict_config_mock = MagicMock()
    monkeypatch.setattr("backlooms.application.dictConfig", dict_config_mock)

    app = Application(
        config=config,
        container_cls=DIContainer,
    )

    assert app._config is config
    assert app._server_adapter is None

    assert isinstance(app._container, containers.DynamicContainer)
    assert isinstance(app._workers, WorkerRegistry)

    dict_config_mock.aassert_called_once_with(config.LOG_CONFIG)

    assert app._typer.info.name == config.PROJECT_NAME
    assert app._typer.info.help is None
    assert app._typer.info.context_settings is not None
    assert "help_option_names" in app._typer.info.context_settings

    assert len(app._typer.registered_commands) == 1
    assert app._typer.registered_commands[0].name == "run"

    assert app.typer == app._typer
    assert app.container == app._container
    assert app.config == config

    ret = runner.invoke(app.typer, ["run", "--help"])
    assert "Worker to run [required]" in ret.stdout
    assert "CMD:{}" in ret.stdout


def test_application_init_server_adapter(config, runner):
    adapter = MagicMock()
    adapter.setup = MagicMock()

    app = Application(
        config=config,
        container_cls=DIContainer,
        server_adapter=adapter,
    )

    assert app._server_adapter is adapter

    adapter.setup.assert_called_once_with(
        config=config, workers=app._workers, container=app._container
    )

    assert len(app._typer.registered_commands) == 2
    assert app._typer.registered_commands[0].name == "run"
    assert app._typer.registered_commands[1].name == "start"

    ret = runner.invoke(app.typer, ["run", "--help"])
    assert "Worker to run [required]" in ret.stdout
    assert "CMD:{}" in ret.stdout

    ret = runner.invoke(app.typer, ["start", "--help"])
    assert "Test Project start" in ret.stdout
    assert "--server-only" in ret.stdout


def test_application_init_with_workers(config, runner):
    adapter = MagicMock()
    workers = WorkerRegistry()

    class DummyWorker(BaseWorker):
        NAME = "dummy"
        DESCRIPTION = "Dummy Worker"

        @asynccontextmanager
        async def lifespan(self):
            yield self  # pragma: no cover

    workers.add(DummyWorker)

    app = Application(
        config=config,
        container_cls=DIContainer,
        server_adapter=adapter,
        workers=workers,
    )

    assert app._workers is workers

    assert len(app._typer.registered_commands) == 2
    assert app._typer.registered_commands[0].name == "run"
    assert app._typer.registered_commands[1].name == "start"

    ret = runner.invoke(app.typer, ["run", "--help"])
    assert "- dummy: Dummy Worker" in ret.stdout
    assert "CMD:{dummy}" in ret.stdout

    ret = runner.invoke(app.typer, ["start", "--help"])
    assert "--with-dummy" in ret.stdout
    assert "--without-dummy" in ret.stdout


def test_application_init_actions(config, runner):
    app = Application(
        config=config,
        container_cls=DIContainer,
        actions=[CLIAction(name="hello"), CLIAction(name="world")],
    )

    assert len(app._typer.registered_commands) == 1
    assert len(app._typer.registered_groups) == 2
    assert app._typer.registered_commands[0].name == "run"

    ret = runner.invoke(app.typer, ["--help"])
    assert "run" in ret.stdout
    assert "hello" in ret.stdout
    assert "world" in ret.stdout


def test_run_command_no_cmd(config):
    app = Application(
        config=config,
        container_cls=DIContainer,
    )
    with pytest.raises(SystemError, match="No worker specified"):
        app._run_command()


def test_run_command_unknown(config):
    app = Application(
        config=config,
        container_cls=DIContainer,
    )
    with pytest.raises(SystemError, match="Worker test not registered"):
        app._run_command(cmd="test")


def test_run_command(config):
    workers = WorkerRegistry()

    class DummyWorker(BaseWorker):
        NAME = "dummy"
        DESCRIPTION = "Dummy Worker"

        @asynccontextmanager
        async def lifespan(self):
            raise RuntimeError("boom")
            yield self  # pragma: no cover  # noqa

    workers.add(DummyWorker)

    app = Application(
        config=config,
        container_cls=DIContainer,
        workers=workers,
    )
    with pytest.raises(RuntimeError, match="boom"):
        app._run_command(cmd="dummy")


def test_start_command_no_server_adapter(config):
    app = Application(
        config=config,
        container_cls=DIContainer,
    )
    assert app._start_command(True) is None


def test_start_command(config):
    adapter = MagicMock()
    adapter.start = MagicMock()
    workers = WorkerRegistry()

    class DummyWorker(BaseWorker):
        NAME = "dummy"
        DESCRIPTION = "Dummy Worker"

        @asynccontextmanager
        async def lifespan(self):
            yield self  # pragma: no cover

    workers.add(DummyWorker)

    app = Application(
        config=config,
        container_cls=DIContainer,
        server_adapter=adapter,
        workers=workers,
    )

    app._start_command(False, dummy=True)
    adapter.start.assert_called_once_with(["dummy"])
    adapter.start.reset_mock()

    app._start_command(True, dummy=True)
    adapter.start.assert_called_once_with([])
    adapter.start.reset_mock()

    app._start_command(False, dummy=False)
    adapter.start.assert_called_once_with([])


async def test_run_worker_not_registered(config):
    app = Application(
        config=config,
        container_cls=DIContainer,
    )
    with pytest.raises(SystemError, match="Worker test not registered"):
        await app._run_worker("test")


async def test_run_worker(config, monkeypatch):
    workers = WorkerRegistry()
    stop_event = AsyncMock()
    stop_event.wait.return_value = None
    event_object = MagicMock(return_value=stop_event)

    monkeypatch.setattr("backlooms.application.asyncio.Event", event_object)

    class DummyWorker(BaseWorker):
        NAME = "dummy"
        DESCRIPTION = "Dummy Worker"

        @asynccontextmanager
        async def lifespan(self):
            yield self

    workers.add(DummyWorker)

    app = Application(
        config=config,
        container_cls=DIContainer,
        workers=workers,
    )

    await app._run_worker("dummy")
    stop_event.wait.assert_awaited_once()


async def test_run_worker_cancelled_error(config):
    workers = WorkerRegistry()

    class DummyWorker(BaseWorker):
        NAME = "dummy"
        DESCRIPTION = "Dummy Worker"

        @asynccontextmanager
        async def lifespan(self):
            raise asyncio.CancelledError()
            yield self  # pragma: no cover  # noqa

    workers.add(DummyWorker)

    app = Application(
        config=config,
        container_cls=DIContainer,
        workers=workers,
    )

    # No CancelledError exception should be raised
    await app._run_worker("dummy")


def test_run(config):
    app = Application(
        config=config,
        container_cls=DIContainer,
    )
    app._typer = MagicMock()
    app.run()
    app._typer.assert_called_once()  # noqa
