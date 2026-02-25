from typing import TYPE_CHECKING, Generator
from uuid import UUID


if TYPE_CHECKING:
    from fastapi import APIRouter

from backlooms.config import BaseConfig, use_config
from backlooms.di import use_dependency
from backlooms.errors import AuthError
from backlooms.users import PureUserService

from .access_token import decode_jwt
from .provider import AuthProvider
from .schema import JWTUserPayload
from .service import AuthService


class IdentityManager:
    _auth_service: AuthService
    _user_service: PureUserService
    _auth_providers: dict[str, AuthProvider]

    def __init__(
        self,
        auth_service: AuthService,
        user_service: PureUserService,
        providers: list[AuthProvider] | None = None,
    ):
        self._auth_service = auth_service
        self._user_service = user_service
        self._auth_providers = {}

        if providers is not None:
            for provider in providers:
                self._auth_providers[provider.NAME] = provider

        for provider in self._auth_providers.values():
            provider.bind(auth_service, user_service)

    def __getitem__(self, item: str) -> AuthProvider:
        if item not in self._auth_providers:
            raise KeyError(f"Provider {item} is not registered")
        return self._auth_providers[item]

    def routers(self) -> Generator["APIRouter"]:
        for provider in self._auth_providers.values():
            router = provider.router
            if router is not None:
                yield router

    def add_provider(self, provider: AuthProvider):
        if provider.NAME in self._auth_providers:
            raise ValueError(f"Provider {provider.NAME} is already registered")

        provider.bind(self._auth_service, self._user_service)
        self._auth_providers[provider.NAME] = provider

    async def logout(self, user_id: UUID):
        await self._auth_service.drop_user_sessions(user_id)

    async def validate_jwt_credentials(self, credentials: str) -> JWTUserPayload:
        config = use_config(BaseConfig)
        payload = decode_jwt(credentials, secret_key=config.SECRET_KEY)

        # Invalid or broken payload
        if (
            payload is None
            or not isinstance(payload, JWTUserPayload)
            or not isinstance(payload.i, UUID)
        ):
            raise AuthError(detail="Invalid or expired session")

        is_allowed = await self._auth_service.is_user_id_allowed(payload.i, payload.n)
        if not is_allowed:
            raise AuthError(detail="Session is blocked or not exists")

        return payload


class AuthProviderDepends:
    def __init__(self, provider: str):
        self.provider = provider

    def __call__(self):
        manager = use_dependency("identity_manager", IdentityManager)
        try:
            return manager[self.provider]
        except KeyError:
            raise ValueError(f"Provider {self.provider} is not registered") from None
