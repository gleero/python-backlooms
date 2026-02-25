from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backlooms.security import generate_unique_index
from tests._utils.users import SessionModel, UserModel


def test_init(session_repository, token_cache):
    assert token_cache._cache == {}
    assert token_cache._session_repository is session_repository


async def test_update_nonce_and_model(token_cache):
    model = SessionModel(user_id=uuid4(), nonce=generate_unique_index())
    await token_cache.update(model.user_id, nonce=model.nonce, model=model)

    key = f"{model.user_id}-{model.nonce}"
    assert key in token_cache._cache
    assert token_cache._cache[key] is True


async def test_update_state_inactive(token_cache):
    model = SessionModel(
        user_id=uuid4(),
        nonce=generate_unique_index(),
        is_active=False,
    )
    await token_cache.update(model.user_id, nonce=model.nonce, model=model)

    key = f"{model.user_id}-{model.nonce}"
    assert key in token_cache._cache
    assert token_cache._cache[key] is False


async def test_update_state_invalidate(token_cache):
    model = SessionModel(user_id=uuid4(), nonce=generate_unique_index())
    await token_cache.update(model.user_id, nonce=model.nonce, model=model)

    key = f"{model.user_id}-{model.nonce}"
    assert key in token_cache._cache

    await token_cache.update(model.user_id, nonce=model.nonce, model=None)
    assert key not in token_cache._cache


async def test_update_model_empty_nonce(token_cache):
    model = SessionModel(user_id=uuid4(), nonce=None)
    await token_cache.update(model.user_id, nonce=None, model=model)

    key = f"{model.user_id}"
    assert key in token_cache._cache
    assert token_cache._cache[key] is True


async def test_update_model_empty_nonce_model_but_nonce(token_cache):
    nonce = generate_unique_index()
    model = SessionModel(user_id=uuid4(), nonce=None)

    with pytest.raises(RuntimeError):
        await token_cache.update(model.user_id, nonce=nonce, model=model)


async def test_update_model_nonce_model_but_empty_nonce(token_cache):
    nonce = generate_unique_index()
    model = SessionModel(user_id=uuid4(), nonce=nonce)

    with pytest.raises(RuntimeError):
        await token_cache.update(model.user_id, nonce=None, model=model)


async def test_contains_true(token_cache):
    model = SessionModel(user_id=uuid4(), nonce=generate_unique_index())
    await token_cache.update(model.user_id, nonce=model.nonce, model=model)

    assert (model.user_id, model.nonce) in token_cache


async def test_contains_false(token_cache):
    model = SessionModel(user_id=uuid4(), nonce=generate_unique_index())

    assert (model.user_id, model.nonce) not in token_cache


async def test_is_record_id_allowed_not_in_cache_not_exists(token_cache):
    model = SessionModel(user_id=uuid4(), nonce=generate_unique_index())

    ret = await token_cache.is_record_id_allowed(model.user_id, nonce=model.nonce)
    key = f"{model.user_id}-{model.nonce}"

    assert ret is False
    assert key in token_cache._cache
    assert token_cache._cache[key] is False


async def test_is_record_id_allowed_not_in_cache_but_exists(
    token_cache,
    session_repository,
    user_repository,
):
    user = UserModel(login="test")
    session = SessionModel(user_id=user.id, nonce=generate_unique_index())

    await user_repository.create(user)
    await session_repository.create(session)

    ret = await token_cache.is_record_id_allowed(user.id, nonce=session.nonce)
    key = f"{session.user_id}-{session.nonce}"

    assert ret is True
    assert key in token_cache._cache
    assert token_cache._cache[key] is True


async def test_is_record_id_allowed_not_in_cache_inactive(
    token_cache, user_repository, session_repository
):
    user = UserModel(login="test")
    session = SessionModel(
        user_id=user.id, nonce=generate_unique_index(), is_active=False
    )

    await user_repository.create(user)
    await session_repository.create(session)

    ret = await token_cache.is_record_id_allowed(user.id, nonce=session.nonce)
    key = f"{session.user_id}-{session.nonce}"

    assert ret is False
    assert key in token_cache._cache
    assert token_cache._cache[key] is False


async def test_is_record_id_allowed_no_nonce(
    token_cache, user_repository, session_repository
):
    user = UserModel(login="test")
    session = SessionModel(user_id=user.id, nonce=None, is_active=True)

    await user_repository.create(user)
    await session_repository.create(session)

    ret = await token_cache.is_record_id_allowed(session.user_id, nonce=None)
    assert ret is True

    ret = await token_cache.is_record_id_allowed(session.user_id, nonce="something")
    assert ret is False


async def test_is_record_id_allowed_miss_cache(
    token_cache, user_repository, session_repository
):
    user = UserModel(login="test")
    session = SessionModel(user_id=user.id, nonce=None, is_active=True)

    await user_repository.create(user)
    await session_repository.create(session)

    token_cache.update = AsyncMock()

    ret = await token_cache.is_record_id_allowed(session.user_id, nonce=None)
    assert ret is False


async def test_drop_cache(token_cache):
    model = SessionModel(user_id=uuid4(), nonce=None)
    await token_cache.update(model.user_id, nonce=None, model=model)

    key = f"{model.user_id}"
    assert key in token_cache._cache
    assert token_cache._cache[key] is True

    await token_cache.drop_cache()
    assert key not in token_cache._cache
