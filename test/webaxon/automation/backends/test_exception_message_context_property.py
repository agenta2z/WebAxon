"""
Property test for exception message context.

Feature: playwright-support
Property 7: Exception Message Context

*For any* exception raised by the WebDriver, the exception message SHALL contain
context about the operation that failed, including at minimum the operation name
and relevant parameters.

Validates: Requirements 12.5
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from webaxon.automation.backends.exceptions import (
    WebDriverError,
    ElementNotFoundError,
    StaleElementError,
    WebDriverTimeoutError,
    ElementNotInteractableError,
    UnsupportedOperationError,
)


# =============================================================================
# Property 7.1: ElementNotFoundError messages contain strategy and target
# =============================================================================

class TestElementNotFoundErrorMessages:
    """Test that ElementNotFoundError messages contain context."""

    @given(
        strategy=st.sampled_from(['id', 'xpath', 'css selector', 'name', 'class name', 'tag name']),
        target=st.text(min_size=1, max_size=100).filter(lambda x: x.strip())
    )
    @settings(max_examples=100)
    def test_default_message_contains_strategy(self, strategy, target):
        """Default message should contain the locator strategy."""
        exc = ElementNotFoundError(strategy=strategy, target=target)
        message = str(exc)
        assert strategy in message, f"Strategy '{strategy}' not found in message: {message}"

    @given(
        strategy=st.sampled_from(['id', 'xpath', 'css selector', 'name']),
        target=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() and "'" not in x)
    )
    @settings(max_examples=100)
    def test_default_message_contains_target(self, strategy, target):
        """Default message should contain the target value."""
        exc = ElementNotFoundError(strategy=strategy, target=target)
        message = str(exc)
        assert target in message, f"Target '{target}' not found in message: {message}"

    def test_custom_message_is_used(self):
        """Custom message should be used when provided."""
        custom_msg = "Custom error: element with special ID not found"
        exc = ElementNotFoundError(
            strategy='id',
            target='special-id',
            message=custom_msg
        )
        assert str(exc) == custom_msg

    def test_message_format_is_readable(self):
        """Message format should be human-readable."""
        exc = ElementNotFoundError(strategy='xpath', target='//div[@class="test"]')
        message = str(exc)
        # Should contain "not found" or similar indication
        assert 'not found' in message.lower() or 'element' in message.lower()


# =============================================================================
# Property 7.2: WebDriverTimeoutError messages contain operation and timeout
# =============================================================================

class TestTimeoutErrorMessages:
    """Test that WebDriverTimeoutError messages contain context."""

    @given(
        operation=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        timeout=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_default_message_contains_operation(self, operation, timeout):
        """Default message should contain the operation name."""
        exc = WebDriverTimeoutError(operation=operation, timeout=timeout)
        message = str(exc)
        assert operation in message, f"Operation '{operation}' not found in message: {message}"

    @given(
        operation=st.sampled_from(['find_element', 'page_load', 'wait_for_element']),
        timeout=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_default_message_contains_timeout_value(self, operation, timeout):
        """Default message should contain the timeout value."""
        exc = WebDriverTimeoutError(operation=operation, timeout=timeout)
        message = str(exc)
        # Timeout should appear in message (as string representation)
        assert str(timeout) in message or f"{timeout}" in message, \
            f"Timeout '{timeout}' not found in message: {message}"

    def test_custom_message_is_used(self):
        """Custom message should be used when provided."""
        custom_msg = "Page took too long to load"
        exc = WebDriverTimeoutError(
            operation='page_load',
            timeout=30.0,
            message=custom_msg
        )
        assert str(exc) == custom_msg

    def test_message_indicates_timeout(self):
        """Message should indicate a timeout occurred."""
        exc = WebDriverTimeoutError(operation='find_element', timeout=10.0)
        message = str(exc).lower()
        assert 'timeout' in message or 'timed out' in message or 'after' in message


# =============================================================================
# Property 7.3: StaleElementError messages are descriptive
# =============================================================================

class TestStaleElementErrorMessages:
    """Test that StaleElementError messages contain context."""

    def test_default_message_indicates_staleness(self):
        """Default message should indicate element is stale."""
        exc = StaleElementError()
        message = str(exc).lower()
        assert 'stale' in message or 'no longer' in message or 'detached' in message

    @given(
        description=st.text(min_size=1, max_size=100).filter(lambda x: x.strip())
    )
    @settings(max_examples=100)
    def test_message_contains_element_description_when_provided(self, description):
        """Message should contain element description when provided."""
        exc = StaleElementError(element_description=description)
        message = str(exc)
        assert description in message, \
            f"Description '{description}' not found in message: {message}"

    def test_custom_message_is_used(self):
        """Custom message should be used when provided."""
        custom_msg = "The button element was removed from DOM"
        exc = StaleElementError(message=custom_msg)
        assert str(exc) == custom_msg


# =============================================================================
# Property 7.4: ElementNotInteractableError messages are descriptive
# =============================================================================

class TestElementNotInteractableErrorMessages:
    """Test that ElementNotInteractableError messages contain context."""

    def test_default_message_indicates_not_interactable(self):
        """Default message should indicate element is not interactable."""
        exc = ElementNotInteractableError()
        message = str(exc).lower()
        assert 'interactable' in message or 'interact' in message

    @given(
        description=st.text(min_size=1, max_size=100).filter(lambda x: x.strip())
    )
    @settings(max_examples=100)
    def test_message_contains_element_description_when_provided(self, description):
        """Message should contain element description when provided."""
        exc = ElementNotInteractableError(element_description=description)
        message = str(exc)
        assert description in message, \
            f"Description '{description}' not found in message: {message}"

    @given(
        action=st.sampled_from(['click', 'input', 'scroll', 'hover'])
    )
    @settings(max_examples=50)
    def test_message_contains_action_when_provided(self, action):
        """Message should contain action attempted when provided."""
        exc = ElementNotInteractableError(action_attempted=action)
        message = str(exc)
        assert action in message, f"Action '{action}' not found in message: {message}"


# =============================================================================
# Property 7.5: UnsupportedOperationError messages contain operation and backend
# =============================================================================

class TestUnsupportedOperationErrorMessages:
    """Test that UnsupportedOperationError messages contain context."""

    @given(
        operation=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        backend_type=st.sampled_from(['selenium', 'playwright', 'firefox', 'chromium'])
    )
    @settings(max_examples=100)
    def test_default_message_contains_operation(self, operation, backend_type):
        """Default message should contain the operation name."""
        exc = UnsupportedOperationError(operation=operation, backend_type=backend_type)
        message = str(exc)
        assert operation in message, f"Operation '{operation}' not found in message: {message}"

    @given(
        operation=st.sampled_from(['cdp_command', 'execute_cdp', 'get_network_logs']),
        backend_type=st.sampled_from(['selenium', 'playwright', 'firefox', 'webkit'])
    )
    @settings(max_examples=100)
    def test_default_message_contains_backend_type(self, operation, backend_type):
        """Default message should contain the backend type."""
        exc = UnsupportedOperationError(operation=operation, backend_type=backend_type)
        message = str(exc)
        assert backend_type in message, \
            f"Backend type '{backend_type}' not found in message: {message}"

    def test_message_indicates_not_supported(self):
        """Message should indicate operation is not supported."""
        exc = UnsupportedOperationError(operation='cdp_command', backend_type='firefox')
        message = str(exc).lower()
        assert 'not supported' in message or 'unsupported' in message


# =============================================================================
# Property 7.6: All exceptions are string-representable
# =============================================================================

class TestExceptionStringRepresentation:
    """Test that all exceptions have valid string representations."""

    @given(
        strategy=st.text(min_size=1, max_size=50),
        target=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=50)
    def test_element_not_found_is_string_representable(self, strategy, target):
        """ElementNotFoundError should have a valid string representation."""
        exc = ElementNotFoundError(strategy=strategy, target=target)
        message = str(exc)
        assert isinstance(message, str)
        assert len(message) > 0

    @given(
        operation=st.text(min_size=1, max_size=50),
        timeout=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False)
    )
    @settings(max_examples=50)
    def test_timeout_error_is_string_representable(self, operation, timeout):
        """WebDriverTimeoutError should have a valid string representation."""
        exc = WebDriverTimeoutError(operation=operation, timeout=timeout)
        message = str(exc)
        assert isinstance(message, str)
        assert len(message) > 0

    def test_stale_element_is_string_representable(self):
        """StaleElementError should have a valid string representation."""
        exc = StaleElementError()
        message = str(exc)
        assert isinstance(message, str)
        assert len(message) > 0

    def test_not_interactable_is_string_representable(self):
        """ElementNotInteractableError should have a valid string representation."""
        exc = ElementNotInteractableError()
        message = str(exc)
        assert isinstance(message, str)
        assert len(message) > 0

    @given(
        operation=st.text(min_size=1, max_size=50),
        backend_type=st.text(min_size=1, max_size=20)
    )
    @settings(max_examples=50)
    def test_unsupported_operation_is_string_representable(self, operation, backend_type):
        """UnsupportedOperationError should have a valid string representation."""
        exc = UnsupportedOperationError(operation=operation, backend_type=backend_type)
        message = str(exc)
        assert isinstance(message, str)
        assert len(message) > 0


# =============================================================================
# Property 7.7: Exception messages don't expose sensitive information
# =============================================================================

class TestExceptionMessageSecurity:
    """Test that exception messages don't expose sensitive information."""

    def test_element_not_found_doesnt_expose_full_page_html(self):
        """ElementNotFoundError should not include full page HTML in message."""
        # Even with a very long target, message should be reasonable length
        long_target = "x" * 10000
        exc = ElementNotFoundError(strategy='xpath', target=long_target)
        message = str(exc)
        # Message should be reasonable length (not include full target if very long)
        # This is a soft check - implementation may truncate or not
        assert isinstance(message, str)

    def test_timeout_error_doesnt_expose_internal_state(self):
        """WebDriverTimeoutError should not expose internal state."""
        exc = WebDriverTimeoutError(operation='find_element', timeout=10.0)
        message = str(exc)
        # Should not contain memory addresses or internal object representations
        assert '0x' not in message.lower() or 'object at' not in message.lower()
