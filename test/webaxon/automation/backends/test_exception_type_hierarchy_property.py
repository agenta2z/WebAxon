"""
Property test for exception type hierarchy.

Feature: playwright-support
Property 6: Exception Type Consistency

*For any* backend (Selenium or Playwright), when an element is not found, the backend
SHALL raise `ElementNotFoundError`; when a timeout occurs, it SHALL raise
`WebDriverTimeoutError`; when an element is stale, it SHALL raise `StaleElementError`.
The exception type SHALL be consistent regardless of which backend is active.

Validates: Requirements 12.1, 12.2, 12.3
"""

import pytest
from hypothesis import given, strategies as st, settings

from webaxon.automation.backends.exceptions import (
    WebDriverError,
    ElementNotFoundError,
    StaleElementError,
    WebDriverTimeoutError,
    ElementNotInteractableError,
    UnsupportedOperationError,
)


# =============================================================================
# Property 6.1: All exception types inherit from WebDriverError
# =============================================================================

class TestExceptionTypeHierarchy:
    """Test that all exception types form a proper hierarchy."""

    def test_element_not_found_inherits_from_webdriver_error(self):
        """ElementNotFoundError should inherit from WebDriverError."""
        assert issubclass(ElementNotFoundError, WebDriverError)
        exc = ElementNotFoundError(strategy='id', target='test-id')
        assert isinstance(exc, WebDriverError)

    def test_stale_element_inherits_from_webdriver_error(self):
        """StaleElementError should inherit from WebDriverError."""
        assert issubclass(StaleElementError, WebDriverError)
        exc = StaleElementError()
        assert isinstance(exc, WebDriverError)

    def test_timeout_error_inherits_from_webdriver_error(self):
        """WebDriverTimeoutError should inherit from WebDriverError."""
        assert issubclass(WebDriverTimeoutError, WebDriverError)
        exc = WebDriverTimeoutError(operation='find_element', timeout=10.0)
        assert isinstance(exc, WebDriverError)

    def test_element_not_interactable_inherits_from_webdriver_error(self):
        """ElementNotInteractableError should inherit from WebDriverError."""
        assert issubclass(ElementNotInteractableError, WebDriverError)
        exc = ElementNotInteractableError()
        assert isinstance(exc, WebDriverError)

    def test_unsupported_operation_inherits_from_webdriver_error(self):
        """UnsupportedOperationError should inherit from WebDriverError."""
        assert issubclass(UnsupportedOperationError, WebDriverError)
        exc = UnsupportedOperationError(operation='cdp_command', backend_type='firefox')
        assert isinstance(exc, WebDriverError)

    def test_webdriver_error_inherits_from_exception(self):
        """WebDriverError should inherit from Exception."""
        assert issubclass(WebDriverError, Exception)


# =============================================================================
# Property 6.2: Exception types do NOT shadow Python built-ins
# =============================================================================

class TestExceptionNaming:
    """Test that exception names don't shadow Python built-ins."""

    def test_timeout_error_does_not_shadow_builtin(self):
        """WebDriverTimeoutError should NOT shadow Python's built-in TimeoutError."""
        # Python's built-in TimeoutError should still be accessible
        import builtins
        assert hasattr(builtins, 'TimeoutError')
        
        # Our exception should be named WebDriverTimeoutError, not TimeoutError
        assert WebDriverTimeoutError.__name__ == 'WebDriverTimeoutError'
        
        # They should be different types
        assert WebDriverTimeoutError is not builtins.TimeoutError
        assert not issubclass(WebDriverTimeoutError, builtins.TimeoutError)


# =============================================================================
# Property 6.3: Exception attributes are properly stored
# =============================================================================

class TestExceptionAttributes:
    """Test that exception attributes are properly stored and accessible."""

    @given(
        strategy=st.text(min_size=1, max_size=50),
        target=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=100)
    def test_element_not_found_stores_strategy_and_target(self, strategy, target):
        """ElementNotFoundError should store strategy and target attributes."""
        exc = ElementNotFoundError(strategy=strategy, target=target)
        assert exc.strategy == strategy
        assert exc.target == target

    @given(
        operation=st.text(min_size=1, max_size=50),
        timeout=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_timeout_error_stores_operation_and_timeout(self, operation, timeout):
        """WebDriverTimeoutError should store operation and timeout attributes."""
        exc = WebDriverTimeoutError(operation=operation, timeout=timeout)
        assert exc.operation == operation
        assert exc.timeout == timeout

    @given(
        operation=st.text(min_size=1, max_size=50),
        backend_type=st.sampled_from(['selenium', 'playwright', 'firefox', 'chromium'])
    )
    @settings(max_examples=100)
    def test_unsupported_operation_stores_attributes(self, operation, backend_type):
        """UnsupportedOperationError should store operation and backend_type."""
        exc = UnsupportedOperationError(operation=operation, backend_type=backend_type)
        assert exc.operation == operation
        assert exc.backend_type == backend_type


# =============================================================================
# Property 6.4: Exceptions can store original exception for debugging
# =============================================================================

class TestExceptionChaining:
    """Test that exceptions can store original exceptions for debugging."""

    def test_element_not_found_stores_original_exception(self):
        """ElementNotFoundError should store original_exception if provided."""
        original = ValueError("Original error")
        exc = ElementNotFoundError(
            strategy='xpath',
            target='//div[@id="test"]',
            original_exception=original
        )
        assert exc.original_exception is original

    def test_stale_element_stores_original_exception(self):
        """StaleElementError should store original_exception if provided."""
        original = RuntimeError("Element detached")
        exc = StaleElementError(original_exception=original)
        assert exc.original_exception is original

    def test_timeout_error_stores_original_exception(self):
        """WebDriverTimeoutError should store original_exception if provided."""
        original = TimeoutError("Playwright timeout")
        exc = WebDriverTimeoutError(
            operation='wait_for_element',
            timeout=30.0,
            original_exception=original
        )
        assert exc.original_exception is original


# =============================================================================
# Property 6.5: All exceptions can be caught by base class
# =============================================================================

class TestExceptionCatching:
    """Test that all exceptions can be caught by WebDriverError."""

    def test_catch_element_not_found_as_webdriver_error(self):
        """ElementNotFoundError should be catchable as WebDriverError."""
        with pytest.raises(WebDriverError):
            raise ElementNotFoundError(strategy='id', target='missing')

    def test_catch_stale_element_as_webdriver_error(self):
        """StaleElementError should be catchable as WebDriverError."""
        with pytest.raises(WebDriverError):
            raise StaleElementError()

    def test_catch_timeout_as_webdriver_error(self):
        """WebDriverTimeoutError should be catchable as WebDriverError."""
        with pytest.raises(WebDriverError):
            raise WebDriverTimeoutError(operation='load', timeout=10.0)

    def test_catch_not_interactable_as_webdriver_error(self):
        """ElementNotInteractableError should be catchable as WebDriverError."""
        with pytest.raises(WebDriverError):
            raise ElementNotInteractableError()

    def test_catch_unsupported_as_webdriver_error(self):
        """UnsupportedOperationError should be catchable as WebDriverError."""
        with pytest.raises(WebDriverError):
            raise UnsupportedOperationError(operation='cdp', backend_type='firefox')


# =============================================================================
# Property 6.6: Exceptions are distinct types (not aliases)
# =============================================================================

class TestExceptionDistinctness:
    """Test that each exception type is distinct."""

    def test_all_exception_types_are_distinct(self):
        """All exception types should be distinct classes."""
        exception_types = [
            WebDriverError,
            ElementNotFoundError,
            StaleElementError,
            WebDriverTimeoutError,
            ElementNotInteractableError,
            UnsupportedOperationError,
        ]
        
        # Check that all types are unique
        assert len(exception_types) == len(set(exception_types))
        
        # Check that no type is an alias for another (except inheritance)
        for i, type_a in enumerate(exception_types):
            for type_b in exception_types[i+1:]:
                # They should not be the same class
                assert type_a is not type_b
                # If one inherits from the other, it should only be from WebDriverError
                if issubclass(type_a, type_b):
                    assert type_b is WebDriverError
                if issubclass(type_b, type_a):
                    assert type_a is WebDriverError

    def test_specific_exceptions_not_interchangeable(self):
        """Specific exception types should not be interchangeable."""
        # ElementNotFoundError should not be catchable as StaleElementError
        with pytest.raises(ElementNotFoundError):
            try:
                raise ElementNotFoundError(strategy='id', target='test')
            except StaleElementError:
                pytest.fail("ElementNotFoundError should not be caught as StaleElementError")
                
        # WebDriverTimeoutError should not be catchable as ElementNotFoundError
        with pytest.raises(WebDriverTimeoutError):
            try:
                raise WebDriverTimeoutError(operation='load', timeout=10.0)
            except ElementNotFoundError:
                pytest.fail("WebDriverTimeoutError should not be caught as ElementNotFoundError")
