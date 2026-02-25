from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field

from backlooms.db.model import PKIDModel


class PasswordAuthProviderModel(PKIDModel, table=True):
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=func.now()),
        default=None,
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=func.now()),
        default=None,
    )
    user_id: UUID = Field(foreign_key="users.id", index=True, unique=True)
    password: str = Field(
        max_length=128,
        nullable=True,
    )

    class Extra:
        name = "auth-provider-passwords"


__all__ = ["PasswordAuthProviderModel"]
