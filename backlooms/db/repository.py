"""
Base Repository Module

This module provides the foundational repository pattern implementation for database operations.
It includes methods for common CRUD operations such as insertion, deletion, updates, and queries.
All other repositories in the system inherit from this base class, ensuring consistent and reusable
database interaction logic.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from typing import (
    AsyncContextManager,
    Callable,
    Generic,
    Optional,
    Sequence,
    Type,
    TypeVar,
    overload,
)

from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import BaseModel
from sqlalchemy import ColumnExpressionArgument
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlmodel import SQLModel, col, insert, select, update

from backlooms.db.model import PKIDModel
from backlooms.errors import DuplicatedError, NotFoundError

from ._utils import dict_to_sqlalchemy_filter_options


_T = TypeVar("_T", bound=PKIDModel | SQLModel)
_F = TypeVar("_F", bound=Optional[Filter])


class BaseRepository(Generic[_T, _F]):
    model: Type[_T]

    def __init__(
        self,
        session_factory: Callable[..., AsyncContextManager[AsyncSession]],
        model: Type[_T],
    ) -> None:
        self.session_factory = session_factory
        self.model = model

    async def create(self, model: _T) -> _T:
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

    async def read_all(self, with_relationships: bool = False) -> Sequence[_T]:
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
    ) -> Sequence[_T]:
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
    ) -> _T | None: ...

    @overload
    async def read_by_where(
        self,
        expression: ColumnExpressionArgument | None | bool,
        first: None = None,
        with_relationships: bool = False,
    ) -> Sequence[_T]: ...

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
            if first is True:
                return result.scalars().first()
            return result.scalars().all()

    async def read_by_id(
        self,
        record_id: int,
        with_relationships: bool = False,
    ) -> _T:
        """
        Return element by ID
        :param record_id: item's ID
        :param with_relationships: Load models with relationships
        """
        if not issubclass(self.model, PKIDModel):
            raise TypeError(f"{self.model.__name__} must be a subclass of PKIDModel")

        item = await self.read_by_where(
            self.model.id == record_id,
            first=True,
            with_relationships=with_relationships,
        )
        if not item:
            raise NotFoundError(detail=f"Record not found: id={record_id}")
        return item

    async def read_by_options(self, schema: BaseModel) -> Sequence[_T]:
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

    async def update(
        self,
        record_id: int,
        **kwargs,
    ) -> _T:
        """
        Update record by ID
        :param record_id: Record's identifier
        :return: Changed record
        """
        if not issubclass(self.model, PKIDModel):
            raise TypeError(f"{self.model.__name__} must be a subclass of PKIDModel")

        async with self.session_factory() as session:
            query = (
                update(self.model).where(col(self.model.id) == record_id).values(kwargs)
            )
            await session.execute(query)
            await session.commit()
            return await self.read_by_id(record_id)

    async def delete_by_id(self, record_id: int):
        """
        Delete record by ID
        :param record_id: Record's identifier
        """
        if not issubclass(self.model, PKIDModel):
            raise TypeError(f"{self.model.__name__} must be a subclass of PKIDModel")

        async with self.session_factory() as session:
            query = select(self.model).where(col(self.model.id) == record_id)
            result = (await session.execute(query)).first()
            if not result:
                raise NotFoundError(detail=f"Record not found: id={record_id}")
            await session.delete(result[0])
            await session.commit()

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


__all__ = ["BaseRepository"]
