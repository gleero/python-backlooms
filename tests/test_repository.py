"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from datetime import datetime

import pytest
from sqlalchemy.dialects import postgresql
from sqlmodel import Field, SQLModel

from backlooms.db._utils import dict_to_sqlalchemy_filter_options


class DBModel(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    some_str: str = Field()
    some_int: int = Field()
    some_float: float = Field()
    some_bool: bool = Field()
    some_datetime: datetime = Field()


def test_query_builder_int():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_int": 42,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_int = " in query


def test_query_builder_float():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_float": 42.0,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_float = " in query


def test_query_builder_string():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_str": "hello",
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_str LIKE " in query


def test_query_builder_bool():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_bool": True,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_bool IS true" in query


def test_query_builder_datetime():
    with pytest.raises(TypeError):
        dict_to_sqlalchemy_filter_options(
            DBModel,
            {
                "some_datetime": datetime.now(),
            },
        )


def test_query_builder_empty():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {},
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert query == "true"


def test_query_builder_custom_in():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_str__in": "hello,world",
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_str IN " in query


def test_query_builder_custom_eq():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_int__eq": 42,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_int = " in query


def test_query_builder_custom_ne():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_int__ne": 42,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_int != " in query


def test_query_builder_custom_lt():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_int__lt": 42,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_int < " in query


def test_query_builder_custom_lte():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_int__lte": 42,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_int <= " in query


def test_query_builder_custom_gt():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_int__gt": 42,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_int > " in query


def test_query_builder_custom_gte():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_int__gte": 42,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_int >= " in query


def test_query_builder_custom_isnull():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_int__isnull": 1,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_int IS NULL" in query


def test_query_builder_custom_isnull_not():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_int__isnull": 0,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert "dbmodel.some_int IS NOT NULL" in query


def test_query_builder_custom_other():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_other_attr": 0,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert query == "true"


def test_query_builder_custom_valid_unknown():
    x = dict_to_sqlalchemy_filter_options(
        DBModel,
        {
            "some_shit__isnull": 0,
        },
    )
    query = str(x.compile(dialect=postgresql.dialect()))
    assert query == "true"
