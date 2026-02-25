from uuid import UUID

from fastapi import Depends

from backlooms.di import use_dependency
from backlooms.security.bearer_token import BaseBearer

from .identity_manager import IdentityManager
from .schema import JWTUserPayload


class JWTUserBearer(BaseBearer):
    """
    Implements JWT-based authentication by validating tokens and ensuring the user is active.
    """

    async def process(
        self,
        credentials: str,
    ) -> JWTUserPayload:
        manager = use_dependency("identity_manager", IdentityManager)
        return await manager.validate_jwt_credentials(credentials)


async def get_current_user_id(
    payload: JWTUserPayload = Depends(JWTUserBearer()),
) -> UUID:
    """
    Dependency to extract the current user's ID from a validated JWT token.
    :param payload: Decoded JWT payload
    :return: User ID
    """
    assert isinstance(payload.i, UUID)
    return payload.i
