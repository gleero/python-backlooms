from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

from backlooms.errors import DuplicatedError, NotFoundError

from .model import PureUserModel
from .repository import PureUserRepository


_MODEL = TypeVar("_MODEL", bound=PureUserModel, default=PureUserModel)


class PureUserService(Generic[_MODEL]):
    _user_repository: PureUserRepository[_MODEL]

    def __init__(self, user_repository: PureUserRepository[_MODEL]):
        self._user_repository = user_repository

    async def create_user(
        self,
        login: str,
        *,
        auth_providers: list[str],
        info: BaseModel | None = None,
    ) -> _MODEL:
        user_info = {}
        if info is not None:
            user_info = info.model_dump(mode="json")

        try:
            user = await self._user_repository.create(
                self._user_repository.model(
                    login=login,
                    info=user_info,
                    auth_providers=auth_providers,
                )
            )
            return user

        except DuplicatedError:
            raise DuplicatedError("User already exists")

    async def find_user_by_login(self, login: str) -> _MODEL:
        result = await self._user_repository.read_by_where(
            self._user_repository.model.login == login, first=True
        )
        if result is None:
            raise NotFoundError(detail=f"User '{login}' is not found")

        return result

    async def get_user_by_id(self, user_id: UUID) -> _MODEL:
        try:
            return await self._user_repository.read_by_id(user_id)
        except NotFoundError:
            raise NotFoundError(detail=f"User '{user_id}' is not found")
