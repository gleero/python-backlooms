from backlooms.auth.provider import AuthProvider


class FakeProvider(AuthProvider):
    NAME = "fake"


async def test_provider_init():
    provider = FakeProvider()
    assert provider.NAME == "fake"
    assert provider._auth_service is None
    assert provider._user_service is None


async def test_provider_bind(auth_service, user_service):
    provider = FakeProvider()
    provider.bind(auth_service, user_service)
    assert provider._auth_service == auth_service
    assert provider._user_service == user_service
