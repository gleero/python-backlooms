from fastapi import APIRouter, Depends

from backlooms.auth import AuthProviderDepends
from backlooms.auth.providers.password import PasswordProvider

from .schema import (
    PasswordLoginUserRequest,
    PasswordLoginUserResponse,
    PasswordRegisterUserRequest,
    PasswordRegisterUserResponse,
)


router = APIRouter(tags=["auth", "password"])


@router.post("/password/sign-up", response_model=PasswordRegisterUserResponse)
async def password_sign_up(
    request: PasswordRegisterUserRequest,
    provider: PasswordProvider = Depends(AuthProviderDepends("password")),
):
    return await provider.register_user(request)


@router.post("/password/sign-in", response_model=PasswordLoginUserResponse)
async def password_sign_in(
    request: PasswordLoginUserRequest,
    provider: PasswordProvider = Depends(AuthProviderDepends("password")),
):
    return await provider.authenticate_user(request)


__all__ = ["router"]
