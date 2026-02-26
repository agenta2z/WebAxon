"""
Shared types for click element functionality across backends.

This module defines enums and types used by both Selenium and Playwright backends
for click_element functionality, particularly for opening links in new tabs.
"""

from enum import Enum
from typing import Tuple, Mapping


class StrEnum(str, Enum):
    """String enum base class for Python < 3.11 compatibility."""
    pass


class OpenInNewTabMode(StrEnum):
    """Determines when to attempt opening elements in new tabs.

    Values:
        ENABLED: Always attempt new-tab click.
        ENABLED_FOR_INTERACTABLE: Open in new tab if the element is not classified as NO_INTERACTION.
        ENABLED_FOR_NON_SAME_PAGE_INTERACTION: Only open in a new tab if the element is likely
            to navigate elsewhere (external links, non-anchor links).
        DISABLED: Normal click (no new tab).
    """
    ENABLED = "enabled"
    ENABLED_FOR_INTERACTABLE = 'enabled_for_interactable'
    ENABLED_FOR_NON_SAME_PAGE_INTERACTION = "enabled_for_non_same_page_interaction"
    DISABLED = "disabled"


class NewTabClickStrategy(StrEnum):
    """Available strategies for opening elements in new tabs.

    Strategies are tried in order until one succeeds.

    Values:
        URL_EXTRACT: Extract URL from element and use window.open() or context.new_page()
        TARGET_BLANK: Set target='_blank' attribute on element then click
        MODIFIER_KEY: Ctrl/Cmd + click (platform-dependent)
        CDP_CREATE_TARGET: Use CDP Target.createTarget (Chrome/Chromium only)
        MIDDLE_CLICK: Middle mouse button click
    """
    URL_EXTRACT = "url_extract"          # Extract URL from element + window.open()
    TARGET_BLANK = "target_blank"        # Set target='_blank' on element + click
    MODIFIER_KEY = "modifier_key"        # Ctrl/Cmd + click
    CDP_CREATE_TARGET = "cdp_create_target"  # CDP Target.createTarget (Chrome/Chromium only)
    MIDDLE_CLICK = "middle_click"        # Middle mouse button click


class NewTabClickResult(StrEnum):
    """Result of new tab click attempt, indicating which strategy succeeded.

    Values:
        SUCCESS_URL_EXTRACT: URL extraction strategy succeeded
        SUCCESS_TARGET_BLANK: target='_blank' strategy succeeded
        SUCCESS_MODIFIER_KEY: Modifier key (Ctrl/Cmd) click succeeded
        SUCCESS_CDP: CDP create target succeeded
        SUCCESS_MIDDLE_CLICK: Middle click succeeded
        FAILED: All strategies failed
    """
    SUCCESS_URL_EXTRACT = "success_url_extract"
    SUCCESS_TARGET_BLANK = "success_target_blank"
    SUCCESS_MODIFIER_KEY = "success_modifier_key"
    SUCCESS_CDP = "success_cdp"
    SUCCESS_MIDDLE_CLICK = "success_middle_click"
    FAILED = "failed"


class NewTabFallbackMode(StrEnum):
    """Controls fallback to normal click when all new-tab strategies fail.

    When enabled, after all new-tab strategies fail to open a new tab,
    click_element() checks if the page content changed. If the page is
    unchanged (strategies had no visible effect), it falls back to a
    normal click.

    Values:
        ENABLED_WHEN_NO_TEXT_CHANGE: Fallback if URL unchanged AND
            document.body.innerText unchanged. Robust against cosmetic
            DOM changes (CSS classes, ripple animations) from mouse events.
        ENABLED_WHEN_NO_HTML_CHANGE: Fallback if URL unchanged AND
            document.documentElement.outerHTML unchanged. More sensitive —
            may skip fallback if strategies caused minor DOM changes.
        DISABLED: No fallback (current behavior).
    """
    ENABLED_WHEN_NO_TEXT_CHANGE = "no_text_change"
    ENABLED_WHEN_NO_HTML_CHANGE = "no_html_change"
    DISABLED = "disabled"


class ClickImplementation(StrEnum):
    """Available implementations for clicking an element.

    When passed as a tuple to the ``implementation`` parameter, implementations
    are tried in order. On ElementClickInterceptedException /
    ElementNotInteractableException, the next implementation in the sequence
    is attempted.

    Values:
        NATIVE: element.click() — Selenium WebDriver native click.
        JAVASCRIPT: driver.execute_script("arguments[0].click();", element) — JS DOM click.
        ACTION_CHAIN: ActionChains(driver).move_to_element(element).pause(0.3).click().perform()
            — full mouse event sequence via Selenium ActionChains.
        EVENT_DISPATCH: new MouseEvent('click', {bubbles, cancelable, view})
            dispatched via dispatchEvent — synthetic MouseEvent via JS.
    """
    NATIVE = "native"
    JAVASCRIPT = "javascript"
    ACTION_CHAIN = "action_chain"
    EVENT_DISPATCH = "event_dispatch"


# Default click implementation order: native first, then JavaScript fallback.
# Preserves the previous default behavior (try_jscript_first=False).
DEFAULT_CLICK_IMPLEMENTATION_ORDER: Tuple[ClickImplementation, ...] = (
    ClickImplementation.NATIVE,
    ClickImplementation.JAVASCRIPT,
)


# Default strategy order - can be customized by caller
DEFAULT_NEW_TAB_STRATEGY_ORDER: Tuple[NewTabClickStrategy, ...] = (
    NewTabClickStrategy.URL_EXTRACT,
    NewTabClickStrategy.TARGET_BLANK,
    NewTabClickStrategy.MODIFIER_KEY,
    NewTabClickStrategy.CDP_CREATE_TARGET,
    NewTabClickStrategy.MIDDLE_CLICK,
)


# Mapping from strategy to result
STRATEGY_TO_RESULT: Mapping[NewTabClickStrategy, NewTabClickResult] = {
    NewTabClickStrategy.URL_EXTRACT: NewTabClickResult.SUCCESS_URL_EXTRACT,
    NewTabClickStrategy.TARGET_BLANK: NewTabClickResult.SUCCESS_TARGET_BLANK,
    NewTabClickStrategy.MODIFIER_KEY: NewTabClickResult.SUCCESS_MODIFIER_KEY,
    NewTabClickStrategy.CDP_CREATE_TARGET: NewTabClickResult.SUCCESS_CDP,
    NewTabClickStrategy.MIDDLE_CLICK: NewTabClickResult.SUCCESS_MIDDLE_CLICK,
}
