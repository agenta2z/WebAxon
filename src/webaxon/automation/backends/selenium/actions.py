import base64
import logging
import time
import warnings
from enum import StrEnum
from typing import Optional, Iterable, Mapping, List, Sequence, TYPE_CHECKING
from typing import Union, Tuple

if TYPE_CHECKING:
    from rich_python_utils.common_objects.debuggable import Debuggable

_logger = logging.getLogger(__name__)

import undetected_chromedriver as uc
from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    ElementNotInteractableException
)
from selenium.webdriver import Keys, ActionChains
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from urllib3.exceptions import ReadTimeoutError

from rich_python_utils.common_utils.system_helper import get_current_platform, OperatingSystem
from rich_python_utils.console_utils import hprint_message
from rich_python_utils.string_utils.misc import camel_to_snake_case
from rich_python_utils.datetime_utils.common import random_sleep
from .common import wait_for_page_loading, get_element_text, get_element_html, \
    solve_scrollable_child, scroll_element_into_view, get_body_html, get_body_text
from webaxon.automation.backends.shared.text_sanitization import (
    sanitize_input_text_for_webdriver,
    NonBMPHandling,
    NewlineHandling,
    WhitespaceHandling
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
from webaxon.html_utils.common import ElementInteractionTypes, DEFAULT_HTML_INTERACTIVE_ATTRIBUTES_AND_VALUES
from webaxon.html_utils.common import get_element_interaction_type as _get_element_interaction_type
from webaxon.html_utils.common import parse_onclick_for_url
from urllib.parse import urljoin, urlparse


class ClearMethod(StrEnum):
    """Strategy for clearing existing content in an input field before typing.

    Attributes:
        SELECT_ALL: Use Ctrl+A (Cmd+A on Mac) to select all text, then typing
            replaces the selection. Works reliably with React/Vue/Angular
            controlled inputs because it uses standard keyboard events.
        ELEMENT_CLEAR: Use Selenium's ``element.clear()`` method. May fail
            silently on framework-controlled inputs (React comboboxes, etc.)
            because it doesn't trigger synthetic event handlers.
    """
    SELECT_ALL = 'select_all'
    ELEMENT_CLEAR = 'element_clear'


def _get_select_all_keys() -> str:
    """Return the platform-appropriate 'select all' key chord (Ctrl+A or Cmd+A)."""
    current_os = get_current_platform()
    modifier = Keys.COMMAND if current_os in (OperatingSystem.MACOS, OperatingSystem.IOS) else Keys.CONTROL
    return modifier + "a"


def _get_attachments_text(attachments, original_text: str = '', separator: str = '\n\n') -> str:
    """
    Extract text from attachments, filtering out those already present in original text.

    Args:
        attachments: Sequence of attachment objects (e.g., AgentAttachment instances)
        original_text: The original text to check for existing attachment IDs
        separator: Separator between attachment texts (default: '\n\n')

    Returns:
        Combined text from attachments that are not already in the original text
    """
    if not attachments:
        return ''

    attachment_texts = []
    for att in attachments:
        # Check if attachment ID is already in original text
        att_id = getattr(att, 'id', None)
        if att_id and att_id in original_text:
            # Extract text from attachment
            if hasattr(att, 'full_text'):
                # Use full_text property if available (e.g., AgentAttachment)
                attachment_texts.append(str(att.full_text))
            elif hasattr(att, 'content'):
                # Fallback to content attribute
                attachment_texts.append(str(att.content))
            else:
                # Fall back to string representation
                attachment_texts.append(str(att))

    return separator.join(attachment_texts) if attachment_texts else ''


def get_element_interaction_type(
        element: WebElement,
        driver: WebDriver,
        interactive_attrs_and_values: Mapping[
            str,
            Union[Iterable, Mapping[str, ElementInteractionTypes], None]
        ] = DEFAULT_HTML_INTERACTIVE_ATTRIBUTES_AND_VALUES,
) -> ElementInteractionTypes:
    """
    Classifies a Selenium WebElement's interaction type relative to the current page's domain.

    1) Checks ``element.get_attribute("href")`` for navigational links (same page anchor,
       same domain, or external domain).
    2) Looks for parseable URLs in ``element.get_attribute("onclick")``.
    3) Considers additional attributes (e.g., ``role="button"``, ``jsname``) to detect
       interactive behavior (e.g. ``SAME_PAGE_INTERACTABLE``, ``UNKNOWN_INTERACTABLE``).

    Args:
        element (WebElement):
            The Selenium element under inspection (e.g., <a>, <button>, etc.).
        driver (WebDriver):
            Used to determine the current domain from ``driver.current_url``.
        interactive_attrs_and_values:
            A mapping defining how certain attributes and values imply interactivity.

    Returns:
        ElementInteractionTypes: One of:
            - NO_INTERACTION
            - SAME_PAGE_ANCHOR_LINK
            - SAME_DOMAIN_LINK
            - EXTERNAL_DOMAIN_LINK
            - SAME_PAGE_INTERACTABLE
            - UNKNOWN_INTERACTABLE
    """

    # Selenium resolves relative hrefs to absolute URLs (e.g., href="#" becomes
    # "https://example.com/#"). Detect resolved same-page anchors before delegating,
    # since classify_url_domain's url.startswith('#') check won't catch them.
    href = element.get_attribute("href")
    if href and '#' in href:
        url_base = href.split('#', 1)[0]
        current_base = driver.current_url.split('#', 1)[0]
        if url_base == current_base:
            return ElementInteractionTypes.SAME_PAGE_ANCHOR_LINK

    return _get_element_interaction_type(
        element=element,
        current_domain=urlparse(driver.current_url).netloc,
        interactive_attrs_and_values=interactive_attrs_and_values,
        element_get_attr_method_name='get_attribute',
        element_has_attr_method_name='get_attribute'
    )


def is_chromium_based_driver(driver: WebDriver) -> bool:
    """
    Detect if the driver is Chrome/Chromium-based and supports CDP commands.

    Args:
        driver: The Selenium WebDriver instance.

    Returns:
        bool: True if the driver supports CDP commands (Chrome, UndetectedChrome, Edge Chromium).
    """
    # Edge is also Chromium-based and supports CDP
    return isinstance(driver, (webdriver.Chrome, uc.Chrome, webdriver.Edge))


def extract_url_from_element(element: WebElement, driver: WebDriver) -> Optional[str]:
    """
    Extract a navigable URL from a WebElement.

    Checks multiple attributes in order of priority:
    1. href (standard link attribute)
    2. data-href (common data attribute)
    3. data-url (common data attribute)
    4. onclick parsed URL (using parse_onclick_for_url)

    Args:
        element: The WebElement to extract URL from.
        driver: WebDriver for resolving relative URLs.

    Returns:
        Absolute URL string if found, None otherwise.
    """
    # Priority order for URL attributes
    url_attributes = ['href', 'data-href', 'data-url', 'data-link', 'data-navigate']

    for attr in url_attributes:
        url = element.get_attribute(attr)
        if url and url.strip() and not url.startswith('#') and not url.startswith('javascript:'):
            # Resolve relative URLs to absolute
            if not url.startswith(('http://', 'https://', '//')):
                url = urljoin(driver.current_url, url)
            return url

    # Try parsing onclick for URL
    onclick = element.get_attribute('onclick')
    if onclick:
        parsed_url = parse_onclick_for_url(onclick)
        if parsed_url:
            if not parsed_url.startswith(('http://', 'https://', '//')):
                parsed_url = urljoin(driver.current_url, parsed_url)
            return parsed_url

    return None


def _try_open_in_new_tab(
        driver: WebDriver,
        element: WebElement,
        handles_before: List[str],
        wait_time: float = 0.5,
        strategy_order: Tuple[NewTabClickStrategy, ...] = DEFAULT_NEW_TAB_STRATEGY_ORDER,
        implementation: Union[ClickImplementation, Tuple[ClickImplementation, ...]] = DEFAULT_CLICK_IMPLEMENTATION_ORDER,
        logger: 'Union[logging.Logger, Debuggable, None]' = None
) -> Tuple[NewTabClickResult, List[str]]:
    """
    Attempt to open an element in a new tab using multiple strategies.

    Strategies are tried in the order specified by `strategy_order`. Each strategy
    checks if a new tab was opened before moving to the next.

    Available strategies:
    - URL_EXTRACT: Extract URL from element + window.open() (most reliable if URL available)
    - TARGET_BLANK: Set target='_blank' on element + click (works for <a> elements)
    - MODIFIER_KEY: Ctrl/Cmd + click (native browser behavior for links)
    - CDP_CREATE_TARGET: CDP Target.createTarget (Chrome/Chromium only, requires URL)
    - MIDDLE_CLICK: Middle mouse button click (fallback)

    Args:
        driver: The Selenium WebDriver instance.
        element: The WebElement to click.
        handles_before: Window handles before the click (for detecting new tabs).
        wait_time: Time to wait after each attempt to check for new tab.
        strategy_order: Order in which to try strategies. Default is DEFAULT_NEW_TAB_STRATEGY_ORDER.
                       Can be customized to prioritize different strategies or exclude some.
        implementation: Controls how clicks are performed within applicable strategies
                       (TARGET_BLANK, MODIFIER_KEY). Accepts a single ClickImplementation
                       or a tuple of them. For TARGET_BLANK: uses the implementation sequence
                       for the click after setting target=_blank. For MODIFIER_KEY: maps to
                       JS MouseEvent dispatch if the first implementation is JAVASCRIPT or
                       EVENT_DISPATCH, or to ActionChains if NATIVE or ACTION_CHAIN.
                       Default is DEFAULT_CLICK_IMPLEMENTATION_ORDER.

    Returns:
        Tuple of (result status, list of new tab handles).
    """

    # Normalize implementation to tuple and derive preferences
    _implementations = (implementation,) if isinstance(implementation, ClickImplementation) else implementation
    _primary_impl = _implementations[0] if _implementations else ClickImplementation.NATIVE
    _prefer_js = _primary_impl in (ClickImplementation.JAVASCRIPT, ClickImplementation.EVENT_DISPATCH)

    def _check_new_tab() -> List[str]:
        """Check if new tabs appeared after an action."""
        time.sleep(wait_time)
        handles_after = driver.window_handles
        return [h for h in handles_after if h not in handles_before]

    # Pre-extract URL (used by multiple strategies)
    url = extract_url_from_element(element, driver)

    # Pre-determine tag name
    try:
        tag_name = element.tag_name.lower() if element.tag_name else ''
    except Exception as e:
        tag_name = ''
        (logger or _logger).debug(f"[_try_open_in_new_tab] tag_name extraction failed: {e}")

    # Determine OS-specific modifier key
    current_os = get_current_platform()
    modifier_key = Keys.COMMAND if current_os in [OperatingSystem.MACOS, OperatingSystem.IOS] else Keys.CONTROL

    _log = logger or _logger
    _log.debug(
        f"[_try_open_in_new_tab] Starting: "
        f"strategies={[s.name for s in strategy_order]}, "
        f"url={url}, tag={tag_name}, "
        f"handles_before={handles_before}"
    )

    # Try each strategy in order
    for strategy in strategy_order:

        # Strategy: URL extraction + window.open()
        if strategy == NewTabClickStrategy.URL_EXTRACT:
            if url:
                try:
                    driver.execute_script("window.open(arguments[0], '_blank');", url)
                    new_handles = _check_new_tab()
                    if new_handles:
                        _log.debug(f"[_try_open_in_new_tab] {strategy.name} succeeded: new_handles={new_handles}")
                        return (STRATEGY_TO_RESULT[strategy], new_handles)
                except Exception as e:
                    _log.debug(f"[_try_open_in_new_tab] {strategy.name} failed: {e}")

        # Strategy: Set target='_blank' on element + click
        elif strategy == NewTabClickStrategy.TARGET_BLANK:
            if tag_name == 'a':
                try:
                    current_target = element.get_attribute("target")
                    driver.execute_script("arguments[0].setAttribute('target','_blank');", element)

                    # Click using the implementation sequence with fallback
                    for _method in _implementations:
                        try:
                            if _method == ClickImplementation.NATIVE:
                                element.click()
                            elif _method == ClickImplementation.JAVASCRIPT:
                                driver.execute_script("arguments[0].click();", element)
                            elif _method == ClickImplementation.ACTION_CHAIN:
                                ActionChains(driver).move_to_element(element).pause(0.3).click().perform()
                            elif _method == ClickImplementation.EVENT_DISPATCH:
                                driver.execute_script(
                                    "var e = new MouseEvent('click', {bubbles: true, cancelable: true, view: window}); "
                                    "arguments[0].dispatchEvent(e);", element
                                )
                            break
                        except (ElementClickInterceptedException, ElementNotInteractableException):
                            continue

                    # Restore original target
                    if current_target:
                        driver.execute_script(f"arguments[0].setAttribute('target','{current_target}');", element)
                    else:
                        driver.execute_script("arguments[0].removeAttribute('target');", element)

                    new_handles = _check_new_tab()
                    if new_handles:
                        _log.debug(f"[_try_open_in_new_tab] {strategy.name} succeeded: new_handles={new_handles}")
                        return (STRATEGY_TO_RESULT[strategy], new_handles)
                except Exception as e:
                    _log.debug(f"[_try_open_in_new_tab] {strategy.name} failed: {e}")

        # Strategy: Modifier key (Ctrl/Cmd) + click
        elif strategy == NewTabClickStrategy.MODIFIER_KEY:
            if _prefer_js:
                # Try JS-based modifier click first
                try:
                    driver.execute_script("""
                        var element = arguments[0];
                        var evt = new MouseEvent('click', {
                            bubbles: true,
                            cancelable: true,
                            view: window,
                            ctrlKey: arguments[1],
                            metaKey: arguments[2]
                        });
                        element.dispatchEvent(evt);
                    """, element,
                        current_os not in [OperatingSystem.MACOS, OperatingSystem.IOS],  # ctrlKey for non-Mac
                        current_os in [OperatingSystem.MACOS, OperatingSystem.IOS]  # metaKey for Mac
                    )
                    new_handles = _check_new_tab()
                    if new_handles:
                        _log.debug(f"[_try_open_in_new_tab] {strategy.name} (JS) succeeded: new_handles={new_handles}")
                        return (STRATEGY_TO_RESULT[strategy], new_handles)
                except Exception as e:
                    _log.debug(f"[_try_open_in_new_tab] {strategy.name} (JS) failed: {e}")

                # Fallback to ActionChains
                try:
                    ActionChains(driver) \
                        .key_down(modifier_key) \
                        .click(element) \
                        .key_up(modifier_key) \
                        .perform()
                    new_handles = _check_new_tab()
                    if new_handles:
                        _log.debug(f"[_try_open_in_new_tab] {strategy.name} (ActionChains) succeeded: new_handles={new_handles}")
                        return (STRATEGY_TO_RESULT[strategy], new_handles)
                except Exception as e:
                    _log.debug(f"[_try_open_in_new_tab] {strategy.name} (ActionChains) failed: {e}")
            else:
                # Try ActionChains first
                try:
                    ActionChains(driver) \
                        .key_down(modifier_key) \
                        .click(element) \
                        .key_up(modifier_key) \
                        .perform()
                    new_handles = _check_new_tab()
                    if new_handles:
                        _log.debug(f"[_try_open_in_new_tab] {strategy.name} (ActionChains) succeeded: new_handles={new_handles}")
                        return (STRATEGY_TO_RESULT[strategy], new_handles)
                except Exception as e:
                    _log.debug(f"[_try_open_in_new_tab] {strategy.name} (ActionChains) failed: {e}")

                # Fallback to JS-based modifier click
                try:
                    driver.execute_script("""
                        var element = arguments[0];
                        var evt = new MouseEvent('click', {
                            bubbles: true,
                            cancelable: true,
                            view: window,
                            ctrlKey: arguments[1],
                            metaKey: arguments[2]
                        });
                        element.dispatchEvent(evt);
                    """, element,
                        current_os not in [OperatingSystem.MACOS, OperatingSystem.IOS],
                        current_os in [OperatingSystem.MACOS, OperatingSystem.IOS]
                    )
                    new_handles = _check_new_tab()
                    if new_handles:
                        _log.debug(f"[_try_open_in_new_tab] {strategy.name} (JS) succeeded: new_handles={new_handles}")
                        return (STRATEGY_TO_RESULT[strategy], new_handles)
                except Exception as e:
                    _log.debug(f"[_try_open_in_new_tab] {strategy.name} (JS) failed: {e}")

        # Strategy: CDP Target.createTarget (Chrome/Chromium only)
        elif strategy == NewTabClickStrategy.CDP_CREATE_TARGET:
            if url and is_chromium_based_driver(driver):
                try:
                    result = driver.execute_cdp_cmd("Target.createTarget", {"url": url})
                    target_id = result.get("targetId")
                    if target_id:
                        new_handles = _check_new_tab()
                        if new_handles:
                            _log.debug(f"[_try_open_in_new_tab] {strategy.name} succeeded: new_handles={new_handles}")
                            return (STRATEGY_TO_RESULT[strategy], new_handles)
                except Exception as e:
                    _log.debug(f"[_try_open_in_new_tab] {strategy.name} failed: {e}")

        # Strategy: Middle mouse button click
        elif strategy == NewTabClickStrategy.MIDDLE_CLICK:
            try:
                driver.execute_script("""
                    var element = arguments[0];
                    var evt = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window,
                        button: 1
                    });
                    element.dispatchEvent(evt);
                """, element)
                new_handles = _check_new_tab()
                if new_handles:
                    _log.debug(f"[_try_open_in_new_tab] {strategy.name} succeeded: new_handles={new_handles}")
                    return (STRATEGY_TO_RESULT[strategy], new_handles)
            except Exception as e:
                _log.debug(f"[_try_open_in_new_tab] {strategy.name} failed: {e}")

    _log.debug("[_try_open_in_new_tab] All strategies exhausted, no new tab opened")
    return (NewTabClickResult.FAILED, [])


def click_element(
        driver: WebDriver,
        element: WebElement,
        try_open_in_new_tab: Union[bool, OpenInNewTabMode] = False,
        wait_before_checking_new_tab: float = 0.5,
        additional_max_wait_for_tab_timeout: float = 5.0,
        only_enable_additional_wait_for_non_anchor_links: bool = True,
        implementation: Union[ClickImplementation, Tuple[ClickImplementation, ...]] = DEFAULT_CLICK_IMPLEMENTATION_ORDER,
        new_tab_strategy_order: Tuple[NewTabClickStrategy, ...] = DEFAULT_NEW_TAB_STRATEGY_ORDER,
        return_strategy_result: bool = False,
        new_tab_fallback_to_normal_click: Union[bool, str, NewTabFallbackMode] = False,
        raise_exception: bool = False,
        logger: 'Union[logging.Logger, Debuggable, None]' = None
) -> Union[Optional[List[str]], Tuple[Optional[List[str]], NewTabClickResult]]:
    """
    Clicks a Selenium WebElement, optionally opening it in a new browser tab, and returns any newly opened tab handles.

    **Workflow**:
      1. Scroll the element into view (centering it) to reduce click interception issues.
      2. Click the element, using either a normal click or a "new-tab" click strategy:
         - If ``try_open_in_new_tab`` is enabled (see parameter info below),
           multiple strategies are attempted in the order specified by ``new_tab_strategy_order``.
      3. Optionally wait for newly opened tabs to appear, then return a list of those tab handles.

    **New Tab Behavior**:
      - Setting ``try_open_in_new_tab`` to ``True`` or ``OpenInNewTabMode.ENABLED`` forces
        a new-tab click for all elements.
      - ``OpenInNewTabMode.ENABLED_FOR_NON_SAME_PAGE_INTERACTION`` attempts new-tab clicks
        only if the element is likely to navigate away from the current page (e.g., external link).
      - ``OpenInNewTabMode.ENABLED_FOR_INTERACTABLE`` attempts new-tab clicks
        if the element is not classified as ``NO_INTERACTION``.

    **Returns**:
      - A list of newly opened window handles if a new tab was opened.
      - An empty list otherwise.
      - If ``return_strategy_result=True``, returns a tuple of (handles, strategy_result).
      - If you want to interact with the newly opened tab, note that this function automatically
        switches the driver context to the first new tab it finds.

    Args:
        driver (WebDriver):
            The Selenium WebDriver instance controlling the browser.
        element (WebElement):
            The web element to be clicked.
        try_open_in_new_tab (Union[bool, OpenInNewTabMode], optional):
            Determines whether to attempt opening the element in a new tab. Defaults to ``False``.
            Possible values:
              - ``False`` or ``OpenInNewTabMode.DISABLED``: normal click (no new tab).
              - ``True`` or ``OpenInNewTabMode.ENABLED``: always attempt new-tab click.
              - ``OpenInNewTabMode.ENABLED_FOR_NON_SAME_PAGE_INTERACTION``:
                only open in a new tab if the element is likely to navigate elsewhere.
              - ``OpenInNewTabMode.ENABLED_FOR_INTERACTABLE``:
                open in a new tab if the element is not classified as ``NO_INTERACTION``.
        wait_before_checking_new_tab (float, optional):
            Sleep time (seconds) immediately after clicking, before checking for new tabs. Defaults to 0.5.
        additional_max_wait_for_tab_timeout (float, optional):
            Additional time (seconds) to wait for a new tab to appear after the initial wait.
            If 0, no extra wait is performed. Defaults to 5.0.
        only_enable_additional_wait_for_non_anchor_links (bool, optional):
            If ``True``, the additional tab wait is applied only if the element is not a same-page anchor link.
            Defaults to ``True``.
        implementation (Union[ClickImplementation, Tuple[ClickImplementation, ...]], optional):
            Controls the click execution implementation and fallback order.
            Accepts a single ClickImplementation (no fallback) or a tuple of ClickImplementation
            values (tried in order on ElementClickInterceptedException /
            ElementNotInteractableException).
            Available implementations:
              - ``ClickImplementation.NATIVE``: element.click() (Selenium WebDriver native click)
              - ``ClickImplementation.JAVASCRIPT``: driver.execute_script("arguments[0].click();")
              - ``ClickImplementation.ACTION_CHAIN``: ActionChains move_to_element + pause + click
              - ``ClickImplementation.EVENT_DISPATCH``: synthetic MouseEvent via dispatchEvent
            Defaults to ``DEFAULT_CLICK_IMPLEMENTATION_ORDER = (NATIVE, JAVASCRIPT)``.
            This affects both normal clicks and new-tab strategies that have
            implementation variants (TARGET_BLANK, MODIFIER_KEY).
        new_tab_strategy_order (Tuple[NewTabClickStrategy, ...], optional):
            Order in which to try new-tab strategies. Defaults to DEFAULT_NEW_TAB_STRATEGY_ORDER.
            Available strategies: URL_EXTRACT, TARGET_BLANK, MODIFIER_KEY, CDP_CREATE_TARGET, MIDDLE_CLICK.
            Can be customized to prioritize different strategies or exclude some.
        return_strategy_result (bool, optional):
            If ``True``, returns a tuple of (new_handles, strategy_result) instead of just new_handles.
            Useful for debugging which strategy succeeded. Defaults to ``False``.
        new_tab_fallback_to_normal_click (Union[bool, str, NewTabFallbackMode], optional):
            When all new-tab strategies fail, fall back to a normal click if the page is unchanged.
            Defaults to ``False`` (no fallback — current behavior).
            Possible values:
              - ``False`` or ``NewTabFallbackMode.DISABLED``: no fallback.
              - ``True`` or ``NewTabFallbackMode.ENABLED_WHEN_NO_TEXT_CHANGE``:
                fallback if URL unchanged AND ``document.body.innerText`` unchanged.
              - ``NewTabFallbackMode.ENABLED_WHEN_NO_HTML_CHANGE`` or ``"no_html_change"``:
                fallback if URL unchanged AND ``document.documentElement.outerHTML`` unchanged.

    Returns:
        Union[Optional[List[str]], Tuple[Optional[List[str]], NewTabClickResult]]:
            - If ``return_strategy_result=False``: A list of newly opened browser tab handles, or empty list.
            - If ``return_strategy_result=True``: A tuple of (handles, NewTabClickResult).
    """
    # region STEP0: Setup
    handles_before = driver.window_handles.copy()
    _log = logger or _logger

    # endregion

    # region STEP1: Normalize arguments
    element_type = get_element_interaction_type(element, driver)
    is_non_same_page_interaction = (element_type in (
        ElementInteractionTypes.EXTERNAL_DOMAIN_LINK,
        ElementInteractionTypes.SAME_DOMAIN_LINK,
        ElementInteractionTypes.UNKNOWN_INTERACTABLE
    ))

    if not isinstance(try_open_in_new_tab, bool):
        if try_open_in_new_tab == OpenInNewTabMode.ENABLED_FOR_NON_SAME_PAGE_INTERACTION:
            try_open_in_new_tab = is_non_same_page_interaction
        elif try_open_in_new_tab == OpenInNewTabMode.ENABLED_FOR_INTERACTABLE:
            try_open_in_new_tab = (element_type != ElementInteractionTypes.NO_INTERACTION)
        elif try_open_in_new_tab == OpenInNewTabMode.ENABLED:
            try_open_in_new_tab = True
        else:
            try_open_in_new_tab = False

    _log.debug(
        f"[click_element] element_type={element_type.name}, "
        f"is_non_same_page={is_non_same_page_interaction}, "
        f"try_open_in_new_tab={try_open_in_new_tab}"
    )

    if only_enable_additional_wait_for_non_anchor_links and (not is_non_same_page_interaction):
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
    if try_open_in_new_tab and _fallback_enabled:
        _fallback_url_before = driver.current_url
        if _use_text_fallback:
            _fallback_content_before = get_body_text(driver)
        else:
            _fallback_content_before = get_body_html(driver)

    # endregion

    # region STEP2: Center the element in view
    center_element_in_view(driver, element)
    # endregion

    strategy_result = NewTabClickResult.FAILED
    new_handles = []

    if try_open_in_new_tab:
        # region STEP3a: New-tab click using multi-strategy approach
        strategy_result, new_handles = _try_open_in_new_tab(
            driver=driver,
            element=element,
            handles_before=handles_before,
            wait_time=wait_before_checking_new_tab,
            strategy_order=new_tab_strategy_order,
            implementation=implementation,
            logger=logger
        )

        _log.debug(
            f"[click_element] New-tab result: strategy={strategy_result.name}, "
            f"new_handles={new_handles}"
        )

        # Additional wait if no new tab yet and timeout is configured
        if not new_handles and additional_max_wait_for_tab_timeout:
            _log.debug(f"[click_element] No new tab yet, waiting up to {additional_max_wait_for_tab_timeout}s")
            try:
                wait = WebDriverWait(driver, additional_max_wait_for_tab_timeout)

                def _new_tab_appeared(_driver: WebDriver):
                    handles_after = _driver.window_handles
                    newly_opened_handles = set(handles_after) - set(handles_before)
                    return bool(newly_opened_handles)

                wait.until(_new_tab_appeared)

                # Re-check for new handles after additional wait
                handles_after = driver.window_handles
                new_handles = [h for h in handles_after if h not in handles_before]
            except TimeoutException:
                pass

        # Switch to new tab if one was opened
        if new_handles:
            _log.debug(f"[click_element] Switching to new tab: {new_handles[0]}")
            driver.switch_to.window(new_handles[0])
        elif _fallback_enabled and _fallback_url_before is not None:
            # All new-tab strategies failed — check if page is unchanged and fall back to normal click.
            # By this point, ~6.5s have elapsed (strategy waits + additional_max_wait polling),
            # giving ample time for any page reactions to manifest.
            time.sleep(wait_before_checking_new_tab)
            url_changed = (driver.current_url != _fallback_url_before)
            if not url_changed:
                if _use_text_fallback:
                    current_content = get_body_text(driver)
                else:
                    current_content = get_body_html(driver)
                content_changed = (current_content != _fallback_content_before)
                if not content_changed:
                    _log.debug("[click_element] New-tab failed, url and content unchanged — falling back to normal click")
                    try:
                        _click_element(driver, element, implementation)
                    except (ElementClickInterceptedException, ElementNotInteractableException) as exc:
                        if raise_exception:
                            raise
                        _log.warning(f"All click implementations exhausted. Last exception: {exc}")
                else:
                    _log.debug("[click_element] New-tab failed, but content changed — NOT falling back")
            else:
                _log.debug(f"[click_element] New-tab failed, but url changed ({_fallback_url_before} → {driver.current_url}) — NOT falling back")
        # endregion
    else:
        # STEP3b: Normal click
        try:
            _click_element(driver, element, implementation)
        except (ElementClickInterceptedException, ElementNotInteractableException) as exc:
            if raise_exception:
                raise
            _log.warning(f"All click implementations exhausted. Last exception: {exc}")

    _log.debug(
        f"[click_element] RETURNING: new_handles={new_handles if new_handles else []}, "
        f"strategy={strategy_result.name}"
    )
    if return_strategy_result:
        return (new_handles if new_handles else [], strategy_result)
    return new_handles if new_handles else []


def _click_element(
        driver: WebDriver,
        element: WebElement,
        implementation: Union[ClickImplementation, Tuple[ClickImplementation, ...]] = DEFAULT_CLICK_IMPLEMENTATION_ORDER,
        raise_exception: bool = True,
):
    """Lightweight click with fallback chain.

    Tries each implementation in order, falling back on
    ``ElementClickInterceptedException`` or ``ElementNotInteractableException``.

    This is the core click logic used by :func:`click_element` (which adds
    tab handling, waits, and strategy chains on top) and by :func:`input_text`
    (which just needs a resilient focus-click before typing).

    Args:
        driver: WebDriver instance.
        element: The WebElement to click.
        implementation: Click implementation(s) to try in order.
        raise_exception: If True, raises the last exception when all
            implementations fail. If False, silently returns. Defaults to True.
    """
    methods = (implementation,) if isinstance(implementation, ClickImplementation) else implementation
    last_exc = None
    for method in methods:
        try:
            if method == ClickImplementation.NATIVE:
                element.click()
            elif method == ClickImplementation.JAVASCRIPT:
                driver.execute_script("arguments[0].click();", element)
            elif method == ClickImplementation.ACTION_CHAIN:
                ActionChains(driver).move_to_element(element).pause(0.3).click().perform()
            elif method == ClickImplementation.EVENT_DISPATCH:
                driver.execute_script(
                    "var e = new MouseEvent('click', {bubbles: true, cancelable: true, view: window}); "
                    "arguments[0].dispatchEvent(e);", element
                )
            return  # Success
        except (ElementClickInterceptedException, ElementNotInteractableException) as exc:
            last_exc = exc
            continue
        except ReadTimeoutError:
            return  # Timeout is non-recoverable
    if last_exc is not None and raise_exception:
        raise last_exc


def _verify_input_value(element: WebElement, expected_text: str, was_cleared: bool) -> None:
    """Check that the element's value matches what was typed and log a warning on mismatch."""
    try:
        actual = element.get_property('value')
    except Exception:
        return  # Element may have been detached or is not an input; skip verification

    if actual is None:
        return

    if was_cleared:
        # When clearing was requested, the final value should be exactly the typed text
        if actual != expected_text:
            _logger.warning(
                "Input verification mismatch: expected %r but got %r "
                "(element.clear/select-all may not have worked on this input)",
                expected_text, actual
            )
    else:
        # When not clearing, text was appended; just check it ends with the typed text
        if not actual.endswith(expected_text):
            _logger.warning(
                "Input verification mismatch: expected value to end with %r but got %r",
                expected_text, actual
            )


def send_keys_with_random_delay(
        driver: WebDriver,
        element: WebElement,
        text: str,
        min_delay: float = 0.1,
        max_delay: float = 1,
        clear_content: bool = False,
        clear_method: ClearMethod = ClearMethod.SELECT_ALL,
        verify_input: bool = True,
        raise_exception: bool = False,
):
    """Send keys to an element, character by character, with a random delay between each key.

    Args:
        driver: WebDriver instance (needed for click fallback).
        element: The WebElement where text will be sent.
        text: The string to send to the element.
        min_delay (float): Minimum delay between key presses in seconds.
        max_delay (float): Maximum delay between key presses in seconds.
        clear_content (bool): Whether to clear the existing content before typing.
        clear_method: Strategy for clearing content. ``SELECT_ALL`` (default) uses
            Ctrl+A/Cmd+A so the first typed character replaces the selection;
            ``ELEMENT_CLEAR`` uses Selenium's ``element.clear()``.
        verify_input: If True (default), reads the element's value after typing
            and logs a warning if it doesn't match the expected text.
        raise_exception: If True, raises on click failure. If False (default),
            warns and skips typing.
    """
    try:
        _click_element(driver, element)
    except (ElementClickInterceptedException, ElementNotInteractableException):
        if raise_exception:
            raise
        warnings.warn(f"Element '{get_element_html(element)}' is not interactable")
        random_sleep(min_delay, max_delay)
        return

    if clear_content:
        if clear_method == ClearMethod.SELECT_ALL:
            element.send_keys(_get_select_all_keys())
            random_sleep(min_delay, max_delay)
        else:
            element.clear()
    random_sleep(min_delay, max_delay)
    for char in text:
        element.send_keys(char)
        random_sleep(min_delay, max_delay)

    if verify_input:
        _verify_input_value(element, text, clear_content)


def input_text(
        driver: WebDriver,
        element: WebElement,
        text: str,
        clear_content: bool = False,
        clear_method: ClearMethod = ClearMethod.SELECT_ALL,
        verify_input: bool = True,
        implementation: str = 'auto',
        default_implementation: str = 'send_keys',
        fast_implementation: str = 'send_keys_fast',
        fast_threshold: int = 20,
        min_delay: float = 0.1,
        max_delay: float = 1,
        sanitize: bool = True,
        auto_sanitization: bool = True,
        non_bmp_handling: NonBMPHandling = NonBMPHandling.REMOVE,
        newline_handling: NewlineHandling = NewlineHandling.SPACE,
        whitespace_handling: WhitespaceHandling = WhitespaceHandling.NORMALIZE
):
    """
    Generic master function for inputting text into an element with different implementation strategies.

    Args:
        driver: WebDriver instance (needed for JavaScript implementation)
        element: The WebElement where text will be input
        text: The string to input to the element
        clear_content: Whether to clear existing content before inputting
        implementation: Implementation strategy to use:
            - 'send_keys': Character-by-character with random delays (most human-like, slowest)
            - 'send_keys_fast': Send entire string at once (faster, still triggers events)
            - 'javascript': Direct value setting via JavaScript (fastest, triggers change events)
            - 'auto': Automatically choose based on text length (default)
        default_implementation: Implementation to use for short text in auto mode (default: 'send_keys')
        fast_implementation: Implementation to use for long text in auto mode (default: 'javascript')
        fast_threshold: Text length threshold for auto mode (default: 20)
            - Text shorter than threshold uses default_implementation
            - Text longer than threshold uses fast_implementation
        min_delay: Minimum delay between keystrokes (for 'send_keys' mode)
        max_delay: Maximum delay between keystrokes (for 'send_keys' mode)
        sanitize: Whether to sanitize text at all (default: True)
            When False, no sanitization is applied (may cause errors with send_keys).
        auto_sanitization: Whether to use implementation-aware sanitization (default: True)
            - True: Automatically choose optimal sanitization based on implementation:
                - send_keys/send_keys_fast: Remove non-BMP, replace newlines with space
                - javascript: Keep non-BMP and newlines (only remove control chars)
              When True, the non_bmp_handling, newline_handling, whitespace_handling
              parameters are ignored.
            - False: Use the explicit sanitization parameters provided below.
              Use this when you need precise control over sanitization behavior.
        non_bmp_handling: How to handle non-BMP characters (only used when auto_sanitization=False)
            - KEEP: Keep non-BMP characters (only safe with javascript implementation)
            - REMOVE: Remove non-BMP characters entirely
            - REPLACE: Replace with a placeholder character
            - TRANSLITERATE: Convert emoji to text (e.g., :smile:)
            - RAISE: Raise exception if non-BMP found
        newline_handling: How to handle newlines (only used when auto_sanitization=False)
            - KEEP: Keep newlines as-is
            - SPACE: Replace with single space
            - REMOVE: Remove entirely
            - NORMALIZE: Convert all to \\n
        whitespace_handling: How to handle whitespace (only used when auto_sanitization=False)
            - KEEP: Keep as-is
            - NORMALIZE: Collapse multiple spaces to single
            - STRIP: Strip leading/trailing only
            - FULL: Both normalize and strip

    Examples:
        # Human-like typing for short user input
        input_text(driver, element, "Hello", implementation='send_keys')

        # Fast input for large attachments
        input_text(driver, element, large_attachment_text, implementation='javascript')

        # Auto-select based on length (default behavior)
        input_text(driver, element, text, implementation='auto')

        # Custom auto mode configuration
        input_text(driver, element, text,
                   default_implementation='send_keys_fast',
                   fast_implementation='javascript',
                   fast_threshold=100)

        # Manual sanitization control - preserve newlines for multi-line text areas
        input_text(driver, element, text,
                   auto_sanitization=False,
                   newline_handling=NewlineHandling.KEEP,
                   whitespace_handling=WhitespaceHandling.KEEP)

        # Manual sanitization control - transliterate emoji instead of removing
        input_text(driver, element, "Hello ",
                   auto_sanitization=False,
                   non_bmp_handling=NonBMPHandling.TRANSLITERATE)

    Comparison with Playwright:
        Both backends have compatible signatures. Key differences:

        | Aspect                | Selenium                          | Playwright                        |
        |-----------------------|-----------------------------------|-----------------------------------|
        | Non-BMP (emoji)       | REMOVE required (ChromeDriver)    | KEEP supported (native)           |
        | Delay implementation  | Manual loop with random_sleep()   | Native delay=ms parameter         |
        | JavaScript events     | Manual dispatchEvent()            | Automatic via fill()              |
        | Append mode           | send_keys() naturally appends     | fill() clears, needs workaround   |

        See: webaxon/automation/backends/docs/input_text_comparison.md for full details.
    """
    # Auto-select implementation based on text length (before sanitization to determine strategy)
    if implementation == 'auto':
        implementation = default_implementation if len(text) <= fast_threshold else fast_implementation

    # Apply sanitization if enabled
    if sanitize:
        if auto_sanitization:
            # Implementation-aware sanitization: choose optimal settings based on implementation
            # - send_keys/send_keys_fast: Must remove non-BMP (ChromeDriver limitation), newlines act as Enter
            # - javascript: Can handle non-BMP and newlines natively (sets element.value directly)
            if implementation in ('send_keys', 'send_keys_fast'):
                text = sanitize_input_text_for_webdriver(
                    text,
                    non_bmp_handling=NonBMPHandling.REMOVE,
                    newline_handling=NewlineHandling.SPACE,
                    whitespace_handling=WhitespaceHandling.NORMALIZE,
                    remove_control_chars=True
                )
            elif implementation == 'javascript':
                text = sanitize_input_text_for_webdriver(
                    text,
                    non_bmp_handling=NonBMPHandling.KEEP,
                    newline_handling=NewlineHandling.KEEP,
                    whitespace_handling=WhitespaceHandling.KEEP,
                    remove_control_chars=True
                )
        else:
            # Manual sanitization: use user-provided parameters exactly
            text = sanitize_input_text_for_webdriver(
                text,
                non_bmp_handling=non_bmp_handling,
                newline_handling=newline_handling,
                whitespace_handling=whitespace_handling,
                remove_control_chars=True
            )

    try:
        if implementation == 'send_keys':
            # Character-by-character with random delays (most human-like)
            send_keys_with_random_delay(
                driver=driver,
                element=element,
                text=text,
                clear_content=clear_content,
                clear_method=clear_method,
                verify_input=verify_input,
                min_delay=min_delay,
                max_delay=max_delay
            )

        elif implementation == 'send_keys_fast':
            # Send entire string at once (faster, still triggers keyboard events)
            _click_element(driver, element)
            if clear_content:
                if clear_method == ClearMethod.SELECT_ALL:
                    element.send_keys(_get_select_all_keys())
                else:
                    element.clear()
            element.send_keys(text)
            if verify_input:
                _verify_input_value(element, text, clear_content)

        elif implementation == 'javascript':
            # Direct value setting via JavaScript (fastest)
            _click_element(driver, element)  # Focus the element
            driver.execute_script("""
                const element = arguments[0];
                const text = arguments[1];
                const clearFirst = arguments[2];

                if (clearFirst) {
                    element.value = '';
                }
                element.value = text;

                // Trigger events for frameworks like React/Vue/Angular
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
                element.dispatchEvent(new Event('blur', { bubbles: true }));
            """, element, text, clear_content)
            if verify_input:
                _verify_input_value(element, text, clear_content)

        else:
            raise ValueError(
                f"Invalid implementation '{implementation}'. "
                f"Must be one of: 'send_keys', 'send_keys_fast', 'javascript', 'auto'"
            )
    except (ElementClickInterceptedException, ElementNotInteractableException):
        warnings.warn(f"Element '{get_element_html(element)}' is not interactable")
        random_sleep(min_delay, max_delay)
        return


def center_element_in_view(driver: WebDriver, element: WebElement) -> None:
    """
    Scrolls the given WebElement into the center of the view.

    Args:
        driver (WebDriver): The Selenium WebDriver instance.
        element (WebElement): The WebElement to bring to the center of the view.
    """
    driver.execute_script("""
        var element = arguments[0];
        element.scrollIntoView({block: 'center', inline: 'center', behavior: 'smooth'});
    """, element)


def _scroll_element_with_javascript(
        driver: WebDriver,
        element: WebElement,
        direction: str,
        distance: str,
        relative_distance: bool = False
) -> None:
    """
    Scroll using JavaScript execution.

    Pros: Most flexible, works on any element including virtual lists
    Cons: Less "native" than other approaches

    Note: Always attempts to scroll the element first. If the element cannot scroll,
    the scrollBy() call safely does nothing.
    """
    # Get viewport dimensions for distance calculation
    viewport_width, viewport_height = get_viewport_size(driver)

    if relative_distance and distance in ['Small', 'Medium', 'Large']:
        # Use relative distance (percentage-based) JavaScript
        driver.execute_script("""
            var element = arguments[0];
            var direction = arguments[1];
            var distance = arguments[2];

            // Map distance to percentage
            var percentages = {'Small': 0.30, 'Medium': 0.60, 'Large': 0.90};
            var percentage = percentages[distance];

            // Use element's client dimensions as reference
            var referenceHeight = element.clientHeight;
            var referenceWidth = element.clientWidth;

            // Calculate scroll amount based on percentage
            var scrollAmount = (direction === 'Up' || direction === 'Down') ?
                              referenceHeight * percentage :
                              referenceWidth * percentage;

            // Determine scroll deltas
            var deltaX = 0;
            var deltaY = 0;

            if (direction === 'Down') {
                deltaY = scrollAmount;
            } else if (direction === 'Up') {
                deltaY = -scrollAmount;
            } else if (direction === 'Right') {
                deltaX = scrollAmount;
            } else if (direction === 'Left') {
                deltaX = -scrollAmount;
            }

            // Always try to scroll the element
            // If it can't scroll, this safely does nothing
            element.scrollBy({
                top: deltaY,
                left: deltaX,
                behavior: 'smooth'
            });
        """, element, direction, distance)
    else:
        # Use fixed distance (pixel-based) JavaScript
        driver.execute_script("""
            var element = arguments[0];
            var direction = arguments[1];
            var distance = arguments[2];
            var viewportWidth = arguments[3];
            var viewportHeight = arguments[4];

            // Map distance to scroll amount
            var scrollAmount;
            if (distance === 'Small') {
                scrollAmount = 600;  // 1 scroll unit
            } else if (distance === 'Medium') {
                scrollAmount = 1800;  // 2 scroll units (default)
            } else if (distance === 'Large') {
                scrollAmount = 3600;  // 6 scroll units
            } else if (distance === 'Half') {
                scrollAmount = (direction === 'Up' || direction === 'Down') ?
                              viewportHeight / 2 : viewportWidth / 2;
            } else if (distance === 'Full') {
                scrollAmount = (direction === 'Up' || direction === 'Down') ?
                              viewportHeight : viewportWidth;
            }

            // Determine scroll deltas
            var deltaX = 0;
            var deltaY = 0;

            if (direction === 'Down') {
                deltaY = scrollAmount;
            } else if (direction === 'Up') {
                deltaY = -scrollAmount;
            } else if (direction === 'Right') {
                deltaX = scrollAmount;
            } else if (direction === 'Left') {
                deltaX = -scrollAmount;
            }

            // Always try to scroll the element
            // If it can't scroll, this safely does nothing
            element.scrollBy({
                top: deltaY,
                left: deltaX,
                behavior: 'smooth'
            });
    """, element, direction, distance, viewport_width, viewport_height)


def _scroll_element_with_action_chains(
        driver: WebDriver,
        element: WebElement,
        direction: str,
        distance: str,
        relative_distance: bool = False,
        mode: str = 'from_origin'
) -> None:
    """
    Scroll targeting a specific element using Selenium ActionChains (Selenium 4+).

    Args:
        mode: How to target the element:
            - 'from_origin': Uses ScrollOrigin.from_element() to scroll from element's position
            - 'focus_first': Focuses element (by clicking) first, then scrolls

    Pros: Targets the element specifically, more reliable than viewport scroll
    Cons: Requires Selenium 4+, may not work with all elements
    """
    # Focus element first if requested
    if mode == 'focus_first':
        try:
            element.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            # If can't click, try to focus with JavaScript
            driver.execute_script("arguments[0].focus();", element)
        time.sleep(0.1)  # Brief pause after focusing

    # Calculate scroll amount
    viewport_width, viewport_height = get_viewport_size(driver)

    if relative_distance and distance in ['Small', 'Medium', 'Large']:
        # Use relative distance (percentage of element size)
        percentage = RELATIVE_DISTANCE_PERCENTAGES[distance]
        # Get element dimensions for reference
        element_size = element.size
        element_height = element_size['height']
        element_width = element_size['width']
        ref_dimension = element_height if direction in ['Up', 'Down'] else element_width
        amount = int(ref_dimension * percentage)
    else:
        # Use fixed distance (pixels)
        distance_map = {
            'Small': 600,
            'Medium': 1800,
            'Large': 3600,
            'Half': viewport_height // 2 if direction in ['Up', 'Down'] else viewport_width // 2,
            'Full': viewport_height if direction in ['Up', 'Down'] else viewport_width
        }
        amount = distance_map.get(distance, 600)

    # Calculate deltas
    delta_x = amount if direction == 'Right' else (-amount if direction == 'Left' else 0)
    delta_y = amount if direction == 'Down' else (-amount if direction == 'Up' else 0)

    # Scroll based on mode
    if mode == 'from_origin':
        scroll_origin = ScrollOrigin.from_element(element)
        ActionChains(driver).scroll_from_origin(scroll_origin, delta_x, delta_y).perform()
    else:  # focus_first
        ActionChains(driver).scroll_by_amount(delta_x, delta_y).perform()


def _scroll_element_with_keystrokes(
        driver: WebDriver,
        element: WebElement,
        direction: str,
        distance: str
) -> None:
    """
    Scroll using keyboard keystrokes.

    Pros: Simulates real user behavior, very simple
    Cons: Element must be focusable, no horizontal scrolling, less precise control
    """
    # Focus the element first
    try:
        element.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        # If can't click, try to focus with JavaScript
        driver.execute_script("arguments[0].focus();", element)

    time.sleep(0.1)

    # Map direction and distance to keystrokes
    if direction in ('Down', 'Up'):
        key = Keys.PAGE_DOWN if direction == 'Down' else Keys.PAGE_UP
        repetitions = {'Small': 1, 'Medium': 2, 'Large': 4, 'Half': 6, 'Full': 10}.get(distance, 2)
        for _ in range(repetitions):
            element.send_keys(key)
            time.sleep(0.5)
    elif direction in ['Left', 'Right']:
        # Horizontal scrolling with keystrokes is limited
        # Try arrow keys multiple times
        key = Keys.ARROW_LEFT if direction == 'Left' else Keys.ARROW_RIGHT
        repetitions = {'Small': 5, 'Medium': 10, 'Large': 20, 'Half': 15, 'Full': 30}.get(distance, 10)
        for _ in range(repetitions):
            element.send_keys(key)
            time.sleep(0.1)


def scroll_element(
        driver: WebDriver,
        element: WebElement,
        direction: str = 'Down',
        distance: str = 'Large',
        implementation: str = 'javascript',
        relative_distance: bool = False,
        try_solve_scrollable_child: Union[bool, str] = True
) -> None:
    """
    Master scroll function that scrolls an element or viewport using the specified implementation.

    Args:
        driver (WebDriver): The Selenium WebDriver instance.
        element (WebElement): The WebElement to scroll or scroll relative to.
        direction (str): Scroll direction - 'Up', 'Down', 'Left', or 'Right'. Defaults to 'Down'.
        distance (str): Scroll distance - 'Small' (1 unit), 'Medium' (2 units), 'Large' (4 units),
                       'Half' (0.5 viewport), or 'Full' (1 viewport). Defaults to 'Large'.
        implementation (str): Scroll implementation method. Defaults to 'javascript'.
            Available methods:
            - 'javascript': Calls element.scrollBy() directly, works with virtual lists
            - 'action_chains_from_origin': Scrolls from element origin using ScrollOrigin.from_element()
            - 'action_chains_focus_first': Focuses element (clicks it) first, then scrolls viewport
            - 'keystrokes': Sends keyboard keys (PAGE_DOWN, etc.) to element
        relative_distance (bool): If True, Small/Medium/Large distances are calculated as percentages
                                 of viewport/container height (30%/60%/90%) rather than fixed pixel
                                 values (600/1800/3600).
                                 - 'javascript': Uses element.clientHeight as reference
                                 - 'action_chains_from_origin': Uses element height as reference
                                 - 'action_chains_focus_first': Uses element height as reference
                                 - 'keystrokes': Ignored (uses fixed repetition counts)
                                 Defaults to False.
        try_solve_scrollable_child (Union[bool, str]): Whether to attempt finding the actual scrollable
                                                       child element. Defaults to True.
            - False: Don't solve, use the original element
            - True: Use default strategy ('first_largest_scrollable')
            - Strategy name: Use specific strategy ('first_scrollable', 'first_largest_scrollable',
                           'deepest_scrollable', 'largest_scrollable', 'largest_scrollable_early_stop')

    Implementation Details:
        - 'javascript': Best for scrollable elements including virtual lists (Slack, etc.)
        - 'action_chains_from_origin': Targets element using ScrollOrigin (Selenium 4+ required)
        - 'action_chains_focus_first': May work if focusing changes scroll target
        - 'keystrokes': Most natural, requires focusable element
    """
    # Normalize inputs
    direction = direction.capitalize() if direction else 'Down'
    distance = distance.capitalize() if distance else 'Medium'
    implementation = implementation.lower() if implementation else 'javascript'

    # Validate direction
    if direction not in ['Up', 'Down', 'Left', 'Right']:
        print(f"[Warning] Invalid scroll direction '{direction}', defaulting to 'Down'")
        direction = 'Down'

    # Validate distance
    if distance not in ['Small', 'Medium', 'Large', 'Half', 'Full']:
        print(f"[Warning] Invalid scroll distance '{distance}', defaulting to 'Medium'")
        distance = 'Medium'

    # Validate implementation
    valid_implementations = ['javascript', 'action_chains_from_origin', 'action_chains_focus_first', 'keystrokes']
    if implementation not in valid_implementations:
        print(f"[Warning] Invalid scroll implementation '{implementation}', defaulting to 'javascript'")
        implementation = 'javascript'

    # Solve for scrollable child if requested
    if try_solve_scrollable_child is not False:
        # Determine strategy
        if try_solve_scrollable_child is True:
            strategy = 'first_largest_scrollable'  # Default strategy
        else:
            strategy = try_solve_scrollable_child  # Use provided strategy name

        # Find the actual scrollable element (using builtin implementation by default)
        element = solve_scrollable_child(driver, element, strategy=strategy, implementation='builtin', direction=direction)

    # First ensure element is in view (except for keystroke and focus_first methods which handle focus differently)
    if implementation not in ['keystrokes', 'action_chains_focus_first']:
        center_element_in_view(driver, element)
        time.sleep(0.3)  # Allow smooth scroll to complete

    # Execute scroll using the specified implementation
    try:
        if implementation == 'javascript':
            _scroll_element_with_javascript(driver, element, direction, distance, relative_distance)
        elif implementation == 'action_chains_from_origin':
            _scroll_element_with_action_chains(driver, element, direction, distance, relative_distance, mode='from_origin')
        elif implementation == 'action_chains_focus_first':
            _scroll_element_with_action_chains(driver, element, direction, distance, relative_distance, mode='focus_first')
        elif implementation == 'keystrokes':
            _scroll_element_with_keystrokes(driver, element, direction, distance)

        # Wait for scroll to complete
        time.sleep(0.5)

    except Exception as e:
        print(f"[Warning] Scroll with {implementation} failed: {e}")
        # Fallback to JavaScript if the chosen method fails
        if implementation != 'javascript':
            print(f"[Info] Falling back to JavaScript scroll")
            _scroll_element_with_javascript(driver, element, direction, distance, relative_distance)
            time.sleep(0.5)


def set_zoom(driver: WebDriver, percentage: Union[int, float]) -> None:
    """
    Sets the zoom level of the webpage to the specified percentage.

    Args:
        driver (WebDriver): The Selenium WebDriver instance.
        percentage (int): The zoom level percentage (e.g., 100 for 100%).
    """
    if isinstance(percentage, float):
        if percentage <= 1:
            percentage = int(percentage * 100)
        else:
            percentage = int(percentage)
    zoom_script = f"document.body.style.zoom='{percentage}%'"
    driver.execute_script(zoom_script)


def get_zoom(driver: WebDriver) -> float:
    zoom = driver.execute_script("return document.body.style.zoom || '100%'").rstrip('%')
    return float(zoom) / 100


def get_viewport_size(driver: WebDriver) -> Tuple[int, int]:
    """
    Gets the viewport width and height of the current window.

    Args:
        driver (WebDriver): The Selenium WebDriver instance.

    Returns:
        tuple: A tuple containing the viewport width and height.
    """
    viewport_size = driver.execute_script("""
        return {
            width: window.innerWidth,
            height: window.innerHeight
        };
    """)
    return viewport_size['width'], viewport_size['height']


def zoom_out_to_fit_element(driver: WebDriver, element: WebElement, buffer: float = 0.05) -> None:
    """
    Zooms out the page until the given WebElement is entirely within the viewport,
    considering a buffer to zoom out more and taking into account the current zoom level.

    Args:
        driver (WebDriver): The Selenium WebDriver instance.
        element (WebElement): The WebElement to fit within the viewport.
        buffer (float): The additional zoom out factor. Defaults to 0.05 (5% more).
    """
    current_zoom = get_zoom(driver)

    driver.execute_script("""
        var element = arguments[0];
        var buffer = arguments[1];
        var currentZoom = arguments[2];
        var rect = element.getBoundingClientRect();
        var elementHeight = rect.height / currentZoom;
        var elementWidth = rect.width / currentZoom;
        var viewportHeight = window.innerHeight;
        var viewportWidth = window.innerWidth;
        var zoomFactor = Math.min(viewportHeight / elementHeight, viewportWidth / elementWidth);
        document.body.style.zoom = zoomFactor - buffer;
    """, element, buffer, current_zoom)


def capture_full_page_screenshot(
        driver: WebDriver,
        output_path,
        center_element: WebElement = None,
        restore_window_size: bool = False,
        reset_zoom: bool = True,
        use_cdp_cmd_for_chrome: bool = False,
        scale_based_on_content_size: bool = True,
        scale: float = 1.0
):
    if scale_based_on_content_size:
        scale *= 1 / driver.execute_script("return window.devicePixelRatio")

    if use_cdp_cmd_for_chrome and isinstance(driver, (webdriver.Chrome, uc.Chrome)):
        total_width = driver.execute_script("return document.body.parentNode.scrollWidth")
        total_height = driver.execute_script("return document.body.parentNode.scrollHeight")
        screenshot = base64.b64decode(driver.execute_cdp_cmd("Page.captureScreenshot", {
            "clip": {
                "x": 0,
                "y": 0,
                "width": total_width,
                "height": total_height,
                "scale": scale
            },
            "captureBeyondViewport": True
        })['data'])

        with open(output_path, "wb") as file:
            file.write(screenshot)
    else:
        original_size = driver.get_window_size()
        total_width = driver.execute_script('return document.body.parentNode.scrollWidth')
        total_height = driver.execute_script('return document.body.parentNode.scrollHeight')
        driver.set_window_size(total_width, total_height)
        time.sleep(3)
        page_zoomed = False
        if center_element is not None:
            zoom_out_to_fit_element(driver, center_element)
            center_element_in_view(driver, center_element)
            page_zoomed = True
        wait_for_page_loading(driver)

        screenshot = driver.get_screenshot_as_png()
        with open(output_path, "wb") as file:
            file.write(screenshot)

        if page_zoomed and reset_zoom:
            set_zoom(driver, 100)
            time.sleep(2)
            wait_for_page_loading(driver)
        if restore_window_size:
            driver.set_window_size(original_size['width'], original_size['height'])
            time.sleep(2)
            wait_for_page_loading(driver)


def open_url(
        driver: WebDriver,
        url: str = None,
        wait_after_opening_url: float = 0,
        try_open_in_new_tab: bool = False,
        logger: 'Union[logging.Logger, Debuggable, None]' = None
) -> Optional[List[str]]:
    """
    Open a URL in the browser, optionally in a new tab.

    Args:
        driver: Selenium WebDriver instance
        url: URL to open
        wait_after_opening_url: Time to wait after opening (seconds)
        try_open_in_new_tab: If True, opens URL in a new tab and switches to it.
                            If False, navigates current tab.
        logger: Optional logger (logging.Logger or Debuggable). Falls back to module _logger.

    Returns:
        List of new tab handles if opened in new tab, None otherwise
    """
    _log = logger or _logger
    new_handles = None
    _log.debug(f"[open_url] Called with url={url}, try_open_in_new_tab={try_open_in_new_tab}")
    if url:
        try:
            if try_open_in_new_tab:
                # Try multiple methods to create new tab (in order of reliability)
                handles_before = set(driver.window_handles)
                current_before = driver.current_window_handle
                _log.debug(f"[open_url] BEFORE: handles={handles_before}, current={current_before}")
                from time import sleep

                # Method 1: Selenium 4's native API (most reliable)
                # Uses WebDriver protocol directly, bypasses popup blockers
                try:
                    driver.switch_to.new_window('tab')
                    sleep(0.3)  # Brief pause for tab to initialize
                    handles_after = set(driver.window_handles)
                    new_handles = list(handles_after - handles_before)
                    _log.debug(f"[open_url] AFTER switch_to.new_window: handles={handles_after}, new_handles={new_handles}")
                except Exception as e:
                    _log.warning(f"[open_url] Method 1 (switch_to.new_window) failed: {e}")
                    new_handles = []

                # Method 2: window.open (fallback)
                if not new_handles:
                    _log.debug(f"[open_url] Trying Method 2: window.open('about:blank')")
                    try:
                        driver.execute_script("window.open('about:blank', '_blank');")
                        sleep(0.5)
                        handles_after = set(driver.window_handles)
                        new_handles = list(handles_after - handles_before)
                        _log.debug(f"[open_url] AFTER window.open: handles={handles_after}, new_handles={new_handles}")
                    except Exception as e:
                        _log.warning(f"[open_url] Method 2 (window.open) failed: {e}")

                # Method 3: Keyboard shortcut Ctrl+T/Cmd+T (last resort)
                if not new_handles:
                    _log.debug(f"[open_url] Trying Method 3: keyboard shortcut")
                    try:
                        # Try to focus the browser window first
                        try:
                            driver.switch_to.window(driver.current_window_handle)
                            driver.execute_script("window.focus();")
                        except Exception:
                            pass  # Continue even if focus fails

                        import platform
                        is_mac = platform.system().lower() == 'darwin'
                        if not is_mac:
                            platform_name = driver.capabilities.get('platformName', '').lower()
                            is_mac = any(x in platform_name for x in ['mac', 'darwin', 'osx'])
                        modifier_key = Keys.COMMAND if is_mac else Keys.CONTROL
                        _log.debug(f"[open_url] Using {'Cmd' if is_mac else 'Ctrl'}+T")
                        ActionChains(driver).key_down(modifier_key).send_keys('t').key_up(modifier_key).perform()
                        sleep(0.5)
                        handles_after = set(driver.window_handles)
                        new_handles = list(handles_after - handles_before)
                        _log.debug(f"[open_url] AFTER keyboard shortcut: handles={handles_after}, new_handles={new_handles}")
                    except Exception as e:
                        _log.warning(f"[open_url] Method 3 (keyboard shortcut) failed: {e}")

                # Switch to new tab and navigate, or fall back to current tab
                if new_handles:
                    driver.switch_to.window(new_handles[0])
                    _log.debug(f"[open_url] Switched to new tab: {new_handles[0]}, navigating to {url}")
                    driver.get(url)
                    _log.debug(f"[open_url] Navigation complete, current_now={driver.current_window_handle}")
                else:
                    _log.warning(f"[open_url] All methods failed! Falling back to current tab navigation.")
                    driver.get(url)
            else:
                driver.get(url)
                _log.debug(f"[open_url] Navigated current tab to {url}")

            if wait_after_opening_url:
                from time import sleep
                sleep(wait_after_opening_url)
        except TimeoutException:
            hprint_message('timeout', url)
            driver.execute_script('window.stop();')
    _log.debug(f"[open_url] RETURNING: new_handles={new_handles}, final_current={driver.current_window_handle}")
    return new_handles


class SearchProviders(StrEnum):
    """Supported search engine providers.

    Attributes:
        GOOGLE: Google search engine.
        BING: Bing search engine.
    """
    GOOGLE = "Google"
    BING = "Bing"


def search(
        driver: WebDriver,
        query: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sites: Optional[Iterable[str]] = None,
        provider: SearchProviders = SearchProviders.GOOGLE,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
        **other_search_args
):
    if provider == SearchProviders.GOOGLE:
        from webaxon.url_utils.search_urls.google_search_url import create_search_url
    elif provider == SearchProviders.BING:
        from webaxon.url_utils.search_urls.bing_search_url import create_search_url
    else:
        raise ValueError(f"Unsupported search provider '{provider}'")
    url = create_search_url(
        query=query,
        start_date=start_date,
        end_date=end_date,
        sites=sites,
        **other_search_args
    )
    open_url(driver, url, wait_after_opening_url=additional_wait_time)
    wait_for_page_loading(driver, timeout=timeout, additional_wait_time=additional_wait_time)


def execute_single_action(
        driver: WebDriver,
        element: Union[str, WebElement],
        action_type: str,
        action_args: Mapping = None,
        attachments: Sequence = None,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
        logger: 'Union[logging.Logger, Debuggable, None]' = None
) -> str:
    action_type = camel_to_snake_case(action_type)
    if not action_args:
        action_args = {}

    # Handle attachments for input-based actions only
    if attachments and action_type in ('input_text', 'append_text'):
        # Make action_args mutable
        action_args = dict(action_args)

        # Get original text and check for existing attachment IDs
        original_text = action_args.get('text', '')

        # Extract attachment text using utility function
        attachment_text = _get_attachments_text(attachments, original_text, separator='\n\n')

        # Append attachment text to the 'text' parameter
        if attachment_text:
            action_args['text'] = f"{original_text}\n\n\n{attachment_text}" if original_text else attachment_text

    if action_type == 'get_text':
        return get_element_text(element)
    if action_type == 'get_html':
        return get_element_html(element)
    else:
        new_tabs_opened = None
        if action_type == 'click':
            # Allow action_args to override the default new-tab behavior
            open_in_new_tab = action_args.get(
                'try_open_in_new_tab',
                OpenInNewTabMode.ENABLED_FOR_NON_SAME_PAGE_INTERACTION
            )
            new_tabs_opened = click_element(
                driver, element,
                try_open_in_new_tab=open_in_new_tab,
                new_tab_fallback_to_normal_click=True,
                logger=logger
            )
        elif action_type == 'browse_link':
            open_in_new_tab = action_args.get('try_open_in_new_tab', OpenInNewTabMode.ENABLED_FOR_NON_SAME_PAGE_INTERACTION)
            new_tabs_opened = click_element(
                driver, element,
                try_open_in_new_tab=open_in_new_tab,
                new_tab_fallback_to_normal_click=True,
                logger=logger
            )
        elif action_type == 'deep_dive_link':
            open_in_new_tab = action_args.get(
                'try_open_in_new_tab',
                OpenInNewTabMode.ENABLED_FOR_NON_SAME_PAGE_INTERACTION
            )
            new_tabs_opened = click_element(
                driver, element,
                try_open_in_new_tab=open_in_new_tab,
                new_tab_fallback_to_normal_click=True,
                logger=logger
            )
        elif action_type == 'next_page':
            click_element(driver, element, try_open_in_new_tab=False, logger=logger)
        elif action_type == 'input_text':
            input_text(driver, element, clear_content=True, **action_args)
        elif action_type == 'append_text':
            input_text(driver, element, clear_content=False, **action_args)
        elif action_type == 'set_file_path':
            # Set file path for file input elements
            # Must use send_keys (not JavaScript) due to browser security restrictions
            # File inputs cannot be clicked or cleared - just send keys directly
            file_path = action_args.get('file_path')
            if not file_path:
                raise ValueError("set_file_path action requires 'file_path' argument")
            # Send keys directly to file input without clicking or clearing
            # File inputs are special - they don't support click() or clear()
            # Use send_keys directly on the element (WebElement.send_keys is a native Selenium method)
            try:
                element.send_keys(file_path)
            except Exception as e:
                # Log error for debugging
                _logger.error(f"Failed to set file path on file input: {e}")
                raise
        elif action_type == 'scroll_up_to_element':
            scroll_element_into_view(driver, element, vertical='bottom', **action_args)
        elif action_type == 'scroll_down_to_element':
            scroll_element_into_view(driver, element, vertical='top', **action_args)
        elif action_type == 'scroll':
            scroll_element(driver, element, **action_args)
        elif action_type == 'visit_url':
            open_url(driver, element, logger=logger, **action_args)
            timeout =  timeout * 3
            additional_wait_time = additional_wait_time * 3

        _log = logger or _logger
        if new_tabs_opened:
            _log.debug(
                f"[execute_single_action] action_type={action_type}, "
                f"new_tabs_opened={new_tabs_opened}"
            )

        wait_for_page_loading(driver, timeout=timeout, additional_wait_time=additional_wait_time)


def _get_common_action_params() -> set:
    """
    Extract common parameter names from execute_single_action signature.

    These parameters should be excluded when extracting action-specific args.

    Returns:
        Set of common parameter names
    """
    import inspect
    sig = inspect.signature(execute_single_action)
    return set(sig.parameters.keys())


# Common parameter names in execute_single_action that should be excluded from action-specific args
_COMMON_ACTION_PARAMS = _get_common_action_params()

# Action type to function mapping
_ACTION_FUNCTIONS = {
    'click': click_element,
    'input_text': input_text,
    'scroll': scroll_element,
    'visit_url': open_url,
    # Add other actions as needed
}


def _get_valid_arg_names_for_action(action_type: str) -> set:
    """
    Get valid argument names for an action type by introspecting the function signature.

    Excludes common parameters like 'driver', 'element', 'action_type', etc.

    Args:
        action_type: The action type (e.g., 'input_text', 'click')

    Returns:
        Set of valid argument names for this action type
    """
    import inspect

    action_func = _ACTION_FUNCTIONS.get(action_type)
    if not action_func:
        # If action not in mapping, allow all args (no validation)
        return set()

    sig = inspect.signature(action_func)
    valid_args = {
        param_name
        for param_name in sig.parameters.keys()
        if param_name not in _COMMON_ACTION_PARAMS
    }
    return valid_args


def _extract_action_specific_args(action_type: str, all_action_args: Mapping) -> Mapping:
    """
    Extract action-specific arguments from a mapping containing args for multiple actions.

    Supports two formats with priority:
    1. Prefixed args (higher priority): 'input_text_text' -> 'text' for input_text action
    2. Non-prefixed args (fallback): 'text' -> 'text' if no prefixed version exists

    This allows flexible configuration where prefixed args override non-prefixed ones.

    Args:
        action_type: The action type to extract args for (e.g., 'input_text', 'click')
        all_action_args: Dictionary containing all action args (with or without prefixes)

    Returns:
        Dictionary containing only the valid args for the specified action type, with prefixes removed
    """
    if not all_action_args:
        return {}

    action_specific_args = {}
    prefix = f"{action_type}_"
    valid_arg_names = _get_valid_arg_names_for_action(action_type)

    # First pass: Extract prefixed args (higher priority)
    for key, value in all_action_args.items():
        if key.startswith(prefix):
            # Remove prefix to get the actual parameter name
            param_name = key[len(prefix):]

            # Validate if we have valid arg names for this action
            if valid_arg_names and param_name not in valid_arg_names:
                # Raise error for invalid explicitly prefixed args
                raise ValueError(
                    f"Invalid argument '{param_name}' for action '{action_type}'. "
                    f"Valid arguments are: {', '.join(sorted(valid_arg_names))}"
                )

            action_specific_args[param_name] = value

    # Second pass: Fallback to non-prefixed args for parameters not found in first pass
    if valid_arg_names:  # Only do fallback if we know what args are valid
        for param_name in valid_arg_names:
            if param_name not in action_specific_args and param_name in all_action_args:
                # Use non-prefixed arg as fallback
                action_specific_args[param_name] = all_action_args[param_name]

    return action_specific_args


def execute_composite_action(
        driver: WebDriver,
        elements: List[WebElement],
        action_config,  # WebAgentAction from webaxon.automation.schema
        action_args: Mapping = None,
        attachments: Sequence = None,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
        logger: 'Union[logging.Logger, Debuggable, None]' = None
):
    """
    Execute a composite action by decomposing it into multiple sub-actions.

    This function handles composite actions that are made up of multiple sequential sub-actions.
    For example, input_and_submit = input_text + click.

    Args:
        driver: WebDriver instance
        elements: List of resolved WebElements corresponding to element IDs in action_target
        action_config: WebAgentAction configuration defining the composite action steps
        action_args: Arguments to pass to sub-actions (typically only for input-type actions)
        attachments: Attachments to pass to sub-actions (typically only for input-type actions)
        timeout: Timeout for each sub-action
        additional_wait_time: Additional wait time after each sub-action

    Raises:
        ValueError: If composite_steps references invalid element indices or unsupported composite mode
    """
    # Check composite action mode - supports both old enum format and new CompositeActionConfig format
    composite_action = action_config.composite_action
    if composite_action is None:
        raise ValueError(
            f"Action '{action_config.name}' is not a composite action (composite_action is None)."
        )

    # Handle both old enum format and new CompositeActionConfig format
    if hasattr(composite_action, 'mode'):
        # New format: CompositeActionConfig with mode field
        mode = composite_action.mode
    elif hasattr(composite_action, 'value'):
        # Old format: WebAgentCompositeActionMode enum
        mode = composite_action.value
    else:
        mode = str(composite_action)

    if mode != "sequential":
        raise ValueError(
            f"Unsupported composite action mode: {mode}. "
            f"Only 'sequential' is currently supported."
        )

    if not action_config.composite_steps:
        raise ValueError(
            f"Composite action '{action_config.name}' has no composite_steps defined."
        )

    # Execute each step defined in composite_steps
    for step_action_type, element_index in action_config.composite_steps:
        if element_index >= len(elements):
            raise ValueError(
                f"Composite action '{action_config.name}' step references element_index {element_index}, "
                f"but only {len(elements)} elements were provided."
            )

        step_element = elements[element_index]

        # Extract action-specific arguments using prefix (e.g., 'input_text_text')
        step_action_args = _extract_action_specific_args(step_action_type, action_args)

        # TODO: The additional_wait_time may not be sufficient for composite actions
        # with many steps or slow-loading pages. Consider adding per-step wait time
        # configuration or adaptive waiting in future optimization.
        execute_single_action(
            driver=driver,
            element=step_element,
            action_type=step_action_type,
            action_args=step_action_args if step_action_args else None,
            attachments=attachments,  # Pass attachments to all steps (filtered at WebDriver level)
            timeout=timeout,
            additional_wait_time=additional_wait_time,
            logger=logger
        )
