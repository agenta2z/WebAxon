"""
Playwright common utilities.

This module contains utility functions for element inspection and manipulation
for the Playwright backend.
"""

import logging
import warnings
from typing import Any, Optional, Tuple, TYPE_CHECKING

from webaxon.automation.backends.types import ElementDimensionInfo
from .shims import PlaywrightElementShim

if TYPE_CHECKING:
    from .playwright_backend import PlaywrightBackend

_logger = logging.getLogger(__name__)


def get_body_html(backend: 'PlaywrightBackend', return_dynamic_contents: bool = True) -> str:
    """Get the body HTML of the current page.

    Args:
        backend: The PlaywrightBackend instance
        return_dynamic_contents: If True, return dynamically rendered content

    Returns:
        Body HTML string
    """
    if return_dynamic_contents:
        return backend._page.evaluate("document.body.outerHTML")
    return backend._page.content()


def get_body_text(backend: 'PlaywrightBackend') -> str:
    """Return the visible text content of the page body via document.body.innerText."""
    return backend._page.evaluate("document.body.innerText")


def get_element_dimension_info(backend: 'PlaywrightBackend', element: Any) -> ElementDimensionInfo:
    """Get comprehensive dimension information about an element.

    Args:
        backend: The PlaywrightBackend instance
        element: The element to inspect

    Returns:
        ElementDimensionInfo with dimension details
    """
    if isinstance(element, PlaywrightElementShim):
        locator = element.locator
    else:
        locator = element

    result = locator.evaluate("""
        element => {
            var computedStyle = window.getComputedStyle(element);
            var offsetWidth = element.offsetWidth;
            var offsetHeight = element.offsetHeight;
            var clientWidth = element.clientWidth;
            var clientHeight = element.clientHeight;
            var scrollWidth = element.scrollWidth;
            var scrollHeight = element.scrollHeight;
            var overflowX = computedStyle.overflowX;
            var overflowY = computedStyle.overflowY;

            var isScrollableX = (
                (overflowX === 'scroll' || overflowX === 'auto' || overflowX === 'hidden') &&
                scrollWidth > clientWidth
            );
            var isScrollableY = (
                (overflowY === 'scroll' || overflowY === 'auto' || overflowY === 'hidden') &&
                scrollHeight > clientHeight
            );

            return {
                offsetWidth: offsetWidth,
                offsetHeight: offsetHeight,
                clientWidth: clientWidth,
                clientHeight: clientHeight,
                scrollWidth: scrollWidth,
                scrollHeight: scrollHeight,
                isScrollableX: isScrollableX,
                isScrollableY: isScrollableY,
                overflowX: overflowX,
                overflowY: overflowY
            };
        }
    """)

    return ElementDimensionInfo(
        width=result['offsetWidth'],
        height=result['offsetHeight'],
        client_width=result['clientWidth'],
        client_height=result['clientHeight'],
        scroll_width=result['scrollWidth'],
        scroll_height=result['scrollHeight'],
        is_scrollable_x=result['isScrollableX'],
        is_scrollable_y=result['isScrollableY'],
        overflow_x=result['overflowX'],
        overflow_y=result['overflowY'],
    )


def get_element_scrollability(backend: 'PlaywrightBackend', element: Any) -> Tuple[bool, bool]:
    """Check if element is scrollable in X and Y directions.

    Args:
        backend: The PlaywrightBackend instance
        element: The element to check

    Returns:
        Tuple of (is_scrollable_x, is_scrollable_y)
    """
    info = get_element_dimension_info(backend, element)
    return info.is_scrollable_x, info.is_scrollable_y


def is_element_stale(element: Any) -> bool:
    """Check if an element reference is stale.

    Args:
        element: The element to check

    Returns:
        True if the element is stale, False otherwise
    """
    try:
        if isinstance(element, PlaywrightElementShim):
            element.locator.is_visible()
        else:
            element.is_visible()
        return False
    except Exception:
        return True


def solve_scrollable_child(
    backend: 'PlaywrightBackend',
    element: Any,
    strategy: str = 'first_largest_scrollable',
    implementation: str = 'javascript',
    direction: Optional[str] = None
) -> Any:
    """Find the actual scrollable child element within an element hierarchy.

    This is useful for container elements that are not themselves scrollable but contain
    a nested scrollable element (e.g., Slack's virtual lists with c-scrollbar__child).

    Args:
        backend: The PlaywrightBackend instance
        element: The parent element to search within
        strategy: The search strategy to use:
            - 'first_scrollable': BFS, return first scrollable element found
            - 'first_largest_scrollable': BFS, at each level if multiple scrollable children exist,
                                         return the largest one and stop (default)
            - 'deepest_scrollable': Return the scrollable element that's most deeply nested
            - 'largest_scrollable': Return element with largest scrollable content area
            - 'largest_scrollable_early_stop': BFS, return largest scrollable when it's larger than
                                              all scrollable children or when all children are non-scrollable
        implementation: Implementation method - 'javascript' (default, only option for Playwright)
        direction: Optional scroll direction to check scrollability for:
            - None: Element needs to be scrollable in at least one direction (X or Y) (default)
            - 'Up'/'Down': Element needs to be scrollable in Y direction
            - 'Left'/'Right': Element needs to be scrollable in X direction

    Returns:
        The scrollable child element if found, otherwise returns the original element
    """
    if isinstance(element, PlaywrightElementShim):
        locator = element.locator
    else:
        locator = element

    # Determine direction check
    check_x = direction is None or direction.capitalize() in ('Left', 'Right')
    check_y = direction is None or direction.capitalize() in ('Up', 'Down')

    # JavaScript to find scrollable child based on strategy
    js_code = """
        (args) => {
            const [rootElement, strategy, checkX, checkY] = args;

            function isScrollable(el) {
                const scrollableY = checkY && (el.scrollHeight > el.clientHeight);
                const scrollableX = checkX && (el.scrollWidth > el.clientWidth);
                return scrollableY || scrollableX;
            }

            function getScrollArea(el) {
                return (el.scrollWidth - el.clientWidth) * (el.scrollHeight - el.clientHeight);
            }

            // Check if root is already scrollable
            if (isScrollable(rootElement)) {
                return rootElement;
            }

            // Strategy implementations
            if (strategy === 'first_scrollable') {
                // BFS, return first scrollable
                const queue = Array.from(rootElement.children);
                while (queue.length > 0) {
                    const current = queue.shift();
                    if (isScrollable(current)) {
                        return current;
                    }
                    for (const child of current.children) {
                        queue.push(child);
                    }
                }
                return rootElement;
            }

            if (strategy === 'first_largest_scrollable') {
                // BFS, at each level return largest scrollable
                let queue = Array.from(rootElement.children);
                while (queue.length > 0) {
                    const scrollableAtLevel = queue.filter(isScrollable);
                    if (scrollableAtLevel.length > 0) {
                        // Return largest at this level
                        return scrollableAtLevel.reduce((a, b) =>
                            getScrollArea(a) >= getScrollArea(b) ? a : b
                        );
                    }
                    // Move to next level
                    const nextLevel = [];
                    for (const el of queue) {
                        for (const child of el.children) {
                            nextLevel.push(child);
                        }
                    }
                    queue = nextLevel;
                }
                return rootElement;
            }

            if (strategy === 'deepest_scrollable') {
                // DFS, return deepest scrollable
                let deepest = null;
                let maxDepth = -1;

                function dfs(el, depth) {
                    if (isScrollable(el) && depth > maxDepth) {
                        deepest = el;
                        maxDepth = depth;
                    }
                    for (const child of el.children) {
                        dfs(child, depth + 1);
                    }
                }

                dfs(rootElement, 0);
                return deepest || rootElement;
            }

            if (strategy === 'largest_scrollable') {
                // Find scrollable with largest scroll area
                let largest = null;
                let maxArea = -1;

                function traverse(el) {
                    if (isScrollable(el)) {
                        const area = getScrollArea(el);
                        if (area > maxArea) {
                            maxArea = area;
                            largest = el;
                        }
                    }
                    for (const child of el.children) {
                        traverse(child);
                    }
                }

                traverse(rootElement);
                return largest || rootElement;
            }

            if (strategy === 'largest_scrollable_early_stop') {
                // BFS with early termination when current is larger than all scrollable children
                let queue = [{el: rootElement, parent: null}];
                let bestScrollable = null;
                let bestArea = -1;

                while (queue.length > 0) {
                    const {el} = queue.shift();

                    if (isScrollable(el)) {
                        const area = getScrollArea(el);
                        if (area > bestArea) {
                            bestArea = area;
                            bestScrollable = el;

                            // Check if any children are scrollable with larger area
                            let hasLargerChild = false;
                            for (const child of el.children) {
                                if (isScrollable(child) && getScrollArea(child) >= area) {
                                    hasLargerChild = true;
                                    break;
                                }
                            }
                            if (!hasLargerChild) {
                                return bestScrollable;
                            }
                        }
                    }

                    for (const child of el.children) {
                        queue.push({el: child, parent: el});
                    }
                }
                return bestScrollable || rootElement;
            }

            // Default: first_scrollable fallback
            const queue = Array.from(rootElement.children);
            while (queue.length > 0) {
                const current = queue.shift();
                if (isScrollable(current)) {
                    return current;
                }
                for (const child of current.children) {
                    queue.push(child);
                }
            }
            return rootElement;
        }
    """

    try:
        # Use evaluate_handle to get an ElementHandle back
        element_handle = locator.evaluate_handle(js_code, [strategy, check_x, check_y])

        # Check if we got a valid element back
        if element_handle:
            as_element = element_handle.as_element()
            if as_element:
                # Assign a unique attribute and then query for it
                unique_attr = f'_pw_scroll_child_{id(element_handle)}'
                backend._page.evaluate(
                    "(args) => args[0].setAttribute(args[1], 'true')",
                    [as_element, unique_attr]
                )

                # Now find the element by this attribute
                found_locator = backend._page.locator(f'[{unique_attr}="true"]')

                # Clean up the attribute
                backend._page.evaluate(
                    "(args) => args[0].removeAttribute(args[1])",
                    [as_element, unique_attr]
                )

                # Return wrapped in shim if original was wrapped
                if isinstance(element, PlaywrightElementShim):
                    return PlaywrightElementShim(found_locator, backend._page)
                return found_locator

        # Fallback to original element
        direction_str = f" in direction '{direction}'" if direction else ""
        warnings.warn(
            f"Could not find scrollable child element{direction_str} using strategy '{strategy}'. "
            f"Returning original element.",
            UserWarning
        )
        return element

    except Exception as e:
        _logger.warning(f"solve_scrollable_child failed: {e}, returning original element")
        return element
