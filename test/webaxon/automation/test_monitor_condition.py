"""
Unit Tests for MonitorCondition (Concrete Layer)

Tests the MonitorCondition class and its check() method for all condition types:
- ELEMENT_PRESENT: Wait for element to appear
- ELEMENT_ABSENT: Wait for element to disappear
- TEXT_CONTAINS: Wait for specific text
- TEXT_CHANGES: Wait for text to change
- CUSTOM: Custom callable condition

Note: Element resolution is handled by create_monitor() using TargetSpec.
The check() method receives a pre-resolved element (or None if not found).

**Feature: monitor-action**
**Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
"""

# Path resolution - must be first
import sys
from pathlib import Path

# Configuration
PIVOT_FOLDER_NAME = 'test'  # The folder name we're inside of

# Get absolute path to this file
current_file = Path(__file__).resolve()

# Navigate up to find the pivot folder (test directory)
current_path = current_file.parent
while current_path.name != PIVOT_FOLDER_NAME and current_path.parent != current_path:
    current_path = current_path.parent

if current_path.name != PIVOT_FOLDER_NAME:
    raise RuntimeError(f"Could not find '{PIVOT_FOLDER_NAME}' folder in path hierarchy")

# WebAgent root is parent of test/ directory
webagent_root = current_path.parent

# Add src directory to path for webaxon imports
src_dir = webagent_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Add science packages if they exist (for tests that need them)
projects_root = webagent_root.parent
rich_python_utils_src = projects_root / "SciencePythonUtils" / "src"
agent_foundation_src = projects_root / "ScienceModelingTools" / "src"

for path_item in [rich_python_utils_src, agent_foundation_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

import pytest
from unittest.mock import MagicMock
from webaxon.automation.monitor import MonitorCondition, MonitorConditionType


# =============================================================================
# Test Fixtures
# =============================================================================

def create_mock_driver():
    """Create a mock Selenium WebDriver for testing."""
    return MagicMock()


def create_mock_element(text="element text"):
    """Create a mock WebElement with configurable text."""
    element = MagicMock()
    element.text = text
    return element


# =============================================================================
# Task 7.1: Test ELEMENT_PRESENT condition with element found/not found
# =============================================================================

class TestElementPresentCondition:
    """Tests for ELEMENT_PRESENT condition type.

    Note: Element resolution is now handled by create_monitor() using TargetSpec.
    check() receives a pre-resolved element (or None).
    """

    def test_returns_true_when_element_found(self):
        """ELEMENT_PRESENT should return (True, text) when element is provided."""
        driver = create_mock_driver()
        element = create_mock_element("Found Element")

        condition = MonitorCondition(
            condition_type=MonitorConditionType.ELEMENT_PRESENT
        )

        # Element is pre-resolved and passed to check()
        met, content = condition.check(driver, element)

        assert met is True
        assert content == "Found Element"

    def test_returns_false_when_element_not_found(self):
        """ELEMENT_PRESENT should return (False, None) when element is None."""
        driver = create_mock_driver()

        condition = MonitorCondition(
            condition_type=MonitorConditionType.ELEMENT_PRESENT
        )

        # Element resolution failed, element is None
        met, content = condition.check(driver, None)

        assert met is False
        assert content is None

    def test_returns_none_content_when_element_has_no_text(self):
        """ELEMENT_PRESENT should return element text even if empty."""
        driver = create_mock_driver()
        element = create_mock_element("")

        condition = MonitorCondition(
            condition_type=MonitorConditionType.ELEMENT_PRESENT
        )

        met, content = condition.check(driver, element)

        assert met is True
        assert content == ""


# =============================================================================
# Task 7.2: Test ELEMENT_ABSENT condition with element present/absent
# =============================================================================

class TestElementAbsentCondition:
    """Tests for ELEMENT_ABSENT condition type.

    Note: Element resolution is now handled by create_monitor() using TargetSpec.
    check() receives a pre-resolved element (or None).
    """

    def test_returns_true_when_element_absent(self):
        """ELEMENT_ABSENT should return (True, None) when element is None."""
        driver = create_mock_driver()

        condition = MonitorCondition(
            condition_type=MonitorConditionType.ELEMENT_ABSENT
        )

        # Element resolution failed, element is None (absent)
        met, content = condition.check(driver, None)

        assert met is True
        assert content is None

    def test_returns_false_when_element_present(self):
        """ELEMENT_ABSENT should return (False, None) when element is provided."""
        driver = create_mock_driver()
        element = create_mock_element("Still Here")

        condition = MonitorCondition(
            condition_type=MonitorConditionType.ELEMENT_ABSENT
        )

        # Element was resolved, so it exists
        met, content = condition.check(driver, element)

        assert met is False
        assert content is None


# =============================================================================
# Task 7.3: Test TEXT_CONTAINS condition with text present/absent
# =============================================================================

class TestTextContainsCondition:
    """Tests for TEXT_CONTAINS condition type."""

    def test_returns_true_when_text_found(self):
        """TEXT_CONTAINS should return (True, expected_text) when text is found."""
        driver = create_mock_driver()
        body = create_mock_element("Page contains Order Complete and other text")
        driver.find_element.return_value = body

        condition = MonitorCondition(
            condition_type=MonitorConditionType.TEXT_CONTAINS,
            expected_text="Order Complete"
        )

        met, content = condition.check(driver)

        assert met is True
        assert content == "Order Complete"
        driver.find_element.assert_called_once_with("tag name", "body")

    def test_returns_true_when_text_found_in_element(self):
        """TEXT_CONTAINS should check element text if element is provided."""
        driver = create_mock_driver()
        element = create_mock_element("This contains Order Complete here")

        condition = MonitorCondition(
            condition_type=MonitorConditionType.TEXT_CONTAINS,
            expected_text="Order Complete"
        )

        met, content = condition.check(driver, element)

        assert met is True
        assert content == "Order Complete"
        # Should not call find_element since element was provided
        driver.find_element.assert_not_called()

    def test_returns_false_when_text_not_found(self):
        """TEXT_CONTAINS should return (False, None) when text is not found."""
        driver = create_mock_driver()
        body = create_mock_element("Page contains different content")
        driver.find_element.return_value = body

        condition = MonitorCondition(
            condition_type=MonitorConditionType.TEXT_CONTAINS,
            expected_text="Order Complete"
        )

        met, content = condition.check(driver)

        assert met is False
        assert content is None

    def test_returns_false_when_body_not_found(self):
        """TEXT_CONTAINS should return (False, None) when body element fails."""
        driver = create_mock_driver()
        driver.find_element.side_effect = Exception("Body not found")

        condition = MonitorCondition(
            condition_type=MonitorConditionType.TEXT_CONTAINS,
            expected_text="Order Complete"
        )

        met, content = condition.check(driver)

        assert met is False
        assert content is None

    def test_case_sensitive_matching(self):
        """TEXT_CONTAINS should be case-sensitive."""
        driver = create_mock_driver()
        body = create_mock_element("Page contains order complete")
        driver.find_element.return_value = body

        condition = MonitorCondition(
            condition_type=MonitorConditionType.TEXT_CONTAINS,
            expected_text="Order Complete"  # Different case
        )

        met, content = condition.check(driver)

        assert met is False
        assert content is None


# =============================================================================
# Task 7.4: Test TEXT_CHANGES condition with text changed/unchanged
# =============================================================================

class TestTextChangesCondition:
    """Tests for TEXT_CHANGES condition type.

    Note: Element resolution is now handled by create_monitor() using TargetSpec.
    check() receives a pre-resolved element (or None).
    """

    def test_first_check_records_baseline_returns_false(self):
        """TEXT_CHANGES should record baseline on first check and return False."""
        driver = create_mock_driver()
        element = create_mock_element("Initial Text")

        condition = MonitorCondition(
            condition_type=MonitorConditionType.TEXT_CHANGES
        )

        # Element is pre-resolved and passed to check()
        met, content = condition.check(driver, element)

        assert met is False
        assert content is None
        # Verify baseline was recorded
        assert condition._initial_text == "Initial Text"

    def test_returns_true_when_text_changes(self):
        """TEXT_CHANGES should return (True, new_text) when text changes."""
        driver = create_mock_driver()

        condition = MonitorCondition(
            condition_type=MonitorConditionType.TEXT_CHANGES
        )

        # First check - record baseline
        element1 = create_mock_element("Initial Text")
        condition.check(driver, element1)

        # Second check - text changed
        element2 = create_mock_element("Changed Text")
        met, content = condition.check(driver, element2)

        assert met is True
        assert content == "Changed Text"

    def test_returns_false_when_text_unchanged(self):
        """TEXT_CHANGES should return (False, None) when text is the same."""
        driver = create_mock_driver()

        condition = MonitorCondition(
            condition_type=MonitorConditionType.TEXT_CHANGES
        )

        # First check - record baseline
        element1 = create_mock_element("Same Text")
        condition.check(driver, element1)

        # Second check - text unchanged
        element2 = create_mock_element("Same Text")
        met, content = condition.check(driver, element2)

        assert met is False
        assert content is None

    def test_returns_false_when_element_not_found(self):
        """TEXT_CHANGES should return (False, None) when element is None."""
        driver = create_mock_driver()

        condition = MonitorCondition(
            condition_type=MonitorConditionType.TEXT_CHANGES
        )

        # Element resolution failed, element is None
        met, content = condition.check(driver, None)

        assert met is False
        assert content is None


# =============================================================================
# Task 7.5: Test CUSTOM condition with callable returning tuple and bool
# =============================================================================

class TestCustomCondition:
    """Tests for CUSTOM condition type."""

    def test_custom_callable_returning_tuple(self):
        """CUSTOM should pass through tuple (bool, content) from callable."""
        driver = create_mock_driver()

        def custom_check(drv):
            return (True, "Custom Content")

        condition = MonitorCondition(
            condition_type=MonitorConditionType.CUSTOM,
            custom_callable=custom_check
        )

        met, content = condition.check(driver)

        assert met is True
        assert content == "Custom Content"

    def test_custom_callable_returning_false_tuple(self):
        """CUSTOM should handle (False, content) tuple from callable."""
        driver = create_mock_driver()

        def custom_check(drv):
            return (False, "Not Ready")

        condition = MonitorCondition(
            condition_type=MonitorConditionType.CUSTOM,
            custom_callable=custom_check
        )

        met, content = condition.check(driver)

        assert met is False
        assert content == "Not Ready"

    def test_custom_callable_returning_bool_true(self):
        """CUSTOM should convert True to (True, True)."""
        driver = create_mock_driver()

        def custom_check(drv):
            return True

        condition = MonitorCondition(
            condition_type=MonitorConditionType.CUSTOM,
            custom_callable=custom_check
        )

        met, content = condition.check(driver)

        assert met is True
        assert content is True

    def test_custom_callable_returning_bool_false(self):
        """CUSTOM should convert False to (False, False)."""
        driver = create_mock_driver()

        def custom_check(drv):
            return False

        condition = MonitorCondition(
            condition_type=MonitorConditionType.CUSTOM,
            custom_callable=custom_check
        )

        met, content = condition.check(driver)

        assert met is False
        assert content is False

    def test_custom_callable_receives_driver(self):
        """CUSTOM callable should receive the driver as argument."""
        driver = create_mock_driver()
        received_driver = None

        def custom_check(drv):
            nonlocal received_driver
            received_driver = drv
            return (True, "Done")

        condition = MonitorCondition(
            condition_type=MonitorConditionType.CUSTOM,
            custom_callable=custom_check
        )

        condition.check(driver)

        assert received_driver is driver

    def test_custom_callable_none_returns_false(self):
        """CUSTOM with no callable should return (False, None)."""
        driver = create_mock_driver()

        condition = MonitorCondition(
            condition_type=MonitorConditionType.CUSTOM,
            custom_callable=None
        )

        met, content = condition.check(driver)

        assert met is False
        assert content is None

    def test_custom_callable_with_complex_logic(self):
        """CUSTOM should support complex condition logic."""
        driver = create_mock_driver()

        def check_price_below_threshold(drv):
            # Simulate checking a price element
            price = 75.50
            threshold = 100.00
            if price < threshold:
                return (True, price)
            return (False, price)

        condition = MonitorCondition(
            condition_type=MonitorConditionType.CUSTOM,
            custom_callable=check_price_below_threshold
        )

        met, content = condition.check(driver)

        assert met is True
        assert content == 75.50
