"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from datetime import datetime
from typing import Any, Type

from sqlalchemy import ColumnElement, Integer, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped
from sqlmodel import SQLModel, and_, cast


SQLALCHEMY_QUERY_MAPPER = {
    "eq": "__eq__",
    "ne": "__ne__",
    "lt": "__lt__",
    "lte": "__le__",
    "gt": "__gt__",
    "gte": "__ge__",
}


def dict_to_sqlalchemy_filter_options(
    model_class: Type[SQLModel],
    search_option_dict: dict[str, Any],
) -> ColumnElement[bool]:
    sql_alchemy_filter_options = []
    copied_dict = search_option_dict.copy()

    for key in search_option_dict:
        attr = getattr(model_class, key, None)
        if attr is None:
            continue
        option_from_dict = copied_dict.pop(key)
        if type(option_from_dict) in [int, float]:
            sql_alchemy_filter_options.append(attr == option_from_dict)
        elif type(option_from_dict) in [str]:
            sql_alchemy_filter_options.append(attr.like("%" + option_from_dict + "%"))
        elif type(option_from_dict) in [bool]:
            sql_alchemy_filter_options.append(attr.is_(option_from_dict))
        else:
            raise TypeError("Use simple types like string, int, float or bool")

    # Check for custom commands
    for custom_option in copied_dict:
        if "__" not in custom_option:
            continue

        key, command = custom_option.split("__")
        attr = getattr(model_class, key, None)
        if attr is None:
            continue

        option_from_dict = copied_dict[custom_option]
        if command == "in":
            sql_alchemy_filter_options.append(
                attr.in_([option.strip() for option in option_from_dict.split(",")])
            )

        elif command in SQLALCHEMY_QUERY_MAPPER.keys():
            sql_alchemy_filter_options.append(
                getattr(attr, SQLALCHEMY_QUERY_MAPPER[command])(option_from_dict)
            )

        elif command == "isnull":
            bool_command = "__eq__" if option_from_dict else "__ne__"
            sql_alchemy_filter_options.append(getattr(attr, bool_command)(None))

    return and_(True, *sql_alchemy_filter_options)


def aggregated_timestamp_field(
    session: AsyncSession, col: Mapped[datetime], interval_seconds: int
):
    dialect_name = session.bind.dialect.name

    if dialect_name == "sqlite":
        # In SQLite, there is no to_timestamp function, so we use strftime and datetime.
        # func.strftime('%s', event_time) returns a string representing epoch seconds,
        # so we cast it to Integer.
        epoch_value = cast(
            func.strftime("%s", col),
            Integer,
        )
        grouped_epoch = cast(epoch_value / interval_seconds, Integer) * interval_seconds
        aggregated_timestamp = func.datetime(
            grouped_epoch,
            "unixepoch",
        ).label("timestamp")

    else:
        # For PostgreSQL, use the standard combination of extract, floor, and to_timestamp.
        aggregated_timestamp = func.to_timestamp(
            func.floor(func.extract("epoch", col) / interval_seconds) * interval_seconds
        ).label("timestamp")

    return aggregated_timestamp
