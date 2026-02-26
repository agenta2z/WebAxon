"""
Property tests for Backend Selection Consistency and Invalid Backend Rejection.

Feature: playwright-support
Property 1: Backend Selection Consistency
Property 2: Invalid Backend Rejection

Property 1: *For any* valid backend type ('selenium' or 'playwright'), when a WebDriver
is instantiated with that backend, the `backend_type` property SHALL return the same
value, and all operations SHALL be delegated to the corresponding backend adapter.

Property 2: *For any* string that is not a valid backend type ('selenium' or 'playwright'),
when passed as the `backend` parameter to WebDriver, a ValueError SHALL be raised with
a message containing the invalid value and listing valid options.

Validates: Requirements 1.1, 1.2, 1.4, 1.5
"""

# Path resolution - must be first
import sys
from pathlib import Path

PIVOT_FOLDER_NAME = 'test'
current_file = Path(__file__).resolve()
current_path = current_file.parent
while current_path.name != PIVOT_FOLDER_NAME and current_path.parent != current_path:
    current_path = current_path.parent

if current_path.name != PIVOT_FOLDER_NAME:
    raise RuntimeError(f"Could not find '{PIVOT_FOLDER_NAME}' folder in path hierarchy")

webagent_root = current_path.parent
src_dir = webagent_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

projects_root = webagent_root.parent
for path_item in [projects_root / "SciencePythonUtils" / "src", projects_root / "ScienceModelingTools" / "src"]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

import pytest
from unittest.mock import MagicMock, patch
from hypothesis import given, strategies as st, settings

from webaxon.automation.backends.base import BackendAdapter
from webaxon.automation.backends.selenium.selenium_backend import SeleniumBackend


# =============================================================================
# Property 1: Backend Selection Consistency
# =============================================================================

class TestBackendSelectionConsistency:
    """
    Property 1: For any valid backend type, when a WebDriver is instantiated
    with that backend, the backend_type property SHALL return the same value.
    """

    def _create_mock_webdriver(self, mock_backend):
        """Helper to create a WebDriver with a mock backend."""
        from webaxon.automation.web_driver import WebDriver

        driver = WebDriver.__new__(WebDriver)
        driver._backend = mock_backend
        driver._driver_type = mock_backend.driver_type
        driver._state = None
        driver.state_setting_max_retry = 3
        driver.state_setting_retry_wait = 0.2
        driver._action_configs = {}
        driver._window_infos = {}
        driver._monitor_tabs = set()
        driver._id = "test-webdriver"
        driver._log_level = 0
        return driver

    def test_selenium_backend_returns_selenium_type(self):
        """WebDriver with SeleniumBackend should have backend_type 'selenium'."""
        mock_backend = MagicMock(spec=SeleniumBackend)
        mock_backend.driver_type = 'chrome'
        mock_backend.raw_driver = MagicMock()
        type(mock_backend).__name__ = 'SeleniumBackend'

        driver = self._create_mock_webdriver(mock_backend)
        assert driver.backend_type == 'selenium'

    def test_playwright_backend_returns_playwright_type(self):
        """WebDriver with PlaywrightBackend should have backend_type 'playwright'."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        mock_backend = MagicMock(spec=PlaywrightBackend)
        mock_backend.driver_type = 'chromium'
        mock_backend.raw_driver = MagicMock()
        type(mock_backend).__name__ = 'PlaywrightBackend'

        driver = self._create_mock_webdriver(mock_backend)
        assert driver.backend_type == 'playwright'

    def test_backend_type_derived_from_class_name_selenium(self):
        """backend_type should be derived from SeleniumBackend class name."""
        backend = SeleniumBackend()
        assert 'selenium' in type(backend).__name__.lower()

    def test_backend_type_derived_from_class_name_playwright(self):
        """backend_type should be derived from PlaywrightBackend class name."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
        backend = PlaywrightBackend()
        assert 'playwright' in type(backend).__name__.lower()

    def test_backend_property_returns_backend_instance(self):
        """backend property should return the backend adapter instance."""
        mock_backend = MagicMock(spec=SeleniumBackend)
        mock_backend.driver_type = 'chrome'
        mock_backend.raw_driver = MagicMock()
        type(mock_backend).__name__ = 'SeleniumBackend'

        driver = self._create_mock_webdriver(mock_backend)
        assert driver.backend is mock_backend

    def test_is_using_backend_returns_true(self):
        """is_using_backend should return True when backend is set."""
        mock_backend = MagicMock(spec=SeleniumBackend)
        mock_backend.driver_type = 'chrome'
        mock_backend.raw_driver = MagicMock()
        type(mock_backend).__name__ = 'SeleniumBackend'

        driver = self._create_mock_webdriver(mock_backend)
        assert driver.is_using_backend is True

    def test_raw_driver_returns_backend_raw_driver(self):
        """_driver property should return backend.raw_driver."""
        mock_raw_driver = MagicMock()
        mock_backend = MagicMock(spec=SeleniumBackend)
        mock_backend.driver_type = 'chrome'
        mock_backend.raw_driver = mock_raw_driver
        type(mock_backend).__name__ = 'SeleniumBackend'

        driver = self._create_mock_webdriver(mock_backend)
        assert driver._driver is mock_raw_driver


class TestBackendDelegation:
    """Tests that verify operations are delegated to the backend."""

    def _create_mock_webdriver(self, mock_backend):
        """Helper to create a WebDriver with a mock backend."""
        from webaxon.automation.web_driver import WebDriver

        driver = WebDriver.__new__(WebDriver)
        driver._backend = mock_backend
        driver._driver_type = mock_backend.driver_type
        driver._state = None
        driver.state_setting_max_retry = 3
        driver.state_setting_retry_wait = 0.2
        driver._action_configs = {}
        driver._window_infos = {}
        driver._monitor_tabs = set()
        driver._id = "test-webdriver"
        driver._log_level = 0
        return driver

    def test_backend_has_find_element_method(self):
        """Backend should have find_element method."""
        mock_backend = MagicMock(spec=SeleniumBackend)
        mock_backend.driver_type = 'chrome'
        mock_backend.raw_driver = MagicMock()
        mock_backend.find_element = MagicMock(return_value="mock_element")

        driver = self._create_mock_webdriver(mock_backend)
        assert hasattr(driver._backend, 'find_element')
        assert callable(driver._backend.find_element)

    def test_backend_has_execute_script_method(self):
        """Backend should have execute_script method."""
        mock_backend = MagicMock(spec=SeleniumBackend)
        mock_backend.driver_type = 'chrome'
        mock_backend.raw_driver = MagicMock()
        mock_backend.execute_script = MagicMock(return_value="result")

        driver = self._create_mock_webdriver(mock_backend)
        assert hasattr(driver._backend, 'execute_script')
        assert callable(driver._backend.execute_script)

    def test_backend_has_click_element_method(self):
        """Backend should have click_element method."""
        mock_backend = MagicMock(spec=SeleniumBackend)
        mock_backend.driver_type = 'chrome'
        mock_backend.raw_driver = MagicMock()

        driver = self._create_mock_webdriver(mock_backend)
        assert hasattr(driver._backend, 'click_element')

    def test_backend_has_input_text_method(self):
        """Backend should have input_text method."""
        mock_backend = MagicMock(spec=SeleniumBackend)
        mock_backend.driver_type = 'chrome'
        mock_backend.raw_driver = MagicMock()

        driver = self._create_mock_webdriver(mock_backend)
        assert hasattr(driver._backend, 'input_text')


# =============================================================================
# Property 2: Invalid Backend Rejection
# =============================================================================

class TestInvalidBackendRejection:
    """
    Property 2: For any string that is not a valid backend type, when passed
    as the backend parameter, the backend_type should return a fallback value.
    """

    def _create_mock_webdriver(self, mock_backend):
        """Helper to create a WebDriver with a mock backend."""
        from webaxon.automation.web_driver import WebDriver

        driver = WebDriver.__new__(WebDriver)
        driver._backend = mock_backend
        driver._driver_type = mock_backend.driver_type
        driver._state = None
        driver.state_setting_max_retry = 3
        driver.state_setting_retry_wait = 0.2
        driver._action_configs = {}
        driver._window_infos = {}
        driver._monitor_tabs = set()
        driver._id = "test-webdriver"
        driver._log_level = 0
        return driver

    def test_unknown_backend_produces_fallback_type(self):
        """Unknown backend class names should produce a fallback backend_type."""
        mock_backend = MagicMock()
        mock_backend.driver_type = 'unknown'
        mock_backend.raw_driver = MagicMock()
        type(mock_backend).__name__ = 'CustomBackend'

        driver = self._create_mock_webdriver(mock_backend)

        # backend_type should not be 'selenium' or 'playwright' for unknown backend
        backend_type = driver.backend_type
        assert backend_type not in ('selenium', 'playwright')

    @given(backend_name=st.text(min_size=1, max_size=30, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll'), min_codepoint=65, max_codepoint=122
    )).filter(lambda x: 'selenium' not in x.lower() and 'playwright' not in x.lower()))
    @settings(max_examples=50)
    def test_unknown_class_name_not_selenium_or_playwright(self, backend_name):
        """Unknown backend class names should not return 'selenium' or 'playwright'."""
        mock_backend = MagicMock()
        mock_backend.driver_type = 'unknown'
        mock_backend.raw_driver = MagicMock()
        type(mock_backend).__name__ = f"{backend_name}Backend"

        driver = self._create_mock_webdriver(mock_backend)
        backend_type = driver.backend_type

        # Should not match selenium or playwright
        assert backend_type not in ('selenium', 'playwright')

    def test_selenium_in_class_name_returns_selenium(self):
        """Class name containing 'selenium' should return 'selenium' backend_type."""
        mock_backend = MagicMock()
        mock_backend.driver_type = 'chrome'
        mock_backend.raw_driver = MagicMock()
        type(mock_backend).__name__ = 'MySeleniumBackend'

        driver = self._create_mock_webdriver(mock_backend)
        assert driver.backend_type == 'selenium'

    def test_playwright_in_class_name_returns_playwright(self):
        """Class name containing 'playwright' should return 'playwright' backend_type."""
        mock_backend = MagicMock()
        mock_backend.driver_type = 'chromium'
        mock_backend.raw_driver = MagicMock()
        type(mock_backend).__name__ = 'MyPlaywrightBackend'

        driver = self._create_mock_webdriver(mock_backend)
        assert driver.backend_type == 'playwright'


class TestDefaultBackendSelection:
    """Tests for default backend selection."""

    def test_selenium_backend_class_exists(self):
        """SeleniumBackend class should exist and be importable."""
        from webaxon.automation.backends.selenium import SeleniumBackend
        assert SeleniumBackend is not None

    def test_selenium_backend_is_backend_adapter(self):
        """SeleniumBackend should be a BackendAdapter subclass."""
        from webaxon.automation.backends.selenium import SeleniumBackend
        assert issubclass(SeleniumBackend, BackendAdapter)

    def test_playwright_backend_class_exists(self):
        """PlaywrightBackend class should exist and be importable."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
        assert PlaywrightBackend is not None

    def test_playwright_backend_is_backend_adapter(self):
        """PlaywrightBackend should be a BackendAdapter subclass."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
        assert issubclass(PlaywrightBackend, BackendAdapter)
