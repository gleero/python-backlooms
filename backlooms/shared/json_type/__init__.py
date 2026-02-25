"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from typing import List, Mapping, TypeAlias, Union


JsonType = Union[
    str, int, float, bool, None, Mapping[str, "JsonType"], List["JsonType"]
]


SafeJson: TypeAlias = int | float | str | bool | None | list | dict


__all__ = ["JsonType", "SafeJson"]
