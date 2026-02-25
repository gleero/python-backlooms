from typing import Optional, Sequence, TypeVar
from uuid import UUID

from fastapi_filter.contrib.sqlalchemy import Filter
from sqlmodel import and_, true

from backlooms.db.repository import BaseIDRepository

from .model import PureSessionModel


_T = TypeVar("_T", bound=PureSessionModel)
_F = TypeVar("_F", bound=Optional[Filter], default=None)


class PureSessionRepository(BaseIDRepository[_T, _F]):

    async def find_session(
        self, user_id: UUID, nonce: str | None
    ) -> PureSessionModel | None:
        return await self.read_by_where(
            and_(
                self.model.user_id == user_id,
                self.model.nonce == nonce,
                self.model.is_active == true(),
            ),
            first=True,
        )

    async def find_user_sessions(self, user_id: UUID) -> Sequence[PureSessionModel]:
        return await self.read_by_where(
            and_(
                self.model.user_id == user_id,
                self.model.is_active == true(),
            ),
        )


__all__ = ["PureSessionRepository"]
