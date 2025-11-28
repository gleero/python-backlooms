"""
Alembic migration CLI commands for Backlooms.

This module exposes a Typer action group named `MigrationAction` that provides
basic database migration commands backed by Alembic. The commands operate on
the Alembic project located within the calling application's source tree.

Commands:
- init: Create the application's database and tables if necessary, then stamp
  the Alembic head revision without applying migrations.
- current: Print the currently recorded Alembic revision for the target DB.
- upgrade [revision=head]: Upgrade the database schema to the given revision
  (defaults to `head`).
- downgrade <revision>: Downgrade the database schema to the given revision.

Behavior and prerequisites:
- The active DI container must be initialized and provide two providers:
  `config` (a `BaseConfig` instance with `DATABASE_URI`) and `db` (a `Database`
  instance from `backlooms.db`).
- Alembic project discovery is automatic - scans upward from the caller's
  module location to find a nearby `alembic.ini` and builds an Alembic
  `Config` for the commands.
- Errors from Alembic/SQL/database drivers propagate to the caller. The `init`
  command may create a PostgreSQL database on demand if it is missing and then
  create tables via SQLModel metadata before stamping the head revision.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import inspect
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Annotated

import asyncpg
from typer import Argument, Option

from backlooms.action import CLIAction
from backlooms.db import Database
from backlooms.di import DIContainer, use_container


action = CLIAction(
    name="migration",
    help="Manage database migrations",
)


if TYPE_CHECKING:
    from alembic.config import Config


@lru_cache
def get_alembic_config() -> "Config":
    """
    Locate and load the Alembic configuration for the calling application.

    Behavior:
    - Inspects the Python call stack to determine the source module that
      invoked a migration command from this module.
    - Starting from that module's directory, searches recursively for an
      `alembic.ini` file and constructs an Alembic `Config` pointing to it.
    - The result is cached for the process lifetime to avoid repeated
      filesystem scans.

    Returns:
    - Config: The Alembic configuration object associated with the discovered
      `alembic.ini` file.

    Raises:
    - RuntimeError: If no `alembic.ini` can be found relative to the caller's
      module location.
    """
    from alembic.config import Config

    source_module: ModuleType | None = None
    stack = inspect.stack()

    for frameinfo in reversed(stack[2:]):
        module = inspect.getmodule(frameinfo.frame)
        if module is None or module.__file__ is None:
            continue

        source_module = module
        break

    if source_module and source_module.__file__:
        src_path = Path(source_module.__file__).parent
        for item in src_path.glob("**/alembic.ini"):
            return Config(item)

    raise RuntimeError("No alembic.ini found")


@action.command("init", help="Create empty database")
async def action_init():
    """
    Initialize the database for migrations and stamp it to the latest revision.

    Behavior:
    - Uses the active DI container to obtain `config` and `db` providers.
    - Ensures the target database exists; for PostgreSQL, if the database is
      missing, it will be created using a connection to the `postgres` system
      database, then application tables are created from SQLModel metadata.
    - Calls Alembic `stamp` to mark the database at `head` without running
      migration scripts, aligning DB state with the latest revision.

    Raises:
    - RuntimeError: If the DI container does not expose a `db` provider.
    - Exceptions from `asyncpg`/SQLAlchemy/Alembic if connectivity or stamping
      fails.
    """
    from alembic import command

    container = use_container(DIContainer)
    config = container.config()

    if not hasattr(container, "db"):
        raise RuntimeError('Container does not have "db" dependency registered')

    db: Database = container.db()

    try:
        await db.create_tables()
    except asyncpg.exceptions.InvalidCatalogNameError:
        db_path = config.DATABASE_URI.replace(config.DB_DATABASE, "postgres")
        await Database.create_database(db_path, config.DB_DATABASE)
        await db.create_tables()

    command.stamp(get_alembic_config(), "head")


@action.command("current", help="Display current revision")
async def action_current(
    verbose: Annotated[bool, Option(help="Verbose output")] = False,
):
    """
    Display the current Alembic revision for the target database.

    Parameters:
    - verbose (bool): When True, prints full revision details; otherwise a
      concise output is used.

    Behavior:
    - Delegates to Alembic `command.current` with the discovered configuration.

    Possible errors:
    - Exceptions propagated by Alembic for configuration, I/O, or DB issues.
    """
    from alembic import command

    command.current(get_alembic_config(), verbose=verbose)


@action.command("upgrade", help="Upgrade migration")
async def action_upgrade(
    revision: Annotated[str, Argument(help="Upgrade to specific revision")] = "head",
):
    """
    Upgrade the database schema to the specified Alembic revision.

    Parameters:
    - revision (str): Target revision identifier; defaults to `head`.

    Behavior:
    - Delegates to Alembic `command.upgrade` using the discovered configuration.

    Possible errors:
    - Exceptions propagated by Alembic for migration failures or invalid
      revision identifiers.
    """
    from alembic import command

    command.upgrade(get_alembic_config(), revision)


@action.command("downgrade", help="Downgrade migration")
async def action_downgrade(
    revision: Annotated[str, Argument(help="Downgrade to specific revision")],
):
    """
    Downgrade the database schema to the specified Alembic revision.

    Parameters:
    - revision (str): Target revision identifier to downgrade to.

    Behavior:
    - Delegates to Alembic `command.downgrade` using the discovered
      configuration.

    Possible errors:
    - Exceptions propagated by Alembic for migration failures or invalid
      revision identifiers.
    """
    from alembic import command

    command.downgrade(get_alembic_config(), revision)


MigrationAction = action


__all__ = ["MigrationAction"]
