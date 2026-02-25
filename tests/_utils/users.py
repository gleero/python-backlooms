"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import pytest
from dependency_injector.providers import Object

from backlooms.auth import (
    AuthService,
    IdentityManager,
    PureSessionModel,
    PureSessionRepository,
    TokenCache,
)
from backlooms.users import PureUserModel, PureUserRepository, PureUserService


class UserModel(PureUserModel, table=True):

    class Extra:
        name = "users"


class SessionModel(PureSessionModel, table=True):

    class Extra:
        name = "sessions"


class UserRepository(PureUserRepository[UserModel]):
    pass


class SessionRepository(PureSessionRepository[SessionModel]):
    pass


class UserService(PureUserService):
    pass


@pytest.fixture
def user_repository(db_container):
    yield UserRepository(session_factory=db_container.db().session)


@pytest.fixture
def session_repository(db_container):
    yield SessionRepository(session_factory=db_container.db().session)


@pytest.fixture
def user_service(user_repository):
    yield UserService(user_repository=user_repository)


@pytest.fixture
def token_cache(session_repository):
    yield TokenCache(session_repository=session_repository)


@pytest.fixture
def auth_service(config, user_repository, session_repository, token_cache):
    yield AuthService(
        user_repository=user_repository,
        session_repository=session_repository,
        cache=token_cache,
    )


@pytest.fixture
def identity_manager(config, container, auth_service, user_service):
    manager = IdentityManager(auth_service=auth_service, user_service=user_service)
    container.identity_manager.override(Object(manager))
    yield manager
