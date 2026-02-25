"""
User Token Cache Module

This module provides the `UserTokenCache` class, which manages a cache of active users and their associated
token initialization vectors (IVs). The cache optimizes performance by reducing database queries for
repeated user validation and token verification operations.

Classes:
    - UserTokenCache: A class for managing user-related caching, including user existence checks,
      token IV storage, and cache updates.

Dependencies:
    - UserRepository: Handles database operations for user-related data.
    - get_password_iv: Generates initialization vectors (IVs) for token validation.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from uuid import UUID

from .model import PureSessionModel
from .repository import PureSessionRepository


class TokenCache:
    _session_repository: PureSessionRepository[PureSessionModel]
    _cache: dict[str, bool]

    def __init__(self, session_repository: PureSessionRepository):
        self._session_repository = session_repository
        self._cache = {}

    def __contains__(self, to_search: tuple[UUID, str | None]) -> bool:
        record_id, nonce = to_search
        search_key = f"{record_id}-{nonce}" if nonce else f"{record_id}"
        return search_key in self._cache

    async def drop_cache(self):
        self._cache = {}

    async def update(
        self,
        record_id: UUID,
        *,
        nonce: str | None = None,
        model: PureSessionModel | None = None,
    ):
        search_key = f"{record_id}-{nonce}" if nonce else f"{record_id}"

        # Remove from the cache
        if model is None:
            if search_key in self._cache:
                del self._cache[search_key]
            return

        if nonce != model.nonce:
            raise RuntimeError(
                f"Nonce {model.nonce} does not match {record_id} ({nonce})"
            )

        is_active = model.is_active
        self._cache[search_key] = is_active

    async def is_record_id_allowed(
        self, record_id: UUID, *, nonce: str | None = None
    ) -> bool:
        search_key = f"{record_id}-{nonce}" if nonce else f"{record_id}"

        # Not in cache, try to fetch from database
        if search_key not in self._cache:
            model = await self._session_repository.find_session(record_id, nonce)
            if not model:
                self._cache[search_key] = False
                return False

            await self.update(record_id, nonce=nonce, model=model)

        try:
            return self._cache[search_key]
        except KeyError:
            return False
