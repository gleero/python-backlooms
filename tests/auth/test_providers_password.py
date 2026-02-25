from datetime import datetime

import pytest

from backlooms.auth.access_token import decode_jwt
from backlooms.auth.providers.password import (
    PasswordLoginUserRequest,
    PasswordProvider,
    PasswordProviderRepository,
    PasswordRegisterUserRequest,
)
from backlooms.errors import AuthError, DuplicatedError, ServiceError
from backlooms.security import get_password_hash, verify_password


@pytest.fixture
def register_request():
    yield PasswordRegisterUserRequest(
        login="test",
        password="pass",
    )


@pytest.fixture
def authenticate_request():
    yield PasswordLoginUserRequest(
        login="test",
        password="pass",
    )


@pytest.fixture
def password_repository(db_container):
    yield PasswordProviderRepository(session_factory=db_container.db().session)


@pytest.fixture
def password_provider(password_repository, auth_service, user_service):
    provider = PasswordProvider(password_repository=password_repository)
    provider.bind(auth_service, user_service)
    yield provider


def test_password_provider_init(password_repository):
    provider = PasswordProvider(password_repository=password_repository)
    assert provider.NAME == "password"
    assert provider._auth_service is None
    assert provider._user_service is None


async def test_register_user_not_bound(register_request, password_repository):
    provider = PasswordProvider(password_repository=password_repository)

    with pytest.raises(ServiceError, match="Services are not bound"):
        await provider.register_user(register_request)


async def test_register_user(
    config,
    password_provider,
    password_repository,
    user_repository,
    session_repository,
    register_request,
    token_cache,
    monkeypatch,
):
    monkeypatch.setattr(config, "AUTH_TOKEN_EXPIRE_MINUTES", None)

    resp = await password_provider.register_user(register_request)

    assert resp.login == "test"
    assert resp.session is not None

    users = await user_repository.read_all()
    assert len(users) == 1

    user = users[0]
    assert user.login == "test"
    assert user.auth_providers == ["password"]

    passwords = await password_repository.read_all()
    assert len(passwords) == 1

    password = passwords[0]
    assert password.id == 1
    assert password.user_id == user.id
    assert isinstance(password.created_at, datetime)
    assert isinstance(password.updated_at, datetime)
    assert verify_password("pass", password.password)

    sessions = await session_repository.read_all()
    assert len(sessions) == 1

    session = sessions[0]
    assert session.id == 1
    assert session.user_id == user.id
    assert session.info == {}
    assert session.nonce is not None

    token = decode_jwt(resp.session.access_token, secret_key=config.SECRET_KEY)
    assert token is not None
    assert token.i == user.id
    assert token.t == "u"
    assert token.n == session.nonce
    assert token.exp is None

    assert (user.id, session.nonce) in token_cache


async def test_register_user_no_config(
    password_provider, register_request, monkeypatch
):
    monkeypatch.setattr("backlooms.config.REGISTERED_GLOBAL_CONFIG", None)

    with pytest.raises(RuntimeError, match="Global config is not initialized"):
        await password_provider.register_user(register_request)


async def test_register_user_duplicate(config, password_provider, register_request):
    await password_provider.register_user(register_request)

    with pytest.raises(DuplicatedError):
        await password_provider.register_user(register_request)


async def test_register_user_exp_config(
    config,
    password_provider,
    register_request,
    monkeypatch,
):
    monkeypatch.setattr(config, "AUTH_TOKEN_EXPIRE_MINUTES", 10)

    resp = await password_provider.register_user(register_request)
    token = decode_jwt(resp.session.access_token, secret_key=config.SECRET_KEY)

    assert token is not None
    assert token.exp is not None and token.exp > 0


async def test_register_user_exp_param(
    config,
    password_provider,
    register_request,
    monkeypatch,
):
    monkeypatch.setattr(config, "AUTH_TOKEN_EXPIRE_MINUTES", None)

    resp = await password_provider.register_user(
        register_request, session_expire_minutes=42
    )
    token = decode_jwt(resp.session.access_token, secret_key=config.SECRET_KEY)

    assert token is not None
    assert token.exp is not None and token.exp > 0


async def test_authenticate_not_bound(authenticate_request, password_repository):
    provider = PasswordProvider(password_repository=password_repository)

    with pytest.raises(ServiceError, match="Services are not bound"):
        await provider.authenticate_user(authenticate_request)


async def test_authenticate_user_not_found(authenticate_request, password_provider):
    with pytest.raises(AuthError, match="Invalid credentials"):
        await password_provider.authenticate_user(authenticate_request)


async def test_authenticate_no_password_method(
    authenticate_request, user_service, password_provider
):
    await user_service.create_user(
        authenticate_request.login,
        auth_providers=["other"],
    )

    with pytest.raises(AuthError, match="Password method is not allowed"):
        await password_provider.authenticate_user(authenticate_request)


async def test_authenticate_no_password_record(
    authenticate_request,
    user_service,
    password_provider,
):
    await user_service.create_user(
        authenticate_request.login,
        auth_providers=["password"],
    )

    with pytest.raises(AuthError, match="Password method unavailable"):
        await password_provider.authenticate_user(authenticate_request)


async def test_authenticate_other_password(
    authenticate_request,
    user_service,
    password_provider,
    password_repository,
):
    user = await user_service.create_user(
        authenticate_request.login,
        auth_providers=["password"],
    )
    await password_repository.set_password(
        user.id,
        get_password_hash("other_password"),
    )

    with pytest.raises(AuthError, match="Invalid credentials"):
        await password_provider.authenticate_user(authenticate_request)


async def test_authenticate_valid_password(
    config,
    authenticate_request,
    user_service,
    password_provider,
    password_repository,
    token_cache,
):
    user = await user_service.create_user(
        authenticate_request.login,
        auth_providers=["password"],
    )
    await password_repository.set_password(
        user.id,
        get_password_hash(authenticate_request.password),
    )

    resp = await password_provider.authenticate_user(authenticate_request)

    token = decode_jwt(resp.session.access_token, secret_key=config.SECRET_KEY)
    assert token is not None
    assert token.i == user.id
    assert token.t == "u"
    assert token.n is not None
    assert len(token.n) == 22
    assert token.exp and token.exp > 0

    assert (user.id, token.n) in token_cache
