"""
Configuration base and global access hook for Backlooms.

This module provides `BaseConfig`, a `pydantic-settings`-powered settings
object intended to be subclassed by applications. A typical pattern is to
create a single concrete configuration class that inherits from `BaseConfig`,
instantiate it once at import time, and re-export that instance for
application-wide use. Upon instantiation, the config instance is registered as
the current global configuration; it can later be retrieved via `use_config`.

Behavior and expectations:
- Environment loading: values may be populated from environment variables and
  other sources supported by `pydantic-settings`.
- Single source of truth: the first created instance becomes the globally
  registered config for the process; `use_config` returns that instance.
- Database DSN: the `DATABASE_URI` property exposes a connection string built
  from the database-related fields for use by clients/ORMs.
- Logging: `default_log_config()` returns a dictionary suitable for
  `logging.config.dictConfig` to initialize basic structured logging.

Notes:
- Instantiating a subclass may raise validation errors if required fields are
  missing or invalid according to `pydantic` rules.
- Case sensitivity for environment variables is enabled to avoid accidental
  overrides.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import os
from typing import cast, TypeVar

from pydantic import Field
from pydantic_settings import BaseSettings


DATABASE_URI_FORMAT = "{db_engine}://{user}:{password}@{host}:{port}/{database}"


def default_log_config():
    """
    Build a logging configuration mapping for `logging.config.dictConfig`.

    Returns:
        dict: A dictionary compliant with `dictConfig` that configures a
        simple stderr handler and a default formatter suitable for CLI and
        service logs.

    Notes:
        - A fresh mapping is returned on each call; callers may safely mutate
          their copy without affecting others.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(asctime)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "root": {"handlers": ["default"], "level": "INFO"},
        },
    }


REGISTERED_GLOBAL_CONFIG: object | None = None


class BaseConfig(BaseSettings):
    """
    Base settings class for Backlooms applications.

    Purpose:
        - Serve as a strong-typed, environment-aware configuration base that
          applications subclass to define their own settings surface.
        - Register the first instantiated config as the process-wide active
          configuration, retrievable via `use_config`.

    Usage pattern (without examples):
        - Define a subclass that sets required fields such as `PROJECT_NAME` and
          `VERSION` and optionally overrides defaults.
        - Instantiate exactly once during application startup and re-export the
          instance for use throughout the codebase.

    Field categories:
        - Project: name, description, version.
        - Server: host, port.
        - Auth: secret key, token algorithm, expirations.
        - CORS: allowed origins list.
        - Database: engine, user, password, host, port, database name and a
          derived `DATABASE_URI` property.
        - Logging: mapping for `logging.config.dictConfig`.

    Notes:
        - Validation and environment binding behavior follow `pydantic-settings`.
        - Environment variable handling is case-sensitive.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global REGISTERED_GLOBAL_CONFIG
        REGISTERED_GLOBAL_CONFIG = self

    @property
    def DATABASE_URI(self) -> str:  # noqa
        """
        Compose and return the database connection URI.

        Returns:
            str: A DSN constructed from the database-related fields using the
            template `DATABASE_URI_FORMAT`.

        Notes:
            - Consumers typically pass this URI to database clients/ORMs.
            - If any of the contributing fields are invalid or empty, the
              resulting URI may be unusable for downstream clients.
        """
        return DATABASE_URI_FORMAT.format(
            db_engine=self.DB_ENGINE,
            user=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_DATABASE,
        )

    PROJECT_ROOT: str = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    # Base
    PROJECT_NAME: str
    PROJECT_DESCRIPTION: str | None = None
    VERSION: str

    # API Server params
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = 8101

    # Auth
    SECRET_KEY: str
    TOKEN_ALGORITHM: str = "HS256"
    AUTH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    API_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 365  # 1 year

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["*"])

    # Database
    DB: str = "postgresql"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_ENGINE: str = "postgresql+asyncpg"
    DB_DATABASE: str = "backlooms"

    # Logging
    LOG_CONFIG: dict = Field(default_factory=default_log_config)

    class ConfigDict:
        case_sensitive = True


T = TypeVar("T", bound=BaseConfig)


def use_config[T](_: T | type[T]) -> T:
    """
    Retrieve the globally registered configuration instance.

    Parameters:
        _ (T | type[T]): A placeholder used solely for typing to indicate the
            expected config subtype. The value is ignored at runtime.

    Returns:
        T: The configuration instance that was previously registered when a
        `BaseConfig` (or subclass) was instantiated.

    Raises:
        RuntimeError: If no configuration has been registered yet. Ensure your
        application creates its concrete config instance during startup.

    Notes:
        - Useful as a lightweight hook in modules that need access to the
          active configuration without passing it through call chains.
    """
    if REGISTERED_GLOBAL_CONFIG is None:
        raise RuntimeError("Global config is not initialized")
    return cast(T, REGISTERED_GLOBAL_CONFIG)


__all__ = ["BaseConfig", "use_config"]
