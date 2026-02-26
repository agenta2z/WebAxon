"""
Playwright action implementations.

This module contains action functions for the Playwright backend, following
the same pattern as Selenium's actions.py where the driver/backend is passed
as the first argument.
"""

import logging
import platform
import random
from time import sleep
from typing import Any, List, Mapping, Optional, Sequence, Tuple, Union, TYPE_CHECKING

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
from webaxon.automation.backends.shared.text_sanitization import (
    sanitize_input_text_for_webdriver,
    NonBMPHandling,
    NewlineHandling,
    WhitespaceHandling,
)
from .common import get_body_html, get_body_text
from .shims import PlaywrightElementShim

if TYPE_CHECKING:
    from .playwright_backend import PlaywrightBackend

_logger = logging.getLogger(__name__)


def click_element(
    backend: 'PlaywrightBackend',
    element: Any,
    try_open_in_new_tab: Union[bool, OpenInNewTabMode] = False,
    wait_before_checking_new_tab: float = 0.5,
    additional_max_wait_for_tab_timeout: float = 5.0,
    only_enable_additional_wait_for_non_anchor_links: bool = True,
    implementation: Union[ClickImplementation, Tuple[ClickImplementation, ...]] = DEFAULT_CLICK_IMPLEMENTATION_ORDER,
    new_tab_strategy_order: Tuple[NewTabClickStrategy, ...] = DEFAULT_NEW_TAB_STRATEGY_ORDER,
    return_strategy_result: bool = False,
    new_tab_fallback_to_normal_click: Union[bool, str, NewTabFallbackMode] = False,
    **kwargs
) -> Union[Optional[List[str]], Tuple[Optional[List[str]], NewTabClickResult]]:
    """Click an element, optionally opening in new tab.

    This method now matches Selenium's click_element signature for full compatibility.

    Args:
        backend: The PlaywrightBackend instance
        element: The element to click
        try_open_in_new_tab: Whether to attempt opening in a new tab.
            - False/OpenInNewTabMode.DISABLED: normal click
            - True/OpenInNewTabMode.ENABLED: always attempt new-tab click
            - OpenInNewTabMode.ENABLED_FOR_NON_SAME_PAGE_INTERACTION: only for external links
            - OpenInNewTabMode.ENABLED_FOR_INTERACTABLE: for any interactable element
        wait_before_checking_new_tab: Sleep time (seconds) after clicking before checking for new tabs
        additional_max_wait_for_tab_timeout: Additional wait time for new tab to appear
        only_enable_additional_wait_for_non_anchor_links: Only use additional wait for non-anchor links
        implementation: Controls click execution implementation and fallback order.
            Accepts a single ClickImplementation or a tuple tried in order on failure.
            Available: NATIVE, JAVASCRIPT, ACTION_CHAIN, EVENT_DISPATCH.
            Defaults to DEFAULT_CLICK_IMPLEMENTATION_ORDER = (NATIVE, JAVASCRIPT)
        new_tab_strategy_order: Order of strategies to try for opening in new tab
        return_strategy_result: If True, return tuple of (handles, strategy_result)
        new_tab_fallback_to_normal_click: When all new-tab strategies fail, fall back
            to a normal click if the page is unchanged. Defaults to False (no fallback).
            - False/NewTabFallbackMode.DISABLED: no fallback.
            - True/NewTabFallbackMode.ENABLED_WHEN_NO_TEXT_CHANGE: fallback if URL
              unchanged AND page text unchanged.
            - NewTabFallbackMode.ENABLED_WHEN_NO_HTML_CHANGE: fallback if URL
              unchanged AND page HTML unchanged.

    Returns:
        List of new window handles, or None if no new tab opened.
        If return_strategy_result=True, returns tuple of (handles, NewTabClickResult)
    """
    old_handles = set(backend.window_handles)

    if isinstance(element, PlaywrightElementShim):
        locator = element.locator
    else:
        locator = element

    def _normal_click():
        """Perform a normal click using the configured implementation order."""
        methods = (implementation,) if isinstance(implementation, ClickImplementation) else implementation
        last_exc = None
        for method in methods:
            try:
                if method == ClickImplementation.NATIVE:
                    locator.click()
                elif method == ClickImplementation.JAVASCRIPT:
                    locator.evaluate("el => el.click()")
                elif method == ClickImplementation.ACTION_CHAIN:
                    locator.hover()
                    locator.click()
                elif method == ClickImplementation.EVENT_DISPATCH:
                    locator.evaluate(
                        "el => { var e = new MouseEvent('click', "
                        "{bubbles: true, cancelable: true, view: window}); "
                        "el.dispatchEvent(e); }"
                    )
                return  # Success
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            _logger.warning(f"All click implementations exhausted. Last exception: {last_exc}")

    def _check_for_new_tabs() -> List[str]:
        """Check for newly opened tabs."""
        sleep(wait_before_checking_new_tab)
        new_handles = set(backend.window_handles)
        new = list(new_handles - old_handles)
        return new

    def _wait_for_new_tab() -> List[str]:
        """Wait for a new tab to appear with timeout."""
        import time
        start = time.time()
        while time.time() - start < additional_max_wait_for_tab_timeout:
            new = _check_for_new_tabs()
            if new:
                return new
            sleep(0.2)
        return []

    # Normalize try_open_in_new_tab to OpenInNewTabMode
    if isinstance(try_open_in_new_tab, bool):
        open_mode = OpenInNewTabMode.ENABLED if try_open_in_new_tab else OpenInNewTabMode.DISABLED
    else:
        open_mode = try_open_in_new_tab

    # Normal click if disabled
    if open_mode == OpenInNewTabMode.DISABLED:
        _normal_click()
        if return_strategy_result:
            return [], NewTabClickResult.FAILED
        return []

    # Check if we should actually try opening in new tab based on mode
    should_open_in_new_tab = True
    if open_mode == OpenInNewTabMode.ENABLED_FOR_NON_SAME_PAGE_INTERACTION:
        # Check if element is likely to navigate away
        href = locator.evaluate("el => el.href || el.getAttribute('href') || ''") or ""
        if href.startswith('#') or not href:
            should_open_in_new_tab = False
    elif open_mode == OpenInNewTabMode.ENABLED_FOR_INTERACTABLE:
        # For Playwright, all clickable elements are interactable
        should_open_in_new_tab = True

    if not should_open_in_new_tab:
        _normal_click()
        if return_strategy_result:
            return [], NewTabClickResult.FAILED
        return []

    # Zero out additional wait for same-page elements (matches Selenium behavior)
    if only_enable_additional_wait_for_non_anchor_links:
        href = locator.evaluate("el => el.href || el.getAttribute('href') || ''") or ""
        is_non_same_page = bool(href) and not href.startswith('#')
        if not is_non_same_page:
            additional_max_wait_for_tab_timeout = 0

    # Resolve new-tab fallback mode
    _use_text_fallback = (
        new_tab_fallback_to_normal_click is True
        or new_tab_fallback_to_normal_click == NewTabFallbackMode.ENABLED_WHEN_NO_TEXT_CHANGE
        or new_tab_fallback_to_normal_click == "no_text_change"
    )
    _use_html_fallback = (
        new_tab_fallback_to_normal_click == NewTabFallbackMode.ENABLED_WHEN_NO_HTML_CHANGE
        or new_tab_fallback_to_normal_click == "no_html_change"
    )
    _fallback_enabled = _use_text_fallback or _use_html_fallback

    # Capture page state before new-tab strategies for fallback comparison
    _fallback_url_before = None
    _fallback_content_before = None
    if _fallback_enabled:
        try:
            _fallback_url_before = backend._page.url
            if _use_text_fallback:
                _fallback_content_before = get_body_text(backend)
            else:
                _fallback_content_before = get_body_html(backend)
        except Exception:
            _fallback_url_before = None
            _fallback_content_before = None

    # Try new-tab strategies in order
    strategy_result = NewTabClickResult.FAILED

    for strategy in new_tab_strategy_order:
        new_handles = []

        try:
            if strategy == NewTabClickStrategy.URL_EXTRACT:
                # Extract URL and open in new page
                url = locator.evaluate(r"""
                    el => {
                        // Try href first
                        if (el.href) return el.href;
                        if (el.getAttribute('href')) return el.getAttribute('href');
                        // Try data attributes
                        if (el.dataset.href) return el.dataset.href;
                        if (el.dataset.url) return el.dataset.url;
                        // Try onclick containing URL
                        const onclick = el.getAttribute('onclick') || '';
                        const urlMatch = onclick.match(/['"]?(https?:\/\/[^'"\\s]+)['"]?/);
                        if (urlMatch) return urlMatch[1];
                        return null;
                    }
                """)
                if url and not url.startswith('#'):
                    # Open URL in new page using context
                    new_page = backend._context.new_page()
                    new_page.goto(url)
                    # Register the new page with the shim
                    handle = backend._driver_shim._register_page(new_page)
                    new_handles = [handle]

            elif strategy == NewTabClickStrategy.TARGET_BLANK:
                # Only applies to <a> elements (matches Selenium behavior)
                _tag_name = locator.evaluate("el => (el.tagName || '').toLowerCase()")
                if _tag_name == 'a':
                    # Set target='_blank' and click using the implementation sequence
                    original_target = locator.evaluate("el => el.target || ''")
                    locator.evaluate("el => el.target = '_blank'")
                    try:
                        _methods = (implementation,) if isinstance(implementation, ClickImplementation) else implementation
                        for _method in _methods:
                            try:
                                if _method == ClickImplementation.NATIVE:
                                    locator.click()
                                elif _method == ClickImplementation.JAVASCRIPT:
                                    locator.evaluate("el => el.click()")
                                elif _method == ClickImplementation.ACTION_CHAIN:
                                    locator.hover()
                                    locator.click()
                                elif _method == ClickImplementation.EVENT_DISPATCH:
                                    locator.evaluate(
                                        "el => { var e = new MouseEvent('click', "
                                        "{bubbles: true, cancelable: true, view: window}); "
                                        "el.dispatchEvent(e); }"
                                    )
                                break
                            except Exception:
                                continue
                        sleep(wait_before_checking_new_tab)
                        new_handles = list(set(backend.window_handles) - old_handles)
                    finally:
                        # Restore original target
                        locator.evaluate(f"el => el.target = '{original_target}'")

            elif strategy == NewTabClickStrategy.MODIFIER_KEY:
                # Ctrl/Cmd + Click
                modifier = 'Meta' if platform.system() == 'Darwin' else 'Control'
                locator.click(modifiers=[modifier])
                sleep(wait_before_checking_new_tab)
                new_handles = list(set(backend.window_handles) - old_handles)

            elif strategy == NewTabClickStrategy.CDP_CREATE_TARGET:
                # CDP create target - Chromium only
                if backend.supports_cdp():
                    url = locator.evaluate("el => el.href || ''")
                    if url:
                        try:
                            cdp = backend._context.new_cdp_session(backend._page)
                            result = cdp.send("Target.createTarget", {"url": url})
                            if result.get("targetId"):
                                # Wait for the new page to appear
                                sleep(wait_before_checking_new_tab)
                                new_handles = list(set(backend.window_handles) - old_handles)
                        except Exception as e:
                            _logger.debug(f"CDP_CREATE_TARGET failed: {e}")

            elif strategy == NewTabClickStrategy.MIDDLE_CLICK:
                # Middle mouse button click
                box = locator.bounding_box()
                if box:
                    x = box['x'] + box['width'] / 2
                    y = box['y'] + box['height'] / 2
                    backend._page.mouse.click(x, y, button='middle')
                    sleep(wait_before_checking_new_tab)
                    new_handles = list(set(backend.window_handles) - old_handles)

            # Check if strategy succeeded
            if new_handles:
                strategy_result = STRATEGY_TO_RESULT[strategy]
                # Switch to new tab
                backend.switch_to_window(new_handles[0])
                if return_strategy_result:
                    return new_handles, strategy_result
                return new_handles

        except Exception as e:
            _logger.debug(f"Strategy {strategy} failed: {e}")
            continue

    # All strategies failed — additional wait, then conditional fallback
    new_handles = _check_for_new_tabs()

    if not new_handles and additional_max_wait_for_tab_timeout > 0:
        new_handles = _wait_for_new_tab()

    if new_handles:
        backend.switch_to_window(new_handles[0])
    elif _fallback_enabled and _fallback_url_before is not None:
        # All new-tab strategies failed — check if page is unchanged and fall back to normal click.
        sleep(wait_before_checking_new_tab)
        try:
            url_changed = (backend._page.url != _fallback_url_before)
        except Exception:
            url_changed = True
        if not url_changed:
            if _use_text_fallback:
                current_content = get_body_text(backend)
            else:
                current_content = get_body_html(backend)
            if current_content == _fallback_content_before:
                _normal_click()

    if return_strategy_result:
        return (new_handles if new_handles else [], strategy_result)
    return new_handles if new_handles else []


def input_text(
    backend: 'PlaywrightBackend',
    element: Any,
    text: str,
    clear_content: bool = False,
    implementation: str = 'auto',
    default_implementation: str = 'send_keys',
    fast_implementation: str = 'send_keys_fast',
    fast_threshold: int = 20,
    min_delay: float = 0.1,
    max_delay: float = 1.0,
    sanitize: bool = True,
    auto_sanitization: bool = True,
    non_bmp_handling: NonBMPHandling = NonBMPHandling.REMOVE,
    newline_handling: NewlineHandling = NewlineHandling.SPACE,
    whitespace_handling: WhitespaceHandling = WhitespaceHandling.NORMALIZE,
    **kwargs
) -> None:
    """Input text into an element.

    Args:
        backend: The PlaywrightBackend instance
        element: Input element
        text: Text to input
        clear_content: If True, clear existing content first
        implementation: Strategy - 'auto', 'send_keys', 'send_keys_fast', 'javascript'
            - 'send_keys': type() with random delays (most human-like, slowest)
            - 'send_keys_fast': type() without delay (faster, triggers keyboard events)
            - 'javascript': fill() direct value setting (fastest)
            - 'auto': Choose based on text length vs fast_threshold
        default_implementation: Implementation for short text in auto mode
        fast_implementation: Implementation for long text in auto mode
        fast_threshold: Text length threshold for auto mode (default: 20)
        min_delay: Min delay between keystrokes in seconds (for send_keys)
        max_delay: Max delay between keystrokes in seconds (for send_keys)
        sanitize: Whether to sanitize text
        auto_sanitization: Use implementation-aware sanitization
            When True, Playwright keeps non-BMP chars (unlike Selenium which must remove them)
        non_bmp_handling: How to handle non-BMP chars (only when auto_sanitization=False)
        newline_handling: How to handle newlines (only when auto_sanitization=False)
        whitespace_handling: How to handle whitespace (only when auto_sanitization=False)
    """
    # Get locator
    if isinstance(element, PlaywrightElementShim):
        locator = element.locator
    else:
        locator = element

    # Auto mode: choose implementation based on text length
    if implementation == 'auto':
        implementation = default_implementation if len(text) <= fast_threshold else fast_implementation

    # Apply text sanitization
    if sanitize:
        if auto_sanitization:
            if implementation in ('send_keys', 'send_keys_fast'):
                # Playwright's type() can handle non-BMP chars better than Selenium's send_keys
                # but still sanitize newlines for single-line inputs
                text = sanitize_input_text_for_webdriver(
                    text,
                    non_bmp_handling=NonBMPHandling.KEEP,  # Playwright handles these natively
                    newline_handling=NewlineHandling.SPACE,
                    whitespace_handling=WhitespaceHandling.NORMALIZE,
                    remove_control_chars=True
                )
            else:  # javascript / fill()
                # fill() handles everything natively
                text = sanitize_input_text_for_webdriver(
                    text,
                    non_bmp_handling=NonBMPHandling.KEEP,
                    newline_handling=NewlineHandling.KEEP,
                    whitespace_handling=WhitespaceHandling.KEEP,
                    remove_control_chars=True
                )
        else:
            # Manual sanitization with user-specified options
            text = sanitize_input_text_for_webdriver(
                text,
                non_bmp_handling=non_bmp_handling,
                newline_handling=newline_handling,
                whitespace_handling=whitespace_handling,
                remove_control_chars=True
            )

    # Execute based on implementation
    if implementation == 'javascript':
        # fill() is fastest - sets value directly
        if clear_content:
            locator.fill(text)
        else:
            # fill() always clears, so append current value
            current = locator.input_value()
            locator.fill(current + text)
    elif implementation == 'send_keys_fast':
        # type() without delay - sends entire string but triggers keyboard events
        if clear_content:
            locator.clear()
        locator.type(text, delay=0)
    elif implementation == 'send_keys':
        # type() with random delay - most human-like
        if clear_content:
            locator.clear()
        delay_ms = random.uniform(min_delay, max_delay) * 1000
        locator.type(text, delay=delay_ms)
    else:
        raise ValueError(f"Unknown implementation: {implementation}")


def scroll_element(
    backend: 'PlaywrightBackend',
    element: Any,
    direction: str = 'Down',
    distance: str = 'Large',
    implementation: str = 'javascript',
    relative_distance: bool = False,
    try_solve_scrollable_child: bool = False,
    **kwargs
) -> None:
    """Scroll an element or viewport.

    Args:
        backend: The PlaywrightBackend instance
        element: The element to scroll within
        direction: Scroll direction - 'Up', 'Down', 'Left', 'Right'
        distance: Scroll distance - 'Small', 'Medium', 'Large', 'Half', 'Full', or pixels as string
        implementation: Scroll method - 'javascript' or 'mouse_wheel'
        relative_distance: If True, Small/Medium/Large distances are calculated as percentages
                          of element's client dimensions (30%/60%/90%) rather than fixed pixel values.
                          Only applies when distance is 'Small', 'Medium', or 'Large'.
        try_solve_scrollable_child: If True, attempt to find the actual scrollable child element
    """
    if try_solve_scrollable_child:
        element = backend.solve_scrollable_child(element)

    if isinstance(element, PlaywrightElementShim):
        locator = element.locator
    else:
        locator = element

    # Normalize direction
    direction = direction.capitalize()

    # Calculate scroll distance
    if relative_distance and distance in ('Small', 'Medium', 'Large'):
        # Relative distance: percentage of element's client dimensions
        percentage = RELATIVE_DISTANCE_PERCENTAGES[distance]

        # Get element dimensions
        dims = locator.evaluate("el => ({h: el.clientHeight, w: el.clientWidth})")

        # Use height for vertical scrolling, width for horizontal
        if direction in ('Up', 'Down'):
            scroll_amount = int(dims['h'] * percentage)
        else:  # Left, Right
            scroll_amount = int(dims['w'] * percentage)
    else:
        # Fixed distance in pixels
        try:
            scroll_amount = int(distance)
        except ValueError:
            scroll_amount = FIXED_DISTANCE_PIXELS.get(distance, 500)

            # Handle 'Half' and 'Full' - use viewport dimensions
            if distance in ('Half', 'Full'):
                viewport_size = backend._page.viewport_size or {'width': 1920, 'height': 1080}
                if direction in ('Up', 'Down'):
                    scroll_amount = viewport_size['height'] // (2 if distance == 'Half' else 1)
                else:  # Left, Right
                    scroll_amount = viewport_size['width'] // (2 if distance == 'Half' else 1)

    # Calculate direction deltas using shared utility
    delta_x, delta_y = compute_scroll_delta(direction, scroll_amount)

    # Use JavaScript scrolling
    if implementation == 'javascript':
        locator.evaluate(f"el => el.scrollBy({delta_x}, {delta_y})")
    else:
        # Use mouse wheel
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if box:
            backend._page.mouse.move(
                box['x'] + box['width'] / 2,
                box['y'] + box['height'] / 2
            )
            backend._page.mouse.wheel(delta_x, delta_y)


def center_element_in_view(backend: 'PlaywrightBackend', element: Any) -> None:
    """Scroll element to center of viewport.

    Args:
        backend: The PlaywrightBackend instance
        element: The element to center
    """
    if isinstance(element, PlaywrightElementShim):
        locator = element.locator
    else:
        locator = element

    locator.evaluate("""
        el => el.scrollIntoView({
            block: 'center',
            inline: 'center',
            behavior: 'smooth'
        })
    """)
