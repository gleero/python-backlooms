"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from uuid import UUID, uuid4

from sqlmodel import Field

from .base import BaseModelType


class PKIDModel(BaseModelType, table=False):
    id: int = Field(primary_key=True, unique=True, default=None)


class PKUUIDModel(BaseModelType, table=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
