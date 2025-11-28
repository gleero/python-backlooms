"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from typing import Any

from fastapi import HTTPException, status


class BadRequestError(HTTPException):
    def __init__(
        self, detail: Any = None, headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, detail, headers)


class AuthError(HTTPException):
    def __init__(
        self, detail: Any = None, headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail, headers)


class ServiceError(HTTPException):
    def __init__(
        self, detail: Any = None, headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, detail, headers)


class ServiceUnavailableError(HTTPException):
    def __init__(
        self, detail: Any = None, headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, detail, headers)


class NotFoundError(HTTPException):
    def __init__(
        self, detail: Any = None, headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, detail, headers)


class NoContentError(HTTPException):
    def __init__(
        self, detail: Any = None, headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status.HTTP_204_NO_CONTENT, detail, headers)


class ValidationError(HTTPException):
    def __init__(
        self, detail: Any = None, headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, headers)


class NotAllowedError(HTTPException):
    def __init__(
        self, detail: Any = None, headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, detail, headers)


class DuplicatedError(HTTPException):
    def __init__(
        self, detail: Any = None, headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, detail, headers)
