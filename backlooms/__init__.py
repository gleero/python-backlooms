"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from .action import CLIAction
from .application import Application
from .config import BaseConfig
from .di import DIContainer, inject, use_container, use_dependency


__version__ = "0.1.0"


__all__ = [
    "Application",
    "BaseConfig",
    "CLIAction",
    "DIContainer",
    "use_container",
    "use_dependency",
    "inject",
]
