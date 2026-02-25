import uuid
from datetime import timedelta

import pytest
from dependency_injector.providers import Object
from fastapi import APIRouter

from backlooms.auth import (
    AuthProvider,
    AuthProviderDepends,
    IdentityManager,
    JWTUserPayload,
)
from backlooms.auth.access_token import create_access_token
from backlooms.errors import AuthError


class MyProvider(AuthProvider):
    NAME = "myprovider"


class RouterProvider(AuthProvider):
    NAME = "router-provider"

    @property
    def router(self):
        return APIRouter()


def test_init_no_providers(user_service, auth_service, identity_manager):
    assert identity_manager._user_service is user_service
    assert identity_manager._auth_service is auth_service
    assert len(identity_manager._auth_providers) == 0


def test_init_provider(auth_service, user_service):

    manager = IdentityManager(
        auth_service=auth_service,
        user_service=user_service,
        providers=[MyProvider()],
    )

    assert len(manager._auth_providers) == 1
    assert "myprovider" in manager._auth_providers
    assert isinstance(manager._auth_providers["myprovider"], MyProvider)

    assert manager._auth_providers["myprovider"]._auth_service is auth_service
    assert manager._auth_providers["myprovider"]._user_service is user_service


def test_add_provider(identity_manager, auth_service, user_service):
    identity_manager.add_provider(MyProvider())

    assert len(identity_manager._auth_providers) == 1
    assert "myprovider" in identity_manager._auth_providers
    assert isinstance(identity_manager._auth_providers["myprovider"], MyProvider)

    assert identity_manager._auth_providers["myprovider"]._auth_service is auth_service
    assert identity_manager._auth_providers["myprovider"]._user_service is user_service


def test_add_provider_duplicate(identity_manager):
    identity_manager.add_provider(MyProvider())

    with pytest.raises(ValueError, match="Provider myprovider is already registered"):
        identity_manager.add_provider(MyProvider())


def test_get_item(identity_manager):
    identity_manager.add_provider(MyProvider())

    item = identity_manager["myprovider"]
    assert isinstance(item, MyProvider)


def test_get_item_not_found(identity_manager):
    with pytest.raises(KeyError, match="Provider myprovider is not registered"):
        _ = identity_manager["myprovider"]


def test_routers_empty(identity_manager):
    routers = [r for r in identity_manager.routers()]

    assert len(routers) == 0


def test_routers_with_no_router_provider(identity_manager):
    identity_manager.add_provider(MyProvider())
    routers = [r for r in identity_manager.routers()]

    assert len(routers) == 0


def test_routers_with_router_provider(identity_manager):
    identity_manager.add_provider(RouterProvider())
    routers = [r for r in identity_manager.routers()]

    assert len(routers) == 1
    assert isinstance(routers[0], APIRouter)


def test_provider_depends(container, identity_manager):
    identity_manager.add_provider(MyProvider())
    obj = Object(identity_manager)
    container.identity_manager.override(obj)

    dep = AuthProviderDepends("myprovider")

    assert dep.provider == "myprovider"
    assert isinstance(dep(), MyProvider)


def test_provider_depends_not_registered(container, identity_manager):
    obj = Object(identity_manager)
    container.identity_manager.override(obj)

    dep = AuthProviderDepends("myprovider")

    assert dep.provider == "myprovider"
    with pytest.raises(ValueError, match="Provider myprovider is not registered"):
        dep()


async def test_logout_unknown_user_id(identity_manager):
    await identity_manager.logout(uuid.uuid4())


async def test_logout(user_service, auth_service, session_repository, identity_manager):
    user = await user_service.create_user(login="user", auth_providers=[])
    for _ in range(10):
        await auth_service.issue_session(user.id)

    sessions = await session_repository.read_all()
    assert len(sessions) == 10

    await identity_manager.logout(user.id)

    sessions = await session_repository.read_all()
    assert len(sessions) == 0


async def test_validate_jwt_credentials_broken(identity_manager):
    with pytest.raises(AuthError, match="Invalid or expired session"):
        await identity_manager.validate_jwt_credentials("broken")


async def test_validate_jwt_credentials_expired(config, identity_manager):
    payload = JWTUserPayload(t="u", i=uuid.uuid4(), n="nonce")
    access_token, _ = create_access_token(
        payload,
        secret_key=config.SECRET_KEY,
        expires_delta=timedelta(minutes=-1000),
        algorithm=config.TOKEN_ALGORITHM,
    )

    with pytest.raises(AuthError, match="Invalid or expired session"):
        await identity_manager.validate_jwt_credentials(access_token)


async def test_validate_jwt_credentials_int_id(config, identity_manager):
    payload = JWTUserPayload(t="u", i=42, n="nonce")
    access_token, _ = create_access_token(
        payload,
        secret_key=config.SECRET_KEY,
        algorithm=config.TOKEN_ALGORITHM,
    )

    with pytest.raises(AuthError, match="Invalid or expired session"):
        await identity_manager.validate_jwt_credentials(access_token)


async def test_validate_jwt_credentials_not_allowed(config, identity_manager):
    payload = JWTUserPayload(t="u", i=uuid.uuid4(), n="nonce")
    access_token, _ = create_access_token(
        payload,
        secret_key=config.SECRET_KEY,
        algorithm=config.TOKEN_ALGORITHM,
    )

    with pytest.raises(AuthError, match="Session is blocked or not exists"):
        await identity_manager.validate_jwt_credentials(access_token)


async def test_validate_jwt_credentials(user_service, auth_service, identity_manager):
    user = await user_service.create_user(login="user", auth_providers=[])
    session = await auth_service.issue_session(user.id)
    payload = await identity_manager.validate_jwt_credentials(session.access_token)

    assert payload.i == user.id
    assert payload.t == "u"
    assert payload.exp > 0
    assert payload.n is not None
