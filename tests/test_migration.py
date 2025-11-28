"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from __future__ import annotations

import copy
import importlib
import sys
from contextlib import contextmanager
import types
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from dependency_injector import providers
from typer.testing import CliRunner

from backlooms import DIContainer
from backlooms.db.database import Database
from backlooms.db.mirgation import MigrationAction


MODULE_NAME = "backlooms.db.mirgation.command"


@pytest.fixture
def init_command():
    init_cmd = None

    for cmd in MigrationAction.registered_commands:
        if cmd.name != "init":
            continue
        init_cmd = cmd

    assert init_cmd is not None
    assert init_cmd.callback is not None

    yield init_cmd


@pytest.fixture
def alembic_config(monkeypatch):
    alembic_config = MagicMock()
    get_alembic_config = MagicMock(return_value=alembic_config)
    monkeypatch.setattr(
        "backlooms.db.mirgation.command.get_alembic_config", get_alembic_config
    )
    yield alembic_config


@pytest.fixture
def runner():
    yield CliRunner()


@pytest.fixture()
def fake_module():
    """
    Provide a dynamically created importable module for models.

    The helper calls importlib.import_module(module.__name__), so we register
    this fake module in sys.modules to make the import succeed.
    """
    import sys

    mod = types.ModuleType("tests.fake_models")
    sys.modules[mod.__name__] = mod
    try:
        yield mod
    finally:
        sys.modules.pop(mod.__name__, None)


@pytest.fixture(scope="session")
def original_cmd_module():
    pkg = importlib.import_module(MODULE_NAME)
    original_dict = copy.copy(pkg.__dict__)
    return pkg, original_dict


@pytest.fixture(scope="function")
def cmd_pkg(original_cmd_module):
    original_module, original_dict = original_cmd_module

    sys.modules.pop(MODULE_NAME, None)
    test_module = importlib.import_module(MODULE_NAME)

    try:
        yield test_module
    finally:
        sys.modules[MODULE_NAME] = original_module
        original_module.__dict__.clear()
        original_module.__dict__.update(original_dict)


def _make_context_with_capture(store: Dict[str, Any]):

    def configure(**kwargs):
        store["configured_with"] = kwargs

    @contextmanager
    def begin_transaction():
        store["begin_tx_called"] = True
        store["begin_tx_entered"] = True
        yield
        store["begin_tx_exited"] = True

    def run_migrations():
        store["ran_migrations"] = True

    def is_offline_mode():
        return False

    # Minimal AlembicConfig stub
    class Cfg:
        config_file_name: str | None = None

    return types.SimpleNamespace(
        config=Cfg(),
        configure=configure,
        begin_transaction=begin_transaction,
        run_migrations=run_migrations,
        is_offline_mode=is_offline_mode,
    )


def test_env_helper_init(monkeypatch, fake_module, config):
    import backlooms.db.mirgation.env_helper as env_mod

    # Provide a fake Alembic context.config
    ctx_store: Dict[str, Any] = {}
    fake_ctx = _make_context_with_capture(ctx_store)
    monkeypatch.setattr(env_mod, "context", fake_ctx)

    helper = env_mod.AlembicEnvHelper(
        app_config=config,
        database_model_module=fake_module,
    )

    # Captured AlembicConfig object is stored internally (not exposed), but
    # we can assert the helper was constructed without raising and context is set.
    assert isinstance(helper, env_mod.AlembicEnvHelper)


def test_env_helper_init_no_alembic_context(monkeypatch, fake_module, config):
    import backlooms.db.mirgation.env_helper as env_mod

    # Simulate missing Alembic context.config attribute
    monkeypatch.setattr(env_mod, "context", types.SimpleNamespace(), raising=True)

    with pytest.raises(RuntimeError, match="Alembic environment not initialized"):
        env_mod.AlembicEnvHelper(app_config=config, database_model_module=fake_module)


def test_env_helper_run_migrations_online(monkeypatch, fake_module, config):
    import backlooms.db.mirgation.env_helper as env_mod

    # Arrange fake Alembic context with capture
    ctx_store: Dict[str, Any] = {}
    fake_ctx = _make_context_with_capture(ctx_store)
    monkeypatch.setattr(env_mod, "context", fake_ctx)

    # Replace BaseModelType with a stub exposing metadata
    target_metadata = object()
    monkeypatch.setattr(
        env_mod,
        "BaseModelType",
        types.SimpleNamespace(metadata=target_metadata),
    )

    # Provide a fake sync SQLAlchemy engine and connection
    calls: Dict[str, Any] = {"engine_url": None, "connect_entered": False}

    class DummyConn:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True  # pragma: nocover

    class DummyEngine:
        @contextmanager
        def connect(self):
            yield DummyConn()

    def fake_create_engine(url: str, *args, **kwargs):
        calls["engine_url"] = url
        return DummyEngine()

    monkeypatch.setattr(env_mod, "create_engine", fake_create_engine)

    # Instantiate helper
    helper = env_mod.AlembicEnvHelper(
        app_config=config, database_model_module=fake_module
    )

    # Act
    helper._run_migrations_online()

    # Assert create_engine called with stripped "+asyncpg"
    assert "+asyncpg" not in calls["engine_url"]
    assert calls["engine_url"].startswith("postgresql://")

    # Assert context.configure received expected entries
    cfg = ctx_store.get("configured_with", {})
    assert cfg.get("connection") is not None
    assert cfg.get("target_metadata") is target_metadata
    assert cfg.get("include_schemas") is True
    assert cfg.get("dialect_opts", {}).get("paramstyle") == "named"
    assert callable(cfg.get("include_name")) and cfg["include_name"]() is True

    # Assert run_migrations was called inside a transaction
    assert ctx_store.get("begin_tx_called") is True
    assert ctx_store.get("begin_tx_entered") is True
    assert ctx_store.get("ran_migrations") is True


def test_env_helper_run_applies_file_config(monkeypatch, fake_module, config):
    import backlooms.db.mirgation.env_helper as env_mod

    # Prepare context with config having a file path and online mode
    ctx_store: Dict[str, Any] = {}
    fake_ctx = _make_context_with_capture(ctx_store)
    fake_ctx.config.config_file_name = "alembic.ini"

    # Patch into module
    monkeypatch.setattr(env_mod, "context", fake_ctx)

    # Capture fileConfig calls
    fcalls: list[str] = []

    def fake_file_config(path: str):
        fcalls.append(path)

    monkeypatch.setattr(env_mod, "fileConfig", fake_file_config)

    # Avoid invoking real SQLAlchemy by stubbing out _run_migrations_online
    ran_online = {"called": False}

    def fake_run_online(self):  # noqa: D401
        ran_online["called"] = True

    monkeypatch.setattr(
        env_mod.AlembicEnvHelper, "_run_migrations_online", fake_run_online
    )

    # Custom config_setup callback capturing the Alembic config instance
    received_cfg: list[Any] = []

    def setup_cb(cfg):
        received_cfg.append(cfg)

    helper = env_mod.AlembicEnvHelper(
        app_config=config,
        database_model_module=fake_module,
        config_setup=setup_cb,
    )

    # Act
    helper.run()

    # fileConfig applied with provided path
    assert fcalls == ["alembic.ini"]

    # config_setup was invoked with the current Alembic config
    assert len(received_cfg) == 1
    assert received_cfg[0] is fake_ctx.config

    # Since offline mode is False by default, online migrations should run
    assert ran_online["called"] is True


def test_env_helper_run_skips_online_in_offline_mode(monkeypatch, fake_module, config):
    import backlooms.db.mirgation.env_helper as env_mod

    # Build context signaling offline mode
    ctx_store: Dict[str, Any] = {}
    fake_ctx = _make_context_with_capture(ctx_store)

    def offline_true():
        return True

    fake_ctx.is_offline_mode = offline_true
    monkeypatch.setattr(env_mod, "context", fake_ctx)

    # Stub _run_migrations_online to ensure it is NOT called
    called = {"n": 0}

    def fake_run_online(self):
        called["n"] += 1  # pragma: nocover

    monkeypatch.setattr(
        env_mod.AlembicEnvHelper, "_run_migrations_online", fake_run_online
    )

    helper = env_mod.AlembicEnvHelper(
        app_config=config, database_model_module=fake_module
    )
    helper.run()

    assert called["n"] == 0


def test_env_helper_init_import_error(monkeypatch, fake_module, config):
    import backlooms.db.mirgation.env_helper as env_mod

    # Provide a fake Alembic context.config so __init__ gets past env check
    fake_ctx = _make_context_with_capture({})
    monkeypatch.setattr(env_mod, "context", fake_ctx)

    # Force import of the provided models module to fail
    def fail_import(_: str):
        raise ImportError("boom")

    monkeypatch.setattr(env_mod.importlib, "import_module", fail_import)

    with pytest.raises(ImportError, match=f"Module {fake_module.__name__} not found"):
        env_mod.AlembicEnvHelper(
            app_config=config,
            database_model_module=fake_module,
        )


def test_command_action_downgrade(runner, alembic_config, monkeypatch):
    downgrade_command = MagicMock()
    monkeypatch.setattr("alembic.command.downgrade", downgrade_command)

    ret = runner.invoke(MigrationAction, ["downgrade", "test"])

    assert ret.exit_code == 0
    downgrade_command.assert_called_once_with(alembic_config, "test")


def test_command_action_upgrade(runner, alembic_config, monkeypatch):
    upgrade_command = MagicMock()
    monkeypatch.setattr("alembic.command.upgrade", upgrade_command)

    ret = runner.invoke(MigrationAction, ["upgrade"])
    assert ret.exit_code == 0
    upgrade_command.assert_called_once_with(alembic_config, "head")
    upgrade_command.reset_mock()

    ret = runner.invoke(MigrationAction, ["upgrade", "specific_revision"])
    assert ret.exit_code == 0
    upgrade_command.assert_called_once_with(alembic_config, "specific_revision")


def test_command_action_current(runner, alembic_config, monkeypatch):
    current_command = MagicMock()
    monkeypatch.setattr("alembic.command.current", current_command)

    ret = runner.invoke(MigrationAction, ["current"])
    assert ret.exit_code == 0
    current_command.assert_called_once_with(alembic_config, verbose=False)
    current_command.reset_mock()

    ret = runner.invoke(MigrationAction, ["current", "--verbose"])
    assert ret.exit_code == 0
    current_command.assert_called_once_with(alembic_config, verbose=True)
    current_command.reset_mock()


def test_command_action_init_no_db(init_command):
    class Container(DIContainer):
        pass

    Container()

    with pytest.raises(RuntimeError, match="Container does not have"):
        init_command.callback()


def test_command_action_init_bad_db(init_command, alembic_config, monkeypatch, config):
    class DummyDB:
        def __init__(self):
            self.raised = False

        async def create_tables(self):
            if not self.raised:
                self.raised = True
                raise asyncpg.exceptions.InvalidCatalogNameError()

    class Container(DIContainer):
        db = providers.Singleton(DummyDB)

    create_db = AsyncMock()
    stamp_command = MagicMock()

    monkeypatch.setattr(Database, "create_database", create_db)
    monkeypatch.setattr("alembic.command.stamp", stamp_command)

    Container(config=config)
    init_command.callback()

    create_db.assert_called_once()
    stamp_command.assert_called_once_with(alembic_config, "head")


def test_command_action_has_db(init_command, alembic_config, monkeypatch, config):
    dummy_db_obj = MagicMock()
    dummy_db_obj.create_tables = AsyncMock()
    dummy_db = MagicMock(return_value=dummy_db_obj)

    class Container(DIContainer):
        db = providers.Singleton(dummy_db)

    stamp_command = MagicMock()
    monkeypatch.setattr("alembic.command.stamp", stamp_command)

    Container(config=config)
    init_command.callback()

    dummy_db_obj.create_tables.assert_called_once()
    stamp_command.assert_called_once_with(alembic_config, "head")


def test_get_alembic_config_empty_stack(cmd_pkg, monkeypatch):
    monkeypatch.setattr(
        "backlooms.db.mirgation.command.inspect.stack",
        lambda: [],
    )

    with pytest.raises(RuntimeError, match="No alembic.ini found"):
        cmd_pkg.get_alembic_config()


def test_get_alembic_config_has_file(cmd_pkg, monkeypatch):
    class Frame:
        def __init__(self, frame):
            self.frame = frame
            self.__file__ = f"/path/to/{frame}.py"

    getmodule = MagicMock(return_value=Frame("ret"))
    alembic_config = MagicMock()

    fo = MagicMock()
    fo.parent.glob = MagicMock(return_value=["/path/to/alembic.ini"])

    path_mock = MagicMock(return_value=fo)

    monkeypatch.setattr(
        "backlooms.db.mirgation.command.inspect.stack",
        lambda: [Frame("f1"), Frame("f2"), Frame("f3"), Frame("f4")],
    )
    monkeypatch.setattr(
        "backlooms.db.mirgation.command.inspect.getmodule",
        getmodule,
    )
    monkeypatch.setattr(
        "backlooms.db.mirgation.command.Path",
        path_mock,
    )
    monkeypatch.setattr(
        "alembic.config.Config",
        alembic_config,
    )

    cmd_pkg.get_alembic_config()

    getmodule.assert_called_once_with("f4")
    path_mock.assert_called_once_with("/path/to/ret.py")
    fo.parent.glob.assert_called_once_with("**/alembic.ini")
    alembic_config.assert_called_once_with("/path/to/alembic.ini")


def test_get_alembic_config_none(cmd_pkg, monkeypatch):
    class Frame:
        def __init__(self, frame):
            self.frame = frame
            self.__file__ = f"/path/to/{frame}.py"

    getmodule = MagicMock(return_value=None)
    monkeypatch.setattr(
        "backlooms.db.mirgation.command.inspect.stack",
        lambda: [Frame("f1"), Frame("f2"), Frame("f3")],
    )
    monkeypatch.setattr(
        "backlooms.db.mirgation.command.inspect.getmodule",
        getmodule,
    )

    with pytest.raises(RuntimeError, match="No alembic.ini found"):
        cmd_pkg.get_alembic_config()

    getmodule.assert_called_once_with("f3")
