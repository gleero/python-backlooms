"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import pytest
from dependency_injector.providers import Singleton
from sqlalchemy import event

from backlooms.db import Database


@pytest.fixture
async def db_container(container):
    from sqlmodel import SQLModel

    database = Singleton(Database, db_url="sqlite+aiosqlite:///:memory:")

    @event.listens_for(database().engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    # Override database provider
    container.db.override(database)

    # Reset tables
    db_engine = container.db().engine
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield container

    # Clean-up
    event.remove(database().engine.sync_engine, "connect", set_sqlite_pragma)
    await container.db().close()
