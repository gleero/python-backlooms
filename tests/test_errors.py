"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import pytest
from fastapi import HTTPException, status

from backlooms.errors import (
    AuthError,
    BadRequestError,
    DuplicatedError,
    NoContentError,
    NotAllowedError,
    NotFoundError,
    ServiceError,
    ServiceUnavailableError,
    ValidationError,
)


@pytest.mark.parametrize(
    "exception_class, expected_status",
    [
        (BadRequestError, status.HTTP_400_BAD_REQUEST),
        (AuthError, status.HTTP_401_UNAUTHORIZED),
        (ServiceError, status.HTTP_500_INTERNAL_SERVER_ERROR),
        (NotFoundError, status.HTTP_404_NOT_FOUND),
        (ValidationError, status.HTTP_422_UNPROCESSABLE_CONTENT),
        (NotAllowedError, status.HTTP_400_BAD_REQUEST),
        (DuplicatedError, status.HTTP_400_BAD_REQUEST),
        (NoContentError, status.HTTP_204_NO_CONTENT),
        (ServiceUnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
def test_http_exception_classes(exception_class, expected_status):
    detail = "Test detail"
    headers = {"X-Test-Header": "value"}

    exception_instance = exception_class(detail=detail, headers=headers)

    assert isinstance(exception_instance, HTTPException)
    assert exception_instance.status_code == expected_status
    assert exception_instance.detail == detail
    assert exception_instance.headers == headers
