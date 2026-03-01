"""Property-based tests for target resolution.

This module contains property-based tests using hypothesis to verify
target resolution behavior as specified in the design document.

Architecture:
- WebDriver.resolve_by_strategy: Simple (strategy, value) -> element resolution
- ActionFlow: Handles all orchestration (fallback, default strategy, description fallback)

**Feature: webdriver-schema-consolidation, Property 1: Strategy resolution consistency**
**Validates: Requirements 1.1**

**Feature: webdriver-schema-consolidation, Property 2: Fallback strategy ordering**
**Validates: Requirements 1.3**

**Feature: webdriver-schema-consolidation, Property 3: Resolution failure produces error**
**Validates: Requirements 1.4**
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Optional

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != 'test' and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
# Add SciencePythonUtils and ScienceModelingTools
_workspace_root = _project_root.parent
_rich_python_utils_src = _workspace_root / "SciencePythonUtils" / "src"
_agent_foundation_src = _workspace_root / "ScienceModelingTools" / "src"
if _rich_python_utils_src.exists() and str(_rich_python_utils_src) not in sys.path:
    sys.path.insert(0, str(_rich_python_utils_src))
if _agent_foundation_src.exists() and str(_agent_foundation_src) not in sys.path:
    sys.path.insert(0, str(_agent_foundation_src))

from hypothesis import given, strategies as st, settings, assume
import pytest

from selenium.common.exceptions import NoSuchElementException

from webaxon.automation.schema import (
    TargetSpec,
    TargetSpecWithFallback,
    ActionMetadataRegistry,
)
from webaxon.html_utils.element_identification import ATTR_NAME_INCREMENTAL_ID


# =============================================================================
# Test Strategies
# =============================================================================

# Valid strategy names that WebDriver supports
SUPPORTED_STRATEGIES = ["id", "xpath", "css", ATTR_NAME_INCREMENTAL_ID, "literal", "description"]

# Strategy for generating valid element IDs
element_id_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"),
    min_size=1,
    max_size=30
).filter(lambda x: x[0].isalpha())

# Strategy for generating valid XPath expressions
xpath_strategy = st.one_of(
    st.just("//button"),
    st.just("//div[@id='test']"),
    st.just("//input[@type='text']"),
    st.builds(lambda tag: f"//{tag}", st.sampled_from(["div", "span", "button", "input", "a"])),
)

# Strategy for generating valid CSS selectors
css_strategy = st.one_of(
    st.just("#test-id"),
    st.just(".test-class"),
    st.just("button.submit"),
    st.builds(lambda tag: f"{tag}.test", st.sampled_from(["div", "span", "button", "input", "a"])),
)

# Strategy for generating valid incremental IDs (numeric strings)
incremental_id_strategy = st.integers(min_value=0, max_value=9999).map(str)

# Strategy for generating valid URLs
url_strategy = st.one_of(
    st.just("https://example.com"),
    st.just("https://test.org/page"),
    st.builds(lambda domain: f"https://{domain}.com", 
              st.text(min_size=3, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz")),
)


@st.composite
def valid_strategy_value_pair(draw, strategy: Optional[str] = None):
    """Generate valid (strategy, value) pairs."""
    if strategy is None:
        # Exclude description for basic tests (it's not implemented)
        strategy = draw(st.sampled_from(["id", "xpath", "css", ATTR_NAME_INCREMENTAL_ID, "literal"]))
    
    if strategy == "id":
        value = draw(element_id_strategy)
    elif strategy == "xpath":
        value = draw(xpath_strategy)
    elif strategy == "css":
        value = draw(css_strategy)
    elif strategy == ATTR_NAME_INCREMENTAL_ID:
        value = draw(incremental_id_strategy)
    elif strategy == "literal":
        value = draw(url_strategy)
    elif strategy == "description":
        value = draw(st.text(min_size=5, max_size=50))
    else:
        value = draw(st.text(min_size=1, max_size=30))
    
    return (strategy, value)


@st.composite
def valid_target_spec_with_strategy(draw, strategy: Optional[str] = None):
    """Generate valid TargetSpec instances with specific or random strategy."""
    strat, value = draw(valid_strategy_value_pair(strategy))
    return TargetSpec(strategy=strat, value=value)


# =============================================================================
# Mock WebDriver for Testing
# =============================================================================

def create_test_webdriver():
    """Create a WebDriver instance with mocked Selenium driver for testing."""
    from webaxon.automation.web_driver import WebDriver
    
    mock_selenium_driver = MagicMock()
    
    with patch('webaxon.automation.web_driver.get_driver', return_value=mock_selenium_driver):
        webdriver = WebDriver.__new__(WebDriver)
        webdriver._driver = mock_selenium_driver
        webdriver._action_configs = {}
        webdriver._window_infos = {}
        webdriver._state = None
        webdriver.state_setting_max_retry = 3
        webdriver.state_setting_retry_wait = 0.2
        webdriver._id = "test-webdriver"
        webdriver._log_level = 0
    
    return webdriver, mock_selenium_driver


# =============================================================================
# Property 1: Strategy resolution consistency (WebDriver.resolve_by_strategy)
# **Feature: webdriver-schema-consolidation, Property 1: Strategy resolution consistency**
# **Validates: Requirements 1.1**
# =============================================================================

@settings(max_examples=100, deadline=None)
@given(strategy_value=valid_strategy_value_pair())
def test_strategy_resolution_returns_element(strategy_value):
    """Property 1: For any valid (strategy, value) pair with existing element,
    resolve_by_strategy SHALL return a WebElement.
    
    **Feature: webdriver-schema-consolidation, Property 1: Strategy resolution consistency**
    **Validates: Requirements 1.1**
    """
    strategy, value = strategy_value
    # Skip literal (returns None) and description (not implemented)
    assume(strategy not in ["literal", "description"])
    
    webdriver, mock_selenium_driver = create_test_webdriver()
    
    mock_element = MagicMock()
    mock_element.tag_name = "div"
    
    if strategy == ATTR_NAME_INCREMENTAL_ID:
        with patch('webaxon.automation.selenium.element_selection.find_element_by_unique_index',
                   return_value=mock_element):
            result = webdriver.resolve_action_target(strategy, value)
            assert result is mock_element
    else:
        mock_selenium_driver.find_element.return_value = mock_element
        result = webdriver.resolve_action_target(strategy, value)
        assert result is mock_element


@settings(max_examples=100, deadline=None)
@given(url=url_strategy)
def test_literal_strategy_returns_value(url):
    """Property 1 (literal case): For literal strategy, resolve_by_strategy SHALL return the value as-is.
    
    **Feature: webdriver-schema-consolidation, Property 1: Strategy resolution consistency**
    **Validates: Requirements 1.5**
    
    Note: Literal strategy returns the value directly (e.g., URL) without element resolution.
    """
    webdriver, _ = create_test_webdriver()
    result = webdriver.resolve_action_target("literal", url)
    assert result == url


@settings(max_examples=100, deadline=None)
@given(description=st.text(min_size=5, max_size=50))
def test_description_strategy_raises_not_implemented(description):
    """Property 1 (description case): For description strategy, resolve_by_strategy 
    SHALL raise NotImplementedError (MVP limitation).
    
    **Feature: webdriver-schema-consolidation, Property 1: Strategy resolution consistency**
    **Validates: Requirements 1.6**
    """
    webdriver, _ = create_test_webdriver()
    with pytest.raises(NotImplementedError):
        webdriver.resolve_action_target("description", description)


# =============================================================================
# Property 2: Fallback strategy ordering (ActionFlow)
# **Feature: webdriver-schema-consolidation, Property 2: Fallback strategy ordering**
# **Validates: Requirements 1.3**
# =============================================================================

def create_test_action_node(action, mock_action_executor):
    """Create an ActionNode with a mock action executor for testing."""
    from agent_foundation.automation.schema.action_node import ActionNode
    
    action_metadata = ActionMetadataRegistry()
    
    node = ActionNode(
        action=action,
        action_executor=mock_action_executor,
        action_metadata=action_metadata,
    )
    
    return node, action_metadata


@settings(max_examples=100, deadline=None)
@given(
    failing_count=st.integers(min_value=0, max_value=2),
    total_strategies=st.integers(min_value=2, max_value=4)
)
def test_fallback_tries_strategies_in_order(failing_count, total_strategies):
    """Property 2: For any TargetSpecWithFallback where the first N strategies fail,
    the executor SHALL try strategies in order and return the first successful result.
    
    **Feature: webdriver-schema-consolidation, Property 2: Fallback strategy ordering**
    **Validates: Requirements 1.3**
    
    Note: After refactor, fallback is handled by ActionNode with WorkGraphNode retry mechanism.
    Each retry increments _fallback_index to try the next strategy.
    """
    # Use ScienceModelingTools models since ActionNode uses those
    from agent_foundation.automation.schema.common import Action as SMTAction
    from agent_foundation.automation.schema.common import TargetSpec as SMTTargetSpec
    from agent_foundation.automation.schema.common import TargetSpecWithFallback as SMTTargetSpecWithFallback
    from agent_foundation.automation.schema.common import ExecutionRuntime
    
    assume(failing_count < total_strategies)
    
    mock_action_executor = MagicMock()
    
    # Create strategies with different values
    strategies = []
    for i in range(total_strategies):
        strategies.append(SMTTargetSpec(strategy="id", value=f"element_{i}"))
    
    fallback_spec = SMTTargetSpecWithFallback(strategies=strategies)
    
    # Create action with fallback target
    action = SMTAction(id="test_action", type="click", target=fallback_spec)
    
    node, _ = create_test_action_node(action, mock_action_executor)
    
    call_order = []
    successful_result = MagicMock()
    
    def mock_execute(action_type, action_target, action_args=None, action_target_strategy=None):
        call_order.append(action_target)
        if len(call_order) - 1 < failing_count:
            raise NoSuchElementException(f"Element not found: {action_target}")
        return successful_result
    
    mock_action_executor.side_effect = mock_execute
    
    # Execute via ActionNode.run() which handles retry/fallback
    context = ExecutionRuntime()
    result = node.run(context)
    
    assert result.success is True
    assert len(call_order) == failing_count + 1


@settings(max_examples=100, deadline=None)
@given(num_strategies=st.integers(min_value=2, max_value=4))
def test_fallback_all_fail_raises_error(num_strategies):
    """Property 2 (failure case): When all strategies fail, executor SHALL return failure result.
    
    **Feature: webdriver-schema-consolidation, Property 2: Fallback strategy ordering**
    **Validates: Requirements 1.3**
    
    Note: After refactor, ActionNode returns ActionResult with success=False when all
    fallback strategies are exhausted (via _get_fallback_result).
    """
    # Use ScienceModelingTools models since ActionNode uses those
    from agent_foundation.automation.schema.common import Action as SMTAction
    from agent_foundation.automation.schema.common import TargetSpec as SMTTargetSpec
    from agent_foundation.automation.schema.common import TargetSpecWithFallback as SMTTargetSpecWithFallback
    from agent_foundation.automation.schema.common import ExecutionRuntime
    
    mock_action_executor = MagicMock()
    
    strategies = [SMTTargetSpec(strategy="id", value=f"nonexistent_{i}") 
                  for i in range(num_strategies)]
    fallback_spec = SMTTargetSpecWithFallback(strategies=strategies)
    
    # Create action with fallback target
    action = SMTAction(id="test_action", type="click", target=fallback_spec)
    
    node, _ = create_test_action_node(action, mock_action_executor)
    
    mock_action_executor.side_effect = NoSuchElementException("Element not found")

    # Execute via ActionNode.run() - should return failure result after exhausting all strategies
    context = ExecutionRuntime()
    result = node.run(context)
    
    # ActionNode returns ActionResult with success=False when all fallbacks fail
    assert result.success is False


# =============================================================================
# Property 3: Resolution failure produces error
# **Feature: webdriver-schema-consolidation, Property 3: Resolution failure produces error**
# **Validates: Requirements 1.4**
# =============================================================================

@settings(max_examples=100, deadline=None)
@given(strategy_value=valid_strategy_value_pair())
def test_resolution_failure_raises_no_such_element_exception(strategy_value):
    """Property 3: When element doesn't exist, resolve_action_target SHALL raise NoSuchElementException.

    **Feature: webdriver-schema-consolidation, Property 3: Resolution failure produces error**
    **Validates: Requirements 1.4**
    """
    strategy, value = strategy_value
    assume(strategy not in ["literal", "description"])

    webdriver, mock_selenium_driver = create_test_webdriver()

    mock_selenium_driver.find_element.side_effect = NoSuchElementException("Element not found")

    with patch('webaxon.automation.selenium.element_selection.find_element_by_unique_index') as mock_find:
        mock_find.side_effect = NoSuchElementException("Element not found")

        with pytest.raises(NoSuchElementException):
            webdriver.resolve_action_target(strategy, value)


@settings(max_examples=100, deadline=None)
@given(unsupported=st.text(min_size=3, max_size=15).filter(
    lambda x: x.strip() and x not in SUPPORTED_STRATEGIES
))
def test_unsupported_strategy_raises_error(unsupported):
    """Property 3 (unsupported): Unsupported strategy SHALL raise NotImplementedError.

    **Feature: webdriver-schema-consolidation, Property 3: Resolution failure produces error**
    **Validates: Requirements 5.5**
    """
    webdriver, _ = create_test_webdriver()

    with pytest.raises(NotImplementedError) as exc_info:
        webdriver.resolve_action_target(unsupported, "test_value")

    assert "unsupported" in str(exc_info.value).lower()


@settings(max_examples=100, deadline=None)
@given(target_value=st.text(min_size=3, max_size=20).filter(lambda x: x.strip()))
def test_string_target_passed_through_to_action_executor(target_value):
    """Property 3 (string target): String target SHALL be passed directly to action_executor.
    
    **Feature: webdriver-schema-consolidation, Property 3: Target pass-through**
    **Validates: Requirements 1.4**
    
    Note: After refactor, ActionNode._execute_action handles target pass-through.
    """
    from agent_foundation.automation.schema.common import Action as SMTAction
    from agent_foundation.automation.schema.common import ExecutionRuntime
    
    mock_action_executor = MagicMock()
    mock_action_executor.return_value = MagicMock()
    
    # Create action with string target
    action = SMTAction(id="test_action", type="click", target=target_value)
    
    node, _ = create_test_action_node(action, mock_action_executor)
    
    # Execute the action via ActionNode
    context = ExecutionRuntime()
    node.run(context)
    
    # Verify the target was passed through directly
    mock_action_executor.assert_called_once()
    call_kwargs = mock_action_executor.call_args
    assert call_kwargs[1]['action_target'] == target_value


if __name__ == '__main__':
    print("Running property-based tests for target resolution...")
    print()
    print("Architecture:")
    print("  - WebDriver.resolve_by_strategy: Simple (strategy, value) -> element")
    print("  - ActionNode: Handles fallback via WorkGraphNode retry mechanism")
    print()
    
    tests = [
        ("Property 1: Strategy resolution returns element", test_strategy_resolution_returns_element),
        ("Property 1: Literal strategy returns value", test_literal_strategy_returns_value),
        ("Property 1: Description strategy raises NotImplementedError", test_description_strategy_raises_not_implemented),
        ("Property 2: Fallback tries strategies in order", test_fallback_tries_strategies_in_order),
        ("Property 2: Fallback all fail raises error", test_fallback_all_fail_raises_error),
        ("Property 3: Resolution failure raises NoSuchElementException", test_resolution_failure_raises_no_such_element_exception),
        ("Property 3: Unsupported strategy raises NotImplementedError", test_unsupported_strategy_raises_error),
        ("Property 3: String target passed through", test_string_target_passed_through_to_action_executor),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            print(f"✓ {test_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {test_name}")
            print(f"  Error: {e}")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\nAll property-based tests passed! ✓")
