"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import pytest

from backlooms.config import BaseConfig, use_config


class DummyConfig(BaseConfig):
    PROJECT_NAME: str = "test"
    VERSION: str = "1.2.3"
    SECRET_KEY: str = "secret"


def test_default_log_config():
    config = DummyConfig()
    c1 = config.LOG_CONFIG
    c2 = config.LOG_CONFIG

    assert c1 is c2

    assert c1["version"] == 1
    assert c1["disable_existing_loggers"] is False
    assert "formatters" in c1 and "handlers" in c1 and "loggers" in c1


def test_default_database_uri():
    config = DummyConfig()
    assert (
        config.DATABASE_URI
        == "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/backlooms"
    )


def test_use_config_not_initialized(monkeypatch):
    monkeypatch.setattr("backlooms.config.REGISTERED_GLOBAL_CONFIG", None)

    with pytest.raises(RuntimeError, match="Global config is not initialized"):
        use_config(BaseConfig)


def test_base_config_registers_global_on_init(monkeypatch):
    monkeypatch.setattr("backlooms.config.REGISTERED_GLOBAL_CONFIG", None)

    class LocalConfig(BaseConfig):
        PROJECT_NAME: str = "X"
        VERSION: str = "0.0.1"
        SECRET_KEY: str = "k"

    cfg = LocalConfig()

    # use_config should return the same instance and preserve type
    ret = use_config(LocalConfig)
    assert ret is cfg
    assert isinstance(ret, LocalConfig)


def test_database_uri_composition():
    class DBConfig(BaseConfig):
        PROJECT_NAME: str = "DB"
        VERSION: str = "1"
        SECRET_KEY: str = "k"
        DB_ENGINE: str = "postgresql+asyncpg"
        DB_USER: str = "user"
        DB_PASSWORD: str = "pass"
        DB_HOST: str = "db.local"
        DB_PORT: int = 5433
        DB_DATABASE: str = "appdb"

    cfg = DBConfig()
    assert cfg.DATABASE_URI == "postgresql+asyncpg://user:pass@db.local:5433/appdb"


def test_field_defaults_and_mutability_isolation():
    class C(BaseConfig):
        PROJECT_NAME: str = "P"
        VERSION: str = "1"
        SECRET_KEY: str = "k"

    c1 = C()
    c2 = C()

    assert c1.SERVER_HOST == "127.0.0.1"
    assert c1.SERVER_PORT == 8101

    # BACKEND_CORS_ORIGINS uses default_factory, must be a fresh list per instance
    assert c1.BACKEND_CORS_ORIGINS == ["*"]
    c1.BACKEND_CORS_ORIGINS.append("http://example.com")
    assert c1.BACKEND_CORS_ORIGINS != c2.BACKEND_CORS_ORIGINS
    assert c2.BACKEND_CORS_ORIGINS == ["*"]


def test_config_case_sensitive_flag():
    assert getattr(BaseConfig.ConfigDict, "case_sensitive", None) is True
