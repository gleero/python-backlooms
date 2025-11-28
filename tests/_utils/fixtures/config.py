import pytest

from backlooms import BaseConfig


class DummyConfig(BaseConfig):
    PROJECT_NAME: str = "Test Project"
    VERSION: str = "1.2.3"
    SECRET_KEY: str = "secret"


@pytest.fixture()
def config():
    return DummyConfig()
