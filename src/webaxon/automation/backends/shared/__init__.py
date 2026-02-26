"""
Shared utilities for WebDriver backends.

This module contains utilities that are shared between Selenium and Playwright
backends, such as text sanitization and click element types.
"""

from webaxon.automation.backends.shared.text_sanitization import (
    NonBMPHandling,
    NewlineHandling,
    WhitespaceHandling,
    is_bmp_character,
    contains_non_bmp,
    get_non_bmp_characters,
    remove_non_bmp,
    replace_non_bmp,
    transliterate_non_bmp,
    handle_non_bmp,
    handle_newlines,
    handle_whitespace,
    remove_control_characters,
    sanitize_input_text_for_webdriver,
    sanitize_input_text_for_webdriver_strict,
    sanitize_input_text_for_webdriver_preserve_formatting,
)

from webaxon.automation.backends.shared.click_types import (
    OpenInNewTabMode,
    NewTabClickStrategy,
    NewTabClickResult,
    NewTabFallbackMode,
    ClickImplementation,
    DEFAULT_NEW_TAB_STRATEGY_ORDER,
    DEFAULT_CLICK_IMPLEMENTATION_ORDER,
    STRATEGY_TO_RESULT,
)

from webaxon.automation.backends.shared.scroll_constants import (
    RELATIVE_DISTANCE_PERCENTAGES,
    FIXED_DISTANCE_PIXELS,
    compute_scroll_delta,
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
