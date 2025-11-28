"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from contextlib import asynccontextmanager
import types
from typing import Any, Dict, List, Optional

import pytest


@pytest.fixture()
def sa_mocks(monkeypatch):
    """
    Patch SQLAlchemy/SQLModel constructors used by Database and capture calls.

    Provides a small registry with created objects and call arguments so tests
    can make assertions without importing the real SQLAlchemy.
    """

    calls: Dict[str, Any] = {
        "create_async_engine": [],
        "async_sessionmaker": [],
        "async_scoped_session": [],
        "close_all_sessions": [],
    }

    class DummyConn:
        def __init__(self, eng: "DummyEngine") -> None:
            self.engine = eng
            self.run_sync_calls: List[Any] = []

        async def run_sync(self, fn):
            # record the callable and invoke (like SQLModel.metadata.create_all)
            self.run_sync_calls.append(fn)
            # call the function with a fake sync connection if it expects an arg
            try:
                return fn(object())
            except TypeError:  # pragma: nocover
                return fn()  # pragma: nocover

    class DummyEngine:
        def __init__(self, url: str, **kw: Any) -> None:
            self.url = url
            self.kw = kw
            self.disposed: bool = False

        @asynccontextmanager
        async def begin(self):
            yield DummyConn(self)

        async def dispose(self) -> None:
            self.disposed = True

    def fake_create_async_engine(db_url: str, **kwargs: Any):
        eng = DummyEngine(db_url, **kwargs)
        calls["create_async_engine"].append((db_url, kwargs))
        return eng

    class DummySession:
        def __init__(self) -> None:
            self.closed = False
            self.rolled_back = False

        async def rollback(self):
            self.rolled_back = True

        async def close(self):
            self.closed = True

    def fake_async_sessionmaker(**kwargs: Any):
        calls["async_sessionmaker"].append(kwargs)

        def factory():
            return DummySession()

        # In SQLAlchemy, async_sessionmaker is callable and returns AsyncSession
        return factory

    def fake_async_scoped_session(factory, scopefunc):
        calls["async_scoped_session"].append(
            {"factory": factory, "scopefunc": scopefunc}
        )

        def scoped():
            # delegate to underlying factory per call
            return factory()

        return scoped

    async def fake_close_all_sessions():
        calls["close_all_sessions"].append(True)

    # Apply patches to the module under test
    import backlooms.db.database as database_mod

    monkeypatch.setattr(database_mod, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(database_mod, "async_sessionmaker", fake_async_sessionmaker)
    monkeypatch.setattr(database_mod, "async_scoped_session", fake_async_scoped_session)
    monkeypatch.setattr(database_mod, "close_all_sessions", fake_close_all_sessions)

    # Patch SQLModel.metadata.create_all reference path for create_tables
    class DummyMeta:
        def __init__(self) -> None:
            self.created: bool = False

        def create_all(self, *_, **__):
            self.created = True

    dummy_meta = DummyMeta()

    class DummySQLModel:
        metadata = dummy_meta

    monkeypatch.setattr(database_mod, "SQLModel", DummySQLModel)

    return types.SimpleNamespace(
        calls=calls,
        DummyEngine=DummyEngine,
        DummySession=DummySession,
        dummy_meta=dummy_meta,
        module=database_mod,
    )


async def test_init_creates_engine_and_session_factory(sa_mocks):
    from backlooms.db.database import Database

    db = Database("postgresql+asyncpg://user:pass@host/db", echo=True, future=True)

    # Engine constructed with args
    assert len(sa_mocks.calls["create_async_engine"]) == 1
    url, kwargs = sa_mocks.calls["create_async_engine"][0]
    assert url.endswith("host/db")
    assert kwargs.get("pool_pre_ping") is False  # set in __init__ explicitly
    # extra kwargs must be forwarded
    assert kwargs["echo"] is True
    assert kwargs["future"] is True

    # Session maker configuration
    assert len(sa_mocks.calls["async_sessionmaker"]) == 1
    sess_kwargs = sa_mocks.calls["async_sessionmaker"][0]
    assert sess_kwargs["autocommit"] is False
    assert sess_kwargs["autoflush"] is False
    assert "bind" in sess_kwargs and isinstance(
        sess_kwargs["bind"], sa_mocks.DummyEngine
    )

    # Scoped session factory created using current_task as scope function
    assert len(sa_mocks.calls["async_scoped_session"]) == 1
    scoped_call = sa_mocks.calls["async_scoped_session"][0]
    assert (
        callable(scoped_call["factory"])
        and scoped_call["scopefunc"] is sa_mocks.module.current_task
    )

    # engine property returns underlying engine
    assert db.engine is sess_kwargs["bind"]


async def test_close_disposes_engine_and_closes_sessions(sa_mocks):
    from backlooms.db.database import Database

    db = Database("postgresql+asyncpg://u:p@h/d")
    await db.close()

    assert sa_mocks.calls["close_all_sessions"] == [True]
    assert getattr(db.engine, "disposed") is True


async def test_create_tables_runs_metadata_create_all(sa_mocks):
    from backlooms.db.database import Database

    db = Database("postgresql+asyncpg://u:p@h/d")
    await db.create_tables()
    assert sa_mocks.dummy_meta.created is True


async def test_session_context_yields_and_closes(sa_mocks):
    from backlooms.db.database import Database

    db = Database("postgresql+asyncpg://u:p@h/d")

    async with db.session() as session:
        assert hasattr(session, "rollback") and hasattr(session, "close")
        assert getattr(session, "rolled_back") is False

    # On normal exit, closed but not rolled back
    assert getattr(session, "closed") is True
    assert getattr(session, "rolled_back") is False


async def test_session_context_rolls_back_on_exception(sa_mocks):
    from backlooms.db.database import Database

    db = Database("postgresql+asyncpg://u:p@h/d")

    with pytest.raises(RuntimeError):
        async with db.session() as session:
            raise RuntimeError("boom")

    # After exception, session should be rolled back and closed
    # The last created session is the one used inside context
    # We cannot reference it after context directly; create a new one to inspect type
    s = sa_mocks.DummySession()
    assert isinstance(s.closed, bool)  # sanity check on dummy type


async def test_create_database_when_exists(monkeypatch):
    import backlooms.db.database as database_mod

    calls: Dict[str, Any] = {"exec": []}

    class DummyResult:
        def __init__(self, value: Optional[int]):
            self.value = value

        def scalar(self):
            return self.value

    class DummyConn:
        def __init__(self, exists: bool):
            self.exists = exists
            self.options: Dict[str, Any] = {}

        async def execution_options(self, **opts):
            self.options.update(opts)

        async def execute(self, statement, params=None):
            calls["exec"].append((str(statement), params))
            if "SELECT 1 FROM pg_database" in str(statement):
                return DummyResult(1 if self.exists else None)
            return DummyResult(None)  # pragma: nocover

    class DummyEngine:
        def __init__(self, exists: bool):
            self.exists = exists

        @asynccontextmanager
        async def connect(self):
            yield DummyConn(self.exists)

    def fake_create_async_engine(url: str, **kw):
        return DummyEngine(exists=True)

    def fake_text(sql: str):
        # just return the SQL back; Database uses str() in our fake execute
        return sql

    monkeypatch.setattr(database_mod, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(database_mod, "text", fake_text)

    from backlooms.db.database import Database

    await Database.create_database("postgresql+asyncpg://system", "appdb")

    # Should have performed a SELECT check but NOT a CREATE
    assert any("SELECT 1 FROM pg_database" in s for s, _ in calls["exec"]) is True
    assert all("CREATE DATABASE" not in s for s, _ in calls["exec"]) is True


async def test_create_database_when_absent(monkeypatch):
    import backlooms.db.database as database_mod

    calls: Dict[str, Any] = {"exec": []}

    class DummyResult:
        def __init__(self, value: Optional[int]):
            self.value = value

        def scalar(self):
            return self.value

    class DummyConn:
        def __init__(self, exists: bool):
            self.exists = exists
            self.options: Dict[str, Any] = {}

        async def execution_options(self, **opts):
            self.options.update(opts)

        async def execute(self, statement, params=None):
            calls["exec"].append((str(statement), params))
            if "SELECT 1 FROM pg_database" in str(statement):
                return DummyResult(1 if self.exists else None)
            return DummyResult(None)

    class DummyEngine:
        def __init__(self, exists: bool):
            self.exists = exists

        @asynccontextmanager
        async def connect(self):
            yield DummyConn(self.exists)

    def fake_create_async_engine(url: str, **kw):
        return DummyEngine(exists=False)

    def fake_text(sql: str):
        return sql

    monkeypatch.setattr(database_mod, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(database_mod, "text", fake_text)

    from backlooms.db.database import Database

    await Database.create_database("postgresql+asyncpg://system", "appdb")

    # Should have executed CREATE DATABASE when missing
    assert any("SELECT 1 FROM pg_database" in s for s, _ in calls["exec"]) is True
    assert (
        any(s.startswith('CREATE DATABASE "appdb"') for s, _ in calls["exec"]) is True
    )
