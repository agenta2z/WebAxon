"""
Browser configuration dataclasses for WebDriver initialization.

This module provides type-safe configuration classes for different browsers,
supporting version specification, binary locations, and browser-specific options.

Usage:
    from webaxon.automation.backends.config import BrowserConfig, UndetectedChromeConfig

    # Simple config
    config = BrowserConfig(headless=False, driver_version="126.0.0")

    # UndetectedChrome with version
    config = BrowserConfig(
        headless=False,
        undetected_chrome=UndetectedChromeConfig(version_main=126)
    )

    # Pass to WebDriver
    driver = WebDriver(config=config)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChromeBrowserConfig:
    """
    Chrome-specific configuration options.

    Works with WebAutomationDrivers.Chrome (uses webdriver-manager).
    For UndetectedChrome, use UndetectedChromeConfig instead.

    Attributes:
        binary_location: Path to Chrome binary (e.g., Chrome Beta)
        arguments: Command-line arguments (e.g., ["--disable-gpu"])
        experimental_options: Experimental options dict
        extensions: List of paths to .crx extension files
        capabilities: Additional capabilities dict

    Example:
        >>> opts = ChromeBrowserConfig(
        ...     binary_location="/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
        ...     experimental_options={"excludeSwitches": ["enable-automation"]},
        ... )
    """

    binary_location: Optional[str] = None
    arguments: List[str] = field(default_factory=list)
    experimental_options: Dict[str, Any] = field(default_factory=dict)
    extensions: List[str] = field(default_factory=list)
    capabilities: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UndetectedChromeConfig:
    """
    UndetectedChrome-specific configuration options.

    IMPORTANT: UndetectedChrome has a DIFFERENT API than regular Chrome:
    - Does NOT use webdriver-manager
    - Uses version_main (int) instead of full version string
    - Uses browser_executable_path instead of binary_location in options
    - user_data_dir is a constructor param, not an option

    Attributes:
        version_main: Major Chrome version as integer (e.g., 126, not "126.0.0")
        browser_executable_path: Path to Chrome binary
        driver_executable_path: Path to specific chromedriver binary
        profile_directory: Chrome profile folder name within user_data_dir
            (e.g., "Default", "Profile 1"). Defaults to "Default" if not specified.
        arguments: Command-line arguments

    Example:
        >>> opts = UndetectedChromeConfig(
        ...     version_main=126,
        ...     browser_executable_path="/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
        ... )
    """

    version_main: Optional[int] = None
    browser_executable_path: Optional[str] = None
    driver_executable_path: Optional[str] = None
    profile_directory: Optional[str] = None
    arguments: List[str] = field(default_factory=list)


@dataclass
class FirefoxBrowserConfig:
    """
    Firefox-specific configuration options.

    Attributes:
        binary_location: Path to Firefox binary
        arguments: Command-line arguments
        preferences: Firefox preferences dict (about:config settings)
        profile_path: Path to existing Firefox profile directory
        capabilities: Additional capabilities dict

    Example:
        >>> opts = FirefoxBrowserConfig(
        ...     profile_path="/path/to/firefox/profile",
        ...     preferences={"dom.webdriver.enabled": False},
        ... )
    """

    binary_location: Optional[str] = None
    arguments: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    profile_path: Optional[str] = None
    capabilities: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeBrowserConfig:
    """
    Microsoft Edge-specific configuration options.

    Edge is Chromium-based and uses EdgeOptions (similar API to Chrome).

    Attributes:
        binary_location: Path to Edge binary
        arguments: Command-line arguments
        experimental_options: Experimental options dict (same as Chrome)
        capabilities: Additional capabilities dict

    Example:
        >>> opts = EdgeBrowserConfig(
        ...     binary_location="/Applications/Microsoft Edge Beta.app/Contents/MacOS/Microsoft Edge Beta",
        ... )
    """

    binary_location: Optional[str] = None
    arguments: List[str] = field(default_factory=list)
    experimental_options: Dict[str, Any] = field(default_factory=dict)
    capabilities: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrowserConfig:
    """
    Unified browser configuration for WebDriver initialization.

    This class provides a single configuration object that can hold settings
    for any supported browser. The WebDriver will use the appropriate
    browser-specific options based on the driver_type.

    Attributes:
        headless: Run browser without UI
        user_agent: Custom user agent string
        timeout: Page load timeout in seconds
        user_data_dir: Path to browser profile directory (NOT for UndetectedChrome)
        driver_version: Driver/browser version string (e.g., "126.0.0")
            - For Chrome: Full version string for webdriver-manager (uses driver_version= param)
            - For Firefox: GeckoDriver version (e.g., "0.33.0") (uses version= param)
            - For Edge: EdgeDriver version (uses version= param)
            - For UndetectedChrome: Use undetected_chrome.version_main instead
        extra_args: Additional command-line arguments (legacy compatibility)
        chrome: Chrome-specific options (WebAutomationDrivers.Chrome)
        undetected_chrome: UndetectedChrome-specific options
        firefox: Firefox-specific options
        edge: Edge-specific options

    Example:
        >>> # Simple usage
        >>> config = BrowserConfig(headless=False, driver_version="126.0.0")

        >>> # Chrome Beta with full config
        >>> config = BrowserConfig(
        ...     headless=False,
        ...     chrome=ChromeBrowserConfig(
        ...         binary_location="/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
        ...     )
        ... )

        >>> # UndetectedChrome with version
        >>> config = BrowserConfig(
        ...     undetected_chrome=UndetectedChromeConfig(
        ...         version_main=126,
        ...         browser_executable_path="/path/to/chrome",
        ...     )
        ... )
    """

    # Common options
    headless: bool = True
    user_agent: Optional[str] = None
    timeout: int = 120
    user_data_dir: Optional[str] = (
        None  # Not used for UndetectedChrome (use its own param)
    )

    # Version (for webdriver-manager browsers only, NOT UndetectedChrome)
    driver_version: Optional[str] = None

    # Browser-specific options
    chrome: Optional[ChromeBrowserConfig] = None
    undetected_chrome: Optional[UndetectedChromeConfig] = None
    firefox: Optional[FirefoxBrowserConfig] = None
    edge: Optional[EdgeBrowserConfig] = None

    # Legacy compatibility
    extra_args: List[str] = field(default_factory=list)

    def get_browser_config(self, driver_type: str):
        """
        Get the browser-specific config for the given driver type.

        Args:
            driver_type: Browser type string (e.g., 'chrome', 'undetected_chrome')

        Returns:
            Browser-specific config object or None
        """
        mapping = {
            "chrome": self.chrome,
            "undetected_chrome": self.undetected_chrome,
            "firefox": self.firefox,
            "edge": self.edge,
        }
        return mapping.get(driver_type)
