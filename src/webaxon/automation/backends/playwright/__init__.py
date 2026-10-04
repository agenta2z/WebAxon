"""
Playwright backend implementation.

This module provides the PlaywrightBackend adapter that implements the BackendAdapter
interface using Playwright for browser automation.

It also exports commonly used types, enums, and functions from the Playwright modules.
"""

# Import action functions
from webaxon.automation.backends.playwright.actions import (
    center_element_in_view,
    click_element,
    input_text,
    scroll_element,
)

# Import common utility functions
from webaxon.automation.backends.playwright.common import (
    get_element_dimension_info,
    get_element_scrollability,
    is_element_stale,
    solve_scrollable_child,
)

# Import element selection functions
from webaxon.automation.backends.playwright.element_selection import (
    add_unique_index_to_elements,
    find_element_by_html,
    find_element_by_unique_index,
    find_element_by_xpath,
    find_elements_by_xpath,
    resolve_action_target,
)

# Import execution functions
from webaxon.automation.backends.playwright.execution import (
    execute_actions,
    execute_composite_action,
    execute_single_action,
)
from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
from webaxon.automation.backends.playwright.shims import (
    PLAYWRIGHT_AVAILABLE,
    PlaywrightDriverShim,
    PlaywrightElementShim,
)

__all__ = [
    # Main backend class
    "PlaywrightBackend",
    # Availability flag
    "PLAYWRIGHT_AVAILABLE",
    # Shims
    "PlaywrightDriverShim",
    "PlaywrightElementShim",
    # Actions
    "click_element",
    "input_text",
    "scroll_element",
    "center_element_in_view",
    # Element selection
    "find_element_by_xpath",
    "find_elements_by_xpath",
    "resolve_action_target",
    "add_unique_index_to_elements",
    "find_element_by_unique_index",
    "find_element_by_html",
    # Common utilities
    "get_element_dimension_info",
    "get_element_scrollability",
    "is_element_stale",
    "solve_scrollable_child",
    # Execution
    "execute_single_action",
    "execute_composite_action",
    "execute_actions",
]
