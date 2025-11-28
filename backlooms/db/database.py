"""
Asynchronous database access utilities for Backlooms.

This module provides a small, black-box `Database` helper around SQLAlchemy's
async engine and sessions with SQLModel integration. It is intended to be
constructed from an application-provided database URI and then used to:
- create and access a shared async engine;
- open task-scoped async sessions via a context manager;
- create database tables from the global `SQLModel.metadata`;
- optionally bootstrap a PostgreSQL database by name if it does not exist.

Notes:
- This module does not prescribe a transaction model. Callers are responsible
  for committing explicitly; on exceptions within the provided session context,
  an automatic rollback is performed before the session is closed.
- The session factory is scoped to the current asyncio task, so calls within the
  same task return the same underlying session instance during its lifetime.
- The `create_database` helper is PostgreSQL-oriented and expects a connection
  URI with privileges sufficient to create databases.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from asyncio import current_task
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    close_all_sessions,
    create_async_engine,
)
from sqlmodel import SQLModel


class Database:
    """
    High-level async database helper.

    Purpose:
        - Provide a minimal, framework-friendly façade over SQLAlchemy async
          engine, sessions, and SQLModel metadata operations.

    Behavior:
        - Holds a single async engine constructed from the provided database URI.
        - Exposes task-scoped async sessions via the `session()` async context
          manager. Sessions are tied to the current asyncio task while the
          context is active.
        - Does not automatically commit; callers should commit explicitly.
        - Offers convenience helpers to create tables and, for PostgreSQL,
          optionally create a database if it does not exist.

    Notes:
        - This class is agnostic of specific models; ensure your SQLModel models
          are imported before calling `create_tables()` so they are present in
          `SQLModel.metadata`.
        - Thread-safety is not guaranteed; prefer using it from async event
          loops and tasks rather than sharing across threads.
    """

    _engine: AsyncEngine
    _session_maker: async_sessionmaker
    _session_factory: async_scoped_session

    @property
    def engine(self) -> AsyncEngine:
        """
        Return the underlying async SQLAlchemy engine.

        Returns:
            AsyncEngine: The engine created for this `Database` instance.

        Notes:
            - The engine remains valid until `close()` is called. After disposal,
              attempting to use it may raise errors from SQLAlchemy.
        """
        return self._engine

    def __init__(self, db_url: str, **kwargs) -> None:
        """
        Initialize the database engine and session factories.

        Parameters:
            db_url (str): SQLAlchemy async database URI (e.g., `postgresql+asyncpg://...`).
            **kwargs: Additional keyword arguments forwarded to
                `sqlalchemy.ext.asyncio.create_async_engine`.

        Behavior:
            - Creates a single async engine for the lifetime of this instance.
            - Prepares an `async_sessionmaker` bound to the engine with
              `autocommit=False` and `autoflush=False`.
            - Configures a task-scoped session factory so calls to `session()`
              within the same asyncio task reuse the same session instance while
              the context manager is active.

        Possible errors:
            - ValueError/ArgumentError: Raised by SQLAlchemy if the URI or
              engine options are invalid.
            - RuntimeError: Propagated from the event loop if misused outside of
              an async context when sessions are created later.
        """
        self._engine = create_async_engine(
            db_url,
            pool_pre_ping=False,
            **kwargs,
        )
        self._session_maker = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine,
        )

        self._session_factory = async_scoped_session(
            self._session_maker, scopefunc=current_task
        )

    async def close(self):
        """
        Close all sessions and dispose the engine.

        Behavior:
            - Requests SQLAlchemy to close all known sessions created by this
              process and disposes the underlying async engine.

        Notes:
            - After disposal, the engine should not be used. Create a new
              `Database` instance if you need to reinitialize connections.

        Possible errors:
            - Exceptions propagated from SQLAlchemy if resources fail to close
              or the event loop is in an invalid state.
        """
        await close_all_sessions()
        await self.engine.dispose()

    async def create_tables(self) -> None:
        """
        Create all tables declared in `SQLModel.metadata`.

        Behavior:
            - Opens a transaction on the engine and invokes
              `SQLModel.metadata.create_all` in a synchronous context adapted for
              the async engine.

        Notes:
            - Ensure all SQLModel declarative models are imported before calling
              this method so they are registered with the global metadata.

        Possible errors:
            - Exceptions propagated from SQLAlchemy/SQLModel if DDL execution
              fails (e.g., connectivity issues, insufficient privileges, or
              invalid model definitions).
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    @classmethod
    async def create_database(cls, db_url: str, db_name: str) -> None:
        """
        Create a PostgreSQL database if it does not already exist.

        Parameters:
            db_url (str): Connection URI to a system database with sufficient
                privileges to create new databases (e.g., `postgres` DB).
            db_name (str): The name of the database to create.

        Behavior:
            - Connects using the provided `db_url` and checks for existence of
              `db_name` via `pg_database`.
            - Executes `CREATE DATABASE` when the database is absent; otherwise
              performs no operation.

        Notes:
            - This helper targets PostgreSQL specifically and relies on
              `pg_database`. It is not portable to other engines.
            - The `db_name` is interpolated as an identifier; ensure it is a
              trusted value. Quoting is applied but does not guard against all
              invalid names.

        Possible errors:
            - SQLAlchemy/driver exceptions for connectivity issues or
              insufficient privileges.
            - ProgrammingError if `db_name` is invalid or conflicts with
              existing objects.
        """
        system_engine = create_async_engine(db_url, echo=True, future=True)
        async with system_engine.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            )
            exists = result.scalar()
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Yield a task-scoped async session with automatic rollback on error.

        Yields:
            AsyncSession: A SQLAlchemy async session bound to this instance's
            engine. The same underlying session is reused within the current
            asyncio task while the context is active.

        Behavior:
            - On normal exit, the session is closed. No implicit commit is
              performed; callers are expected to commit explicitly.
            - If an exception escapes the context block, a rollback is issued
              before the session is closed and the exception is re-raised.

        Possible errors:
            - Exceptions propagated from SQLAlchemy when beginning, executing,
              committing, rolling back, or closing operations.
        """
        session = self._session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


__all__ = ["Database"]
