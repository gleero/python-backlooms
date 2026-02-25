"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import logging
from abc import ABCMeta, abstractmethod
from typing import Any

from fastapi import Request
from fastapi.security import HTTPBearer

from backlooms.errors import AuthError


logger = logging.getLogger()


class BaseBearer(HTTPBearer, metaclass=ABCMeta):
    async def __call__(self, request: Request):
        credentials = await super(BaseBearer, self).__call__(request)

        if credentials is None:
            return None

        try:
            return await self.process(credentials.credentials)
        except Exception as e:
            logger.exception(f"Authorize error: {e}")
            if self.auto_error:
                raise AuthError(detail="Invalid or expired token")
            return None

    @abstractmethod
    async def process(self, credentials: str) -> Any:  # pragma: no cover
        pass
