from typing import Generic, TypeVar

from pydantic import BaseModel

from backlooms.auth.schema import UserSessionResponse


_REG = TypeVar("_REG", bound=BaseModel, default=BaseModel)


class PasswordRegisterUserRequest(BaseModel, Generic[_REG]):
    login: str
    password: str
    user_info: _REG | None = None


class PasswordRegisterUserResponse(BaseModel):
    login: str
    session: UserSessionResponse


class PasswordLoginUserRequest(BaseModel):
    login: str
    password: str


class PasswordLoginUserResponse(BaseModel):
    login: str
    session: UserSessionResponse
