from typing import Optional, TypeVar

from fastapi_filter.contrib.sqlalchemy import Filter

from backlooms.db.repository import BaseIDRepository

from .model import PureUserModel


_T = TypeVar("_T", bound=PureUserModel)
_F = TypeVar("_F", bound=Optional[Filter], default=None)


class PureUserRepository(BaseIDRepository[_T, _F]):
    pass


__all__ = ["PureUserRepository"]
