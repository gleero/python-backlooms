import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backlooms.auth import PasswordProvider
from backlooms.auth.providers.password import PasswordProviderRepository
from backlooms.auth.router import AuthRouter


@pytest.fixture
def password_repository(db_container):
    yield PasswordProviderRepository(session_factory=db_container.db().session)


@pytest.fixture
def password_identity_manager(identity_manager, password_repository):
    identity_manager.add_provider(PasswordProvider(password_repository))
    yield identity_manager


@pytest.fixture
def fastapi(password_identity_manager):
    yield FastAPI()


async def test_no_router(fastapi):
    with TestClient(fastapi) as client:
        ret = client.post("/auth/sign-out")
        assert ret.status_code == 404


async def test_sign_out_not_authenticated(fastapi):
    fastapi.include_router(AuthRouter(prefix="/auth"))
    with TestClient(fastapi) as client:
        ret = client.post("/auth/sign-out")
        assert ret.status_code == 401
