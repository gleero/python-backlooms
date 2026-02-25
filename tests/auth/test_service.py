import uuid

import pytest
from pydantic import BaseModel

from backlooms.auth.access_token import decode_jwt
from backlooms.errors import NotFoundError


async def test_issue_session(
    config, token_cache, auth_service, session_repository, user_service
):
    user = await user_service.create_user(login="user", auth_providers=[])
    response = await auth_service.issue_session(user.id)

    sessions = await session_repository.read_all()
    assert len(sessions) == 1

    assert sessions[0].user_id == user.id
    assert sessions[0].info == {}
    assert len(sessions[0].nonce) == 22

    token = decode_jwt(response.access_token, secret_key=config.SECRET_KEY)
    assert token is not None
    assert token.i == user.id
    assert token.t == "u"
    assert token.n == sessions[0].nonce
    assert token.exp is not None

    assert (user.id, sessions[0].nonce) in token_cache

    upd_user = await user_service.get_user_by_id(user.id)
    assert upd_user.last_authorized_at is not None


async def test_issue_session_unknown_user_id(auth_service):
    with pytest.raises(NotFoundError):
        await auth_service.issue_session(uuid.uuid4())


async def test_issue_session_session_info(
    auth_service, user_service, session_repository
):
    class MyModel(BaseModel):
        ip: str
        user_agent: str

    user = await user_service.create_user(login="user", auth_providers=[])
    await auth_service.issue_session(
        user.id, session_info=MyModel(ip="127.0.0.1", user_agent="test")
    )

    sessions = await session_repository.read_all()
    assert len(sessions) == 1

    assert sessions[0].user_id == user.id
    assert sessions[0].info == {"ip": "127.0.0.1", "user_agent": "test"}
    assert len(sessions[0].nonce) == 22


async def test_drop_session_user_not_found(auth_service):
    with pytest.raises(NotFoundError, match="Session not found"):
        await auth_service.drop_session(uuid.uuid4(), None)


async def test_drop_session_invalid_nonce(user_service, auth_service):
    user = await user_service.create_user(login="user", auth_providers=[])
    await auth_service.issue_session(user.id)

    with pytest.raises(NotFoundError, match="Session not found"):
        await auth_service.drop_session(user.id, nonce="invalid")


async def test_drop_session(
    user_service, auth_service, session_repository, token_cache
):
    user = await user_service.create_user(login="user", auth_providers=[])
    await auth_service.issue_session(user.id)

    session = (await session_repository.read_all())[0]

    await auth_service.drop_session(user.id, nonce=session.nonce)
    search_key = f"{user.id}-{session.nonce}"

    assert len(await session_repository.read_all()) == 0
    assert search_key not in token_cache._cache


async def test_drop_user_sessions_unknown_user_id(auth_service):
    await auth_service.drop_user_sessions(uuid.uuid4())


async def test_drop_user_sessions(user_service, auth_service, session_repository):
    user = await user_service.create_user(login="user", auth_providers=[])
    for _ in range(10):
        await auth_service.issue_session(user.id)

    sessions = await session_repository.read_all()
    assert len(sessions) == 10

    await auth_service.drop_user_sessions(user.id)

    sessions = await session_repository.read_all()
    assert len(sessions) == 0


async def test_is_user_id_allowed_true(user_service, auth_service, session_repository):
    user = await user_service.create_user(login="user", auth_providers=[])
    await auth_service.issue_session(user.id)

    session = (await session_repository.read_all())[0]

    assert await auth_service.is_user_id_allowed(user.id, session.nonce) is True


async def test_is_user_id_allowed_invalidate(
    user_service, auth_service, session_repository
):
    user = await user_service.create_user(login="user", auth_providers=[])
    await auth_service.issue_session(user.id)

    session = (await session_repository.read_all())[0]

    assert await auth_service.is_user_id_allowed(user.id, session.nonce) is True

    await auth_service.drop_session(user.id, nonce=session.nonce)
    assert await auth_service.is_user_id_allowed(user.id, session.nonce) is False
