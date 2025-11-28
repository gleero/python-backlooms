"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from sqlmodel import Field

from .base import BaseModelType


class PKIDModel(BaseModelType):
    id: int = Field(primary_key=True, unique=True, default=None)
