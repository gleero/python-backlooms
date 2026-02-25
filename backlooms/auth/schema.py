from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class JWTUserPayload(BaseModel):
    i: int | UUID  # User ID
    t: Literal["u", "t"] = "u"  # Token type (user or token)
    n: str | None = None  # Token nonce
    exp: int | None = None  # Expiration timestamp


class UserSessionResponse(BaseModel):
    access_token: str
    expiration: datetime | None = None


class LoginUserRequest(BaseModel):
    login: str


class LoginMethod(BaseModel):
    method: str


class LoginUserResponse(BaseModel):
    login: str
    methods: list[LoginMethod]
