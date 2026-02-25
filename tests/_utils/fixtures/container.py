"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from typing import TYPE_CHECKING

import pytest
from dependency_injector.providers import Singleton

from backlooms.di import DIContainer


if TYPE_CHECKING:
    from backlooms.auth import IdentityManager
    from backlooms.db import Database


class Container(DIContainer):
    db: Singleton["Database"] = Singleton()
    identity_manager: Singleton["IdentityManager"] = Singleton()


@pytest.fixture
async def container(request, config):
    container = Container(config=config)
    container.wire(modules=[request.module.__name__, __name__])
    yield container
    container.reset_override()
