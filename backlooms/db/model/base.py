"""
Base SQL Models Module

This module provides foundational SQLModel classes for database entities.
It includes reusable base models that define common fields and behaviors,
ensuring consistency and reducing duplication across the system's database schemas.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from sqlalchemy.orm import declared_attr
from sqlmodel import SQLModel


class BaseModelType(SQLModel):
    __cached_table_name__: str | None = None

    @declared_attr  # type: ignore
    def __tablename__(cls) -> str:  # type: ignore  # noqa
        if cls.__cached_table_name__ is None:  # pragma: nocover
            cls.__cached_table_name__ = cls.__name__.lower()  # pragma: nocover
            if hasattr(cls, "Extra"):  # pragma: nocover
                settings = getattr(cls, "Extra")  # pragma: nocover
                if hasattr(settings, "name"):  # pragma: nocover
                    cls.__cached_table_name__ = settings.name  # pragma: nocover

        return cls.__cached_table_name__  # type: ignore  # pragma: nocover
