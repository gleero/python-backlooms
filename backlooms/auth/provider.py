from abc import ABCMeta
from typing import TYPE_CHECKING, Optional

from backlooms.users.service import PureUserService

from .service import AuthService


if TYPE_CHECKING:
    from fastapi import APIRouter


class AuthProvider(metaclass=ABCMeta):
    NAME: str

    _auth_service: AuthService | None
    _user_service: PureUserService | None

    @property
    def router(self) -> Optional["APIRouter"]:
        return None

    def __init__(self):
        self._auth_service = None
        self._user_service = None

    def bind(self, auth_service: AuthService, user_service: PureUserService):
        self._auth_service = auth_service
        self._user_service = user_service
