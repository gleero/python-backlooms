from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

from backlooms.config import BaseConfig, use_config
from backlooms.errors import DuplicatedError, NotFoundError
from backlooms.security import generate_unique_index
from backlooms.users.model import PureUserModel
from backlooms.users.repository import PureUserRepository

from .access_token import create_access_token
from .model import PureSessionModel
from .repository import PureSessionRepository
from .schema import JWTUserPayload, UserSessionResponse
from .token_cache import TokenCache


_USER_MODEL = TypeVar("_USER_MODEL", bound=PureUserModel)
_SESSION_MODEL = TypeVar("_SESSION_MODEL", bound=PureSessionModel)


class AuthService(Generic[_USER_MODEL, _SESSION_MODEL]):
    _user_repository: PureUserRepository[_USER_MODEL]
    _session_repository: PureSessionRepository[_SESSION_MODEL]

    _cache: TokenCache

    def __init__(
        self,
        user_repository: PureUserRepository[_USER_MODEL],
        session_repository: PureSessionRepository[_SESSION_MODEL],
        cache: TokenCache,
    ):
        self._user_repository = user_repository
        self._session_repository = session_repository
        self._cache = cache

    async def issue_session(
        self,
        user_id: UUID,
        *,
        session_expire_minutes: int | None = None,
        session_info: BaseModel | None = None,
    ) -> UserSessionResponse:
        token_lifespan = None
        config = use_config(BaseConfig)

        # Generate random nonce
        nonce = generate_unique_index()

        # Create session
        session_info_raw = {}
        if session_info:
            session_info_raw = session_info.model_dump(mode="json")

        try:
            session = await self._session_repository.create(
                self._session_repository.model(
                    user_id=user_id,
                    info=session_info_raw,
                    nonce=nonce,
                )
            )
        except DuplicatedError:  # Integrity: FOREIGN KEY constraint failed
            raise NotFoundError(f"User '{user_id}' not found")

        # Build JWT payload
        payload = JWTUserPayload(t="u", i=user_id, n=nonce)

        # Try to read config value if session expire is not provided
        if session_expire_minutes is None:
            session_expire_minutes = config.AUTH_TOKEN_EXPIRE_MINUTES

        if session_expire_minutes is not None:
            token_lifespan = timedelta(minutes=session_expire_minutes)

        access_token, expiration_datetime = create_access_token(
            payload,
            secret_key=config.SECRET_KEY,
            expires_delta=token_lifespan,
            algorithm=config.TOKEN_ALGORITHM,
        )

        await self._cache.update(user_id, nonce=nonce, model=session)

        # Update user's last authentication timestamp
        await self._user_repository.update_by_id(
            user_id, last_authorized_at=datetime.now(tz=UTC)
        )

        return UserSessionResponse(
            access_token=access_token,
            expiration=expiration_datetime,
        )

    async def drop_session(self, user_id: UUID, nonce: str | None):
        session = await self._session_repository.find_session(user_id, nonce)
        if not session:
            raise NotFoundError("Session not found")

        await self._session_repository.delete_by_id(session.id)
        await self._cache.update(user_id, nonce=nonce, model=None)

    async def drop_user_sessions(self, user_id: UUID):
        sessions = await self._session_repository.find_user_sessions(user_id)
        for session in sessions:
            await self._session_repository.delete_by_id(session.id)
            await self._cache.update(user_id, nonce=session.nonce, model=None)

    async def is_user_id_allowed(self, user_id: UUID, nonce: str | None = None) -> bool:
        return await self._cache.is_record_id_allowed(user_id, nonce=nonce)
