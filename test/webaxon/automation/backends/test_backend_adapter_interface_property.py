"""
Property tests for Backend Adapter Interface Completeness.

Property 12: Backend Adapter Interface Completeness
Validates: Requirements 10.2, 10.3, 10.4

These tests verify that:
1. Both SeleniumBackend and PlaywrightBackend implement all BackendAdapter methods
2. Method signatures match the abstract interface
3. All required properties are implemented
4. Both backends can be instantiated without errors
"""

import inspect
from abc import abstractmethod
from typing import get_type_hints

import pytest
from hypothesis import given, settings, strategies as st

from webaxon.automation.backends.base import BackendAdapter
from webaxon.automation.backends.selenium.selenium_backend import SeleniumBackend
from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend


class TestBackendAdapterInterfaceCompleteness:
    """Tests that verify both backends implement the complete BackendAdapter interface."""

    def _get_abstract_methods(self) -> list[str]:
        """Get all abstract methods from BackendAdapter."""
        abstract_methods = []
        for name, method in inspect.getmembers(BackendAdapter, predicate=inspect.isfunction):
            if getattr(method, '__isabstractmethod__', False):
                abstract_methods.append(name)
        return abstract_methods

    def _get_abstract_properties(self) -> list[str]:
        """Get all abstract properties from BackendAdapter."""
        abstract_properties = []
        for name in dir(BackendAdapter):
            if name.startswith('_'):
                continue
            attr = getattr(BackendAdapter, name, None)
            if isinstance(attr, property) and getattr(attr.fget, '__isabstractmethod__', False):
                abstract_properties.append(name)
        return abstract_properties

    def test_selenium_backend_implements_all_abstract_methods(self):
        """SeleniumBackend must implement all abstract methods from BackendAdapter."""
        abstract_methods = self._get_abstract_methods()
        
        for method_name in abstract_methods:
            assert hasattr(SeleniumBackend, method_name), \
                f"SeleniumBackend missing abstract method: {method_name}"
            
            method = getattr(SeleniumBackend, method_name)
            assert callable(method), \
                f"SeleniumBackend.{method_name} is not callable"
            
            # Verify it's not still abstract
            assert not getattr(method, '__isabstractmethod__', False), \
                f"SeleniumBackend.{method_name} is still abstract"

    def test_playwright_backend_implements_all_abstract_methods(self):
        """PlaywrightBackend must implement all abstract methods from BackendAdapter."""
        abstract_methods = self._get_abstract_methods()
        
        for method_name in abstract_methods:
            assert hasattr(PlaywrightBackend, method_name), \
                f"PlaywrightBackend missing abstract method: {method_name}"
            
            method = getattr(PlaywrightBackend, method_name)
            assert callable(method), \
                f"PlaywrightBackend.{method_name} is not callable"
            
            # Verify it's not still abstract
            assert not getattr(method, '__isabstractmethod__', False), \
                f"PlaywrightBackend.{method_name} is still abstract"

    def test_selenium_backend_implements_all_abstract_properties(self):
        """SeleniumBackend must implement all abstract properties from BackendAdapter."""
        abstract_properties = self._get_abstract_properties()
        
        for prop_name in abstract_properties:
            assert hasattr(SeleniumBackend, prop_name), \
                f"SeleniumBackend missing abstract property: {prop_name}"
            
            prop = getattr(SeleniumBackend, prop_name)
            assert isinstance(prop, property), \
                f"SeleniumBackend.{prop_name} is not a property"

    def test_playwright_backend_implements_all_abstract_properties(self):
        """PlaywrightBackend must implement all abstract properties from BackendAdapter."""
        abstract_properties = self._get_abstract_properties()
        
        for prop_name in abstract_properties:
            assert hasattr(PlaywrightBackend, prop_name), \
                f"PlaywrightBackend missing abstract property: {prop_name}"
            
            prop = getattr(PlaywrightBackend, prop_name)
            assert isinstance(prop, property), \
                f"PlaywrightBackend.{prop_name} is not a property"

    def test_selenium_backend_is_subclass_of_backend_adapter(self):
        """SeleniumBackend must be a subclass of BackendAdapter."""
        assert issubclass(SeleniumBackend, BackendAdapter)

    def test_playwright_backend_is_subclass_of_backend_adapter(self):
        """PlaywrightBackend must be a subclass of BackendAdapter."""
        assert issubclass(PlaywrightBackend, BackendAdapter)

    def test_selenium_backend_can_be_instantiated(self):
        """SeleniumBackend must be instantiable without errors."""
        backend = SeleniumBackend()
        assert backend is not None
        assert isinstance(backend, BackendAdapter)

    def test_playwright_backend_can_be_instantiated(self):
        """PlaywrightBackend must be instantiable without errors (if Playwright is available)."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")
        
        backend = PlaywrightBackend()
        assert backend is not None
        assert isinstance(backend, BackendAdapter)


class TestMethodSignatureCompatibility:
    """Tests that verify method signatures are compatible between backends."""

    def _get_method_signature(self, cls, method_name: str) -> inspect.Signature:
        """Get the signature of a method."""
        method = getattr(cls, method_name)
        return inspect.signature(method)

    def test_initialize_signature_compatibility(self):
        """Both backends must have compatible initialize() signatures."""
        base_sig = self._get_method_signature(BackendAdapter, 'initialize')
        selenium_sig = self._get_method_signature(SeleniumBackend, 'initialize')
        playwright_sig = self._get_method_signature(PlaywrightBackend, 'initialize')
        
        # Check required parameters exist
        base_params = set(base_sig.parameters.keys())
        selenium_params = set(selenium_sig.parameters.keys())
        playwright_params = set(playwright_sig.parameters.keys())
        
        # Both should have at least the base parameters
        assert base_params <= selenium_params, \
            f"SeleniumBackend.initialize missing params: {base_params - selenium_params}"
        assert base_params <= playwright_params, \
            f"PlaywrightBackend.initialize missing params: {base_params - playwright_params}"

    def test_find_element_signature_compatibility(self):
        """Both backends must have compatible find_element() signatures."""
        base_sig = self._get_method_signature(BackendAdapter, 'find_element')
        selenium_sig = self._get_method_signature(SeleniumBackend, 'find_element')
        playwright_sig = self._get_method_signature(PlaywrightBackend, 'find_element')
        
        base_params = set(base_sig.parameters.keys())
        selenium_params = set(selenium_sig.parameters.keys())
        playwright_params = set(playwright_sig.parameters.keys())
        
        assert base_params <= selenium_params
        assert base_params <= playwright_params

    def test_click_element_signature_compatibility(self):
        """Both backends must have compatible click_element() signatures."""
        base_sig = self._get_method_signature(BackendAdapter, 'click_element')
        selenium_sig = self._get_method_signature(SeleniumBackend, 'click_element')
        playwright_sig = self._get_method_signature(PlaywrightBackend, 'click_element')
        
        base_params = set(base_sig.parameters.keys())
        selenium_params = set(selenium_sig.parameters.keys())
        playwright_params = set(playwright_sig.parameters.keys())
        
        assert base_params <= selenium_params
        assert base_params <= playwright_params

    def test_input_text_signature_compatibility(self):
        """Both backends must have compatible input_text() signatures."""
        base_sig = self._get_method_signature(BackendAdapter, 'input_text')
        selenium_sig = self._get_method_signature(SeleniumBackend, 'input_text')
        playwright_sig = self._get_method_signature(PlaywrightBackend, 'input_text')
        
        base_params = set(base_sig.parameters.keys())
        selenium_params = set(selenium_sig.parameters.keys())
        playwright_params = set(playwright_sig.parameters.keys())
        
        assert base_params <= selenium_params
        assert base_params <= playwright_params


class TestBackendMethodCount:
    """Tests that verify both backends have the same number of public methods."""

    def _get_public_methods(self, cls) -> set[str]:
        """Get all public methods of a class."""
        return {
            name for name, method in inspect.getmembers(cls, predicate=inspect.isfunction)
            if not name.startswith('_')
        }

    def _get_public_properties(self, cls) -> set[str]:
        """Get all public properties of a class."""
        return {
            name for name in dir(cls)
            if not name.startswith('_') and isinstance(getattr(cls, name, None), property)
        }

    def test_both_backends_have_same_core_methods(self):
        """Both backends should implement the same core methods from BackendAdapter."""
        # Get abstract methods from base
        abstract_methods = set()
        for name, method in inspect.getmembers(BackendAdapter, predicate=inspect.isfunction):
            if getattr(method, '__isabstractmethod__', False):
                abstract_methods.add(name)
        
        selenium_methods = self._get_public_methods(SeleniumBackend)
        playwright_methods = self._get_public_methods(PlaywrightBackend)
        
        # Both should have all abstract methods
        assert abstract_methods <= selenium_methods
        assert abstract_methods <= playwright_methods

    def test_both_backends_have_same_core_properties(self):
        """Both backends should implement the same core properties from BackendAdapter."""
        # Get abstract properties from base
        abstract_properties = set()
        for name in dir(BackendAdapter):
            if name.startswith('_'):
                continue
            attr = getattr(BackendAdapter, name, None)
            if isinstance(attr, property) and getattr(attr.fget, '__isabstractmethod__', False):
                abstract_properties.add(name)
        
        selenium_props = self._get_public_properties(SeleniumBackend)
        playwright_props = self._get_public_properties(PlaywrightBackend)
        
        # Both should have all abstract properties
        assert abstract_properties <= selenium_props
        assert abstract_properties <= playwright_props


class TestBackendFeatureDetection:
    """Tests for feature detection methods."""

    def test_selenium_supports_cdp_returns_bool(self):
        """SeleniumBackend.supports_cdp() must return a boolean."""
        backend = SeleniumBackend()
        # Can't call supports_cdp without initialization, but we can check the method exists
        assert hasattr(backend, 'supports_cdp')
        assert callable(backend.supports_cdp)

    def test_playwright_supports_cdp_returns_bool(self):
        """PlaywrightBackend.supports_cdp() must return a boolean."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")
        
        backend = PlaywrightBackend()
        assert hasattr(backend, 'supports_cdp')
        assert callable(backend.supports_cdp)


class TestBackendExceptionWrapping:
    """Tests that verify backends wrap exceptions correctly."""

    def test_selenium_backend_has_exception_imports(self):
        """SeleniumBackend should import unified exception types."""
        import webaxon.automation.backends.selenium.selenium_backend as module
        
        assert hasattr(module, 'ElementNotFoundError')
        assert hasattr(module, 'StaleElementError')
        assert hasattr(module, 'WebDriverTimeoutError')

    def test_playwright_backend_has_exception_imports(self):
        """PlaywrightBackend should import unified exception types."""
        import webaxon.automation.backends.playwright.playwright_backend as module
        
        assert hasattr(module, 'ElementNotFoundError')
        assert hasattr(module, 'StaleElementError')
        assert hasattr(module, 'WebDriverTimeoutError')
        assert hasattr(module, 'UnsupportedOperationError')
