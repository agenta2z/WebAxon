"""
Integration Tests for Action Sequence Schema System

Tests integration with WebDriver and actual execution (mocked for MVP).
"""

import sys
from pathlib import Path

# Add project root to path
# Path: test_integration.py -> schema -> automation -> webaxon -> test -> WebAgent -> workspace root
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
webagent_src = project_root / "WebAgent" / "src"
rich_python_utils_src = project_root / "SciencePythonUtils" / "src"
agent_foundation_src = project_root / "ScienceModelingTools" / "src"

for path in [webagent_src, rich_python_utils_src, agent_foundation_src]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from attr import attrs, attrib

from webaxon.automation.schema import (
    load_sequence,
    ActionMetadataRegistry,
    ActionFlow,
    ExecutionResult,
)


# Get examples directory - navigate from test/webaxon/automation/schema to src/webaxon/automation/schema/examples
EXAMPLES_DIR = Path(__file__).parent.parent.parent.parent.parent / "src" / "webaxon" / "automation" / "schema" / "examples"


@attrs(slots=True)
class MockActionResult:
    """Mock result that mimics WebDriverActionResult."""
    source: str = attrib(default="https://example.com")
    is_follow_up: bool = attrib(default=False)


def create_mock_action_executor():
    """Create a mock action executor with WebDriver.__call__ signature."""
    mock_executor = Mock()
    mock_executor.return_value = MockActionResult()
    return mock_executor


def test_sequence_executor_initialization():
    """Test that ActionFlow can be initialized with callable components."""
    # Create mock action executor
    mock_executor = create_mock_action_executor()
    action_metadata = ActionMetadataRegistry()
    
    # Create executor with new interface
    executor = ActionFlow(
        action_executor=mock_executor,
        action_metadata=action_metadata
    )
    
    assert executor is not None
    assert executor.action_executor == mock_executor
    assert executor.action_metadata == action_metadata


def test_execute_wait_action():
    """Test executing a simple wait action (no target required)."""
    # Create mock action executor
    mock_executor = create_mock_action_executor()
    
    # Load a simple sequence with just a wait action
    sequence_json = '''
    {
        "version": "1.0",
        "id": "test_wait",
        "actions": [
            {
                "id": "wait1",
                "type": "wait",
                "args": {"seconds": 0.1}
            }
        ]
    }
    '''
    
    from webaxon.automation.schema import load_sequence_from_string
    sequence = load_sequence_from_string(sequence_json)
    
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=mock_executor,
        action_metadata=action_metadata
    )
    
    # Execute sequence
    result = executor.execute(sequence)
    
    # Verify result
    assert result.success is True
    assert "wait1" in result.context.results
    assert result.context.results["wait1"].success is True
    
    # Verify action_executor was called with correct parameters
    mock_executor.assert_called_once()
    call_kwargs = mock_executor.call_args.kwargs
    assert call_kwargs["action_type"] == "wait"
    assert call_kwargs["action_target"] is None
    assert call_kwargs["action_args"] == {"seconds": 0.1}


def test_execute_visit_url_action():
    """Test executing a visit_url action."""
    # Create mock action executor
    mock_executor = create_mock_action_executor()
    
    # Load a simple sequence with visit_url
    sequence_json = '''
    {
        "version": "1.0",
        "id": "test_visit",
        "actions": [
            {
                "id": "visit1",
                "type": "visit_url",
                "target": "https://example.com"
            }
        ]
    }
    '''
    
    from webaxon.automation.schema import load_sequence_from_string
    sequence = load_sequence_from_string(sequence_json)
    
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=mock_executor,
        action_metadata=action_metadata
    )
    
    # Execute sequence
    result = executor.execute(sequence)
    
    # Verify result
    assert result.success is True
    assert "visit1" in result.context.results
    assert result.context.results["visit1"].success is True
    
    # Verify action_executor was called with URL as target
    mock_executor.assert_called_once()
    call_kwargs = mock_executor.call_args.kwargs
    assert call_kwargs["action_type"] == "visit_url"
    assert call_kwargs["action_target"] == "https://example.com"


def test_execute_click_action_with_target():
    """Test executing a click action with target."""
    # Create mock action executor
    mock_executor = create_mock_action_executor()
    
    # Load a simple sequence with click
    sequence_json = '''
    {
        "version": "1.0",
        "id": "test_click",
        "actions": [
            {
                "id": "click1",
                "type": "click",
                "target": {
                    "strategy": "id",
                    "value": "button1"
                }
            }
        ]
    }
    '''
    
    from webaxon.automation.schema import load_sequence_from_string
    sequence = load_sequence_from_string(sequence_json)
    
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=mock_executor,
        action_metadata=action_metadata
    )
    
    # Execute sequence
    result = executor.execute(sequence)
    
    # Verify result
    assert result.success is True
    assert "click1" in result.context.results
    assert result.context.results["click1"].success is True
    
    # Verify action_executor was called with target value
    mock_executor.assert_called_once()
    call_kwargs = mock_executor.call_args.kwargs
    assert call_kwargs["action_type"] == "click"
    assert call_kwargs["action_target"] == "button1"


def test_execute_sequence_with_error():
    """Test that execution stops on error."""
    # Create mock action executor that fails
    mock_executor = Mock(side_effect=Exception("Element not found"))
    
    # Load a sequence that will fail
    sequence_json = '''
    {
        "version": "1.0",
        "id": "test_error",
        "actions": [
            {
                "id": "click1",
                "type": "click",
                "target": {
                    "strategy": "id",
                    "value": "nonexistent"
                }
            },
            {
                "id": "wait1",
                "type": "wait",
                "args": {"seconds": 0.1}
            }
        ]
    }
    '''
    
    from webaxon.automation.schema import load_sequence_from_string
    sequence = load_sequence_from_string(sequence_json)
    
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=mock_executor,
        action_metadata=action_metadata
    )
    
    # Execute sequence
    result = executor.execute(sequence)
    
    # Verify result
    assert result.success is False
    assert result.failed_action_id == "click1"
    assert result.error is not None
    
    # Verify second action was not executed
    assert "wait1" not in result.context.results


def test_execute_with_fallback():
    """Test that fallback tries each target until one succeeds."""
    call_count = [0]
    
    def mock_executor_with_fallback(action_type, action_target, action_args):
        call_count[0] += 1
        # Fail on first target, succeed on second
        if action_target == "target1":
            raise Exception("Target not found")
        return MockActionResult()
    
    sequence_json = '''
    {
        "version": "1.0",
        "id": "test_fallback",
        "actions": [
            {
                "id": "click1",
                "type": "click",
                "target": {
                    "strategies": [
                        {"strategy": "id", "value": "target1"},
                        {"strategy": "id", "value": "target2"}
                    ]
                }
            }
        ]
    }
    '''
    
    from webaxon.automation.schema import load_sequence_from_string
    sequence = load_sequence_from_string(sequence_json)
    
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=mock_executor_with_fallback,
        action_metadata=action_metadata
    )
    
    result = executor.execute(sequence)
    
    # Should succeed with second target
    assert result.success is True
    assert call_count[0] == 2  # Called twice: first failed, second succeeded


def test_composite_action_passes_target_directly():
    """
    Test that composite actions pass target directly to action_executor.
    
    Design Principle:
    - Non-composite action: target is single element ID
    - Composite action: target is space-separated element IDs (string)
    - ActionFlow passes target through; WebDriver handles the distinction
    """
    mock_executor = create_mock_action_executor()
    
    # Create a sequence with composite action using space-separated target
    # This is the new design: composite actions use 'target' with space-separated IDs
    sequence_json = '''
    {
        "version": "1.0",
        "id": "test_composite",
        "actions": [
            {
                "id": "drag1",
                "type": "drag_and_drop",
                "target": "source_elem target_elem"
            }
        ]
    }
    '''
    
    from webaxon.automation.schema import load_sequence_from_string
    sequence = load_sequence_from_string(sequence_json)
    
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=mock_executor,
        action_metadata=action_metadata
    )
    
    result = executor.execute(sequence)
    
    # Verify action_executor was called with target passed through directly
    mock_executor.assert_called_once()
    call_kwargs = mock_executor.call_args.kwargs
    assert call_kwargs["action_target"] == "source_elem target_elem"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
