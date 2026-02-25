"""
Base Repository Module

This module provides the foundational repository pattern implementation for database operations.
It includes methods for common CRUD operations such as insertion, deletion, updates, and queries.
All other repositories in the system inherit from this base class, ensuring consistent and reusable
database interaction logic.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from functools import cache
from typing import (
    AsyncContextManager,
    Callable,
    Generic,
    Optional,
    Sequence,
    Type,
    TypeVar,
    get_args,
    get_origin,
    overload,
)
from uuid import UUID

from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import BaseModel
from sqlalchemy import ColumnExpressionArgument
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlmodel import SQLModel, col, insert, select, update

from backlooms.db.model import PKIDModel, PKUUIDModel
from backlooms.errors import DuplicatedError, NotFoundError

from ._utils import dict_to_sqlalchemy_filter_options


_B = TypeVar("_B", bound=SQLModel)
_T = TypeVar("_T", bound=PKIDModel | PKUUIDModel)
_F = TypeVar("_F", bound=Optional[Filter], default=None)


type RecordID = int | UUID


@cache
def is_subclass_of_base_repository(cls: type) -> bool:
    if f"{cls.__module__}.{cls.__name__}" == "backlooms.db.repository.BaseRepository":
        return True

    for sub in cls.__bases__:
        if (
            f"{sub.__module__}.{sub.__name__}"
            == "backlooms.db.repository.BaseRepository"
        ):
            return True
        return is_subclass_of_base_repository(sub)
    return False


class RepoMeta(type):
    def __new__(mcls, name, bases, ns, **kwargs):
        cls = super().__new__(mcls, name, bases, ns, **kwargs)
        result = RepoMeta._resolve_model_type(cls)
        setattr(cls, "model", result)
        return cls

    @staticmethod
    def _resolve_model_type(source_cls: type) -> Type | None:
        orig_bases = getattr(source_cls, "__orig_bases__", ())

        for base in orig_bases:
            origin = get_origin(base)
            if origin is None:
                continue

            args = get_args(base)
            if not args:
                continue

            if isinstance(origin, type) and is_subclass_of_base_repository(origin):
                t_arg = args[0]
                from typing import TypeVar as _TypeVar

                if isinstance(t_arg, _TypeVar):
                    continue

                if not issubclass(t_arg, SQLModel):
                    continue

                return t_arg

        return None


class BaseRepository(Generic[_B, _F], metaclass=RepoMeta):
    model: Type[_B]

    def __init__(
        self,
        session_factory: Callable[..., AsyncContextManager[AsyncSession]],
    ) -> None:
        self.session_factory = session_factory
        if self.model is None:
            raise ValueError("Model is not set")

    async def create(self, model: _B) -> _B:
        """
        Create a new instance of the model
        """
        async with self.session_factory() as session:
            try:
                session.add(model)
                await session.commit()
                await session.refresh(model)
            except IntegrityError as e:
                raise DuplicatedError(detail=str(e.orig))
            return model

    async def read_all(self, with_relationships: bool = False) -> Sequence[_B]:
        """
        Return all elements from the model
        :return: list of elements
        """
        async with self.session_factory() as session:
            query = select(self.model)

            # Add relationships if needed
            if with_relationships:
                for relationship in getattr(self.model, "__mapper__").relationships:
                    query = query.options(joinedload(relationship))

            result = await session.execute(query)
            return result.scalars().all()

    async def read_by_filter(
        self, f: _F, with_relationships: bool = False
    ) -> Sequence[_B]:
        """
        Return filtered elements
        :param f: Filter instance
        :param with_relationships: Add relationships
        :return: list of elements
        """
        if f is None:
            raise NotImplementedError()

        async with self.session_factory() as session:
            query = f.filter(select(self.model))

            # Add relationships if needed
            if with_relationships:
                for relationship in getattr(self.model, "__mapper__").relationships:
                    query = query.options(joinedload(relationship))

            # Check for sorting
            try:
                query = f.sort(query)
            except AttributeError:
                pass

            result = await session.execute(query)
            return result.scalars().all()

    @overload
    async def read_by_where(
        self,
        expression: ColumnExpressionArgument | None | bool,
        first: bool,
        with_relationships: bool = False,
    ) -> _B | None: ...

    @overload
    async def read_by_where(
        self,
        expression: ColumnExpressionArgument | None | bool,
        first: None = None,
        with_relationships: bool = False,
    ) -> Sequence[_B]: ...

    async def read_by_where(
        self,
        expression: ColumnExpressionArgument | None | bool = None,
        first: bool | None = None,
        with_relationships: bool = False,
    ):
        """
        Return element by where expression
        :param expression: where value
        :param first: search first or all
        :param with_relationships: Load models with relationships
        :return: element or list of elements or None
        """
        async with self.session_factory() as session:
            query = select(self.model)

            # Add relationships if needed
            if with_relationships:
                for relationship in getattr(self.model, "__mapper__").relationships:
                    query = query.options(joinedload(relationship))

            if expression is not None:
                query = query.where(expression)
            if first:
                query = query.limit(1)

            result = await session.execute(query)
            if first:
                return result.scalars().first()
            return result.scalars().all()

    async def read_by_options(self, schema: BaseModel) -> Sequence[_B]:
        """
        Find elements by custom model schema
        :param schema: Pydantic model schema
        :return: list of elements
        """
        filter_options = None
        if schema is not None:
            schema_as_dict = schema.model_dump(exclude_none=True)
            filter_options = dict_to_sqlalchemy_filter_options(
                self.model, schema_as_dict
            )

        return await self.read_by_where(filter_options)

    async def insert_many(self, items: list):
        """
        Insert multiple records to database
        :param items: list of items to insert
        """
        async with self.session_factory() as session:
            await session.execute(insert(self.model), items)
            await session.commit()

    async def delete_by_options(self, schema: BaseModel):
        """
        Delete records by custom fields
        :param schema: information to delete
        """
        async with self.session_factory() as session:
            query = select(self.model)
            if schema is not None:
                schema_as_dict = schema.model_dump(exclude_none=True)
                filter_options = dict_to_sqlalchemy_filter_options(
                    self.model, schema_as_dict
                )
                query = query.where(filter_options)
            result = (await session.execute(query)).first()
            if not result:
                raise NotFoundError(detail=f"not found id : {id}")
            await session.delete(result[0])
            await session.commit()


class BaseIDRepository(BaseRepository[_T, _F], Generic[_T, _F]):
    model: Type[_T]

    async def read_by_id(
        self,
        record_id: RecordID,
        with_relationships: bool = False,
    ) -> _T:
        """
        Return element by ID
        :param record_id: item's ID
        :param with_relationships: Load models with relationships
        """
        item = await self.read_by_where(
            self.model.id == record_id,
            first=True,
            with_relationships=with_relationships,
        )
        if not item:
            raise NotFoundError(detail=f"Record not found: id={record_id}")
        return item

    async def update_by_id(
        self,
        record_id: RecordID,
        **kwargs,
    ) -> _T:
        """
        Update record by ID
        :param record_id: Record's identifier
        :return: Changed record
        """
        async with self.session_factory() as session:
            query = (
                update(self.model).where(col(self.model.id) == record_id).values(kwargs)
            )
            await session.execute(query)
            await session.commit()
            return await self.read_by_id(record_id)

    async def delete_by_id(self, record_id: RecordID):
        """
        Delete record by ID
        :param record_id: Record's identifier
        """
        async with self.session_factory() as session:
            query = select(self.model).where(col(self.model.id) == record_id)
            result = (await session.execute(query)).first()
            if not result:
                raise NotFoundError(detail=f"Record not found: id={record_id}")
            await session.delete(result[0])
            await session.commit()


__all__ = ["BaseRepository", "BaseIDRepository"]
