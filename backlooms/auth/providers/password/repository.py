from uuid import UUID

from backlooms.db.repository import BaseRepository
from backlooms.errors import NotFoundError

from .model import PasswordAuthProviderModel


class PasswordProviderRepository(BaseRepository[PasswordAuthProviderModel]):

    async def set_password(
        self, user_id: UUID, password: str
    ) -> PasswordAuthProviderModel:
        return await self.create(
            PasswordAuthProviderModel(user_id=user_id, password=password)
        )

    async def get_by_user_id(self, user_id: UUID) -> PasswordAuthProviderModel:
        ret = await self.read_by_where(
            PasswordAuthProviderModel.user_id == user_id, first=True
        )
        if ret is None:
            raise NotFoundError(f"Password for user {user_id} is not found")

        return ret


__all__ = ["PasswordProviderRepository"]
