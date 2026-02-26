"""
Property tests for Shim Interface Compatibility.

Property 13: Driver Shim Interface Compatibility
Validates: Requirements 13.2, 13.4

These tests verify that:
1. PlaywrightDriverShim provides the same interface as Selenium WebDriver for common operations
2. PlaywrightElementShim provides the same interface as Selenium WebElement for common operations
3. Method signatures are compatible
4. Properties match between shims and Selenium counterparts
"""

import inspect
from typing import get_type_hints

import pytest

from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE


# Skip all tests if Playwright is not available
pytestmark = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE,
    reason="Playwright not installed"
)


class TestPlaywrightDriverShimInterface:
    """Tests that verify PlaywrightDriverShim provides WebDriver-like interface."""

    # Core WebDriver methods that should be present
    REQUIRED_METHODS = [
        'get',
        'close',
        'quit',
        'find_element',
        'find_elements',
        'execute_script',
        'execute_async_script',
        'get_cookies',
        'add_cookie',
        'delete_cookie',
        'delete_all_cookies',
        'get_window_size',
        'set_window_size',
        'maximize_window',
        'minimize_window',
        'fullscreen_window',
        'set_page_load_timeout',
        'implicitly_wait',
        'back',
        'forward',
        'refresh',
        'get_screenshot_as_file',
        'get_screenshot_as_png',
        'get_screenshot_as_base64',
    ]

    # Core WebDriver properties that should be present
    REQUIRED_PROPERTIES = [
        'current_url',
        'title',
        'page_source',
        'window_handles',
        'current_window_handle',
        'switch_to',
    ]

    def test_has_all_required_methods(self):
        """PlaywrightDriverShim must have all WebDriver-compatible methods."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        for method_name in self.REQUIRED_METHODS:
            assert hasattr(PlaywrightDriverShim, method_name), \
                f"PlaywrightDriverShim missing method: {method_name}"

            method = getattr(PlaywrightDriverShim, method_name)
            assert callable(method), \
                f"PlaywrightDriverShim.{method_name} is not callable"

    def test_has_all_required_properties(self):
        """PlaywrightDriverShim must have all WebDriver-compatible properties."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        for prop_name in self.REQUIRED_PROPERTIES:
            assert hasattr(PlaywrightDriverShim, prop_name), \
                f"PlaywrightDriverShim missing property: {prop_name}"

    def test_get_method_signature(self):
        """get() must accept a URL string parameter."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        sig = inspect.signature(PlaywrightDriverShim.get)
        params = list(sig.parameters.keys())

        assert 'self' in params
        assert len(params) >= 2  # self + url

    def test_find_element_method_signature(self):
        """find_element() must accept by and value parameters."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        sig = inspect.signature(PlaywrightDriverShim.find_element)
        params = list(sig.parameters.keys())

        assert 'self' in params
        assert 'by' in params
        assert 'value' in params

    def test_find_elements_method_signature(self):
        """find_elements() must accept by and value parameters."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        sig = inspect.signature(PlaywrightDriverShim.find_elements)
        params = list(sig.parameters.keys())

        assert 'self' in params
        assert 'by' in params
        assert 'value' in params

    def test_execute_script_method_signature(self):
        """execute_script() must accept script and optional args."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        sig = inspect.signature(PlaywrightDriverShim.execute_script)
        params = list(sig.parameters.keys())

        assert 'self' in params
        assert 'script' in params

    def test_switch_to_has_window_method(self):
        """switch_to must have window() method."""
        from webaxon.automation.backends.playwright.shims import _SwitchToAdapter

        assert hasattr(_SwitchToAdapter, 'window')
        assert callable(getattr(_SwitchToAdapter, 'window'))

    def test_switch_to_has_frame_method(self):
        """switch_to must have frame() method."""
        from webaxon.automation.backends.playwright.shims import _SwitchToAdapter

        assert hasattr(_SwitchToAdapter, 'frame')
        assert callable(getattr(_SwitchToAdapter, 'frame'))

    def test_switch_to_has_default_content_method(self):
        """switch_to must have default_content() method."""
        from webaxon.automation.backends.playwright.shims import _SwitchToAdapter

        assert hasattr(_SwitchToAdapter, 'default_content')
        assert callable(getattr(_SwitchToAdapter, 'default_content'))


class TestPlaywrightElementShimInterface:
    """Tests that verify PlaywrightElementShim provides WebElement-like interface."""

    # Core WebElement methods that should be present
    REQUIRED_METHODS = [
        'click',
        'send_keys',
        'clear',
        'submit',
        'get_attribute',
        'get_property',
        'is_displayed',
        'is_enabled',
        'is_selected',
        'find_element',
        'find_elements',
        'screenshot',
        'value_of_css_property',
    ]

    # Core WebElement properties that should be present
    REQUIRED_PROPERTIES = [
        'text',
        'tag_name',
        'size',
        'location',
        'rect',
    ]

    def test_has_all_required_methods(self):
        """PlaywrightElementShim must have all WebElement-compatible methods."""
        from webaxon.automation.backends.playwright.shims import PlaywrightElementShim

        for method_name in self.REQUIRED_METHODS:
            assert hasattr(PlaywrightElementShim, method_name), \
                f"PlaywrightElementShim missing method: {method_name}"

            method = getattr(PlaywrightElementShim, method_name)
            assert callable(method), \
                f"PlaywrightElementShim.{method_name} is not callable"

    def test_has_all_required_properties(self):
        """PlaywrightElementShim must have all WebElement-compatible properties."""
        from webaxon.automation.backends.playwright.shims import PlaywrightElementShim

        for prop_name in self.REQUIRED_PROPERTIES:
            assert hasattr(PlaywrightElementShim, prop_name), \
                f"PlaywrightElementShim missing property: {prop_name}"

            prop = getattr(PlaywrightElementShim, prop_name)
            assert isinstance(prop, property), \
                f"PlaywrightElementShim.{prop_name} should be a property"

    def test_get_attribute_method_signature(self):
        """get_attribute() must accept attribute name parameter."""
        from webaxon.automation.backends.playwright.shims import PlaywrightElementShim

        sig = inspect.signature(PlaywrightElementShim.get_attribute)
        params = list(sig.parameters.keys())

        assert 'self' in params
        assert 'name' in params

    def test_find_element_method_signature(self):
        """find_element() must accept by and value parameters."""
        from webaxon.automation.backends.playwright.shims import PlaywrightElementShim

        sig = inspect.signature(PlaywrightElementShim.find_element)
        params = list(sig.parameters.keys())

        assert 'self' in params
        assert 'by' in params
        assert 'value' in params

    def test_find_elements_method_signature(self):
        """find_elements() must accept by and value parameters."""
        from webaxon.automation.backends.playwright.shims import PlaywrightElementShim

        sig = inspect.signature(PlaywrightElementShim.find_elements)
        params = list(sig.parameters.keys())

        assert 'self' in params
        assert 'by' in params
        assert 'value' in params


class TestLocatorConversion:
    """Tests for Selenium to Playwright locator conversion."""

    def test_convert_selenium_locator_function_exists(self):
        """_convert_selenium_locator function must exist."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        assert callable(_convert_selenium_locator)

    def test_id_locator_conversion(self):
        """ID locator should be converted to attribute selector."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        result = _convert_selenium_locator('id', 'my-element')
        assert '[id="my-element"]' == result

    def test_class_name_locator_conversion(self):
        """Class name locator should be converted to attribute selector."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        result = _convert_selenium_locator('class name', 'my-class')
        assert '[class~="my-class"]' == result

    def test_name_locator_conversion(self):
        """Name locator should be converted to attribute selector."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        result = _convert_selenium_locator('name', 'my-input')
        assert '[name="my-input"]' == result

    def test_xpath_locator_conversion(self):
        """XPath locator should be prefixed with 'xpath='."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        result = _convert_selenium_locator('xpath', '//div[@id="test"]')
        assert result == 'xpath=//div[@id="test"]'

    def test_css_selector_conversion(self):
        """CSS selector should be passed through unchanged."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        result = _convert_selenium_locator('css selector', 'div.my-class')
        assert result == 'div.my-class'

    def test_tag_name_locator_conversion(self):
        """Tag name locator should be passed through unchanged."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        result = _convert_selenium_locator('tag name', 'div')
        assert result == 'div'

    def test_link_text_locator_conversion(self):
        """Link text locator should use has-text selector."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        result = _convert_selenium_locator('link text', 'Click me')
        assert 'a:has-text("Click me")' == result

    def test_partial_link_text_locator_conversion(self):
        """Partial link text locator should use text-matches selector."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        result = _convert_selenium_locator('partial link text', 'Click')
        assert 'a:text-matches("Click", "i")' == result

    def test_special_characters_in_id(self):
        """ID with special characters should work with attribute selector."""
        from webaxon.automation.backends.playwright.shims import _convert_selenium_locator

        # Test with period in ID (would fail with # selector)
        result = _convert_selenium_locator('id', 'my.element.id')
        assert '[id="my.element.id"]' == result

        # Test with colon in ID
        result = _convert_selenium_locator('id', 'ns:element')
        assert '[id="ns:element"]' == result


class TestAdditionalShimMethods:
    """Tests for additional Playwright-specific methods exposed by shims."""

    def test_element_shim_has_fill_method(self):
        """PlaywrightElementShim should have fill() method."""
        from webaxon.automation.backends.playwright.shims import PlaywrightElementShim

        assert hasattr(PlaywrightElementShim, 'fill')
        assert callable(getattr(PlaywrightElementShim, 'fill'))

    def test_element_shim_has_hover_method(self):
        """PlaywrightElementShim should have hover() method."""
        from webaxon.automation.backends.playwright.shims import PlaywrightElementShim

        assert hasattr(PlaywrightElementShim, 'hover')
        assert callable(getattr(PlaywrightElementShim, 'hover'))

    def test_element_shim_has_focus_method(self):
        """PlaywrightElementShim should have focus() method."""
        from webaxon.automation.backends.playwright.shims import PlaywrightElementShim

        assert hasattr(PlaywrightElementShim, 'focus')
        assert callable(getattr(PlaywrightElementShim, 'focus'))

    def test_element_shim_has_locator_property(self):
        """PlaywrightElementShim should expose underlying locator."""
        from webaxon.automation.backends.playwright.shims import PlaywrightElementShim

        assert hasattr(PlaywrightElementShim, 'locator')
        assert isinstance(getattr(PlaywrightElementShim, 'locator'), property)

    def test_driver_shim_has_page_property(self):
        """PlaywrightDriverShim should expose underlying page."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        assert hasattr(PlaywrightDriverShim, 'page')
        assert isinstance(getattr(PlaywrightDriverShim, 'page'), property)

    def test_driver_shim_has_browser_property(self):
        """PlaywrightDriverShim should expose underlying browser."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        assert hasattr(PlaywrightDriverShim, 'browser')
        assert isinstance(getattr(PlaywrightDriverShim, 'browser'), property)

    def test_driver_shim_has_context_property(self):
        """PlaywrightDriverShim should expose underlying context."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        assert hasattr(PlaywrightDriverShim, 'context')
        assert isinstance(getattr(PlaywrightDriverShim, 'context'), property)


class TestShimHandleManagement:
    """Tests for window handle management in shims."""

    def test_driver_shim_has_handle_methods(self):
        """PlaywrightDriverShim should have internal handle management methods."""
        from webaxon.automation.backends.playwright.shims import PlaywrightDriverShim

        # These are private methods but we verify they exist for completeness
        assert hasattr(PlaywrightDriverShim, '_register_page')
        assert hasattr(PlaywrightDriverShim, '_unregister_page')
        assert hasattr(PlaywrightDriverShim, '_switch_to_window')

    def test_switch_to_adapter_has_active_element(self):
        """_SwitchToAdapter should have active_element() method."""
        from webaxon.automation.backends.playwright.shims import _SwitchToAdapter

        assert hasattr(_SwitchToAdapter, 'active_element')
        assert callable(getattr(_SwitchToAdapter, 'active_element'))

    def test_switch_to_adapter_has_parent_frame(self):
        """_SwitchToAdapter should have parent_frame() method."""
        from webaxon.automation.backends.playwright.shims import _SwitchToAdapter

        assert hasattr(_SwitchToAdapter, 'parent_frame')
        assert callable(getattr(_SwitchToAdapter, 'parent_frame'))


class TestPlaywrightAvailableFlag:
    """Tests for PLAYWRIGHT_AVAILABLE flag."""

    def test_playwright_available_is_boolean(self):
        """PLAYWRIGHT_AVAILABLE should be a boolean."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE

        assert isinstance(PLAYWRIGHT_AVAILABLE, bool)

    def test_playwright_available_is_true_if_playwright_installed(self):
        """PLAYWRIGHT_AVAILABLE should be True if Playwright is installed."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE

        # This test only runs if Playwright is available (see pytestmark)
        assert PLAYWRIGHT_AVAILABLE is True
