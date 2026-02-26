"""
Selenium backend implementation.

This module provides the SeleniumBackend adapter that implements the BackendAdapter
interface using Selenium WebDriver for browser automation.

It also exports commonly used types, enums, and functions from the Selenium modules.
"""

from .selenium_backend import SeleniumBackend
from .types import ElementDict, ElementCondition, ElementConditions
from .driver_factory import WebAutomationDrivers, get_driver, DEFAULT_USER_AGENT_STRING
from .actions import SearchProviders, search
from .common import is_element_stale
from .element_selection import add_unique_index_to_elements

__all__ = [
    "SeleniumBackend",
    "ElementDict",
    "ElementCondition",
    "ElementConditions",
    "WebAutomationDrivers",
    "get_driver",
    "DEFAULT_USER_AGENT_STRING",
    "SearchProviders",
    "search",
    "is_element_stale",
    "add_unique_index_to_elements",
]
