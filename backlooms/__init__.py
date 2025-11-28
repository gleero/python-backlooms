"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

from .action import CLIAction
from .application import Application
from .config import BaseConfig
from .di import DIContainer


__version__ = "0.0.1"


__all__ = [
    "Application",
    "BaseConfig",
    "CLIAction",
    "DIContainer",
]
