"""
Playwright backend implementation.

This module implements the BackendAdapter interface using Playwright
for browser automation.
"""

import logging
import random
from time import sleep
from typing import Any, List, Mapping, Optional, Sequence, Tuple, TYPE_CHECKING, Union

from webaxon.automation.backends.base import BackendAdapter
from webaxon.automation.backends.exceptions import (
    ElementNotFoundError,
    StaleElementError,
    UnsupportedOperationError,
    WebDriverTimeoutError,
)
from webaxon.automation.backends.playwright.shims import (
    PLAYWRIGHT_AVAILABLE,
    PlaywrightDriverShim,
    PlaywrightElementShim,
)
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
    NewlineHandling,
    NonBMPHandling,
    sanitize_input_text_for_webdriver,
    WhitespaceHandling,
)
from webaxon.automation.backends.types import ElementDimensionInfo
from webaxon.automation.schema import TargetStrategy

if TYPE_CHECKING:
    from webaxon.automation.backends.config import BrowserConfig


class _BackendSwitchToAdapter:
    """
    Switch-to adapter that ensures backend._page stays synchronized with shim._page.

    This adapter wraps window switching to update both the shim and backend page references,
    solving the sync issue where switch_to.window() only updated the shim's _page.
    """

    def __init__(self, backend: "PlaywrightBackend"):
        self._backend = backend

    def window(self, handle: str) -> None:
        """Switch to a window/tab by handle, updating both shim and backend."""
        self._backend.switch_to_window(handle)

    def frame(self, frame_reference) -> None:
        """Switch to a frame."""
        self._backend._driver_shim.switch_to.frame(frame_reference)

    def default_content(self) -> None:
        """Switch back to main content."""
        self._backend._driver_shim.switch_to.default_content()

    def parent_frame(self) -> None:
        """Switch to parent frame."""
        self._backend._driver_shim.switch_to.parent_frame()

    def active_element(self):
        """Get the currently focused element."""
        return self._backend._driver_shim.switch_to.active_element()

    def alert(self):
        """Get alert dialog."""
        return self._backend._driver_shim.switch_to.alert()


from webaxon.html_utils.element_identification import ATTR_NAME_INCREMENTAL_ID

_logger = logging.getLogger(__name__)


class PlaywrightBackend(BackendAdapter):
    """
    Playwright implementation of the BackendAdapter interface.

    Uses Playwright for browser automation with a Selenium-like interface
    through PlaywrightDriverShim and PlaywrightElementShim.
    """

    def __init__(self):
        """Initialize PlaywrightBackend without starting a browser."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Install it with: pip install playwright && playwright install"
            )
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._driver_shim = None
        self._switch_to_adapter = None
        self._driver_type: Optional[str] = None
        self._stealth_enabled: bool = False

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
        config: Optional["BrowserConfig"] = None,
        driver_version: Optional[str] = None,
        binary_location: Optional[str] = None,
        stealth: bool = True,
        **kwargs,
    ) -> None:
        """Initialize the Playwright browser with the specified configuration.

        Args:
            browser_type: Browser to use ('chromium', 'chrome', 'firefox', 'webkit')
            headless: Whether to run in headless mode
            user_agent: Custom user agent string
            timeout: Default timeout in seconds
            options: Additional browser launch arguments
            user_data_dir: User data directory (limited support in Playwright)
            config: BrowserConfig object with comprehensive browser settings.
                NOTE: Browser-specific config options (chrome, firefox, edge, undetected_chrome)
                are NOT supported in PlaywrightBackend and will be ignored with a warning.
            driver_version: Browser/driver version string.
                NOTE: NOT supported in PlaywrightBackend. Use 'playwright install chromium@version'
                to install specific versions. Will log a warning if provided.
            binary_location: Path to browser binary.
                NOTE: NOT supported in PlaywrightBackend. Playwright manages its own browsers.
                Will log a warning if provided.
            stealth: If True, apply anti-bot-detection measures (default True)

        Raises:
            ValueError: If browser_type is not a supported type
        """
        from playwright.sync_api import sync_playwright

        # Warn about unsupported parameters
        if driver_version:
            _logger.warning(
                f"driver_version='{driver_version}' is not supported in PlaywrightBackend. "
                "Use 'playwright install chromium@version' to install specific versions."
            )
        if binary_location:
            _logger.warning(
                "binary_location is not supported in PlaywrightBackend. "
                "Playwright manages its own browser binaries."
            )
        if config:
            if (
                config.chrome
                or config.firefox
                or config.edge
                or config.undetected_chrome
            ):
                _logger.warning(
                    "Browser-specific config options (chrome, firefox, edge, undetected_chrome) "
                    "are not supported in PlaywrightBackend and will be ignored."
                )
            # Extract common config values
            if config.headless is not None:
                headless = config.headless
            if config.user_agent:
                user_agent = config.user_agent
            if config.timeout:
                timeout = config.timeout
            if config.user_data_dir:
                user_data_dir = config.user_data_dir
            if config.extra_args:
                options = (options or []) + config.extra_args

        # Validate browser type BEFORE starting Playwright to avoid resource leaks
        if not browser_type or not isinstance(browser_type, str):
            raise ValueError(
                f"browser_type must be a non-empty string, got: {browser_type!r}. "
                f"Supported types: chromium, chrome, firefox, webkit, safari"
            )

        browser_type_lower = browser_type.strip().lower()
        if not browser_type_lower:
            raise ValueError(
                f"browser_type must be a non-empty string, got: {browser_type!r}. "
                f"Supported types: chromium, chrome, firefox, webkit, safari"
            )

        # Map browser type to internal identifier (validate before starting Playwright)
        if browser_type_lower in ("chromium", "chrome", "undetected_chrome"):
            browser_key = "chromium"
        elif browser_type_lower in ("firefox", "gecko"):
            browser_key = "firefox"
        elif browser_type_lower in ("webkit", "safari"):
            browser_key = "webkit"
        else:
            raise ValueError(
                f"Unsupported browser type: {browser_type}. "
                f"Supported types: chromium, chrome, firefox, webkit, safari"
            )

        self._driver_type = browser_type
        self._stealth_enabled = stealth
        self._playwright = sync_playwright().start()

        # Get the browser launcher based on validated browser key
        if browser_key == "chromium":
            browser_launcher = self._playwright.chromium
        elif browser_key == "firefox":
            browser_launcher = self._playwright.firefox
        else:  # webkit
            browser_launcher = self._playwright.webkit

        # Prepare launch options with anti-detection args for Chromium
        launch_args = []
        if options:
            launch_args.extend(options)

        # Add anti-detection arguments for Chromium-based browsers
        if stealth and browser_key == "chromium":
            anti_detection_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            for arg in anti_detection_args:
                if arg not in launch_args:
                    launch_args.append(arg)

        # Launch browser
        self._browser = browser_launcher.launch(
            headless=headless,
            args=launch_args if launch_args else None,
        )

        # Create context with optional settings
        context_options = {}
        if user_agent:
            context_options["user_agent"] = user_agent
        if user_data_dir:
            _logger.warning(
                "user_data_dir is not directly supported in Playwright. "
                "Consider using persistent context instead."
            )

        # Set viewport if not specified
        if "viewport" not in context_options:
            context_options["viewport"] = {"width": 1280, "height": 720}

        self._context = self._browser.new_context(**context_options)

        # Set default timeout
        self._context.set_default_timeout(timeout * 1000)
        self._context.set_default_navigation_timeout(timeout * 1000)

        # Create initial page
        self._page = self._context.new_page()

        # Apply stealth scripts if enabled
        if stealth:
            self._apply_stealth_scripts(self._page)

        # Create driver shim for Selenium-like interface
        self._driver_shim = PlaywrightDriverShim(
            self._browser, self._page, self._context
        )

        # Create switch_to adapter that keeps backend._page in sync with shim._page
        self._switch_to_adapter = _BackendSwitchToAdapter(self)

    def quit(self) -> None:
        """Terminate the browser session and release all resources."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._context = None
        self._page = None
        self._driver_shim = None

    def _apply_stealth_scripts(self, page) -> None:
        """Apply anti-bot-detection scripts to a page.

        These scripts help bypass common bot detection mechanisms by:
        - Removing navigator.webdriver flag
        - Masking automation-related properties
        - Adding missing browser features

        Args:
            page: Playwright page object to apply stealth to
        """
        # Script to remove webdriver flag and mask automation indicators
        stealth_script = """
        () => {
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Override the plugins to appear more realistic
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    },
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    }
                ],
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Hide automation-related chrome properties
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Override toString to hide modifications
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === window.navigator.permissions.query) {
                    return 'function query() { [native code] }';
                }
                return originalToString.call(this);
            };
        }
        """

        # Add stealth script to run on every navigation
        page.add_init_script(stealth_script)

    def close(self) -> None:
        """Close the current window/tab."""
        if self._page is not None:
            self._page.close()
            # Switch to another page if available
            pages = self._context.pages
            if pages:
                self._page = pages[0]
                self._driver_shim._page = self._page

    # ==========================================================================
    # Properties
    # ==========================================================================

    @property
    def current_url(self) -> str:
        """Get the current page URL."""
        return self._page.url

    @property
    def title(self) -> str:
        """Get the current page title."""
        return self._page.title()

    @property
    def page_source(self) -> str:
        """Get the full HTML source of the current page."""
        return self._page.content()

    @property
    def window_handles(self) -> List[str]:
        """Get list of all window/tab handles."""
        return self._driver_shim.window_handles

    def current_window_handle(self) -> str:
        """Get the handle of the current window/tab.

        Returns the handle of the programmatically tracked current page.

        Note:
            This only tracks programmatic tab switches (via switch_to.window()).
            It cannot detect manual tab switches by the user. This is a fundamental
            limitation of browser automation APIs - neither Selenium nor Playwright
            can detect which tab the user is viewing.
        """
        return self._driver_shim.current_window_handle()

    @property
    def raw_driver(self) -> Any:
        """Get the underlying Playwright Page (or driver shim)."""
        return self._page

    @property
    def driver_type(self) -> str:
        """Get the browser type string."""
        return self._driver_type

    @property
    def switch_to(self):
        """Access the switch_to interface for window/frame switching.

        This returns a backend-level adapter that ensures backend._page
        stays in sync with shim._page when switching windows.
        """
        return self._switch_to_adapter

    # ==========================================================================
    # Feature Detection
    # ==========================================================================

    def supports_cdp(self) -> bool:
        """Check if the backend supports Chrome DevTools Protocol."""
        return self._driver_type in ("chromium", "chrome", "undetected_chrome")

    # ==========================================================================
    # Navigation
    # ==========================================================================

    def get(self, url: str) -> None:
        """Navigate to a URL."""
        self._page.goto(url)

    def open_url(
        self, url: str, wait_after_opening_url: float = 0
    ) -> Optional[List[str]]:
        """Open URL. Returns new tab handles if a new tab was opened."""
        old_handles = set(self.window_handles)
        self._page.goto(url)

        if wait_after_opening_url > 0:
            sleep(wait_after_opening_url)

        new_handles = set(self.window_handles)
        new = list(new_handles - old_handles)
        return new if new else None

    def wait_for_page_loading(
        self,
        timeout: int = 20,
        extra_wait_min: float = 1.0,
        extra_wait_max: float = 5.0,
        ignore_timeout: bool = True,
    ) -> None:
        """Wait for page to be fully loaded."""
        try:
            self._page.wait_for_load_state("load", timeout=timeout * 1000)
        except Exception as e:
            if not ignore_timeout:
                raise WebDriverTimeoutError(
                    timeout=timeout,
                    operation="wait_for_page_loading",
                    message=str(e),
                ) from e

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
        if url:
            self._page.goto(url)
            if initial_wait > 0:
                sleep(initial_wait)
            self.wait_for_page_loading(timeout=timeout_for_page_loading)

        return self.get_body_html(return_dynamic_contents=return_dynamic_contents)

    # ==========================================================================
    # Element Resolution
    # ==========================================================================

    def find_element(self, by: str, value: str, timeout: int = 10000) -> Any:
        """Find a single element by locator strategy.

        Args:
            by: Locator strategy (e.g., 'xpath', 'id', 'css selector')
            value: Locator value
            timeout: Maximum time to wait for element in milliseconds (default 10000ms)
        """
        import logging

        _logger = logging.getLogger(__name__)
        _logger.debug(
            f"[PlaywrightBackend.find_element] by={by}, value={value}, timeout={timeout}, "
            f"backend._page.url={self._page.url}, "
            f"shim._page.url={self._driver_shim._page.url}, "
            f"same_page={self._page is self._driver_shim._page}"
        )

        element = self._driver_shim.find_element(by, value)
        _logger.debug(
            f"[PlaywrightBackend.find_element] Created element shim, waiting for element..."
        )

        # Check if element exists
        try:
            element.locator.wait_for(timeout=timeout)
            _logger.debug(
                f"[PlaywrightBackend.find_element] Element found successfully"
            )
        except Exception as e:
            _logger.error(
                f"[PlaywrightBackend.find_element] FAILED: {type(e).__name__}: {e}"
            )
            raise ElementNotFoundError(
                strategy=by,
                target=value,
                message=f"Element not found with {by}='{value}': {e}",
            ) from e
        return element

    def find_elements(self, by: str, value: str) -> List[Any]:
        """Find multiple elements by locator strategy."""
        return self._driver_shim.find_elements(by, value)

    def find_element_by_xpath(
        self,
        tag_name: Optional[str] = "*",
        attributes: Optional[Mapping[str, Any]] = None,
        text: Optional[str] = None,
        immediate_text: Optional[str] = None,
    ) -> Any:
        """Find element using XPath with tag, attributes, and text filters."""
        from webaxon.html_utils.element_identification import get_xpath

        xpath = get_xpath(
            tag_name=tag_name,
            attributes=attributes,
            text=text,
            immediate_text=immediate_text,
        )
        try:
            locator = self._page.locator(f"xpath={xpath}").first
            locator.wait_for(timeout=1000)
            return PlaywrightElementShim(locator, self._page)
        except Exception as e:
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
        from webaxon.html_utils.element_identification import get_xpath

        xpath = get_xpath(
            tag_name=tag_name,
            attributes=attributes,
            text=text,
            immediate_text=immediate_text,
        )
        locators = self._page.locator(f"xpath={xpath}")
        count = locators.count()
        return [
            PlaywrightElementShim(locators.nth(i), self._page) for i in range(count)
        ]

    def resolve_action_target(self, strategy: str, action_target: str) -> Any:
        """Resolve element using explicit strategy."""
        import logging

        _logger = logging.getLogger(__name__)
        _logger.debug(
            f"[PlaywrightBackend.resolve_action_target] strategy={strategy}, action_target={action_target}"
        )

        # Normalize strategy
        if hasattr(strategy, "value"):
            strategy = strategy.value
            _logger.debug(
                f"[PlaywrightBackend.resolve_action_target] Normalized strategy to: {strategy}"
            )

        try:
            if strategy == TargetStrategy.FRAMEWORK_ID.value:  # '__id__'
                _logger.debug(
                    f"[PlaywrightBackend.resolve_action_target] Using FRAMEWORK_ID strategy"
                )
                return self.find_element_by_unique_index(action_target)
            elif strategy == TargetStrategy.ID.value:  # 'id'
                _logger.debug(
                    f"[PlaywrightBackend.resolve_action_target] Using ID strategy"
                )
                return self.find_element("id", action_target)
            elif strategy == TargetStrategy.XPATH.value:  # 'xpath'
                _logger.debug(
                    f"[PlaywrightBackend.resolve_action_target] Using XPATH strategy"
                )
                return self.find_element("xpath", action_target)
            elif strategy in (TargetStrategy.CSS.value, "css_selector"):  # 'css'
                return self.find_element("css selector", action_target)
            elif strategy == TargetStrategy.TEXT.value:  # 'text'
                locator = self._page.locator(f"text={action_target}").first
                return PlaywrightElementShim(locator, self._page)
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
            elif strategy == "name":
                return self.find_element("name", action_target)
            elif strategy in ("tag", "tag_name"):
                return self.find_element("tag_name", action_target)
            elif strategy in ("class", "class_name"):
                return self.find_element("class_name", action_target)
            elif strategy == "link_text":
                return self.find_element("link_text", action_target)
            elif strategy == "partial_link_text":
                return self.find_element("partial_link_text", action_target)
            else:
                raise NotImplementedError(f"Unsupported strategy: {strategy}")
        except Exception as e:
            if isinstance(e, (ElementNotFoundError, NotImplementedError)):
                raise
            raise ElementNotFoundError(
                strategy=strategy,
                target=action_target,
                message=str(e),
            ) from e

    def add_unique_index_to_elements(self, index_name: Optional[str] = None) -> None:
        """Inject unique ID attributes to all elements on the page."""
        if index_name is None:
            index_name = ATTR_NAME_INCREMENTAL_ID

        script = f"""
        let elements = document.getElementsByTagName('*');
        for (let i = 0; i < elements.length; i++) {{
            elements[i].setAttribute('{index_name}', i);
        }}
        """
        self._page.evaluate(script)

    def find_element_by_unique_index(
        self, index_value: str, index_name: Optional[str] = None
    ) -> Any:
        """Find element by framework-assigned unique index."""
        if index_name is None:
            index_name = ATTR_NAME_INCREMENTAL_ID

        try:
            locator = self._page.locator(f"[{index_name}='{index_value}']").first
            locator.wait_for(timeout=1000)
            return PlaywrightElementShim(locator, self._page)
        except Exception as e:
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
        from webaxon.html_utils.common import get_tag_text_and_attributes_from_element

        tag_name, text, attributes = get_tag_text_and_attributes_from_element(
            target_element_html
        )

        # Build selector from tag and attributes
        selector = tag_name or "*"
        for attr in identifying_attributes:
            if attr in attributes:
                value = attributes[attr]
                if isinstance(value, list):
                    value = " ".join(value)
                selector += f"[{attr}='{value}']"

        locators = self._page.locator(selector)
        count = locators.count()

        if count == 0:
            return None
        elif count == 1 or always_return_single_element:
            return PlaywrightElementShim(locators.first, self._page)
        else:
            return [
                PlaywrightElementShim(locators.nth(i), self._page) for i in range(count)
            ]

    # ==========================================================================
    # HTML Retrieval
    # ==========================================================================

    def get_body_html(self, return_dynamic_contents: bool = True) -> str:
        """Get the body HTML of the current page."""
        if return_dynamic_contents:
            return self._page.evaluate("document.body.outerHTML")
        return self._page.content()

    def get_element_html(self, element: Any) -> Optional[str]:
        """Get the outer HTML of an element."""
        if element is None:
            return None
        if isinstance(element, PlaywrightElementShim):
            return element.outer_html()
        return element.evaluate("el => el.outerHTML")

    def get_element_text(self, element: Any) -> Optional[str]:
        """Get the visible text of an element."""
        if element is None:
            return None
        if isinstance(element, PlaywrightElementShim):
            return element.text
        return element.inner_text()

    # ==========================================================================
    # Actions
    # ==========================================================================

    def click_element(
        self,
        element: Any,
        try_open_in_new_tab: Union[bool, OpenInNewTabMode] = False,
        wait_before_checking_new_tab: float = 0.5,
        additional_max_wait_for_tab_timeout: float = 5.0,
        only_enable_additional_wait_for_non_anchor_links: bool = True,
        implementation: Union[ClickImplementation, Tuple[ClickImplementation, ...]] = DEFAULT_CLICK_IMPLEMENTATION_ORDER,
        new_tab_strategy_order: Tuple[
            NewTabClickStrategy, ...
        ] = DEFAULT_NEW_TAB_STRATEGY_ORDER,
        return_strategy_result: bool = False,
        new_tab_fallback_to_normal_click: Union[bool, str, NewTabFallbackMode] = False,
        **kwargs,
    ) -> Union[Optional[List[str]], Tuple[Optional[List[str]], NewTabClickResult]]:
        """Click an element, optionally opening in new tab.

        This method delegates to the actions module for implementation.
        See actions.click_element for full documentation.
        """
        from .actions import click_element as pw_click_element

        return pw_click_element(
            self,
            element,
            try_open_in_new_tab=try_open_in_new_tab,
            wait_before_checking_new_tab=wait_before_checking_new_tab,
            additional_max_wait_for_tab_timeout=additional_max_wait_for_tab_timeout,
            only_enable_additional_wait_for_non_anchor_links=only_enable_additional_wait_for_non_anchor_links,
            implementation=implementation,
            new_tab_strategy_order=new_tab_strategy_order,
            return_strategy_result=return_strategy_result,
            new_tab_fallback_to_normal_click=new_tab_fallback_to_normal_click,
            **kwargs,
        )

    def input_text(
        self,
        element: Any,
        text: str,
        clear_content: bool = False,
        implementation: str = "auto",
        default_implementation: str = "send_keys",
        fast_implementation: str = "send_keys_fast",
        fast_threshold: int = 20,
        min_delay: float = 0.1,
        max_delay: float = 1.0,
        sanitize: bool = True,
        auto_sanitization: bool = True,
        non_bmp_handling: NonBMPHandling = NonBMPHandling.REMOVE,
        newline_handling: NewlineHandling = NewlineHandling.SPACE,
        whitespace_handling: WhitespaceHandling = WhitespaceHandling.NORMALIZE,
        **kwargs,
    ) -> None:
        """Input text into an element.

        This method delegates to the actions module for implementation.
        See actions.input_text for full documentation.
        """
        from .actions import input_text as pw_input_text

        pw_input_text(
            self,
            element,
            text,
            clear_content=clear_content,
            implementation=implementation,
            default_implementation=default_implementation,
            fast_implementation=fast_implementation,
            fast_threshold=fast_threshold,
            min_delay=min_delay,
            max_delay=max_delay,
            sanitize=sanitize,
            auto_sanitization=auto_sanitization,
            non_bmp_handling=non_bmp_handling,
            newline_handling=newline_handling,
            whitespace_handling=whitespace_handling,
            **kwargs,
        )

    def scroll_element(
        self,
        element: Any,
        direction: str = "Down",
        distance: str = "Large",
        implementation: str = "javascript",
        relative_distance: bool = False,
        try_solve_scrollable_child: bool = False,
        **kwargs,
    ) -> None:
        """Scroll an element or viewport.

        This method delegates to the actions module for implementation.
        See actions.scroll_element for full documentation.
        """
        from .actions import scroll_element as pw_scroll_element

        pw_scroll_element(
            self,
            element,
            direction=direction,
            distance=distance,
            implementation=implementation,
            relative_distance=relative_distance,
            try_solve_scrollable_child=try_solve_scrollable_child,
            **kwargs,
        )

    def center_element_in_view(self, element: Any) -> None:
        """Scroll element to center of viewport.

        This method delegates to the actions module for implementation.
        """
        from .actions import center_element_in_view as pw_center_element

        pw_center_element(self, element)

    def execute_single_action(
        self,
        element: Any,
        action_type: str,
        action_args: Optional[Mapping] = None,
        attachments: Optional[Sequence] = None,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
    ) -> Optional[str]:
        """Execute a single action on an element.

        This method delegates to the execution module for implementation.
        See execution.execute_single_action for full documentation.
        """
        from .execution import execute_single_action as pw_execute_single_action

        return pw_execute_single_action(
            self,
            element,
            action_type,
            action_args=action_args,
            attachments=attachments,
            timeout=timeout,
            additional_wait_time=additional_wait_time,
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
        """Execute a composite action by decomposing it into multiple sub-actions.

        This method delegates to the execution module for implementation.
        See execution.execute_composite_action for full documentation.
        """
        from .execution import execute_composite_action as pw_execute_composite_action

        pw_execute_composite_action(
            self,
            elements,
            action_config,
            action_args=action_args,
            attachments=attachments,
            timeout=timeout,
            additional_wait_time=additional_wait_time,
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
        """Execute a sequence of actions with conditions.

        This method delegates to the execution module for implementation.
        See execution.execute_actions for full documentation.
        """
        from .execution import execute_actions as pw_execute_actions

        pw_execute_actions(
            self,
            actions,
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
        """Switch to a specific window/tab.

        This method updates both shim._page and backend._page to ensure they
        stay synchronized when switching between tabs/windows.

        Unlike Selenium which automatically brings the tab to the foreground,
        Playwright requires an explicit bring_to_front() call to visually
        switch the browser tab.
        """
        _logger.debug(
            f"[PlaywrightBackend.switch_to_window] Switching to handle={handle}, "
            f"BEFORE: backend._page.url={self._page.url}"
        )
        self._driver_shim._switch_to_window(handle)
        self._page = self._driver_shim._page

        # Bring the tab to the foreground in the browser UI
        # This is needed because Playwright doesn't automatically focus the tab
        # when switching, unlike Selenium's switch_to.window()
        try:
            self._page.bring_to_front()
            _logger.debug(
                f"[PlaywrightBackend.switch_to_window] Called bring_to_front() on page"
            )
        except Exception as e:
            _logger.warning(
                f"[PlaywrightBackend.switch_to_window] bring_to_front() failed: {e}"
            )

        _logger.debug(
            f"[PlaywrightBackend.switch_to_window] AFTER: "
            f"backend._page.url={self._page.url}, "
            f"shim._page.url={self._driver_shim._page.url}, "
            f"same_page={self._page is self._driver_shim._page}"
        )

    # ==========================================================================
    # JavaScript Execution
    # ==========================================================================

    def execute_script(self, script: str, *args) -> Any:
        """Execute JavaScript in the browser context."""
        return self._driver_shim.execute_script(script, *args)

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
        if center_element:
            self.center_element_in_view(center_element)

        if reset_zoom:
            self.set_zoom(100)

        self._page.screenshot(path=output_path, full_page=True)

    # ==========================================================================
    # Element Properties
    # ==========================================================================

    def get_element_dimension_info(self, element: Any) -> ElementDimensionInfo:
        """Get comprehensive dimension information about an element.

        This method delegates to the common module for implementation.
        """
        from .common import get_element_dimension_info as pw_get_element_dimension_info

        return pw_get_element_dimension_info(self, element)

    def get_element_scrollability(self, element: Any) -> Tuple[bool, bool]:
        """Check if element is scrollable in X and Y directions.

        This method delegates to the common module for implementation.
        """
        from .common import get_element_scrollability as pw_get_element_scrollability

        return pw_get_element_scrollability(self, element)

    def is_element_stale(self, element: Any) -> bool:
        """Check if an element reference is stale.

        This method delegates to the common module for implementation.
        """
        from .common import is_element_stale as pw_is_element_stale

        return pw_is_element_stale(element)

    # ==========================================================================
    # Viewport and Zoom
    # ==========================================================================

    def get_viewport_size(self) -> Tuple[int, int]:
        """Get viewport width and height."""
        viewport = self._page.viewport_size
        if viewport:
            return viewport["width"], viewport["height"]
        return 0, 0

    def set_viewport_size(self, width: int, height: int) -> None:
        """Set viewport size."""
        self._page.set_viewport_size({"width": width, "height": height})

    def get_window_size(self) -> Tuple[int, int]:
        """Get window width and height."""
        # In Playwright, viewport is essentially the window size in headless mode
        return self.get_viewport_size()

    def set_window_size(self, width: int, height: int) -> None:
        """Set window size."""
        self.set_viewport_size(width, height)

    def set_zoom(self, percentage: Union[int, float]) -> None:
        """Set page zoom level."""
        zoom = percentage / 100.0
        self._page.evaluate(f"document.body.style.zoom = '{zoom}'")

    def get_zoom(self) -> float:
        """Get current page zoom level."""
        result = self._page.evaluate("parseFloat(document.body.style.zoom || 1) * 100")
        return float(result)

    # ==========================================================================
    # Scrollable Child Resolution
    # ==========================================================================

    def solve_scrollable_child(
        self,
        element: Any,
        strategy: str = "first_largest_scrollable",
        implementation: str = "javascript",
        direction: Optional[str] = None,
    ) -> Any:
        """Find the actual scrollable child element within an element hierarchy.

        This method delegates to the common module for implementation.
        See common.solve_scrollable_child for full documentation.
        """
        from .common import solve_scrollable_child as pw_solve_scrollable_child

        return pw_solve_scrollable_child(
            self,
            element,
            strategy=strategy,
            implementation=implementation,
            direction=direction,
        )

    # ==========================================================================
    # Session Data
    # ==========================================================================

    def get_cookies(self) -> List[dict]:
        """Get all cookies from the current browser session."""
        return self._context.cookies()

    def get_user_agent(self) -> str:
        """Get the user agent string of the current browser session."""
        return self._page.evaluate("navigator.userAgent")
