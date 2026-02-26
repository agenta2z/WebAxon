"""
BackendAdapter abstract base class.

This module defines the interface that all browser automation backends
(Selenium, Playwright) must implement. The WebDriver class delegates
all browser operations to the active backend adapter.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Mapping, Optional, Sequence, Tuple, TYPE_CHECKING, Union

from webaxon.automation.backends.types import ElementDimensionInfo

if TYPE_CHECKING:
    from webaxon.automation.backends.config import BrowserConfig


class BackendAdapter(ABC):
    """
    Abstract base class defining the interface for browser automation backends.

    All backend implementations (Selenium, Playwright) must implement this interface.
    The WebDriver class delegates all browser operations to the active backend adapter.

    Design principles:
    - Methods should have consistent signatures across backends
    - Backend-specific exceptions are wrapped into unified exception types
    - Optional features use `supports_*()` methods for feature detection
    """

    # ==========================================================================
    # Lifecycle Methods
    # ==========================================================================

    @abstractmethod
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
        **kwargs
    ) -> None:
        """
        Initialize the browser with the specified configuration.

        Args:
            browser_type: Browser type string (e.g., 'chrome', 'firefox', 'chromium')
            headless: Whether to run in headless mode
            user_agent: Custom user agent string
            timeout: Default page load timeout in seconds
            options: Additional browser-specific options
            user_data_dir: Path to browser profile directory
            config: BrowserConfig object with comprehensive browser settings.
                When provided, takes precedence over individual parameters.
            driver_version: Browser/driver version string.
                - Chrome: Full version for webdriver-manager (e.g., "126.0.6478.63")
                - Firefox: GeckoDriver version (e.g., "0.33.0")
                - Edge: EdgeDriver version
                - UndetectedChrome: Use config.undetected_chrome.version_main instead
            binary_location: Path to browser binary executable (e.g., Chrome Beta).
            **kwargs: Additional backend-specific options
        """
        pass

    @abstractmethod
    def quit(self) -> None:
        """
        Terminate the browser session and release all resources.

        This method:
        - Closes ALL open windows and tabs
        - Terminates the WebDriver process
        - Releases all system resources
        - Makes the driver instance unusable
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the current window/tab."""
        pass

    # ==========================================================================
    # Properties
    # ==========================================================================

    @property
    @abstractmethod
    def current_url(self) -> str:
        """Get the current page URL."""
        pass

    @property
    @abstractmethod
    def title(self) -> str:
        """Get the current page title."""
        pass

    @property
    @abstractmethod
    def window_handles(self) -> List[str]:
        """Get list of all window/tab handles."""
        pass

    @abstractmethod
    def current_window_handle(self) -> str:
        """Get the handle of the current window/tab.

        Returns the handle of the programmatically tracked current page.

        Note:
            This only tracks programmatic tab switches (via switch_to.window()).
            It cannot detect manual tab switches by the user. This is a fundamental
            limitation of browser automation APIs - neither Selenium nor Playwright
            can detect which tab the user is viewing.
        """
        pass

    @property
    @abstractmethod
    def raw_driver(self) -> Any:
        """
        Get the underlying driver instance.

        WARNING: Returns different types per backend:
        - Selenium: selenium.webdriver.remote.webdriver.WebDriver
        - Playwright: playwright.sync_api.Page

        Code using raw_driver should use backend_type checks or
        supports_*() methods for backend-specific operations.
        """
        pass

    @property
    @abstractmethod
    def driver_type(self) -> str:
        """Get the browser type string (e.g., 'chrome', 'firefox', 'chromium')."""
        pass

    # ==========================================================================
    # Feature Detection
    # ==========================================================================

    @abstractmethod
    def supports_cdp(self) -> bool:
        """
        Check if the backend supports Chrome DevTools Protocol.

        Returns:
            True for Chrome/Chromium-based browsers, False otherwise.
            Playwright supports CDP via page.context.new_cdp_session().
        """
        pass

    # ==========================================================================
    # Navigation
    # ==========================================================================

    @abstractmethod
    def get(self, url: str) -> None:
        """Navigate to a URL."""
        pass

    @abstractmethod
    def open_url(
        self, url: str, wait_after_opening_url: float = 0
    ) -> Optional[List[str]]:
        """
        Open URL. Returns new tab handles if a new tab was opened.

        Args:
            url: URL to navigate to
            wait_after_opening_url: Time to wait after opening (seconds)

        Returns:
            List of new tab handles if opened in new tab, None otherwise

        Note: try_open_in_new_tab is handled at WebDriver level via action_args.
        """
        pass

    @abstractmethod
    def wait_for_page_loading(
        self,
        timeout: int = 20,
        extra_wait_min: float = 1.0,
        extra_wait_max: float = 5.0,
        ignore_timeout: bool = True,
    ) -> None:
        """
        Wait for page to be fully loaded.

        Args:
            timeout: Maximum time to wait for page load in seconds
            extra_wait_min: Minimum additional random wait after load
            extra_wait_max: Maximum additional random wait after load
            ignore_timeout: If True, suppress timeout exceptions and continue
        """
        pass

    @abstractmethod
    def get_body_html_from_url(
        self,
        url: Optional[str] = None,
        initial_wait: float = 0,
        timeout_for_page_loading: int = 20,
        return_dynamic_contents: bool = True,
    ) -> str:
        """
        Navigate to URL and return body HTML.

        Args:
            url: URL to navigate to (uses current page if None)
            initial_wait: Wait time after navigation before getting HTML
            timeout_for_page_loading: Page load timeout
            return_dynamic_contents: Whether to include dynamically rendered content

        Returns:
            Body HTML content
        """
        pass

    # ==========================================================================
    # Element Resolution
    # ==========================================================================

    @abstractmethod
    def find_element(self, by: str, value: str) -> Any:
        """
        Find a single element by locator strategy.

        Args:
            by: Locator strategy (e.g., 'id', 'xpath', 'css selector')
            value: Locator value

        Returns:
            Element object (WebElement for Selenium, Locator for Playwright)

        Raises:
            ElementNotFoundError: If element cannot be found
        """
        pass

    @abstractmethod
    def find_elements(self, by: str, value: str) -> List[Any]:
        """
        Find multiple elements by locator strategy.

        Args:
            by: Locator strategy
            value: Locator value

        Returns:
            List of element objects (may be empty if none found)
        """
        pass

    @abstractmethod
    def find_element_by_xpath(
        self,
        tag_name: Optional[str] = "*",
        attributes: Optional[Mapping[str, Any]] = None,
        text: Optional[str] = None,
        immediate_text: Optional[str] = None,
    ) -> Any:
        """
        Find element using XPath with tag, attributes, and text filters.

        Args:
            tag_name: HTML tag name or '*' for any
            attributes: Attribute name-value pairs to match
            text: Text content to search for (contains)
            immediate_text: Immediate text content (not in descendants)

        Returns:
            Element object

        Raises:
            ElementNotFoundError: If element cannot be found
        """
        pass

    @abstractmethod
    def find_elements_by_xpath(
        self,
        tag_name: Optional[str] = "*",
        attributes: Optional[Mapping[str, Any]] = None,
        text: Optional[str] = None,
        immediate_text: Optional[str] = None,
    ) -> List[Any]:
        """
        Find elements using XPath with tag, attributes, and text filters.

        Args:
            tag_name: HTML tag name or '*' for any
            attributes: Attribute name-value pairs to match
            text: Text content to search for (contains)
            immediate_text: Immediate text content (not in descendants)

        Returns:
            List of element objects
        """
        pass

    @abstractmethod
    def resolve_action_target(self, strategy: str, action_target: str) -> Any:
        """
        Resolve element using explicit strategy.

        Supported strategies:
        - '__id__': Framework-assigned unique ID attribute
        - 'id': Element ID
        - 'xpath': XPath expression
        - 'css' / 'css_selector': CSS selector
        - 'text': Find by text content
        - 'source': Find by HTML source snippet
        - 'literal': Return value as-is (for URLs)

        Args:
            strategy: Resolution strategy string
            action_target: Strategy-specific value

        Returns:
            Element object or literal value

        Raises:
            ElementNotFoundError: If element cannot be found
            NotImplementedError: If strategy is not supported
        """
        pass

    @abstractmethod
    def add_unique_index_to_elements(self, index_name: Optional[str] = None) -> None:
        """
        Inject unique ID attributes to all elements on the page.

        Args:
            index_name: Attribute name to use (defaults to '__id__')
        """
        pass

    @abstractmethod
    def find_element_by_unique_index(
        self, index_value: str, index_name: Optional[str] = None
    ) -> Any:
        """
        Find element by framework-assigned unique index.

        Args:
            index_value: The value of the index attribute
            index_name: Attribute name (defaults to '__id__')

        Returns:
            Element object

        Raises:
            ElementNotFoundError: If element cannot be found
        """
        pass

    @abstractmethod
    def find_element_by_html(
        self,
        target_element_html: str,
        identifying_attributes: Tuple[str, ...] = ("id", "aria-label", "class"),
        always_return_single_element: bool = False,
    ) -> Optional[Any]:
        """
        Find element by HTML snippet.

        Args:
            target_element_html: HTML snippet to match
            identifying_attributes: Attributes to use for matching
            always_return_single_element: If True, always return single element

        Returns:
            Element if found, None if not found (when always_return_single_element=False)
        """
        pass

    # ==========================================================================
    # HTML Retrieval
    # ==========================================================================

    @property
    @abstractmethod
    def page_source(self) -> str:
        """
        Get the full HTML source of the current page.

        Returns:
            Full page HTML string including <html>, <head>, and <body> tags.
        """
        pass

    @abstractmethod
    def get_body_html(self, return_dynamic_contents: bool = True) -> str:
        """
        Get the body HTML of the current page.

        Args:
            return_dynamic_contents: If True, include dynamically rendered content

        Returns:
            Body HTML string
        """
        pass

    @abstractmethod
    def get_element_html(self, element: Any) -> Optional[str]:
        """
        Get the outer HTML of an element.

        Args:
            element: Element object

        Returns:
            Outer HTML string, or None if element is None
        """
        pass

    @abstractmethod
    def get_element_text(self, element: Any) -> Optional[str]:
        """
        Get the visible text of an element.

        Args:
            element: Element object

        Returns:
            Visible text string, or None if element is None
        """
        pass

    # ==========================================================================
    # Actions
    # ==========================================================================

    @abstractmethod
    def click_element(
        self, element: Any, try_open_in_new_tab: bool = False, **kwargs
    ) -> Optional[List[str]]:
        """
        Click an element, optionally opening in new tab.

        Args:
            element: Element to click
            try_open_in_new_tab: If True, attempt to open link in new tab
            **kwargs: Additional backend-specific options

        Returns:
            List of new tab handles if new tab opened, None otherwise
        """
        pass

    @abstractmethod
    def input_text(
        self,
        element: Any,
        text: str,
        clear_content: bool = False,
        implementation: str = "auto",
        **kwargs
    ) -> None:
        """
        Input text into an element.

        Args:
            element: Input element
            text: Text to input
            clear_content: If True, clear existing content first
            implementation: Input method ('auto', 'javascript', 'send_keys')
            **kwargs: Additional options (min_delay, max_delay for send_keys)
        """
        pass

    @abstractmethod
    def scroll_element(
        self,
        element: Any,
        direction: str = "Down",
        distance: str = "Large",
        implementation: str = "javascript",
        try_solve_scrollable_child: bool = False,
        **kwargs
    ) -> None:
        """
        Scroll an element or viewport.

        Args:
            element: Element to scroll (or container)
            direction: 'Up', 'Down', 'Left', 'Right'
            distance: 'Small', 'Medium', 'Large' or pixel value
            implementation: Scroll method ('javascript', 'actionchains', 'keystrokes')
            try_solve_scrollable_child: If True, find scrollable child first
            **kwargs: Additional backend-specific options
        """
        pass

    @abstractmethod
    def center_element_in_view(self, element: Any) -> None:
        """
        Scroll element to center of viewport.

        Args:
            element: Element to center
        """
        pass

    @abstractmethod
    def execute_single_action(
        self,
        element: Any,
        action_type: str,
        action_args: Optional[Mapping] = None,
        attachments: Optional[Sequence] = None,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
    ) -> Optional[str]:
        """
        Execute a single action on an element.

        Args:
            element: Target element
            action_type: Action type string (e.g., 'click', 'input_text', 'scroll')
            action_args: Action-specific arguments
            attachments: Optional attachments for input actions
            timeout: Page load timeout
            additional_wait_time: Wait time after action

        Returns:
            Action result (e.g., text for 'get_text'), None for most actions
        """
        pass

    @abstractmethod
    def execute_composite_action(
        self,
        elements: List[Any],
        action_config,  # WebAgentAction from webaxon.automation.schema
        action_args: Optional[Mapping] = None,
        attachments: Optional[Sequence] = None,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
    ) -> None:
        """
        Execute a composite action by decomposing it into multiple sub-actions.

        This method handles composite actions made up of multiple sequential sub-actions.
        For example, input_and_submit = input_text + click.

        Args:
            elements: List of resolved elements corresponding to element IDs in action_target
            action_config: WebAgentAction configuration defining the composite action steps
            action_args: Arguments to pass to sub-actions (typically only for input-type actions)
            attachments: Attachments to pass to sub-actions
            timeout: Timeout for each sub-action
            additional_wait_time: Additional wait time after each sub-action

        Raises:
            ValueError: If composite_steps references invalid element indices or unsupported composite mode
        """
        pass

    @abstractmethod
    def execute_actions(
        self,
        actions: Mapping,
        init_cond: Any = None,
        repeat: int = 0,
        repeat_when: Any = None,
        elements_dict: Any = None,
        output_path_action_records: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Execute a sequence of actions with conditions.

        Args:
            actions: Action definitions mapping
            init_cond: Initial conditions to check before starting
            repeat: Number of times to repeat
            repeat_when: Conditions for repeating
            elements_dict: Cached element dictionary
            output_path_action_records: Path to save action records
            **kwargs: Additional options
        """
        pass

    # ==========================================================================
    # Window Management
    # ==========================================================================

    @abstractmethod
    def switch_to_window(self, handle: str) -> None:
        """
        Switch to a specific window/tab.

        Args:
            handle: Window handle string

        Raises:
            ValueError: If handle doesn't exist
        """
        pass

    # ==========================================================================
    # JavaScript Execution
    # ==========================================================================

    @abstractmethod
    def execute_script(self, script: str, *args) -> Any:
        """
        Execute JavaScript in the browser context.

        Args:
            script: JavaScript code to execute
            *args: Arguments to pass to the script

        Returns:
            Script return value
        """
        pass

    # ==========================================================================
    # Screenshots
    # ==========================================================================

    @abstractmethod
    def capture_full_page_screenshot(
        self,
        output_path: str,
        center_element: Any = None,
        restore_window_size: bool = False,
        reset_zoom: bool = True,
        use_cdp_cmd_for_chrome: bool = False,
    ) -> None:
        """
        Capture a full-page screenshot.

        Args:
            output_path: Path to save the screenshot
            center_element: Element to center in view before capture
            restore_window_size: If True, restore original window size after
            reset_zoom: If True, reset zoom to 100% before capture
            use_cdp_cmd_for_chrome: If True, use CDP for Chrome screenshots
        """
        pass

    # ==========================================================================
    # Element Properties
    # ==========================================================================

    @abstractmethod
    def get_element_dimension_info(self, element: Any) -> ElementDimensionInfo:
        """
        Get comprehensive dimension information about an element.

        Args:
            element: Element object

        Returns:
            ElementDimensionInfo with size and scrollability data
        """
        pass

    @abstractmethod
    def get_element_scrollability(self, element: Any) -> Tuple[bool, bool]:
        """
        Check if element is scrollable in X and Y directions.

        Args:
            element: Element object

        Returns:
            Tuple of (is_scrollable_x, is_scrollable_y)
        """
        pass

    @abstractmethod
    def is_element_stale(self, element: Any) -> bool:
        """
        Check if an element reference is stale.

        Args:
            element: Element object

        Returns:
            True if element is stale, False if still valid
        """
        pass

    # ==========================================================================
    # Viewport and Zoom
    # ==========================================================================

    @abstractmethod
    def get_viewport_size(self) -> Tuple[int, int]:
        """
        Get viewport width and height.

        Returns:
            Tuple of (width, height) in pixels
        """
        pass

    @abstractmethod
    def set_viewport_size(self, width: int, height: int) -> None:
        """
        Set viewport size.

        Args:
            width: Viewport width in pixels
            height: Viewport height in pixels
        """
        pass

    @abstractmethod
    def get_window_size(self) -> Tuple[int, int]:
        """
        Get window width and height.

        Returns:
            Tuple of (width, height) in pixels
        """
        pass

    @abstractmethod
    def set_window_size(self, width: int, height: int) -> None:
        """
        Set window size.

        Args:
            width: Window width in pixels
            height: Window height in pixels
        """
        pass

    @abstractmethod
    def set_zoom(self, percentage: Union[int, float]) -> None:
        """
        Set page zoom level.

        Args:
            percentage: Zoom percentage (100 = normal)
        """
        pass

    @abstractmethod
    def get_zoom(self) -> float:
        """
        Get current page zoom level.

        Returns:
            Zoom percentage (100.0 = normal)
        """
        pass

    # ==========================================================================
    # Scrollable Child Resolution
    # ==========================================================================

    @abstractmethod
    def solve_scrollable_child(
        self, element: Any, strategy: str = "first_scrollable"
    ) -> Any:
        """
        Find the actual scrollable child element.

        Some containers have nested scrollable elements (e.g., virtual lists).
        This method finds the actual scrollable element within a container.

        Args:
            element: Parent element to search within
            strategy: One of:
                - 'first_scrollable': First scrollable descendant (DFS)
                - 'first_largest_scrollable': First scrollable with largest scroll area
                - 'deepest_scrollable': Deepest scrollable in DOM tree
                - 'largest_scrollable': Scrollable with largest scroll area overall

        Returns:
            The scrollable child element, or the original element if none found
        """
        pass

    # ==========================================================================
    # Session Data
    # ==========================================================================

    @abstractmethod
    def get_cookies(self) -> List[dict]:
        """
        Get all cookies from the current browser session.

        Returns:
            List of cookie dictionaries with keys: name, value, domain, path, etc.
        """
        pass

    @abstractmethod
    def get_user_agent(self) -> str:
        """
        Get the user agent string of the current browser session.

        Returns:
            User agent string
        """
        pass
