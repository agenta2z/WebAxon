"""
Shared type definitions for WebDriver backends.

These types are used by both Selenium and Playwright backends
to ensure consistent data structures across implementations.
"""

from typing import Dict, List, Mapping, Optional, Sequence, Union
from attr import attrs, attrib


@attrs(slots=True)
class ElementDimensionInfo:
    """
    Comprehensive dimension information about an element.

    This class provides detailed size and scrollability information
    for an element, used by both Selenium and Playwright backends.

    Attributes:
        width: Element's offset width in pixels
        height: Element's offset height in pixels
        client_width: Element's client width (excludes scrollbar)
        client_height: Element's client height (excludes scrollbar)
        scroll_width: Total scrollable width including overflow
        scroll_height: Total scrollable height including overflow
        is_scrollable_x: Whether the element can scroll horizontally
        is_scrollable_y: Whether the element can scroll vertically
        overflow_x: CSS overflow-x value (e.g., 'auto', 'scroll', 'hidden')
        overflow_y: CSS overflow-y value (e.g., 'auto', 'scroll', 'hidden')
    """
    width: int = attrib()
    height: int = attrib()
    client_width: int = attrib()
    client_height: int = attrib()
    scroll_width: int = attrib()
    scroll_height: int = attrib()
    is_scrollable_x: bool = attrib()
    is_scrollable_y: bool = attrib()
    overflow_x: str = attrib()
    overflow_y: str = attrib()


# Type aliases for element dictionaries and conditions
# These match the existing types in selenium/types.py
ElementDict = Dict[str, Union[str, Sequence]]
ElementCondition = Mapping[str, Union[str, Sequence[str]]]
ElementConditions = Union[ElementCondition, Sequence[ElementCondition]]


# Scrollable child resolution strategies
SCROLLABLE_CHILD_STRATEGIES = (
    'first_scrollable',           # First scrollable descendant (DFS)
    'first_largest_scrollable',   # First scrollable with largest scroll area
    'deepest_scrollable',         # Deepest scrollable in DOM tree
    'largest_scrollable',         # Scrollable with largest scroll area overall
)
