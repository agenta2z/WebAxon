"""
Driver factory for Selenium WebDriver initialization.

This module provides the get_driver() function and WebAutomationDrivers enum
for creating Selenium WebDriver instances. It's extracted from web_driver.py
to prevent circular imports when SeleniumBackend needs to import it.

Usage:
    from webaxon.automation.backends.selenium.driver_factory import get_driver, WebAutomationDrivers

    driver = get_driver(
        driver_type=WebAutomationDrivers.Chrome,
        headless=True
    )

    # With version and config
    from webaxon.automation.backends.config import BrowserConfig, UndetectedChromeConfig
    config = BrowserConfig(
        headless=False,
        undetected_chrome=UndetectedChromeConfig(version_main=126)
    )
    driver = get_driver(
        driver_type=WebAutomationDrivers.UndetectedChrome,
        config=config
    )
"""

import logging
from enum import Enum
from typing import List, Optional, TYPE_CHECKING, Union

import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

if TYPE_CHECKING:
    from webaxon.automation.backends.config import (
        BrowserConfig,
        ChromeBrowserConfig,
        EdgeBrowserConfig,
        FirefoxBrowserConfig,
        UndetectedChromeConfig,
    )

_logger = logging.getLogger(__name__)

# Default user agent string used when user_agent='default'
DEFAULT_USER_AGENT_STRING = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class WebAutomationDrivers(str, Enum):
    """
    Enumeration of supported browser types for WebDriver automation.

    Selenium-supported browsers:
        Firefox: Mozilla Firefox via GeckoDriver
        Chrome: Google Chrome via ChromeDriver
        UndetectedChrome: Chrome with bot detection bypass
        Edge: Microsoft Edge (Chromium-based)
        Safari: Apple Safari (macOS only)

    Playwright-specific browsers (aliases for backend compatibility):
        Chromium: Playwright's Chromium browser
        WebKit: Playwright's WebKit (Safari engine)
    """

    # Selenium-supported browsers
    Firefox = "firefox"
    Chrome = "chrome"
    UndetectedChrome = "undetected_chrome"
    Edge = "edge"
    Safari = "safari"

    # Playwright-specific browsers (aliases)
    Chromium = "chromium"  # Playwright's Chromium
    WebKit = "webkit"  # Playwright's WebKit (Safari engine)


def get_driver(
    driver_type: WebAutomationDrivers = WebAutomationDrivers.Firefox,
    headless: bool = True,
    user_agent: Optional[str] = None,
    timeout: int = 120,
    options: Optional[List[str]] = None,
    user_data_dir: Optional[str] = None,
    config: Optional["BrowserConfig"] = None,
    driver_version: Optional[str] = None,
    binary_location: Optional[str] = None,
) -> Union[webdriver.Firefox, webdriver.Chrome, webdriver.Edge, webdriver.Safari]:
    """
    Initialize and return a Selenium webdriver instance.

    Creates a configured WebDriver instance for the specified browser type.
    Supports various configuration options including headless mode, custom
    user agent, browser version, and browser-specific options.

    Args:
        driver_type: Specifies the browser type. Default is Firefox.
            Supported values:
            - WebAutomationDrivers.Firefox
            - WebAutomationDrivers.Chrome
            - WebAutomationDrivers.UndetectedChrome
            - WebAutomationDrivers.Edge
            - WebAutomationDrivers.Safari
        headless: If True, run the browser without UI. Default is True.
            Headless mode consumes fewer resources.
        user_agent: Custom user-agent string, or 'default' to use
            DEFAULT_USER_AGENT_STRING. Default is None (browser default).
        timeout: Page load timeout in seconds. Default is 120.
        options: Additional browser-specific command-line options.
            Example: ["--disable-extensions", "--disable-gpu"]
        user_data_dir: Path to browser profile directory. Useful for
            preserving cookies and settings across sessions.
        config: BrowserConfig object with comprehensive browser settings.
            When provided, takes precedence over individual parameters.
        driver_version: Browser/driver version string.
            - Chrome: Full version for webdriver-manager (e.g., "126.0.6478.63")
            - Firefox: GeckoDriver version (e.g., "0.33.0")
            - Edge: EdgeDriver version
            - UndetectedChrome: Use config.undetected_chrome.version_main instead
        binary_location: Path to browser binary executable (e.g., Chrome Beta).

    Returns:
        A configured Selenium WebDriver instance.

    Raises:
        ValueError: If an unsupported driver type is specified.

    Example:
        >>> # Get a headless Firefox driver
        >>> driver = get_driver()

        >>> # Get a Chrome driver with custom options
        >>> driver = get_driver(
        ...     driver_type=WebAutomationDrivers.Chrome,
        ...     options=["--disable-extensions"]
        ... )

        >>> # Get UndetectedChrome with version and persistent profile
        >>> from webaxon.automation.backends.config import BrowserConfig, UndetectedChromeConfig
        >>> config = BrowserConfig(
        ...     undetected_chrome=UndetectedChromeConfig(version_main=126)
        ... )
        >>> driver = get_driver(
        ...     driver_type=WebAutomationDrivers.UndetectedChrome,
        ...     config=config,
        ...     user_data_dir="/path/to/profile"
        ... )
    """
    # Merge config with individual params (config takes precedence)
    effective_headless = config.headless if config else headless
    effective_user_agent = (
        config.user_agent if config and config.user_agent else user_agent
    )
    effective_timeout = config.timeout if config else timeout
    effective_user_data_dir = (
        config.user_data_dir if config and config.user_data_dir else user_data_dir
    )
    effective_driver_version = (
        config.driver_version if config and config.driver_version else driver_version
    )
    effective_extra_args = (config.extra_args if config else []) + (options or [])

    # Get browser-specific config
    browser_config = config.get_browser_config(driver_type.value) if config else None

    # Type-specific config variables
    chrome_config: Optional["ChromeBrowserConfig"] = None
    uc_config: Optional["UndetectedChromeConfig"] = None
    firefox_config: Optional["FirefoxBrowserConfig"] = None
    edge_config: Optional["EdgeBrowserConfig"] = None

    # =========================================================================
    # Firefox
    # =========================================================================
    if driver_type == WebAutomationDrivers.Firefox:
        # Version support - NOTE: GeckoDriverManager uses 'version=' param
        if effective_driver_version:
            webdriver_service = FirefoxService(
                GeckoDriverManager(version=effective_driver_version).install()
            )
        else:
            webdriver_service = FirefoxService(GeckoDriverManager().install())

        _options = FirefoxOptions()
        driver_class = webdriver.Firefox

        # Get Firefox-specific config
        if browser_config:
            firefox_config = browser_config

        # Firefox profile in Selenium 4.x (using options.profile)
        if effective_user_data_dir:
            _options.profile = effective_user_data_dir

        # Apply Firefox-specific config
        if firefox_config:
            # Binary location
            if firefox_config.binary_location:
                _options.binary_location = firefox_config.binary_location
            elif binary_location:
                _options.binary_location = binary_location

            # Firefox preferences (about:config settings)
            for pref, value in firefox_config.preferences.items():
                _options.set_preference(pref, value)

            # Profile path (overrides user_data_dir if specified)
            if firefox_config.profile_path:
                _options.profile = firefox_config.profile_path

            # Additional arguments from config
            for arg in firefox_config.arguments:
                _options.add_argument(arg)
        elif binary_location:
            _options.binary_location = binary_location

    # =========================================================================
    # Chrome (regular, using webdriver-manager)
    # =========================================================================
    elif driver_type == WebAutomationDrivers.Chrome:
        # Version support - NOTE: ChromeDriverManager uses 'driver_version=' param
        if effective_driver_version:
            webdriver_service = ChromeService(
                ChromeDriverManager(driver_version=effective_driver_version).install()
            )
        else:
            webdriver_service = ChromeService(ChromeDriverManager().install())

        _options = ChromeOptions()
        driver_class = webdriver.Chrome

        # Get Chrome-specific config
        if browser_config:
            chrome_config = browser_config

        # Apply user_data_dir for Chrome
        if effective_user_data_dir:
            _options.add_argument(f"--user-data-dir={effective_user_data_dir}")

        # Apply Chrome-specific config
        if chrome_config:
            # Binary location
            if chrome_config.binary_location:
                _options.binary_location = chrome_config.binary_location
            elif binary_location:
                _options.binary_location = binary_location

            # Experimental options
            for key, value in chrome_config.experimental_options.items():
                _options.add_experimental_option(key, value)

            # Extensions
            for ext_path in chrome_config.extensions:
                _options.add_extension(ext_path)

            # Additional arguments from config
            for arg in chrome_config.arguments:
                _options.add_argument(arg)
        elif binary_location:
            _options.binary_location = binary_location

    # =========================================================================
    # UndetectedChrome (SPECIAL HANDLING - different API)
    # =========================================================================
    elif driver_type == WebAutomationDrivers.UndetectedChrome:
        webdriver_service = None  # UC doesn't use services
        _options = uc.ChromeOptions()
        _options.add_argument("--profile-directory=Default")
        driver_class = uc.Chrome

        # Get UndetectedChrome-specific config
        if browser_config:
            uc_config = browser_config

        # Apply arguments from UC config
        if uc_config and uc_config.arguments:
            for arg in uc_config.arguments:
                _options.add_argument(arg)

    # =========================================================================
    # Edge (uses EdgeOptions - best practice)
    # =========================================================================
    elif driver_type == WebAutomationDrivers.Edge:
        # Version support - NOTE: EdgeChromiumDriverManager uses 'version=' param
        if effective_driver_version:
            webdriver_service = EdgeService(
                EdgeChromiumDriverManager(version=effective_driver_version).install()
            )
        else:
            webdriver_service = EdgeService(EdgeChromiumDriverManager().install())

        _options = EdgeOptions()  # Best practice: use EdgeOptions (not ChromeOptions)
        driver_class = webdriver.Edge

        # Get Edge-specific config
        if browser_config:
            edge_config = browser_config

        # Apply user_data_dir for Edge
        if effective_user_data_dir:
            _options.add_argument(f"--user-data-dir={effective_user_data_dir}")

        # Apply Edge-specific config
        if edge_config:
            # Binary location
            if edge_config.binary_location:
                _options.binary_location = edge_config.binary_location
            elif binary_location:
                _options.binary_location = binary_location

            # Experimental options (Edge supports same API as Chrome)
            for key, value in edge_config.experimental_options.items():
                _options.add_experimental_option(key, value)

            # Additional arguments from config
            for arg in edge_config.arguments:
                _options.add_argument(arg)
        elif binary_location:
            _options.binary_location = binary_location

    # =========================================================================
    # Safari (no custom options support)
    # =========================================================================
    elif driver_type == WebAutomationDrivers.Safari:
        webdriver_service = None
        _options = None
        driver_class = webdriver.Safari

        # Warn about unsupported options
        if config or binary_location or effective_driver_version:
            _logger.warning(
                "Safari does not support custom options, binary location, or version specification. "
                "These settings will be ignored."
            )
    else:
        raise ValueError(f"Unsupported driver type: {driver_type}")

    # =========================================================================
    # Apply common options (except Safari and UndetectedChrome for some)
    # =========================================================================
    if _options is not None:
        # Anti-automation detection for Chrome-based browsers
        # NOTE: uc.ChromeOptions is excluded - UndetectedChrome has built-in anti-detection
        if isinstance(_options, (ChromeOptions, EdgeOptions)):
            _options.add_experimental_option("excludeSwitches", ["enable-automation"])
            _options.add_experimental_option("useAutomationExtension", False)
            _options.add_argument("--disable-blink-features=AutomationControlled")

        # Headless mode
        # NOTE: UndetectedChrome uses constructor param, not --headless argument
        if effective_headless and driver_type != WebAutomationDrivers.UndetectedChrome:
            _options.add_argument("--headless")

        # User agent
        if effective_user_agent:
            agent_string = (
                DEFAULT_USER_AGENT_STRING
                if effective_user_agent == "default"
                else effective_user_agent
            )
            _options.add_argument(f"user-agent={agent_string}")

        # Extra arguments (legacy compatibility)
        for arg in effective_extra_args:
            _options.add_argument(arg)

    # =========================================================================
    # Create driver instance
    # =========================================================================
    _logger.debug(
        f"Creating driver: driver_class={driver_class}, service={webdriver_service}"
    )

    if webdriver_service is not None:
        driver = driver_class(service=webdriver_service, options=_options)

    elif driver_class is uc.Chrome:
        # UndetectedChrome has special handling for user_data_dir and version_main
        _logger.debug(f"Creating UndetectedChrome with user_data_dir={user_data_dir}")
        # Auto-detect installed Chrome major version to avoid driver/browser mismatch
        from webaxon.browser_utils.chrome.chrome_version import get_chrome_major_version
        chrome_major = get_chrome_major_version()
        uc_kwargs = {"options": _options}
        if effective_user_data_dir:
            uc_kwargs["user_data_dir"] = effective_user_data_dir
        if effective_headless:
            uc_kwargs["headless"] = True
        # Priority: uc_config.version_main > auto-detected chrome_major
        if uc_config and uc_config.version_main:
            uc_kwargs["version_main"] = uc_config.version_main
        elif chrome_major:
            uc_kwargs["version_main"] = chrome_major
        # Apply UC-specific paths from config
        if uc_config:
            if uc_config.browser_executable_path:
                uc_kwargs["browser_executable_path"] = uc_config.browser_executable_path
            if uc_config.driver_executable_path:
                uc_kwargs["driver_executable_path"] = uc_config.driver_executable_path
        driver = driver_class(**uc_kwargs)
    else:
        _logger.debug(f"Creating driver with options only: {driver_class}")
        driver = driver_class(options=_options)

    _logger.debug(f"Driver created successfully: {driver}")

    # =========================================================================
    # Post-creation anti-automation scripts
    # =========================================================================
    if driver_class is webdriver.Chrome or driver_class is uc.Chrome:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        driver.execute_script("window.navigator.webdriver = undefined")
        driver.execute_script("window.navigator.languages = ['en-US', 'en']")
        driver.execute_script("window.navigator.plugins = [1, 2, 3, 4, 5]")
        driver.execute_script("window.navigator.platform = 'Win32'")

    driver.set_page_load_timeout(effective_timeout)
    return driver
