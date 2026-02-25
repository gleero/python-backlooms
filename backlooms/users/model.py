from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, func
from sqlalchemy.sql.sqltypes import JSON
from sqlmodel import Field

from backlooms.db.model import PKUUIDModel
from backlooms.shared import SafeJson


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class PureUserModel(PKUUIDModel, table=False):
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=func.now()),
        default=None,
    )
    last_authorized_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), default=None, nullable=True),
        default=None,
    )
    login: str = Field(
        unique=True,
        index=True,
        max_length=128,
    )
    info: SafeJson = Field(
        sa_column=Column(JSON),
        default={},
    )
    auth_providers: list[str] = Field(
        sa_column=Column(JSON),
        default=["password"],
    )
    status: UserStatus = Field(
        default=UserStatus.ACTIVE,
    )


__all__ = ["PureUserModel", "UserStatus"]
