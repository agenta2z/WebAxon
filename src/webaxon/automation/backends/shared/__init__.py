"""
Shared utilities for WebDriver backends.

This module contains utilities that are shared between Selenium and Playwright
backends, such as text sanitization and click element types.
"""

from webaxon.automation.backends.shared.click_types import (
    ClickImplementation,
    DEFAULT_CLICK_IMPLEMENTATION_ORDER,
    DEFAULT_NEW_TAB_STRATEGY_ORDER,
    NewTabClickResult,
    NewTabClickStrategy,
    NewTabFallbackMode,
    OpenInNewTabMode,
    STRATEGY_TO_RESULT,
)
from webaxon.automation.backends.shared.scroll_constants import (
    compute_scroll_delta,
    FIXED_DISTANCE_PIXELS,
    RELATIVE_DISTANCE_PERCENTAGES,
)
from webaxon.automation.backends.shared.text_sanitization import (
    contains_non_bmp,
    get_non_bmp_characters,
    handle_newlines,
    handle_non_bmp,
    handle_whitespace,
    is_bmp_character,
    NewlineHandling,
    NonBMPHandling,
    remove_control_characters,
    remove_non_bmp,
    replace_non_bmp,
    sanitize_input_text_for_webdriver,
    sanitize_input_text_for_webdriver_preserve_formatting,
    sanitize_input_text_for_webdriver_strict,
    transliterate_non_bmp,
    WhitespaceHandling,
)

__all__ = [
    # Text sanitization enums
    "NonBMPHandling",
    "NewlineHandling",
    "WhitespaceHandling",
    # BMP utilities
    "is_bmp_character",
    "contains_non_bmp",
    "get_non_bmp_characters",
    "remove_non_bmp",
    "replace_non_bmp",
    "transliterate_non_bmp",
    # Handlers
    "handle_non_bmp",
    "handle_newlines",
    "handle_whitespace",
    "remove_control_characters",
    # Main sanitization functions
    "sanitize_input_text_for_webdriver",
    "sanitize_input_text_for_webdriver_strict",
    "sanitize_input_text_for_webdriver_preserve_formatting",
    # Click element types
    "OpenInNewTabMode",
    "NewTabClickStrategy",
    "NewTabClickResult",
    "NewTabFallbackMode",
    "ClickImplementation",
    "DEFAULT_NEW_TAB_STRATEGY_ORDER",
    "DEFAULT_CLICK_IMPLEMENTATION_ORDER",
    "STRATEGY_TO_RESULT",
    # Scroll constants
    "RELATIVE_DISTANCE_PERCENTAGES",
    "FIXED_DISTANCE_PIXELS",
    "compute_scroll_delta",
]
