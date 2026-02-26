"""
Selenium-compatible shims for Playwright objects.

These shim classes wrap Playwright objects (Locator, Page, Browser) to provide
a Selenium-like interface, enabling code written for Selenium to work with
Playwright with minimal changes.

Design notes:
- PlaywrightElementShim wraps Playwright Locator to provide WebElement-like interface
- PlaywrightDriverShim wraps Playwright Page/Browser to provide WebDriver-like interface
- The shims use lazy evaluation to handle Playwright's Locator pattern
"""

import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

_logger = logging.getLogger(__name__)

# Try to import playwright, but don't fail if not installed
try:
    from playwright.sync_api import (
        Browser,
        BrowserContext,
        ElementHandle,
        Locator,
        Page,
        sync_playwright,
    )
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None
    BrowserContext = None
    ElementHandle = None
    Locator = None
    Page = None
    sync_playwright = None


class PlaywrightElementShim:
    """
    Selenium WebElement-compatible wrapper for Playwright Locator.

    This shim provides a WebElement-like interface for Playwright Locators,
    enabling existing code written for Selenium to work with Playwright.

    Key differences from WebElement:
    - Playwright Locators are lazy (don't resolve until action)
    - Some methods require explicit waits
    - Text content access uses different methods

    Usage:
        locator = page.locator('#my-element')
        element = PlaywrightElementShim(locator, page)
        element.click()  # Works like WebElement.click()
        print(element.text)  # Works like WebElement.text
    """

    def __init__(self, locator: 'Locator', page: 'Page'):
        """
        Initialize the element shim.

        Args:
            locator: Playwright Locator object
            page: Playwright Page object (needed for some operations)
        """
        self._locator = locator
        self._page = page

    @property
    def locator(self) -> 'Locator':
        """Get the underlying Playwright Locator."""
        return self._locator

    @property
    def page(self) -> 'Page':
        """Get the Playwright Page object."""
        return self._page

    # ==========================================================================
    # WebElement-compatible properties
    # ==========================================================================

    @property
    def text(self) -> str:
        """
        Get the visible text of the element.

        Equivalent to WebElement.text in Selenium.
        Uses Playwright's inner_text() which returns visible text.
        """
        return self._locator.inner_text()

    @property
    def tag_name(self) -> str:
        """
        Get the tag name of the element.

        Equivalent to WebElement.tag_name in Selenium.
        """
        return self._locator.evaluate("el => el.tagName.toLowerCase()")

    @property
    def size(self) -> Dict[str, int]:
        """
        Get the size of the element.

        Equivalent to WebElement.size in Selenium.
        Returns dict with 'width' and 'height' keys.
        """
        box = self._locator.bounding_box()
        if box:
            return {'width': int(box['width']), 'height': int(box['height'])}
        return {'width': 0, 'height': 0}

    @property
    def location(self) -> Dict[str, int]:
        """
        Get the location of the element.

        Equivalent to WebElement.location in Selenium.
        Returns dict with 'x' and 'y' keys.
        """
        box = self._locator.bounding_box()
        if box:
            return {'x': int(box['x']), 'y': int(box['y'])}
        return {'x': 0, 'y': 0}

    @property
    def rect(self) -> Dict[str, int]:
        """
        Get the location and size of the element.

        Equivalent to WebElement.rect in Selenium.
        """
        box = self._locator.bounding_box()
        if box:
            return {
                'x': int(box['x']),
                'y': int(box['y']),
                'width': int(box['width']),
                'height': int(box['height']),
            }
        return {'x': 0, 'y': 0, 'width': 0, 'height': 0}

    # ==========================================================================
    # WebElement-compatible methods
    # ==========================================================================

    def click(self, **kwargs) -> None:
        """
        Click the element.

        Equivalent to WebElement.click() in Selenium.
        Supports additional Playwright options via kwargs.
        """
        self._locator.click(**kwargs)

    def send_keys(self, *value: str) -> None:
        """
        Type text into the element.

        Equivalent to WebElement.send_keys() in Selenium.
        Note: Unlike Selenium, this appends to existing text by default.
        Use clear() first if you want to replace content.
        """
        text = ''.join(str(v) for v in value)
        self._locator.type(text)

    def clear(self) -> None:
        """
        Clear the content of an input element.

        Equivalent to WebElement.clear() in Selenium.
        """
        self._locator.clear()

    def submit(self) -> None:
        """
        Submit a form.

        Equivalent to WebElement.submit() in Selenium.
        Finds and submits the parent form.
        """
        self._locator.evaluate("el => el.form && el.form.submit()")

    def get_attribute(self, name: str) -> Optional[str]:
        """
        Get an attribute value.

        Equivalent to WebElement.get_attribute() in Selenium.

        Note: For 'value' attribute on input/textarea elements, Selenium returns
        the JavaScript property (current typed value), not the HTML attribute.
        We mimic this behavior for compatibility.
        """
        if name == 'value':
            # For 'value', return the JavaScript property like Selenium does
            # This captures the current typed value, not the initial HTML attribute
            return self._locator.input_value()
        return self._locator.get_attribute(name)

    def get_property(self, name: str) -> Any:
        """
        Get a JavaScript property value.

        Equivalent to WebElement.get_property() in Selenium.
        """
        return self._locator.evaluate(f"el => el.{name}")

    def is_displayed(self) -> bool:
        """
        Check if element is visible.

        Equivalent to WebElement.is_displayed() in Selenium.
        """
        return self._locator.is_visible()

    def is_enabled(self) -> bool:
        """
        Check if element is enabled.

        Equivalent to WebElement.is_enabled() in Selenium.
        """
        return self._locator.is_enabled()

    def is_selected(self) -> bool:
        """
        Check if element is selected (for checkboxes, radio buttons).

        Equivalent to WebElement.is_selected() in Selenium.
        """
        return self._locator.is_checked()

    def find_element(self, by: str, value: str) -> 'PlaywrightElementShim':
        """
        Find a child element.

        Equivalent to WebElement.find_element() in Selenium.
        """
        selector = _convert_selenium_locator(by, value)
        child_locator = self._locator.locator(selector).first
        return PlaywrightElementShim(child_locator, self._page)

    def find_elements(self, by: str, value: str) -> List['PlaywrightElementShim']:
        """
        Find child elements.

        Equivalent to WebElement.find_elements() in Selenium.
        """
        selector = _convert_selenium_locator(by, value)
        child_locators = self._locator.locator(selector)
        return [
            PlaywrightElementShim(child_locators.nth(i), self._page)
            for i in range(child_locators.count())
        ]

    def screenshot(self, filename: Optional[str] = None) -> bytes:
        """
        Take a screenshot of the element.

        Equivalent to WebElement.screenshot() in Selenium.
        """
        if filename:
            return self._locator.screenshot(path=filename)
        return self._locator.screenshot()

    def value_of_css_property(self, property_name: str) -> str:
        """
        Get a CSS property value.

        Equivalent to WebElement.value_of_css_property() in Selenium.
        """
        return self._locator.evaluate(
            f"el => window.getComputedStyle(el).getPropertyValue('{property_name}')"
        )

    # ==========================================================================
    # Additional Playwright-specific methods exposed for convenience
    # ==========================================================================

    def fill(self, value: str) -> None:
        """
        Fill the element with text (clears first).

        This is Playwright's recommended way to input text.
        Unlike send_keys(), this clears existing content first.
        """
        self._locator.fill(value)

    def scroll_into_view_if_needed(self) -> None:
        """Scroll element into view if not already visible."""
        self._locator.scroll_into_view_if_needed()

    def hover(self) -> None:
        """Hover over the element."""
        self._locator.hover()

    def focus(self) -> None:
        """Focus the element."""
        self._locator.focus()

    def inner_html(self) -> str:
        """Get the inner HTML of the element."""
        return self._locator.inner_html()

    def outer_html(self) -> str:
        """Get the outer HTML of the element (equivalent to outerHTML attribute)."""
        return self._locator.evaluate("el => el.outerHTML")


class _SwitchToAdapter:
    """
    Adapter providing switch_to interface for PlaywrightDriverShim.

    Provides switch_to.window(), switch_to.frame(), etc.
    """

    def __init__(self, driver_shim: 'PlaywrightDriverShim'):
        self._driver = driver_shim

    def window(self, handle: str) -> None:
        """Switch to a window/tab by handle."""
        self._driver._switch_to_window(handle)

    def frame(self, frame_reference: Union[str, int, 'PlaywrightElementShim']) -> None:
        """Switch to a frame."""
        if isinstance(frame_reference, int):
            # Switch by index
            frame_locator = self._driver._page.frame_locator(f"iframe >> nth={frame_reference}")
        elif isinstance(frame_reference, str):
            # Switch by name or ID
            frame_locator = self._driver._page.frame_locator(f"iframe[name='{frame_reference}'], iframe[id='{frame_reference}']")
        elif isinstance(frame_reference, PlaywrightElementShim):
            # Switch by element
            frame_locator = frame_reference.locator.content_frame()
        else:
            raise ValueError(f"Invalid frame reference type: {type(frame_reference)}")
        # Store frame locator for context
        self._driver._current_frame = frame_locator

    def default_content(self) -> None:
        """Switch back to main content."""
        self._driver._current_frame = None

    def parent_frame(self) -> None:
        """Switch to parent frame."""
        # Playwright doesn't have direct parent frame navigation
        # Reset to main content as fallback
        self._driver._current_frame = None

    def active_element(self) -> PlaywrightElementShim:
        """Get the currently focused element."""
        locator = self._driver._page.locator("*:focus")
        return PlaywrightElementShim(locator, self._driver._page)

    def alert(self) -> None:
        """Get alert dialog - not directly supported in Playwright."""
        raise NotImplementedError(
            "Playwright handles dialogs differently. Use page.on('dialog', handler)"
        )


class PlaywrightDriverShim:
    """
    Selenium WebDriver-compatible wrapper for Playwright Browser/Page.

    This shim provides a WebDriver-like interface for Playwright,
    enabling existing code written for Selenium to work with Playwright.

    Key differences from WebDriver:
    - Window handles are managed internally (Playwright uses Page objects)
    - Some async operations are handled synchronously
    - CDP access requires explicit setup

    Usage:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            driver = PlaywrightDriverShim(browser, page)
            driver.get("https://example.com")
            print(driver.title)
    """

    def __init__(self, browser: 'Browser', page: 'Page', context: Optional['BrowserContext'] = None):
        """
        Initialize the driver shim.

        Args:
            browser: Playwright Browser instance
            page: Playwright Page instance (current active page)
            context: Optional BrowserContext (uses page's context if not provided)
        """
        self._browser = browser
        self._page = page
        self._context = context or page.context
        self._current_frame = None

        # Manage window handles using a stable mapping
        # Playwright pages don't have stable IDs, so we assign our own
        self._page_to_handle: Dict['Page', str] = {}
        self._handle_to_page: Dict[str, 'Page'] = {}
        self._handle_counter = 0

        # Register initial page
        self._register_page(page)

        # switch_to adapter
        self._switch_to = _SwitchToAdapter(self)

    def _register_page(self, page: 'Page') -> str:
        """Register a page and return its handle."""
        if page not in self._page_to_handle:
            handle = f"CDwindow-{self._handle_counter:08X}"
            self._handle_counter += 1
            self._page_to_handle[page] = handle
            self._handle_to_page[handle] = page
        return self._page_to_handle[page]

    def _unregister_page(self, page: 'Page') -> None:
        """Unregister a page when it's closed."""
        if page in self._page_to_handle:
            handle = self._page_to_handle.pop(page)
            self._handle_to_page.pop(handle, None)

    def _switch_to_window(self, handle: str) -> None:
        """Switch to window by handle."""
        if handle not in self._handle_to_page:
            raise ValueError(f"No window with handle: {handle}")
        self._page = self._handle_to_page[handle]

    # ==========================================================================
    # WebDriver-compatible properties
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
        """Get the page source HTML."""
        return self._page.content()

    @property
    def window_handles(self) -> List[str]:
        """Get list of all window handles."""
        # Sync with actual browser pages
        current_pages = set(self._context.pages)

        # Remove handles for closed pages
        for page in list(self._page_to_handle.keys()):
            if page not in current_pages:
                self._unregister_page(page)

        # Register any new pages
        for page in current_pages:
            self._register_page(page)

        return list(self._handle_to_page.keys())

    def current_window_handle(self) -> str:
        """Get the current window handle.

        Returns the handle of the programmatically tracked current page.

        Note:
            This only tracks programmatic tab switches (via switch_to.window()).
            It cannot detect manual tab switches by the user. This is a fundamental
            limitation of browser automation APIs - neither Selenium nor Playwright
            can detect which tab the user is viewing.

            Approaches that were tried and don't work:
            - document.visibilityState: Returns 'visible' for ALL tabs in a
              non-minimized browser window
            - document.hasFocus(): Calling page.evaluate() on each page causes
              each page to temporarily gain focus, so all report True
            - Event listeners (focus/blur): Same problem - checking triggers events
            - CDP Target.getTargets: No 'isActive' or 'isForeground' property exists
        """
        return self._page_to_handle.get(self._page, "")

    @property
    def switch_to(self) -> _SwitchToAdapter:
        """Get the switch_to interface."""
        return self._switch_to

    # ==========================================================================
    # WebDriver-compatible methods
    # ==========================================================================

    def get(self, url: str) -> None:
        """Navigate to a URL."""
        self._page.goto(url)

    def close(self) -> None:
        """Close the current window/page."""
        current_handle = self.current_window_handle()
        self._page.close()
        self._unregister_page(self._page)

        # Switch to another page if available
        remaining = self.window_handles
        if remaining:
            self._page = self._handle_to_page[remaining[0]]

    def quit(self) -> None:
        """Close the browser and end the session."""
        self._browser.close()
        self._page_to_handle.clear()
        self._handle_to_page.clear()

    def find_element(self, by: str, value: str) -> PlaywrightElementShim:
        """Find a single element."""
        import logging
        _logger = logging.getLogger(__name__)
        selector = _convert_selenium_locator(by, value)
        _logger.debug(f"[PlaywrightDriverShim.find_element] by={by}, value={value}, selector={selector}")
        locator = self._page.locator(selector).first
        _logger.debug(f"[PlaywrightDriverShim.find_element] Created locator: {locator}")
        return PlaywrightElementShim(locator, self._page)

    def find_elements(self, by: str, value: str) -> List[PlaywrightElementShim]:
        """Find multiple elements."""
        selector = _convert_selenium_locator(by, value)
        locators = self._page.locator(selector)
        count = locators.count()
        return [
            PlaywrightElementShim(locators.nth(i), self._page)
            for i in range(count)
        ]

    def execute_script(self, script: str, *args) -> Any:
        """
        Execute JavaScript in the page context.

        Args are converted to Playwright-compatible format.
        """
        # Convert PlaywrightElementShim args to locators
        converted_args = []
        for arg in args:
            if isinstance(arg, PlaywrightElementShim):
                # Get element handle for passing to JS
                converted_args.append(arg.locator.element_handle())
            else:
                converted_args.append(arg)

        if converted_args:
            return self._page.evaluate(script, converted_args)
        return self._page.evaluate(script)

    def execute_async_script(self, script: str, *args) -> Any:
        """Execute async JavaScript."""
        # Playwright's evaluate handles async functions automatically
        return self.execute_script(script, *args)

    def get_cookies(self) -> List[Dict]:
        """Get all cookies."""
        return self._context.cookies()

    def add_cookie(self, cookie_dict: Dict) -> None:
        """Add a cookie."""
        self._context.add_cookies([cookie_dict])

    def delete_cookie(self, name: str) -> None:
        """Delete a cookie by name."""
        cookies = [c for c in self._context.cookies() if c['name'] != name]
        self._context.clear_cookies()
        if cookies:
            self._context.add_cookies(cookies)

    def delete_all_cookies(self) -> None:
        """Delete all cookies."""
        self._context.clear_cookies()

    def get_window_size(self) -> Dict[str, int]:
        """Get window size."""
        viewport = self._page.viewport_size
        if viewport:
            return {'width': viewport['width'], 'height': viewport['height']}
        return {'width': 0, 'height': 0}

    def set_window_size(self, width: int, height: int) -> None:
        """Set window size."""
        self._page.set_viewport_size({'width': width, 'height': height})

    def maximize_window(self) -> None:
        """Maximize window - not directly supported in Playwright headless."""
        # Set to a large viewport size as approximation
        self._page.set_viewport_size({'width': 1920, 'height': 1080})

    def minimize_window(self) -> None:
        """Minimize window - not supported in Playwright."""
        _logger.warning("minimize_window() is not supported in Playwright")

    def fullscreen_window(self) -> None:
        """Fullscreen window - not supported in Playwright."""
        _logger.warning("fullscreen_window() is not supported in Playwright")

    def set_page_load_timeout(self, time_to_wait: int) -> None:
        """Set page load timeout in seconds."""
        self._page.set_default_navigation_timeout(time_to_wait * 1000)

    def implicitly_wait(self, time_to_wait: int) -> None:
        """Set implicit wait timeout in seconds."""
        self._page.set_default_timeout(time_to_wait * 1000)

    def back(self) -> None:
        """Go back in browser history."""
        self._page.go_back()

    def forward(self) -> None:
        """Go forward in browser history."""
        self._page.go_forward()

    def refresh(self) -> None:
        """Refresh the current page."""
        self._page.reload()

    def get_screenshot_as_file(self, filename: str) -> bool:
        """Save screenshot to file."""
        self._page.screenshot(path=filename)
        return True

    def get_screenshot_as_png(self) -> bytes:
        """Get screenshot as PNG bytes."""
        return self._page.screenshot()

    def get_screenshot_as_base64(self) -> str:
        """Get screenshot as base64 string."""
        import base64
        png_bytes = self._page.screenshot()
        return base64.b64encode(png_bytes).decode('utf-8')

    # ==========================================================================
    # Playwright-specific methods
    # ==========================================================================

    @property
    def page(self) -> 'Page':
        """Get the underlying Playwright Page."""
        return self._page

    @property
    def browser(self) -> 'Browser':
        """Get the underlying Playwright Browser."""
        return self._browser

    @property
    def context(self) -> 'BrowserContext':
        """Get the underlying Playwright BrowserContext."""
        return self._context


def _convert_selenium_locator(by: str, value: str) -> str:
    """
    Convert Selenium locator to Playwright selector.

    Args:
        by: Selenium By constant (e.g., 'id', 'xpath', 'css selector')
        value: Locator value

    Returns:
        Playwright-compatible selector string
    """
    # Handle selenium.webdriver.common.by.By constants
    by_lower = by.lower().replace(' ', '_')

    if by_lower == 'id':
        # Use attribute selector for robustness with special characters
        # e.g., id="my.element" works, but #my.element fails
        return f"[id=\"{value}\"]"
    elif by_lower == 'class_name' or by_lower == 'class':
        # Use attribute selector for robustness with special characters
        return f"[class~=\"{value}\"]"
    elif by_lower == 'name':
        return f"[name=\"{value}\"]"
    elif by_lower == 'tag_name' or by_lower == 'tag':
        return value
    elif by_lower == 'xpath':
        return f"xpath={value}"
    elif by_lower == 'css_selector' or by_lower == 'css':
        return value
    elif by_lower == 'link_text':
        return f"a:has-text(\"{value}\")"
    elif by_lower == 'partial_link_text':
        return f"a:text-matches(\"{value}\", \"i\")"
    else:
        # Default to CSS selector
        return value
