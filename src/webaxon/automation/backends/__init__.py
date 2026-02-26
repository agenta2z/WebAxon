"""
Backend abstraction layer for WebDriver.

This module provides a unified interface for browser automation backends,
enabling support for both Selenium and Playwright.

Components:
- BackendAdapter: Abstract base class defining the backend interface
- Unified exception types for consistent error handling
- Shared type definitions
- Browser configuration dataclasses
"""

from webaxon.automation.backends.base import BackendAdapter
from webaxon.automation.backends.config import (
    BrowserConfig,
    ChromeBrowserConfig,
    EdgeBrowserConfig,
    FirefoxBrowserConfig,
    UndetectedChromeConfig,
)
from webaxon.automation.backends.exceptions import (
    ElementNotFoundError,
    ElementNotInteractableError,
    StaleElementError,
    UnsupportedOperationError,
    WebDriverError,
    WebDriverTimeoutError,
)
from webaxon.automation.backends.playwright import (
    PlaywrightBackend,
    PlaywrightDriverShim,
    PlaywrightElementShim,
)
from webaxon.automation.backends.selenium import SeleniumBackend
from webaxon.automation.backends.switch_to_adapter import SwitchToAdapter
from webaxon.automation.backends.types import ElementDimensionInfo

__all__ = [
    # Base class
    "BackendAdapter",
    # Browser configuration
    "BrowserConfig",
    "ChromeBrowserConfig",
    "UndetectedChromeConfig",
    "FirefoxBrowserConfig",
    "EdgeBrowserConfig",
    # Backend implementations
    "SeleniumBackend",
    "PlaywrightBackend",
    "PlaywrightDriverShim",
    "PlaywrightElementShim",
    # Exceptions
    "WebDriverError",
    "ElementNotFoundError",
    "StaleElementError",
    "WebDriverTimeoutError",
    "ElementNotInteractableError",
    "UnsupportedOperationError",
    # Types
    "ElementDimensionInfo",
    # Adapters
    "SwitchToAdapter",
]
