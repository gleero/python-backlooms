"""
Alembic environment helper for automated configuration and migration runs.

This module provides `AlembicEnvHelper`, a small utility intended to be
instantiated from your project's Alembic `env.py` file located inside the
migrations directory (as described in the official Alembic documentation). The
helper wires the Alembic context, ensures your application's SQLModel models
are imported, and runs migrations in online mode using a synchronous SQLAlchemy
engine derived from your application's database configuration.

High‑level behavior:
- Reads Alembic's `alembic.ini` logging configuration (if present).
- Imports the provided database models module so that metadata is available to
  Alembic's autogeneration and migration routines.
- Builds a synchronous SQLAlchemy engine from the application's database URI
  (async drivers are adapted to their sync counterpart for migration execution).
- Runs migrations in online mode; offline mode is intentionally not handled by
  this helper and should be implemented in your `env.py` if required.

Usage (place in your Alembic `env.py` under the migrations folder):
    ```python
    # env.py
    from backlooms.db.mirgation import AlembicEnvHelper
    from myproj.core import Config  # your concrete Backlooms BaseConfig instance

    # Import your SQLModel models so they are registered in SQLModel.metadata
    import myproj.model

    AlembicEnvHelper(
        app_config=Config,
        database_model_module=myproj.model,
    ).run()
    ```

Notes:
- Ensure the `env.py` file resides in the Alembic migrations directory created
  by `alembic init`, so that Alembic can locate and execute it correctly.
- This helper focuses on online migrations and does not modify Alembic
  configuration files. Advanced configuration can be performed directly in
  `env.py` before invoking `run()`.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import importlib
from logging.config import fileConfig
from types import ModuleType
from typing import Callable

from alembic import context
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine

from backlooms.config import BaseConfig
from backlooms.db import BaseModelType


type ConfigSetupFn = Callable[[AlembicConfig], None]


class AlembicEnvHelper:
    """
    Thin helper to bootstrap Alembic and execute migrations from `env.py`.

    Purpose:
        - Centralize minimal, repeatable setup so your project's Alembic `env.py`
          stays concise and declarative.

    Behavior:
        - Validates that it runs within an Alembic environment and captures the
          current Alembic `Config` object.
        - Ensures your SQLModel models are imported so their metadata is visible
          to Alembic for autogenerate and migration execution.
        - Converts the application's database URI to a synchronous engine form
          where necessary and runs migrations in online mode.

    Notes:
        - This helper intentionally focuses on online migrations. If you need
          offline migrations (rendering SQL scripts without connecting), you can
          handle that separately in your `env.py`.
        - The Alembic `env.py` using this helper must reside inside the
          migrations directory created by Alembic (e.g., via `alembic init`).
    """

    _ctx_config: AlembicConfig
    _app_config: BaseConfig
    _config_setup: ConfigSetupFn | None

    def __init__(
        self,
        *,
        app_config: BaseConfig,
        database_model_module: ModuleType,
        config_setup: ConfigSetupFn | None = None,
    ):
        """
        Initialize the helper for use from Alembic's `env.py`.

        Parameters:
            app_config (BaseConfig): The already-instantiated application config
                that exposes a database URI via `BaseConfig.DATABASE_URI`.
            database_model_module (ModuleType): A module that imports/declares
                all SQLModel models used by your application so that their
                metadata is available for migrations and autogeneration.
            config_setup (Callable[[AlembicConfig], None] | None): Optional
                callback intended to receive the active Alembic config for
                additional adjustments prior to running migrations.

        Behavior:
            - Captures the active Alembic config from the execution context.
            - Imports the supplied `database_model_module` to ensure models are
              loaded and registered within SQLModel metadata.

        Usage example (inside Alembic `env.py` located in the migrations folder):
            ```python
            from backlooms.db.mirgation import AlembicEnvHelper
            from myproj.core import Config  # instance of your BaseConfig subclass

            # Ensure database models are imported
            import myproj.model

            AlembicEnvHelper(
                app_config=Config,
                database_model_module=myproj.model,
            ).run()
            ```

        Raises:
            RuntimeError: If called outside of an initialized Alembic context.
            ImportError: If `database_model_module` cannot be imported.
        """
        self._app_config = app_config
        self._config_setup = config_setup

        # this is the Alembic Config object, which provides
        # access to the values within the .ini file in use.
        try:
            self._ctx_config = context.config
        except AttributeError:
            raise RuntimeError("Alembic environment not initialized")

        # Preload database model module
        try:
            importlib.import_module(database_model_module.__name__)
        except ImportError as e:
            raise ImportError(
                f"Module {database_model_module.__name__} not found"
            ) from e

    def _run_migrations_online(self) -> None:
        """
        Execute Alembic migrations in online mode using the application's DB URI.

        Behavior:
            - Builds a synchronous SQLAlchemy engine from the configured
              application database URI (async drivers are adapted for sync
              execution).
            - Configures the Alembic context with project metadata and runs the
              migration sequence inside a transaction.

        Possible errors:
            - Exceptions propagated by SQLAlchemy or Alembic if connectivity or
              migration execution fails.
        """
        connectable = create_engine(
            self._app_config.DATABASE_URI.replace(
                "+asyncpg",
                "",
            ),
        )
        target_metadata = BaseModelType.metadata

        def include_name(*args, **kwargs):  # noqa
            return True

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_schemas=True,
                dialect_opts={"paramstyle": "named"},
                include_name=include_name,
            )

            with context.begin_transaction():
                context.run_migrations()

    def run(self):
        """
        Run the Alembic environment using the configured settings.

        Behavior:
            - Applies logging configuration referenced by Alembic's `alembic.ini`
              if available.
            - When running in online mode (default for Alembic CLI), executes the
              migration flow. Offline mode is not handled by this helper.

        Possible errors:
            - Exceptions raised by Alembic during environment setup or migration
              execution.
        """
        # Interpret the config file for Python logging.
        if self._ctx_config.config_file_name is not None:
            fileConfig(self._ctx_config.config_file_name)

        if self._config_setup is not None:
            self._config_setup(self._ctx_config)

        if not context.is_offline_mode():
            self._run_migrations_online()
