"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pwdlib import PasswordHash

from backlooms.security import (
    generate_password,
    generate_unique_index,
    get_password_hash,
    verify_password,
)
from backlooms.security.bearer_token import BaseBearer


@pytest.fixture
def fastapi_test_client():
    app = FastAPI()

    class SpecificBaseBearer(BaseBearer):
        async def process(self, credentials: str):
            if credentials == "err":
                raise ValueError
            return credentials

    @app.get("/")
    async def root_no_auto_error(d=Depends(SpecificBaseBearer(auto_error=False))):
        return {"ret": d}

    @app.get("/auto-error")
    async def root_auto_error(d=Depends(SpecificBaseBearer(auto_error=True))):
        return {}  # pragma: nocover

    client = TestClient(app)
    yield client


def test_get_password_hash():
    password_hash = PasswordHash.recommended()
    password = "securepassword123"
    hashed_password = get_password_hash(password)

    assert isinstance(hashed_password, str)
    assert password_hash.verify(password, hashed_password) is True


def test_verify_password():
    password = "mypassword"
    hashed_password = get_password_hash(password)

    assert verify_password(password, hashed_password) is True
    assert verify_password("wrongpassword", hashed_password) is False


def test_generate_password():
    p = generate_password(32)
    assert len(p) == 32


def test_generate_unique_index():
    p = generate_unique_index()
    assert len(p) > 0


def test_base_bearer_no_credentials_no_auto_error(fastapi_test_client):
    ret = fastapi_test_client.get("/")
    assert ret.status_code == 200
    assert ret.json() == {"ret": None}


def test_base_bearer_no_credentials_auto_error(fastapi_test_client):
    ret = fastapi_test_client.get("/auto-error")
    assert ret.status_code == 401


def test_base_bearer(fastapi_test_client):
    ret = fastapi_test_client.get(
        "/",
        headers={"Authorization": "Bearer mytoken"},
    )
    assert ret.json() == {"ret": "mytoken"}


def test_base_bearer_exc_no_auto_error(fastapi_test_client):
    ret = fastapi_test_client.get(
        "/",
        headers={"Authorization": "Bearer err"},
    )
    assert ret.status_code == 200
    assert ret.json() == {"ret": None}


def test_base_bearer_exc_auto_error(fastapi_test_client):
    ret = fastapi_test_client.get(
        "/auto-error",
        headers={"Authorization": "Bearer err"},
    )
    assert ret.status_code == 401
