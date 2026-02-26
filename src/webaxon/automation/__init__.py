"""
WebAgent Automation Module

Provides browser automation capabilities including:
- WebDriver wrapper with monitor tab tracking
- Monitor support for element monitoring on current tab
- Selenium-based action implementations
"""

from .web_driver import WebDriver
from .monitor import (
    MonitorCondition,
    MonitorConditionType,
    create_monitor,
)

__all__ = [
    "WebDriver",
    "MonitorCondition",
    "MonitorConditionType",
    "create_monitor",
]
