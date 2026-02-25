from datetime import datetime

import pytest
from pydantic import BaseModel

from backlooms.errors import DuplicatedError, NotFoundError
from backlooms.users import PureUserRepository, UserStatus
from backlooms.users.service import PureUserService


class UserInfo(BaseModel):
    name: str
    email: str


async def test_state(user_service):
    assert isinstance(user_service, PureUserService)
    assert isinstance(user_service._user_repository, PureUserRepository)


async def test_create_user(user_service):
    user = await user_service.create_user(login="user", auth_providers=[])
    assert user.login == "user"
    assert user.auth_providers == []
    assert isinstance(user.created_at, datetime)
    assert user.last_authorized_at is None
    assert user.info == {}
    assert user.status == UserStatus.ACTIVE


async def test_create_user_info(user_service):
    info = UserInfo(name="John", email="john@user.me")
    user = await user_service.create_user(login="user", auth_providers=[], info=info)
    assert user.info == {"name": "John", "email": "john@user.me"}


async def test_create_user_duplicate(user_service):
    await user_service.create_user(login="user", auth_providers=[])
    with pytest.raises(DuplicatedError):
        await user_service.create_user(login="user", auth_providers=[])


async def test_find_user_by_login_not_found(user_service):
    with pytest.raises(NotFoundError):
        await user_service.find_user_by_login("user")


async def test_find_user_by_login(user_service):
    user = await user_service.create_user(login="user", auth_providers=[])
    found = await user_service.find_user_by_login("user")

    assert found.login == "user"
    assert user.id == found.id
