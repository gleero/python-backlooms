from backlooms.auth.provider import AuthProvider
from backlooms.errors import AuthError, NotFoundError, ServiceError
from backlooms.security import get_password_hash
from backlooms.security.utils import verify_password

from .repository import PasswordProviderRepository
from .schema import (
    PasswordLoginUserRequest,
    PasswordLoginUserResponse,
    PasswordRegisterUserRequest,
    PasswordRegisterUserResponse,
)


class PasswordProvider(AuthProvider):
    NAME = "password"

    _password_repository: PasswordProviderRepository

    def __init__(self, password_repository: PasswordProviderRepository):
        super().__init__()
        self._password_repository = password_repository

    @property
    def router(self):
        from .fastapi_router import router

        return router

    async def register_user(
        self,
        request: PasswordRegisterUserRequest,
        *,
        session_expire_minutes: int | None = None,
    ) -> PasswordRegisterUserResponse:
        if self._user_service is None or self._auth_service is None:
            raise ServiceError("Services are not bound")

        # Create user and add it to the database
        user = await self._user_service.create_user(
            request.login,
            auth_providers=["password"],
        )

        # Set password to the user
        hashed_password = get_password_hash(request.password)
        await self._password_repository.set_password(user.id, hashed_password)

        # Create session
        session = await self._auth_service.issue_session(
            user.id,
            session_expire_minutes=session_expire_minutes,
        )
        return PasswordRegisterUserResponse(
            session=session,
            login=user.login,
        )

    async def authenticate_user(
        self,
        request: PasswordLoginUserRequest,
        *,
        session_expire_minutes: int | None = None,
    ):
        if self._user_service is None or self._auth_service is None:
            raise ServiceError("Services are not bound")

        try:
            user = await self._user_service.find_user_by_login(request.login)
        except NotFoundError:
            raise AuthError("Invalid credentials")

        # Validate providers
        if "password" not in user.auth_providers:
            raise AuthError("Password method is not allowed for this user")

        # Find and verify password
        try:
            password = await self._password_repository.get_by_user_id(user.id)
        except NotFoundError:
            raise AuthError("Password method unavailable")

        is_valid = verify_password(request.password, password.password)
        if not is_valid:
            raise AuthError("Invalid credentials")

        # Create session
        session = await self._auth_service.issue_session(
            user.id,
            session_expire_minutes=session_expire_minutes,
        )

        return PasswordLoginUserResponse(
            session=session,
            login=user.login,
        )
