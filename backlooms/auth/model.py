from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, DateTime, func
from sqlalchemy.sql.sqltypes import JSON
from sqlmodel import Field

from backlooms.db.model import PKIDModel
from backlooms.shared import SafeJson


class PureSessionModel(PKIDModel, table=False):
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=func.now()),
        default=None,
    )
    is_active: bool = Field(default=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, unique=False)
    info: SafeJson = Field(
        sa_column=Column(JSON),
        default={},
    )
    nonce: str | None = Field(
        max_length=22,
        min_length=22,
        default=None,
        nullable=True,
    )


__all__ = ["PureSessionModel"]
