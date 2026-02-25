from contextlib import asynccontextmanager
from enum import Enum
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI

from backlooms import use_dependency
from backlooms.errors import NoContentError

from .dependencies import get_current_user_id
from .identity_manager import IdentityManager


base_router = APIRouter()


@base_router.post("/sign-out")
async def sign_out_request(user_id: UUID = Depends(get_current_user_id)):
    manager = use_dependency("identity_manager", IdentityManager)

    await manager.logout(user_id)
    raise NoContentError()


class AuthRouter(APIRouter):
    def __init__(
        self,
        *,
        prefix: str = "auth",
        tags: Optional[list[Union[str, Enum]]] = None,
        **kwargs,
    ):
        if tags is None or "auth" not in tags:
            tags = ["auth"]

        super().__init__(prefix=prefix, tags=tags, lifespan=self._lifespan, **kwargs)
        self.include_router(base_router)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        manager = use_dependency("identity_manager", IdentityManager)
        for router in manager.routers():
            app.mount(self.prefix, router)

        yield


__all__ = ["AuthRouter"]
