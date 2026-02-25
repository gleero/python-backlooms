"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from jose import jwt

from backlooms.auth import JWTUserPayload
from backlooms.auth.access_token import create_access_token, decode_jwt


@pytest.fixture
def jwt_user_payload():
    return JWTUserPayload(
        i=1,
        n="test-nonce",
        exp=int((datetime.now(tz=UTC) + timedelta(minutes=30)).timestamp()),
    )


def test_create_access_token_jose_call(monkeypatch):
    payload = JWTUserPayload(i=1, n="test-nonce")
    encode_mock = MagicMock(return_value="test")
    monkeypatch.setattr("backlooms.auth.access_token.jwt.encode", encode_mock)

    token, exp_date = create_access_token(
        payload,
        secret_key="secret",
    )

    encode_mock.assert_called_once_with(
        payload.model_dump(exclude_none=True),
        "secret",
        algorithm="HS256",
    )
    assert token == "test"
    assert exp_date is None


def test_create_access_token_expire(jwt_user_payload):
    token, exp_date = create_access_token(
        jwt_user_payload,
        secret_key="secret",
        expires_delta=timedelta(minutes=30),
    )

    assert isinstance(token, str)
    assert exp_date is not None
    assert isinstance(exp_date, datetime)

    decoded = jwt.decode(token, "secret", algorithms="HS256")
    assert decoded["i"] == jwt_user_payload.i
    assert decoded["n"] == jwt_user_payload.n
    assert decoded["t"] == "u"
    assert "exp" in decoded


def test_create_access_token_uuid():
    uuid_value = uuid4()
    payload = JWTUserPayload(i=uuid_value, n="test-nonce")
    token, _ = create_access_token(
        payload,
        secret_key="secret",
        expires_delta=timedelta(minutes=30),
    )
    decoded = jwt.decode(token, "secret", algorithms="HS256")
    assert decoded["i"] == str(uuid_value)


def test_create_access_token_not_expire_remove_e(jwt_user_payload):
    token, exp_date = create_access_token(jwt_user_payload, secret_key="secret")

    assert isinstance(token, str)
    assert exp_date is None

    decoded = jwt.decode(token, "secret", algorithms="HS256")
    assert "exp" not in decoded


def test_create_access_token_not_expire_without_e():
    payload = JWTUserPayload(i=1, n="test-nonce")
    token, exp_date = create_access_token(payload, secret_key="secret")

    assert isinstance(token, str)
    assert exp_date is None

    decoded = jwt.decode(token, "secret", algorithms="HS256")
    assert decoded["i"] == 1
    assert decoded["n"] == "test-nonce"
    assert "exp" not in decoded


def test_decode_jwt_valid_token(jwt_user_payload):
    token, _ = create_access_token(
        jwt_user_payload,
        secret_key="secret",
        expires_delta=timedelta(minutes=30),
    )
    decoded_payload = decode_jwt(token, secret_key="secret")

    assert decoded_payload is not None
    assert decoded_payload.i == jwt_user_payload.i
    assert decoded_payload.n == jwt_user_payload.n
    assert decoded_payload.t == jwt_user_payload.t


def test_decode_jwt_expired_token(jwt_user_payload):
    token, _ = create_access_token(
        jwt_user_payload,
        secret_key="secret",
        expires_delta=timedelta(seconds=-1),
    )
    decoded_payload = decode_jwt(token, secret_key="secret")

    assert decoded_payload is None


def test_decode_jwt_invalid_token():
    invalid_token = "this.is.not.a.valid.token"
    decoded_payload = decode_jwt(invalid_token, secret_key="secret")

    assert decoded_payload is None


@pytest.mark.parametrize(
    "exp_time, is_valid",
    [
        (None, False),
        (timedelta(minutes=5), True),
        (timedelta(hours=1), True),
        (timedelta(hours=-1), True),
    ],
)
def test_create_access_token_with_different_expiry(
    jwt_user_payload, exp_time, is_valid
):
    token, exp_date = create_access_token(
        jwt_user_payload,
        secret_key="secret",
        expires_delta=exp_time,
    )

    assert isinstance(token, str)
    if is_valid:
        assert exp_date is not None
    else:
        assert exp_date is None
