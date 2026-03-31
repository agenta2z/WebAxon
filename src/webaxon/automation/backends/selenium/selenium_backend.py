"""
Selenium backend implementation.

This module implements the BackendAdapter interface using Selenium WebDriver
for browser automation. It delegates to existing Selenium helper functions.
"""

import logging
import random
from time import sleep
from typing import Any, List, Mapping, Optional, Sequence, Tuple, TYPE_CHECKING, Union

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from webaxon.automation.backends.base import BackendAdapter
from webaxon.automation.backends.exceptions import (
    ElementNotFoundError,
    StaleElementError,
    WebDriverTimeoutError,
)
from webaxon.automation.backends.types import ElementDimensionInfo
from webaxon.automation.schema import TargetStrategy
from webaxon.html_utils.element_identification import ATTR_NAME_INCREMENTAL_ID

from .driver_factory import get_driver, WebAutomationDrivers

if TYPE_CHECKING:
    from webaxon.automation.backends.config import BrowserConfig

_logger = logging.getLogger(__name__)


class SeleniumBackend(BackendAdapter):
    """
    Selenium implementation of the BackendAdapter interface.

    Delegates browser operations to Selenium WebDriver and existing
    helper functions in the selenium module.
    """

    def __init__(self):
        """Initialize SeleniumBackend without starting a browser."""
        self._driver = None
        self._driver_type: Optional[str] = None
        self._logger = None  # Set by WebDriver for Debuggable logging passthrough

    # ==========================================================================
    # Lifecycle Methods
    # ==========================================================================

    def initialize(
        self,
        browser_type: str,
        headless: bool = True,
        user_agent: Optional[str] = None,
        timeout: int = 120,
        options: Optional[List[str]] = None,
        user_data_dir: Optional[str] = None,
        profile_directory: Optional[str] = None,
        config: Optional["BrowserConfig"] = None,
        driver_version: Optional[str] = None,
        binary_location: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Initialize the Selenium WebDriver with the specified configuration.

        Args:
            browser_type: Browser type string (e.g., 'chrome', 'firefox')
            headless: Whether to run in headless mode
            user_agent: Custom user agent string
            timeout: Default page load timeout in seconds
            options: Additional browser-specific command-line options
            user_data_dir: Path to browser profile directory
            profile_directory: Chrome profile folder name within user_data_dir
                (e.g., "Default", "Profile 1"). Only applies to Chromium-based browsers.
            config: BrowserConfig object with comprehensive browser settings
            driver_version: Browser/driver version string
            binary_location: Path to browser binary executable
            **kwargs: Additional options (ignored)
        """
        # Convert browser_type string to WebAutomationDrivers enum
        try:
            driver_enum = WebAutomationDrivers(browser_type)
        except ValueError:
            raise ValueError(
                f"Unsupported browser type: {browser_type}. "
                f"Supported types: {[e.value for e in WebAutomationDrivers]}"
            )

        self._driver_type = browser_type
        self._driver = get_driver(
            driver_type=driver_enum,
            headless=headless,
            user_agent=user_agent,
            timeout=timeout,
            options=options,
            user_data_dir=user_data_dir,
            profile_directory=profile_directory,
            config=config,
            driver_version=driver_version,
            binary_location=binary_location,
        )

    def quit(self) -> None:
        """Terminate the browser session and release all resources."""
        if self._driver is not None:
            self._driver.quit()
            self._driver = None

    def close(self) -> None:
        """Close the current window/tab."""
        if self._driver is not None:
            self._driver.close()

    # ==========================================================================
    # Properties
    # ==========================================================================

    @property
    def current_url(self) -> str:
        """Get the current page URL."""
        return self._driver.current_url

    @property
    def title(self) -> str:
        """Get the current page title."""
        return self._driver.title

    @property
    def page_source(self) -> str:
        """Get the full HTML source of the current page."""
        return self._driver.page_source

    @property
    def window_handles(self) -> List[str]:
        """Get list of all window/tab handles."""
        return self._driver.window_handles

    def current_window_handle(self) -> str:
        """Get the handle of the current window/tab.

        Returns the handle of the programmatically tracked current page.

        Note:
            This only tracks programmatic tab switches (via switch_to.window()).
            It cannot detect manual tab switches by the user. This is a fundamental
            limitation of browser automation APIs - neither Selenium nor Playwright
            can detect which tab the user is viewing.
        """
        return self._driver.current_window_handle

    @property
    def raw_driver(self) -> Any:
        """Get the underlying Selenium WebDriver instance."""
        return self._driver

    @property
    def driver_type(self) -> str:
        """Get the browser type string."""
        return self._driver_type

    @property
    def switch_to(self):
        """Access the switch_to interface for window/frame switching."""
        return self._driver.switch_to

    # ==========================================================================
    # Feature Detection
    # ==========================================================================

    def supports_cdp(self) -> bool:
        """Check if the backend supports Chrome DevTools Protocol."""
        return self._driver_type in ("chrome", "undetected_chrome", "edge")

    # ==========================================================================
    # Navigation
    # ==========================================================================

    def get(self, url: str) -> None:
        """Navigate to a URL."""
        self._driver.get(url)

    def open_url(
        self, url: str, wait_after_opening_url: float = 0
    ) -> Optional[List[str]]:
        """Open URL. Returns new tab handles if a new tab was opened."""
        from .actions import open_url as selenium_open_url

        return selenium_open_url(
            driver=self._driver,
            url=url,
            wait_after_opening_url=wait_after_opening_url,
            logger=self._logger,
        )

    def wait_for_page_loading(
        self,
        timeout: int = 20,
        extra_wait_min: float = 1.0,
        extra_wait_max: float = 5.0,
        ignore_timeout: bool = True,
    ) -> None:
        """Wait for page to be fully loaded."""
        from .common import wait_for_page_loading as selenium_wait

        selenium_wait(
            driver=self._driver,
            timeout=timeout,
            ignore_timeout=ignore_timeout,
        )
        if extra_wait_min > 0 or extra_wait_max > 0:
            sleep(random.uniform(extra_wait_min, extra_wait_max))

    def get_body_html_from_url(
        self,
        url: Optional[str] = None,
        initial_wait: float = 0,
        timeout_for_page_loading: int = 20,
        return_dynamic_contents: bool = True,
    ) -> str:
        """Navigate to URL and return body HTML."""
        from .common import get_body_html_from_url as selenium_get_body_html_from_url

        return selenium_get_body_html_from_url(
            driver=self._driver,
            url=url,
            initial_wait_after_opening_url=initial_wait,
            timeout_for_page_loading=timeout_for_page_loading,
            return_dynamic_contents=return_dynamic_contents,
        )

    # ==========================================================================
    # Element Resolution
    # ==========================================================================

    def find_element(self, by: str, value: str) -> Any:
        """Find a single element by locator strategy."""
        try:
            return self._driver.find_element(by, value)
        except NoSuchElementException as e:
            raise ElementNotFoundError(
                strategy=by,
                target=value,
                message=f"Element not found with {by}='{value}'",
            ) from e

    def find_elements(self, by: str, value: str) -> List[Any]:
        """Find multiple elements by locator strategy."""
        return self._driver.find_elements(by, value)

    def find_element_by_xpath(
        self,
        tag_name: Optional[str] = "*",
        attributes: Optional[Mapping[str, Any]] = None,
        text: Optional[str] = None,
        immediate_text: Optional[str] = None,
    ) -> Any:
        """Find element using XPath with tag, attributes, and text filters."""
        from .element_selection import (
            find_element_by_xpath as selenium_find_element_by_xpath,
        )

        try:
            return selenium_find_element_by_xpath(
                driver=self._driver,
                tag_name=tag_name,
                attributes=attributes,
                text=text,
                immediate_text=immediate_text,
            )
        except NoSuchElementException as e:
            raise ElementNotFoundError(
                strategy="xpath",
                target=f"tag={tag_name}, attributes={attributes}, text={text}",
                message=str(e),
            ) from e

    def find_elements_by_xpath(
        self,
        tag_name: Optional[str] = "*",
        attributes: Optional[Mapping[str, Any]] = None,
        text: Optional[str] = None,
        immediate_text: Optional[str] = None,
    ) -> List[Any]:
        """Find elements using XPath with tag, attributes, and text filters."""
        from .element_selection import (
            find_elements_by_xpath as selenium_find_elements_by_xpath,
        )

        return selenium_find_elements_by_xpath(
            driver=self._driver,
            tag_name=tag_name,
            attributes=attributes,
            text=text,
            immediate_text=immediate_text,
        )

    def resolve_action_target(self, strategy: str, action_target: str) -> Any:
        """Resolve element using explicit strategy."""
        # Normalize strategy (handle TargetStrategy enum values)
        if hasattr(strategy, "value"):
            strategy = strategy.value

        try:
            if strategy == TargetStrategy.FRAMEWORK_ID.value:  # '__id__'
                return self.find_element_by_unique_index(action_target)
            elif strategy == TargetStrategy.ID.value:  # 'id'
                return self._driver.find_element(By.ID, action_target)
            elif strategy == TargetStrategy.XPATH.value:  # 'xpath'
                return self._driver.find_element(By.XPATH, action_target)
            elif strategy in (TargetStrategy.CSS.value, "css_selector"):  # 'css'
                return self._driver.find_element(By.CSS_SELECTOR, action_target)
            elif strategy == TargetStrategy.TEXT.value:  # 'text'
                xpath = f"//*[contains(text(), '{action_target}')]"
                return self._driver.find_element(By.XPATH, xpath)
            elif strategy == TargetStrategy.SOURCE.value:  # 'source'
                return self.find_element_by_html(
                    action_target, always_return_single_element=True
                )
            elif strategy == TargetStrategy.LITERAL.value:  # 'literal'
                return action_target
            elif strategy == TargetStrategy.DESCRIPTION.value:  # 'description'
                raise NotImplementedError(
                    "Description-based element resolution is not yet implemented"
                )
            # Additional Selenium locators
            elif strategy == "name":
                return self._driver.find_element(By.NAME, action_target)
            elif strategy in ("tag", "tag_name"):
                return self._driver.find_element(By.TAG_NAME, action_target)
            elif strategy in ("class", "class_name"):
                return self._driver.find_element(By.CLASS_NAME, action_target)
            elif strategy == "link_text":
                return self._driver.find_element(By.LINK_TEXT, action_target)
            elif strategy == "partial_link_text":
                return self._driver.find_element(By.PARTIAL_LINK_TEXT, action_target)
            else:
                raise NotImplementedError(f"Unsupported strategy: {strategy}")
        except NoSuchElementException as e:
            raise ElementNotFoundError(
                strategy=strategy,
                target=action_target,
                message=str(e),
            ) from e

    def add_unique_index_to_elements(self, index_name: Optional[str] = None) -> None:
        """Inject unique ID attributes to all elements on the page."""
        from .element_selection import (
            add_unique_index_to_elements as selenium_add_unique_index,
        )

        selenium_add_unique_index(self._driver, index_name=index_name)

    def find_element_by_unique_index(
        self, index_value: str, index_name: Optional[str] = None
    ) -> Any:
        """Find element by framework-assigned unique index."""
        from .element_selection import (
            find_element_by_unique_index as selenium_find_by_index,
        )

        try:
            return selenium_find_by_index(self._driver, index_value, index_name)
        except NoSuchElementException as e:
            raise ElementNotFoundError(
                strategy="framework_id",
                target=index_value,
                message=str(e),
            ) from e

    def find_element_by_html(
        self,
        target_element_html: str,
        identifying_attributes: Tuple[str, ...] = ("id", "aria-label", "class"),
        always_return_single_element: bool = False,
    ) -> Optional[Any]:
        """Find element by HTML snippet."""
        from .element_selection import find_element_by_html as selenium_find_by_html

        return selenium_find_by_html(
            driver=self._driver,
            target_element_html=target_element_html,
            identifying_attributes=identifying_attributes,
            always_return_single_element=always_return_single_element,
        )

    # ==========================================================================
    # HTML Retrieval
    # ==========================================================================

    def get_body_html(self, return_dynamic_contents: bool = True) -> str:
        """Get the body HTML of the current page."""
        from .common import get_body_html as selenium_get_body_html

        return selenium_get_body_html(
            driver=self._driver,
            return_dynamic_contents=return_dynamic_contents,
        )

    def get_element_html(self, element: Any) -> Optional[str]:
        """Get the outer HTML of an element."""
        from .common import get_element_html as selenium_get_element_html

        return selenium_get_element_html(element)

    def get_element_text(self, element: Any) -> Optional[str]:
        """Get the visible text of an element."""
        from .common import get_element_text as selenium_get_element_text

        return selenium_get_element_text(element)

    # ==========================================================================
    # Actions
    # ==========================================================================

    def click_element(
        self, element: Any, try_open_in_new_tab: bool = False, **kwargs
    ) -> Optional[List[str]]:
        """Click an element, optionally opening in new tab."""
        from .actions import click_element as selenium_click_element
        kwargs.setdefault('logger', self._logger)
        return selenium_click_element(
            driver=self._driver,
            element=element,
            try_open_in_new_tab=try_open_in_new_tab,
            **kwargs,
        )

    def input_text(
        self,
        element: Any,
        text: str,
        clear_content: bool = False,
        implementation: str = "auto",
        **kwargs,
    ) -> None:
        """Input text into an element."""
        from .actions import input_text as selenium_input_text

        selenium_input_text(
            driver=self._driver,
            element=element,
            text=text,
            clear_content=clear_content,
            implementation=implementation,
            **kwargs,
        )

    def scroll_element(
        self,
        element: Any,
        direction: str = "Down",
        distance: str = "Large",
        implementation: str = "javascript",
        try_solve_scrollable_child: bool = False,
        **kwargs,
    ) -> None:
        """Scroll an element or viewport."""
        from .actions import scroll_element as selenium_scroll_element

        selenium_scroll_element(
            driver=self._driver,
            element=element,
            direction=direction,
            distance=distance,
            implementation=implementation,
            try_solve_scrollable_child=try_solve_scrollable_child,
            **kwargs,
        )

    def center_element_in_view(self, element: Any) -> None:
        """Scroll element to center of viewport."""
        from .common import scroll_element_into_view

        scroll_element_into_view(
            driver=self._driver,
            element=element,
            vertical="center",
            horizontal="center",
        )

    def execute_single_action(
        self,
        element: Any,
        action_type: str,
        action_args: Optional[Mapping] = None,
        attachments: Optional[Sequence] = None,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
    ) -> Optional[str]:
        """Execute a single action on an element."""
        from .actions import execute_single_action as selenium_execute_single_action

        return selenium_execute_single_action(
            driver=self._driver,
            element=element,
            action_type=action_type,
            action_args=action_args,
            attachments=attachments,
            timeout=timeout,
            additional_wait_time=additional_wait_time,
            logger=self._logger,
        )

    def execute_composite_action(
        self,
        elements: List[Any],
        action_config,  # WebAgentAction from webaxon.automation.schema
        action_args: Optional[Mapping] = None,
        attachments: Optional[Sequence] = None,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
    ) -> None:
        """Execute a composite action by decomposing it into multiple sub-actions."""
        from .actions import (
            execute_composite_action as selenium_execute_composite_action,
        )

        selenium_execute_composite_action(
            driver=self._driver,
            elements=elements,
            action_config=action_config,
            action_args=action_args,
            attachments=attachments,
            timeout=timeout,
            additional_wait_time=additional_wait_time,
            logger=self._logger,
        )

    def execute_actions(
        self,
        actions: Mapping,
        init_cond: Any = None,
        repeat: int = 0,
        repeat_when: Any = None,
        elements_dict: Any = None,
        output_path_action_records: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Execute a sequence of actions with conditions."""
        from .execution import execute_actions as selenium_execute_actions

        selenium_execute_actions(
            driver=self._driver,
            actions=actions,
            init_cond=init_cond,
            repeat=repeat,
            repeat_when=repeat_when,
            elements_dict=elements_dict,
            output_path_action_records=output_path_action_records,
            **kwargs,
        )

    # ==========================================================================
    # Window Management
    # ==========================================================================

    def switch_to_window(self, handle: str) -> None:
        """Switch to a specific window/tab."""
        if handle not in self._driver.window_handles:
            raise ValueError(
                f"Window handle '{handle}' does not exist. "
                f"Available handles: {self._driver.window_handles}"
            )
        self._driver.switch_to.window(handle)

    # ==========================================================================
    # JavaScript Execution
    # ==========================================================================

    def execute_script(self, script: str, *args) -> Any:
        """Execute JavaScript in the browser context."""
        return self._driver.execute_script(script, *args)

    # ==========================================================================
    # Screenshots
    # ==========================================================================

    def capture_full_page_screenshot(
        self,
        output_path: str,
        center_element: Any = None,
        restore_window_size: bool = False,
        reset_zoom: bool = True,
        use_cdp_cmd_for_chrome: bool = False,
    ) -> None:
        """Capture a full-page screenshot."""
        from .actions import capture_full_page_screenshot as selenium_capture_screenshot

        selenium_capture_screenshot(
            driver=self._driver,
            output_path=output_path,
            center_element=center_element,
            restore_window_size=restore_window_size,
            reset_zoom=reset_zoom,
            use_cdp_cmd_for_chrome=use_cdp_cmd_for_chrome,
        )

    # ==========================================================================
    # Element Properties
    # ==========================================================================

    def get_element_dimension_info(self, element: Any) -> ElementDimensionInfo:
        """Get comprehensive dimension information about an element."""
        from .common import get_element_dimension_info as selenium_get_dimension_info

        info = selenium_get_dimension_info(self._driver, element)
        # Convert from selenium's ElementDimensionInfo to backends' ElementDimensionInfo
        return ElementDimensionInfo(
            width=info.width,
            height=info.height,
            client_width=info.client_width,
            client_height=info.client_height,
            scroll_width=info.scroll_width,
            scroll_height=info.scroll_height,
            is_scrollable_x=info.is_scrollable_x,
            is_scrollable_y=info.is_scrollable_y,
            overflow_x=info.overflow_x,
            overflow_y=info.overflow_y,
        )

    def get_element_scrollability(self, element: Any) -> Tuple[bool, bool]:
        """Check if element is scrollable in X and Y directions."""
        from .common import get_element_scrollability as selenium_get_scrollability

        return selenium_get_scrollability(self._driver, element)

    def is_element_stale(self, element: Any) -> bool:
        """Check if an element reference is stale."""
        from .common import is_element_stale as selenium_is_element_stale

        return selenium_is_element_stale(element)

    # ==========================================================================
    # Viewport and Zoom
    # ==========================================================================

    def get_viewport_size(self) -> Tuple[int, int]:
        """Get viewport width and height."""
        result = self._driver.execute_script(
            "return {width: window.innerWidth, height: window.innerHeight}"
        )
        return result["width"], result["height"]

    def set_viewport_size(self, width: int, height: int) -> None:
        """Set viewport size."""
        # Selenium doesn't directly set viewport, so we adjust window size
        current_window = self.get_window_size()
        current_viewport = self.get_viewport_size()

        # Calculate the chrome (non-viewport) size
        chrome_width = current_window[0] - current_viewport[0]
        chrome_height = current_window[1] - current_viewport[1]

        # Set window size to achieve desired viewport
        self.set_window_size(width + chrome_width, height + chrome_height)

    def get_window_size(self) -> Tuple[int, int]:
        """Get window width and height."""
        size = self._driver.get_window_size()
        return size["width"], size["height"]

    def set_window_size(self, width: int, height: int) -> None:
        """Set window size."""
        self._driver.set_window_size(width, height)

    def set_zoom(self, percentage: Union[int, float]) -> None:
        """Set page zoom level."""
        zoom = percentage / 100.0
        self._driver.execute_script(f"document.body.style.zoom = '{zoom}'")

    def get_zoom(self) -> float:
        """Get current page zoom level."""
        result = self._driver.execute_script(
            "return parseFloat(document.body.style.zoom || 1) * 100"
        )
        return float(result)

    # ==========================================================================
    # Scrollable Child Resolution
    # ==========================================================================

    def solve_scrollable_child(
        self, element: Any, strategy: str = "first_scrollable"
    ) -> Any:
        """Find the actual scrollable child element."""
        from .common import solve_scrollable_child as selenium_solve_scrollable_child

        return selenium_solve_scrollable_child(
            driver=self._driver,
            element=element,
            strategy=strategy,
        )

    # ==========================================================================
    # Session Data
    # ==========================================================================

    def get_cookies(self) -> List[dict]:
        """Get all cookies from the current browser session."""
        return self._driver.get_cookies()

    def add_cookies(self, cookies: List[dict]) -> None:
        """Add cookies to the current browser session.

        Selenium's add_cookie() expects specific keys. We normalize the
        cookie dicts to match Selenium's expected format.
        """
        for cookie in cookies:
            selenium_cookie = {
                "name": cookie["name"],
                "value": cookie["value"],
            }
            # Optional fields
            if "domain" in cookie:
                selenium_cookie["domain"] = cookie["domain"]
            if "path" in cookie:
                selenium_cookie["path"] = cookie["path"]
            else:
                selenium_cookie["path"] = "/"
            if "secure" in cookie:
                selenium_cookie["secure"] = cookie["secure"]
            if "httpOnly" in cookie:
                selenium_cookie["httpOnly"] = cookie["httpOnly"]
            if "expiry" in cookie:
                selenium_cookie["expiry"] = int(cookie["expiry"])
            elif "expirationDate" in cookie:
                selenium_cookie["expiry"] = int(cookie["expirationDate"])
            if "sameSite" in cookie:
                # Selenium expects "Strict", "Lax", or "None"
                ss = cookie["sameSite"]
                if ss.lower() in ("strict", "lax", "none"):
                    selenium_cookie["sameSite"] = ss.capitalize()
                    if ss.capitalize() == "None":
                        selenium_cookie["sameSite"] = "None"

            try:
                self._driver.add_cookie(selenium_cookie)
            except Exception as e:
                _logger.warning(
                    f"Failed to add cookie '{cookie.get('name')}': {e}"
                )

    def delete_all_cookies(self) -> None:
        """Delete all cookies from the current browser session."""
        self._driver.delete_all_cookies()

    def get_user_agent(self) -> str:
        """Get the user agent string of the current browser session."""
        return self._driver.execute_script("return navigator.userAgent")
