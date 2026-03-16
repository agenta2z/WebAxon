import logging
import os
from datetime import datetime
from time import sleep
from typing import (
    Any,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    TYPE_CHECKING,
    Union,
)

_logger = logging.getLogger(__name__)

from attr import attrib, attrs
from agent_foundation.common.memory import ContentMemory
from rich_python_utils.common_objects.debuggable import Debuggable
from rich_python_utils.common_utils import execute_with_retry, get_
from rich_python_utils.io_utils.artifact import artifact_field
from rich_python_utils.string_utils import cut, split_
from rich_python_utils.string_utils.misc import camel_to_snake_case
from selenium.webdriver.remote.webelement import WebElement
from webaxon.automation.backends.exceptions import ElementNotFoundError
from webaxon.automation.backends.selenium.actions import SearchProviders

# Import driver factory components (extracted to prevent circular imports)
from webaxon.automation.backends.selenium.driver_factory import (
    DEFAULT_USER_AGENT_STRING,
    WebAutomationDrivers,
)
from webaxon.automation.backends.selenium.types import ElementConditions, ElementDict
from webaxon.automation.schema import (
    ActionMemoryMode,
    DEFAULT_ACTION_CONFIGS,
    TargetStrategy,
    WebAgentAction,
)
from webaxon.html_utils.element_identification import ATTR_NAME_INCREMENTAL_ID
from webaxon.html_utils.sanitization import (
    clean_html,
    DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP,
    DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE,
    DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
    DEFAULT_RULE_ACTIVATION_FLAGS,
)

if TYPE_CHECKING:
    from webaxon.automation.backends.config import BrowserConfig


@artifact_field('body_html_before_last_action', type='html', group='ui_source')
@artifact_field('body_html_after_last_action', type='html', group='ui_source')
@artifact_field('cleaned_body_html_after_last_action', type='html', group='ui_source')
@attrs(slots=True)
class WebDriverActionResult:
    body_html_before_last_action: str = attrib()
    body_html_after_last_action: str = attrib()
    cleaned_body_html_after_last_action: str = attrib()
    is_cleaned_body_html_only_incremental_change: bool = attrib()
    source: str = attrib()
    action_memory: Optional[ContentMemory] = attrib(default=None)
    is_follow_up: bool = attrib(default=False)
    action_skipped: bool = attrib(default=False)
    skip_reason: Optional[str] = attrib(default=None)
    screenshot_before_path: Optional[str] = attrib(default=None)
    screenshot_after_path: Optional[str] = attrib(default=None)

    def __str__(self):
        return self.cleaned_body_html_after_last_action


@attrs
class WindowInfo:
    """
    Encapsulates per-window state for WebDriver.

    Tracks window-specific information including action history and action memory.
    """

    handle: str = attrib()  # Selenium window handle
    action_memory: ContentMemory = attrib()  # Per-window HTML change tracking
    last_action_type: Optional[str] = attrib(default=None)  # Last executed action type
    created_at: datetime = attrib(
        factory=datetime.now
    )  # For debugging/lifecycle tracking


class WebDriver(Debuggable):
    """
    A class to manage the creation of WebDriver instances for different browsers with configurable options.

    Supports two modes of operation:
    1. Direct Selenium mode (default): Uses Selenium WebDriver directly
    2. Backend mode: Uses a BackendAdapter for abstracted browser control (supports Playwright)

    Example with backend:
        from webaxon.automation.backends import PlaywrightBackend
        backend = PlaywrightBackend()
        backend.initialize(browser_type='chromium', headless=True)
        driver = WebDriver(backend=backend)
    """

    STATE_FIELD_CURRENT_WINDOW = "current_window"

    def __init__(
            self,
            driver_type: WebAutomationDrivers = WebAutomationDrivers.UndetectedChrome,
            headless: bool = True,
            user_agent: str = None,
            timeout: int = 120,
            options: List[str] = None,
            user_data_dir: str = None,
            state: Mapping[str, Any] = None,
            state_setting_max_retry: int = 3,
            state_setting_min_wait: float = 0.2,
            action_configs: Mapping[str, WebAgentAction] = None,
            backend: Optional[Any] = None,
            config: Optional[Any] = None,
            **kwargs
    ):
        """
        Initializes a WebDriver instance with the specified configuration upon creation of the class instance.

        Args:
            driver_type (WebAutomationDrivers): The type of browser for the WebDriver. Default is UndetectedChrome.
            headless (bool): Whether to run the browser in headless mode. Default is True.
            user_agent (str): Custom user-agent string, or 'default' for built-in default. Default is None.
            timeout (int): The maximum time to wait for a page to load. Default is 120 seconds.
            options (List[str]): Additional browser-specific options to set. Default is None.
            user_data_dir (str): Path to browser profile directory. Default is None.
            state (Mapping[str, Any]): Initial state for the WebDriver. Default is None.
            state_setting_max_retry (int): Max retries for state setting. Default is 3.
            state_setting_min_wait (float): Min wait between retries. Default is 0.2.
            action_configs (Mapping[str, WebAgentAction]): Action configuration mapping. Defaults to DEFAULT_ACTION_CONFIGS.
            backend (BackendAdapter, optional): Pre-initialized backend adapter to use instead of creating
                a Selenium driver. When provided, driver_type, headless, user_agent, timeout, options,
                and user_data_dir are ignored. The backend should already be initialized.
        """
        # Initialize parent class (Debuggable -> Identifiable)
        super().__init__(**kwargs)

        # Always use a backend adapter for unified interface
        if backend is not None:
            self._backend = backend
        else:
            # Default to SeleniumBackend for backward compatibility
            from webaxon.automation.backends.selenium import SeleniumBackend

            self._backend = SeleniumBackend()
            # Convert enum to string for backend interface
            browser_type = (
                driver_type.value if hasattr(driver_type, "value") else str(driver_type)
            )
            self._backend.initialize(
                browser_type=browser_type,
                headless=headless,
                user_agent=user_agent,
                timeout=timeout,
                options=options,
                user_data_dir=user_data_dir,
                config=config,
            )

        # Set self as Debuggable logger on backend for session-level log passthrough
        if hasattr(self._backend, '_logger'):
            self._backend._logger = self

        # Get driver type from backend
        backend_type = self._backend.driver_type
        if isinstance(backend_type, str):
            try:
                self._driver_type = WebAutomationDrivers(backend_type)
            except ValueError:
                self._driver_type = backend_type
        else:
            self._driver_type = backend_type

        self._state = state
        self.state_setting_max_retry = state_setting_max_retry
        self.state_setting_retry_wait = state_setting_min_wait

        # Action configurations (defines memory modes and follow-up behavior per action)
        if action_configs is None:
            self._action_configs = DEFAULT_ACTION_CONFIGS
        else:
            self._action_configs = action_configs

        # Window management: each window gets its own WindowInfo instance
        self._window_infos: Mapping[str, WindowInfo] = {}

        # Monitor tab tracking: handles of tabs dedicated to monitoring
        # These tabs are excluded from action execution to prevent accidental use
        self._monitor_tabs: set = set()

        # Trajectory capture: save per-step screenshots for evaluation
        self._capture_trajectory: bool = False
        self._trajectory_dir: Optional[str] = None
        self._trajectory_step_counter: int = 0

    def _log_trajectory_screenshot(
        self, screenshot_path: str, step: int, phase: str = "before"
    ) -> None:
        """Log a trajectory screenshot as an artifact through the Debuggable logger.

        This enables turn-aware association: SessionLogger routes the log entry
        into the current turn's session.jsonl via ``group='turn_NNN'``.
        """
        from datetime import datetime

        self.log_info(
            {
                "artifact_type": "Screenshot",
                "path": screenshot_path,
                "step": step,
                "phase": phase,
                "timestamp": datetime.now().isoformat(),
            },
            log_type="TrajectoryScreenshot",
        )

    @property
    def backend(self) -> Optional[Any]:
        """Get the backend adapter if using backend mode, None otherwise."""
        return self._backend

    @property
    def is_using_backend(self) -> bool:
        """Check if WebDriver is using a backend adapter."""
        return self._backend is not None

    @property
    def _driver(self):
        """Backward compatibility: access the underlying driver via backend."""
        return self._backend.raw_driver

    @property
    def driver_type(self) -> WebAutomationDrivers:
        """Get the type of the underlying browser driver."""
        return self._driver_type

    @property
    def backend_type(self) -> str:
        """
        Get the backend type string ('selenium' or 'playwright').

        Returns:
            str: 'selenium' for SeleniumBackend, 'playwright' for PlaywrightBackend

        Example:
            >>> driver = WebDriver()  # Default Selenium
            >>> driver.backend_type
            'selenium'
            >>> driver = WebDriver(backend=PlaywrightBackend())
            >>> driver.backend_type
            'playwright'
        """
        backend_class_name = type(self._backend).__name__.lower()
        if "selenium" in backend_class_name:
            return "selenium"
        elif "playwright" in backend_class_name:
            return "playwright"
        else:
            # For other backends, return the class name without 'Backend' suffix
            return backend_class_name.replace("backend", "")

    def is_selenium_backend(self) -> bool:
        """
        Check if the WebDriver is using a Selenium backend.

        Returns:
            bool: True if using SeleniumBackend, False otherwise

        Example:
            >>> driver = WebDriver()  # Default Selenium
            >>> driver.is_selenium_backend()
            True
        """
        return self.backend_type == "selenium"

    def is_playwright_backend(self) -> bool:
        """
        Check if the WebDriver is using a Playwright backend.

        Returns:
            bool: True if using PlaywrightBackend, False otherwise

        Example:
            >>> from webaxon.automation.backends import PlaywrightBackend
            >>> backend = PlaywrightBackend()
            >>> backend.initialize(browser_type='chromium')
            >>> driver = WebDriver(backend=backend)
            >>> driver.is_playwright_backend()
            True
        """
        return self.backend_type == "playwright"

    def supports_cdp(self) -> bool:
        """
        Check if the driver supports Chrome DevTools Protocol (CDP) commands.

        CDP is supported by Chrome, UndetectedChrome, Edge (Chromium-based), and Chromium browsers.

        Returns:
            bool: True if the driver supports CDP commands, False otherwise.
        """
        return self._backend.supports_cdp()

    # region Monitor Tab Tracking
    # These methods track tabs dedicated to monitoring, preventing actions from
    # accidentally executing on them. Monitor tabs are managed by the iteration
    # callable created by create_monitor().

    def register_monitor_tab(self, handle: str) -> None:
        """
        Register a tab as a monitor tab (not available for actions).

        Monitor tabs are dedicated to watching for conditions and should not be
        used for action execution. This method is called by the monitor iteration
        callable when opening a new monitor tab.

        Args:
            handle: The window handle of the monitor tab

        Example:
            >>> webdriver.register_monitor_tab("CDwindow-ABC123")
            >>> webdriver.is_monitor_tab("CDwindow-ABC123")
            True
        """
        self._monitor_tabs.add(handle)

    def unregister_monitor_tab(self, handle: str) -> None:
        """
        Unregister a monitor tab (e.g., when monitoring completes).

        This method is called by the monitor iteration callable when closing
        a monitor tab or when monitoring completes/errors.

        Args:
            handle: The window handle to unregister

        Example:
            >>> webdriver.unregister_monitor_tab("CDwindow-ABC123")
            >>> webdriver.is_monitor_tab("CDwindow-ABC123")
            False
        """
        self._monitor_tabs.discard(handle)

    def is_monitor_tab(self, handle: str) -> bool:
        """
        Check if a tab handle is a monitor tab.

        Args:
            handle: The window handle to check

        Returns:
            True if the handle is registered as a monitor tab, False otherwise

        Example:
            >>> webdriver.register_monitor_tab("CDwindow-ABC123")
            >>> webdriver.is_monitor_tab("CDwindow-ABC123")
            True
            >>> webdriver.is_monitor_tab("CDwindow-XYZ789")
            False
        """
        return handle in self._monitor_tabs

    def get_action_tabs(self) -> List[str]:
        """
        Get all tabs available for actions (excludes monitor tabs).

        This method returns window handles that can be used for action execution,
        filtering out any tabs that are dedicated to monitoring.

        Returns:
            List of window handles available for actions

        Example:
            >>> # With 3 tabs open, 1 being a monitor tab
            >>> webdriver.get_action_tabs()
            ['CDwindow-ABC123', 'CDwindow-DEF456']  # excludes monitor tab
        """
        return [h for h in self.window_handles if not self.is_monitor_tab(h)]

    def get_monitor_tabs(self) -> List[str]:
        """
        Get all active monitor tabs.

        Returns:
            List of window handles that are registered as monitor tabs

        Example:
            >>> webdriver.register_monitor_tab("CDwindow-MONITOR1")
            >>> webdriver.get_monitor_tabs()
            ['CDwindow-MONITOR1']
        """
        return list(self._monitor_tabs)

    def switch_to_action_tab(self, handle: Optional[str] = None) -> str:
        """
        Switch to an action tab, preventing accidental switch to monitor tabs.

        This method ensures that actions are never executed on monitor tabs by
        validating the target handle before switching.

        Args:
            handle: Specific tab handle to switch to, or None to use first
                   available action tab

        Returns:
            The handle of the tab switched to

        Raises:
            ValueError: If handle is a monitor tab or no action tabs available

        Example:
            >>> # Switch to a specific action tab
            >>> webdriver.switch_to_action_tab("CDwindow-ABC123")
            'CDwindow-ABC123'

            >>> # Switch to first available action tab
            >>> webdriver.switch_to_action_tab()
            'CDwindow-ABC123'

            >>> # Attempting to switch to a monitor tab raises error
            >>> webdriver.register_monitor_tab("CDwindow-MONITOR")
            >>> webdriver.switch_to_action_tab("CDwindow-MONITOR")
            ValueError: Cannot switch to monitor tab CDwindow-MONITOR for actions
        """
        if handle is not None:
            if self.is_monitor_tab(handle):
                raise ValueError(f"Cannot switch to monitor tab {handle} for actions")
            self.switch_to.window(handle)
            return handle

        action_tabs = self.get_action_tabs()
        if not action_tabs:
            raise ValueError("No action tabs available")
        self.switch_to.window(action_tabs[0])
        return action_tabs[0]

    # endregion

    def get_body_html_from_url(
        self,
        url: str = None,
        initial_wait: float = 0,
        timeout_for_page_loading: int = 20,
        return_dynamic_contents: bool = True,
    ):
        return self._backend.get_body_html_from_url(
            url=url,
            initial_wait=initial_wait,
            timeout_for_page_loading=timeout_for_page_loading,
            return_dynamic_contents=return_dynamic_contents,
        )

    def get_body_html(self, return_dynamic_contents: bool = True) -> str:
        return self._backend.get_body_html(
            return_dynamic_contents=return_dynamic_contents
        )

    def get_element_html(self, element) -> str:
        return self._backend.get_element_html(element=element)

    def wait_for_page_loading(
        self, timeout: int = 30, extra_wait_min=1, extra_wait_max=5
    ):
        self._backend.wait_for_page_loading(
            timeout=timeout,
            extra_wait_min=extra_wait_min,
            extra_wait_max=extra_wait_max,
        )

    def find_element_by_xpath(
        self,
        tag_name: Optional[str] = "*",
        attributes: Mapping[str, Any] = None,
        text: str = None,
        immediate_text: str = None,
    ):
        return self._backend.find_element_by_xpath(
            tag_name=tag_name,
            attributes=attributes,
            text=text,
            immediate_text=immediate_text,
        )

    def find_elements_by_xpath(
        self,
        tag_name: Optional[str] = "*",
        attributes: Mapping[str, Any] = None,
        text: str = None,
        immediate_text: str = None,
    ):
        return self._backend.find_elements_by_xpath(
            tag_name=tag_name,
            attributes=attributes,
            text=text,
            immediate_text=immediate_text,
        )

    def add_unique_index_to_elements(self, index_name=None):
        self._backend.add_unique_index_to_elements(index_name=index_name)

    def find_element_by_html(
        self,
        target_element_html,
        identifying_attributes=("id", "aria-label", "class"),
        always_return_single_element: bool = False,
    ):
        return self._backend.find_element_by_html(
            target_element_html=target_element_html,
            identifying_attributes=identifying_attributes,
            always_return_single_element=always_return_single_element,
        )

    # region schema-based target resolution

    def resolve_action_target(
        self, strategy: Union[TargetStrategy, str], action_target: str
    ) -> Optional[WebElement]:
        """
        Resolve element using explicit strategy.

        This is the simple contract for ActionFlow's strategy_resolver.
        All orchestration logic (fallback, default strategy lookup) is handled
        by ActionFlow.

        Supported strategies (TargetStrategy enum or string):
        - FRAMEWORK_ID / "__id__": Find by framework-assigned unique ID attribute
        - ID / "id": Find by element ID
        - XPATH / "xpath": Find by XPath expression
        - CSS / "css" / "css_selector": Find by CSS selector
        - TEXT / "text": Find by text content (via XPath contains)
        - SOURCE / "source": Find element by HTML source (via find_element_by_html)
        - LITERAL / "literal": Return value as-is (e.g., for URLs)
        - DESCRIPTION / "description": AI-based natural language resolution (not yet implemented)

        Additional Selenium locators (string only, not in TargetStrategy enum):
        - "name": Find by name attribute
        - "tag" / "tag_name": Find by tag name
        - "class" / "class_name": Find by class name
        - "link_text": Find by exact link text
        - "partial_link_text": Find by partial link text

        Args:
            strategy: Resolution strategy (TargetStrategy enum or string)
            action_target: Strategy-specific value (e.g., element ID, XPath expression)

        Returns:
            Selenium WebElement, or the literal value for literal strategy

        Raises:
            NoSuchElementException: If element cannot be located (from Selenium)
            NotImplementedError: If strategy is not supported
        """
        # Normalize strategy to string for comparison
        # TargetStrategy is a str enum, so we can use str() or .value
        if hasattr(strategy, "value"):
            strategy_str = strategy.value
        else:
            strategy_str = str(strategy)

        # TargetStrategy enum values - delegate to backend for consistent behavior
        if strategy_str == TargetStrategy.FRAMEWORK_ID.value:  # '__id__'
            return self._backend.find_element_by_unique_index(action_target)
        elif strategy_str == TargetStrategy.ID.value:  # 'id'
            return self.find_element("id", action_target)
        elif strategy_str == TargetStrategy.XPATH.value:  # 'xpath'
            return self.find_element("xpath", action_target)
        elif (
            strategy_str == TargetStrategy.CSS.value or strategy_str == "css_selector"
        ):  # 'css'
            return self.find_element("css selector", action_target)
        elif strategy_str == TargetStrategy.TEXT.value:  # 'text'
            # Find element containing the specified text
            xpath = f"//*[contains(text(), '{action_target}')]"
            return self.find_element("xpath", xpath)
        elif strategy_str == TargetStrategy.SOURCE.value:  # 'source'
            # Find element by HTML source snippet
            return self._backend.find_element_by_html(
                action_target, always_return_single_element=True
            )
        elif strategy_str == TargetStrategy.LITERAL.value:  # 'literal'
            return action_target
        elif strategy_str == TargetStrategy.DESCRIPTION.value:  # 'description'
            # AI-based natural language resolution
            raise NotImplementedError(
                f"Description-based element resolution is not yet implemented"
            )
        # Additional Selenium locators (string-based, not in TargetStrategy enum)
        elif strategy_str == "name":
            return self.find_element("name", action_target)
        elif strategy_str in ("tag", "tag_name"):
            return self.find_element("tag name", action_target)
        elif strategy_str in ("class", "class_name"):
            return self.find_element("class name", action_target)
        elif strategy_str == "link_text":
            return self.find_element("link text", action_target)
        elif strategy_str == "partial_link_text":
            return self.find_element("partial link text", action_target)
        else:
            raise NotImplementedError(f"Unsupported strategy: {strategy_str}")

    # endregion

    def capture_full_page_screenshot(
        self,
        output_path: str,
        center_element: WebElement = None,
        restore_window_size: bool = False,
        reset_zoom: bool = True,
        use_cdp_cmd_for_chrome: bool = False,
    ):
        self._backend.capture_full_page_screenshot(
            output_path=output_path,
            center_element=center_element,
            restore_window_size=restore_window_size,
            reset_zoom=reset_zoom,
            use_cdp_cmd_for_chrome=use_cdp_cmd_for_chrome,
        )

    def capture_screenshot(self, output_path: str, reset_zoom: bool = True) -> None:
        """Capture a full-page screenshot via the backend.

        Simplified wrapper around capture_full_page_screenshot() for evaluation
        and trajectory capture use cases.
        """
        self._backend.capture_full_page_screenshot(
            output_path=output_path,
            reset_zoom=reset_zoom,
            use_cdp_cmd_for_chrome=(
                hasattr(self._backend, 'supports_cdp') and self._backend.supports_cdp()
            ),
        )

    # region action methods
    def open_url(self, url: str = None, wait_after_opening_url: float = 0):
        return self._backend.open_url(
            url=url, wait_after_opening_url=wait_after_opening_url
        )

    def search(
        self,
        query: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sites: Optional[Iterable[str]] = None,
        provider: SearchProviders = SearchProviders.GOOGLE,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
        **other_search_args,
    ):
        from webaxon.automation.backends.selenium.actions import search

        return search(
            driver=self._driver,
            query=query,
            start_date=start_date,
            end_date=end_date,
            sites=sites,
            provider=provider,
            timeout=timeout,
            additional_wait_time=additional_wait_time,
            **other_search_args,
        )

    def execute_single_action(
        self,
        element,
        action_type: str,
        action_args: Mapping = None,
        attachments: Sequence = None,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
    ):
        """
        Execute a single action on an element.

        Args:
            element: WebElement or PlaywrightElementShim to perform action on
            action_type: Type of action (e.g., 'click', 'scroll', 'input_text')
            action_args: Optional arguments for the action
            timeout: Maximum time to wait for page loading
            additional_wait_time: Extra time to wait after page loads

        Returns:
            str for 'get_text'/'get_html', None otherwise
        """
        return self._backend.execute_single_action(
            element=element,
            action_type=action_type,
            action_args=action_args,
            attachments=attachments,
            timeout=timeout,
            additional_wait_time=additional_wait_time,
        )

    def execute_actions(
        self,
        actions: Mapping,
        init_cond: Union[bool, ElementConditions] = None,
        repeat: int = 0,
        repeat_when: ElementConditions = None,
        elements_dict: ElementDict = None,
        output_path_action_records: str = None,
        **kwargs,
    ):
        self._backend.execute_actions(
            actions=actions,
            init_cond=init_cond,
            repeat=repeat,
            repeat_when=repeat_when,
            elements_dict=elements_dict,
            output_path_action_records=output_path_action_records,
            **kwargs,
        )

    # endregion

    # region Action Memory Integration

    def _get_window_info(self, window: Optional[str] = None) -> WindowInfo:
        """
        Get or create WindowInfo for specified window or current window.

        Args:
            window: Optional window handle. If None, uses current active window.

        Returns:
            WindowInfo instance for the window

        Raises:
            ValueError: If specified window doesn't exist in browser
        """
        window_handle = window if window is not None else self.current_window_handle()

        # Validate window exists in browser
        if window_handle not in self.window_handles:
            raise ValueError(
                f"Window '{window_handle}' does not exist in browser. "
                f"Open windows: {self.window_handles}"
            )

        if window_handle not in self._window_infos:
            # Create new WindowInfo with configured ContentMemory
            self._window_infos[window_handle] = WindowInfo(
                handle=window_handle,
                action_memory=ContentMemory(
                    accumulate=True,
                    auto_merge_memory=True,
                    use_base_memory_for_merge=True,
                    default_get_children=self._extract_html_elements,
                    default_get_signature=self._get_element_html_signature,
                    get_base_signatures=self._extract_html_element_signatures,
                    base_memory=None,
                    associated_attributes={},
                ),
            )

        return self._window_infos[window_handle]

    def _extract_html_elements(self, html: str):
        """
        Parse HTML and extract all elements as BeautifulSoup Tags.

        Args:
            html: HTML string to parse

        Returns:
            List of BeautifulSoup Tag objects
        """
        from bs4 import BeautifulSoup

        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        # Extract all elements (excluding NavigableString and other non-Tag nodes)
        from bs4 import Tag

        return [elem for elem in soup.descendants if isinstance(elem, Tag)]

    def _get_element_html_signature(self, element) -> str:
        """
        Compute signature for a BeautifulSoup element using get_element_signature.

        Args:
            element: BeautifulSoup Tag object

        Returns:
            Signature string for the element
        """
        from webaxon.html_utils.element_identification import get_element_signature

        return get_element_signature(
            element=element,
            ignore_attrs=(ATTR_NAME_INCREMENTAL_ID,),
            consider_text=False,  # Match the behavior in extract_incremental_html_change
            consider_children=False,
        )

    def _extract_html_element_signatures(self, html: str) -> set:
        """
        Extract all element signatures from HTML for deduplication.

        Args:
            html: HTML string

        Returns:
            Set of signatures for all elements in the HTML
        """
        elements = self._extract_html_elements(html)
        return {self._get_element_html_signature(elem) for elem in elements}

    def _get_current_window_memory(self, window: Optional[str] = None) -> ContentMemory:
        """
        Get ContentMemory instance for the specified window or current window.

        Args:
            window: Optional window handle. If None, uses current active window.

        Returns:
            ContentMemory instance for the window
        """
        return self._get_window_info(window).action_memory

    def _should_treat_action_as_follow_up(
        self,
        is_follow_up: bool,
        action_config: WebAgentAction,
        window: Optional[str] = None,
    ) -> bool:
        """
        Determine if action should be treated as follow-up.

        Returns False if:
        - is_follow_up is False
        - Action doesn't allow follow-up
        - Last action type differs from current action

        Args:
            is_follow_up: Caller's indication that this is a follow-up
            action_config: Configuration for the current action
            window: Optional window handle

        Returns:
            True if should treat as follow-up, False otherwise
        """
        if not is_follow_up:
            return False

        if not action_config.allow_follow_up:
            return False

        window_info = self._get_window_info(window)
        if window_info.last_action_type != action_config.name:
            return False

        return True

    @staticmethod
    def _clean_html_for_memory(html: str) -> str:
        # NOTE: the clean-html setup is subject to change
        additional_rule_set_activation_flags = None

        return clean_html(
            html,
            tags_to_always_remove=DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=(
                *DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP,
                ATTR_NAME_INCREMENTAL_ID,
            ),
            keep_elements_with_immediate_text=True,
            keep_only_incremental_change=False,
            html_content_to_compare=None,
            consider_text_for_comparison=False,
            keep_all_text_in_hierarchy_for_incremental_change=True,
            ignore_attrs_for_comparison=(ATTR_NAME_INCREMENTAL_ID,),
            collapse_non_interactive_tags=True,
            collapse_non_interactive_tags_merge_attributes_exclusion=(
                ATTR_NAME_INCREMENTAL_ID,
            ),
            additional_rule_set_activation_flags=additional_rule_set_activation_flags,
        )

    @staticmethod
    def _clean_html_for_action_results(
        html_after_action: str,
        html_before_action: Optional[str],
        return_only_incremental_change: bool,
    ) -> str:
        return clean_html(
            html_after_action,
            tags_to_always_remove=DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=(
                *DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP,
                ATTR_NAME_INCREMENTAL_ID,
            ),
            keep_elements_with_immediate_text=True,
            keep_only_incremental_change=return_only_incremental_change,
            html_content_to_compare=html_before_action,
            consider_text_for_comparison=False,
            keep_all_text_in_hierarchy_for_incremental_change=True,
            ignore_attrs_for_comparison=(ATTR_NAME_INCREMENTAL_ID,),
            collapse_non_interactive_tags=True,
            collapse_non_interactive_tags_merge_attributes_exclusion=(
                ATTR_NAME_INCREMENTAL_ID,
            ),
            additional_rule_set_activation_flags=DEFAULT_RULE_ACTIVATION_FLAGS,
        )

    def _capture_base_memory(
        self,
        action_config: WebAgentAction,
        element: Optional[Any],
        memory: ContentMemory,
    ):
        """
        Capture base memory for a new action sequence.

        This method captures the baseline HTML content based on the action's
        base_memory_mode configuration and stores it in the provided memory.

        Args:
            action_config: Configuration for the current action
            element: Target element (WebElement) for the action, or None for actions without elements
            memory: ContentMemory instance to capture into
        """

        if action_config.base_memory_mode == ActionMemoryMode.FULL:
            # Capture full body HTML as base
            base_html = self.get_body_html(return_dynamic_contents=True)
            cleaned_base_html = self._clean_html_for_memory(base_html)

            # If incremental mode is TARGET, also capture target element base for comparison/deduplication
            if action_config.incremental_change_mode == ActionMemoryMode.TARGET:
                target_element_html = self.get_element_html(element)
                if target_element_html:
                    cleaned_target_element_html = self._clean_html_for_memory(
                        target_element_html
                    )
                    memory.set_base_memory(
                        cleaned_base_html, cleaned_target_element_html
                    )
                else:
                    memory.set_base_memory(cleaned_base_html)
            else:
                memory.set_base_memory(cleaned_base_html)

        elif action_config.base_memory_mode == ActionMemoryMode.TARGET:
            # Capture target element HTML as base (also used for comparison)
            target_element_html = self.get_element_html(element)
            cleaned_target_element_html = self._clean_html_for_memory(
                target_element_html
            )
            if cleaned_target_element_html:
                memory.set_base_memory(cleaned_target_element_html)
        elif action_config.base_memory_mode == ActionMemoryMode.NONE:
            # New action disables action memory
            # At the moment one memory object is used for all actions, so we clear it
            memory.clear()
        else:
            raise ValueError(
                f"Invalid base memory mode '{action_config.base_memory_mode}'"
            )

    def _capture_incremental_memory(
        self,
        action_config: WebAgentAction,
        element: Optional[Any],
        memory: ContentMemory,
    ):
        """
        Capture incremental memory snapshot based on action config.

        Args:
            action_config: Configuration for the current action
            element: Target element (WebElement) for the action, or None for actions without elements
            memory: ContentMemory instance to capture into
        """
        from webaxon.automation.backends.selenium.common import is_element_stale

        html = None
        if action_config.incremental_change_mode == ActionMemoryMode.FULL:
            html = self.get_body_html(return_dynamic_contents=True)
        elif action_config.incremental_change_mode == ActionMemoryMode.TARGET:
            if element is not None:
                # Check if element became stale after action
                if is_element_stale(element):
                    self.log_warning(
                        f"Target element became stale after '{action_config.name}' action. "
                        f"Skipping incremental memory capture for this iteration. "
                        f"This can happen when the DOM is re-rendered during action execution."
                    )
                else:
                    html = self.get_element_html(element)
        elif action_config.base_memory_mode != ActionMemoryMode.NONE:
            raise ValueError(
                f"Invalid base memory mode '{action_config.base_memory_mode}'"
            )

        if html:
            cleaned_html = self._clean_html_for_memory(html)
            memory.capture_snapshot(cleaned_html)

    # endregion

    @property
    def source(self):
        return self._backend.current_url

    @property
    def raw_driver(self):
        """Access the underlying driver instance for direct operations."""
        return self._backend.raw_driver

    @property
    def current_url(self) -> str:
        """Get the current URL of the browser."""
        return self._backend.current_url

    @property
    def title(self) -> str:
        """Get the title of the current page."""
        return self._backend.title

    @property
    def page_source(self) -> str:
        """Get the full HTML source of the current page."""
        return self._backend.page_source

    @property
    def window_handles(self) -> List[str]:
        """Get list of all window handles."""
        return self._backend.window_handles

    def current_window_handle(self) -> str:
        """Get the handle of the current window.

        Returns the handle of the programmatically tracked current page.

        Note:
            This only tracks programmatic tab switches (via switch_to.window()).
            It cannot detect manual tab switches by the user. This is a fundamental
            limitation of browser automation APIs - neither Selenium nor Playwright
            can detect which tab the user is viewing.
        """
        return self._backend.current_window_handle()

    @property
    def switch_to(self):
        """Access the switch_to interface for window/frame switching."""
        return self._backend.switch_to

    def execute_script(self, script: str, *args):
        """Execute JavaScript in the browser."""
        return self._backend.execute_script(script, *args)

    def get(self, url: str):
        """Navigate to a URL."""
        return self._backend.get(url)

    def close(self):
        """Close the current window."""
        return self._backend.close()

    def find_element(self, by: str, value: str):
        """Find a single element by locator strategy."""
        return self._backend.find_element(by, value)

    def find_elements(self, by: str, value: str):
        """Find multiple elements by locator strategy."""
        return self._backend.find_elements(by, value)

    @property
    def state(self) -> Mapping[str, Any]:
        """
        Get the current state of the WebDriver.

        This property provides a dictionary containing information about the current browser window,
        such as the handle of the currently active window.

        Returns:
            Mapping[str, Any]: A dictionary with the current browser state, including:
                - 'current_window': The handle of the currently active window.

        Example:
            >>> web_driver = WebDriver(WebAutomationDrivers.UndetectedChrome)
            >>> web_driver.state
            {'current_window': ...}
        """
        return {"current_window": self.current_window_handle()}

    @state.setter
    def state(self, state: Mapping[str, Any]):
        """
        Set the current state of the WebDriver.

        This property allows switching the WebDriver's active window to the one specified in the input state.
        The input must contain a valid 'current_window' key corresponding to an existing browser window handle.

        Args:
            state (Mapping[str, Any]): A dictionary containing the target window's handle. Must include:
                - 'current_window': The handle of the window to switch to.
        """
        # ignores empty `state`
        if not state:
            # No state provided; nothing to do
            self.log_warning("No state provided. Skipping state update.")
            return

        # Check if the state contains the 'current_window' key
        if "current_window" not in state:
            self.log_warning(
                "The provided state does not contain 'current_window'. Skipping window switch."
            )
            return

        target_window = state[self.STATE_FIELD_CURRENT_WINDOW]

        # Check if the current browser window is the same as the target window
        if self.current_window_handle() == target_window:
            return

        # Check if the target window exists among current browser windows
        if target_window not in self.window_handles:
            self.log_warning(
                f"The requested window '{target_window}' does not exist among open windows. "
                f"Open windows: {self.window_handles}"
            )
            return

        def _set_state():
            # Attempt to switch to the specified window
            try:
                self.switch_to.window(target_window)
            except Exception as e:
                self.log_warning(
                    f"Failed to switch to window '{target_window}' due to an error: {e}"
                )
            return self.current_window_handle()

        def _set_state_validator(_driver_current_window_handle):
            if _driver_current_window_handle == target_window:
                return True
            else:
                self.log_warning(
                    f"Attempted to switch to window '{target_window}' but the active window is "
                    f"still '{_driver_current_window_handle}'."
                )
                return False

        execute_with_retry(
            func=_set_state,
            max_retry=self.state_setting_max_retry,
            min_retry_wait=self.state_setting_retry_wait,
            output_validator=_set_state_validator,
        )

    def __call__(
        self,
        action_type: str,
        action_target: str = None,
        action_args: Mapping = None,
        attachments: Sequence = None,
        timeout: int = 20,
        additional_wait_time: float = 2.0,
        return_only_incremental_change_for_cleaned_body_html: Union[
            bool, float
        ] = False,
        action_is_follow_up: bool = False,
        action_memory_target: str = None,
        action_configs: Mapping[str, WebAgentAction] = None,
        action_target_strategy: Union[str, TargetStrategy] = None,
        force_new_tab_if_current_tab_is_monitored: bool = True,
        no_action_if_target_not_found: bool = False,
        ongoing_sequence_actions: bool = False,
    ):
        """
        Execute a web action with configuration-driven memory capture.

        Args:
            action_type: Type of action to execute
            action_target: Target element ID or URL for the action
            action_args: Additional arguments for the action
            timeout: Timeout for action execution
            additional_wait_time: Additional wait time after action
            return_only_incremental_change_for_cleaned_body_html: Whether to return only incremental changes (for backward compatibility)
            action_is_follow_up: Whether this action is a follow-up to a previous action of the same type
            action_memory_target: Optional element ID for memory capture (if different from action_target).
                                 Allows tracking HTML changes in a different element than the action target.
                                 Example: Click a "Load More" button but track changes in the list container.
            action_configs: Action configuration mapping (uses default if None)
            force_new_tab_if_current_tab_is_monitored: If True (default) and current tab is being monitored,
                                                       opens visit_url in a new tab to preserve the monitored tab.
            no_action_if_target_not_found: If True, skip action gracefully when target element is not found
                                          instead of raising ElementNotFoundError. Returns a WebDriverActionResult
                                          with action_skipped=True. Default is False (raises exception).
            reindex_after_action: If True (default), re-assign __id__ attributes to all DOM elements
                                 after action execution. Set to False when executing batched actions
                                 to preserve the __id__ values that the LLM planned against.

        Returns:
            WebDriverActionResult with execution details and captured HTML
        """
        _logger.debug(
            f"[WebDriver.__call__] RECEIVED: action_type={action_type}, "
            f"action_target={action_target}, "
            f"action_target_type={type(action_target).__name__}, "
            f"action_target_strategy={action_target_strategy}"
        )
        action_type = cut(action_type, cut_before_last=".").strip()
        action_type = camel_to_snake_case(action_type)
        if action_args:
            action_args = {camel_to_snake_case(k): v for k, v in action_args.items()}

        if action_configs is None:
            action_configs = self._action_configs
        action_config = action_configs.get(action_type)
        if action_config is None:
            action_config = DEFAULT_ACTION_CONFIGS.get(
                action_type,
                WebAgentAction(name=action_type),  # Default: no memory capture
            )

        action_is_follow_up = self._should_treat_action_as_follow_up(
            action_is_follow_up, action_config
        )
        window_info = self._get_window_info()
        action_memory = window_info.action_memory

        if return_only_incremental_change_for_cleaned_body_html:
            body_html_before_last_action = self.get_body_html(
                return_dynamic_contents=True
            )
        else:
            body_html_before_last_action = None

        # Initialize trajectory screenshot paths (set in execute_single_action branch)
        _screenshot_before_path = None
        _screenshot_after_path = None

        if action_type == 'no_op':
            # No operation — just capture current page state (used after user copilot interactions)
            action_is_follow_up = False
            element = None
            memory_element = None
        elif action_type == 'wait':
            action_is_follow_up = False
            element = None
            memory_element = None  # No memory capture for wait actions
            wait_duration = float(action_target) if action_target else 1.0
            sleep(wait_duration)
        elif action_type == "search":
            action_is_follow_up = False
            element = None
            memory_element = None  # No memory capture for search actions
            provider_string = get_(action_args, "provider", default="Google")
            providers = split_(provider_string, ",", lstrip=True, rstrip=True)
            for provider in providers:
                self.search(
                    query=action_target,
                    start_date=get_(action_args, "start_date", default=None),
                    end_date=get_(action_args, "end_date", default=None),
                    sites=get_(action_args, "sites", default=None),
                    provider=SearchProviders(provider),
                    timeout=timeout,
                    additional_wait_time=additional_wait_time,
                )
        elif action_config.composite_action is not None:
            # Handle composite actions
            action_is_follow_up = False  # Composite actions don't support follow-up
            element = None
            memory_element = None  # No memory capture for composite actions

            # Split action_target by space to get individual element IDs
            element_ids = action_target.split()

            # Resolve all element IDs to WebElements
            elements = []
            for element_id in element_ids:
                elem = self._backend.find_element_by_unique_index(element_id)
                elements.append(elem)

            # Filter attachments based on action config
            filtered_attachments = (
                attachments if action_config.allow_attachments else None
            )

            # Execute composite action using backend-specific implementation
            self._backend.execute_composite_action(
                elements=elements,
                action_config=action_config,
                action_args=action_args,
                attachments=filtered_attachments,
                timeout=timeout,
                additional_wait_time=additional_wait_time,
            )
        else:
            if action_type == "visit_url":
                element = action_target
                action_is_follow_up = False  # disable follow-up for 'visit_url'

                # If current tab is monitored, open URL in a new tab to preserve the monitored tab
                current_handle = self.current_window_handle()
                is_monitored = self.is_monitor_tab(current_handle)
                _logger.debug(
                    f"[visit_url] current_handle={current_handle}, "
                    f"is_monitored={is_monitored}, "
                    f"force_new_tab_if_monitored={force_new_tab_if_current_tab_is_monitored}"
                )
                if force_new_tab_if_current_tab_is_monitored and is_monitored:
                    action_args = dict(action_args) if action_args else {}
                    action_args["try_open_in_new_tab"] = True
                    _logger.debug(f"[visit_url] Setting try_open_in_new_tab=True")
            else:
                # Resolve element using strategy if provided, otherwise default to INCREMENTAL_ID
                _logger.debug(
                    f"[WebDriver.__call__] Resolving element: "
                    f"action_target_strategy={action_target_strategy}, "
                    f"action_target={action_target}"
                )
                try:
                    if action_target_strategy is not None:
                        _logger.debug(
                            f"[WebDriver.__call__] Using resolve_action_target({action_target_strategy}, {action_target})"
                        )
                        element = self.resolve_action_target(
                            action_target_strategy, action_target
                        )
                    else:
                        _logger.debug(
                            f"[WebDriver.__call__] Using find_element_by_unique_index({action_target})"
                        )
                        element = self._backend.find_element_by_unique_index(
                            action_target
                        )
                except ElementNotFoundError as e:
                    if no_action_if_target_not_found:
                        _logger.info(
                            f"[WebDriver.__call__] Target not found for '{action_type}', "
                            f"skipping due to no_action_if_target_not_found=True. "
                            f"Strategy={action_target_strategy}, Target={action_target}"
                        )
                        return WebDriverActionResult(
                            body_html_before_last_action=body_html_before_last_action
                            or "",
                            body_html_after_last_action="",
                            cleaned_body_html_after_last_action="",
                            is_cleaned_body_html_only_incremental_change=False,
                            source="skipped",
                            action_skipped=True,
                            skip_reason=f"Element not found: {e}",
                        )
                    else:
                        raise

            # Determine memory element (can be different from action element)
            try:
                if action_memory_target and action_memory_target != action_target:
                    # Memory target is specified and different from action target
                    memory_element = self._backend.find_element_by_unique_index(
                        action_memory_target
                    )
                else:
                    # Use the same element for both action and memory
                    memory_element = element
            except ElementNotFoundError:
                if no_action_if_target_not_found:
                    memory_element = None
                else:
                    raise

            if not action_is_follow_up:
                # First action in the series, capture initial memory
                action_memory.exclude_last_entry_from_memory = (
                    action_config.capture_incremental_memory_after_action
                )
                self._capture_base_memory(action_config, memory_element, action_memory)
            elif not action_config.capture_incremental_memory_after_action:
                # For follow-up actions with before-capture mode:
                # Capture current state before the action (gets result of previous action)
                self._capture_incremental_memory(
                    action_config, memory_element, action_memory
                )

            _handles_before = set(self.window_handles)
            _current_before = self.current_window_handle()

            # Trajectory capture: screenshot BEFORE action
            _screenshot_before_path = None
            if self._capture_trajectory and self._trajectory_dir:
                _screenshot_before_path = os.path.join(
                    self._trajectory_dir,
                    f"{self._trajectory_step_counter}_screenshot.png",
                )
                try:
                    os.makedirs(self._trajectory_dir, exist_ok=True)
                    self.capture_screenshot(_screenshot_before_path)
                    self._log_trajectory_screenshot(
                        _screenshot_before_path,
                        self._trajectory_step_counter,
                        phase="before",
                    )
                except Exception as _exc:
                    _logger.warning("Trajectory pre-screenshot failed: %s", _exc)
                    _screenshot_before_path = None

            self.execute_single_action(
                element=element,
                action_type=action_type,
                action_args=action_args,
                attachments=attachments,
                timeout=timeout,
                additional_wait_time=additional_wait_time,
            )

            # Trajectory capture: screenshot AFTER action
            _screenshot_after_path = None
            if self._capture_trajectory and self._trajectory_dir:
                _screenshot_after_path = os.path.join(
                    self._trajectory_dir,
                    f"{self._trajectory_step_counter}_post_screenshot.png",
                )
                try:
                    self.capture_screenshot(_screenshot_after_path)
                    self._log_trajectory_screenshot(
                        _screenshot_after_path,
                        self._trajectory_step_counter,
                        phase="after",
                    )
                except Exception as _exc:
                    _logger.warning("Trajectory post-screenshot failed: %s", _exc)
                    _screenshot_after_path = None
                self._trajectory_step_counter += 1

            # Log window handle after visit_url to trace tab switching
            if action_type == 'visit_url':
                _logger.debug(
                    f"[visit_url] AFTER execute_single_action: "
                    f"current_window_handle={self.current_window_handle()}"
                )

        # Capture incremental memory after action with after-capture mode
        if (
            action_config.capture_incremental_memory_after_action
            and memory_element is not None
        ):
            self._capture_incremental_memory(
                action_config, memory_element, action_memory
            )

        if not ongoing_sequence_actions:
            self.add_unique_index_to_elements(index_name=ATTR_NAME_INCREMENTAL_ID)
        body_html_after_last_action = self.get_body_html(return_dynamic_contents=True)
        cleaned_body_html_after_last_action = self._clean_html_for_action_results(
            html_after_action=body_html_after_last_action,
            html_before_action=body_html_before_last_action,
            return_only_incremental_change=return_only_incremental_change_for_cleaned_body_html,
        )

        # Update last action type for follow-up detection
        window_info.last_action_type = action_type

        return WebDriverActionResult(
            body_html_before_last_action=body_html_before_last_action,
            body_html_after_last_action=body_html_after_last_action,
            cleaned_body_html_after_last_action=cleaned_body_html_after_last_action,
            is_cleaned_body_html_only_incremental_change=return_only_incremental_change_for_cleaned_body_html,
            source=self.source,
            action_memory=action_memory,
            is_follow_up=action_is_follow_up,
            screenshot_before_path=_screenshot_before_path,
            screenshot_after_path=_screenshot_after_path,
        )

    def quit(self):
        """
        Terminate the entire browser session and release all resources.

        Unlike close() which only closes the current window/tab, quit() completely
        shuts down the browser:
        - Closes ALL open windows and tabs
        - Terminates the WebDriver process (chromedriver, geckodriver, etc.)
        - Releases all system resources (ports, memory, file handles)
        - Makes the driver instance unusable after this call

        Use quit() for final cleanup when you're done with the browser entirely.
        Use close() when you only want to close the current tab but keep the session.

        Note:
            This method is also called automatically in __del__ for cleanup,
            but explicit calls are recommended for deterministic resource release.
        """
        if hasattr(self, "_backend") and self._backend is not None:
            self._backend.quit()
            self._backend = None

    def __del__(self):
        self.quit()
