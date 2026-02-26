"""Property-based tests for ActionFlow callable delegation.

This module contains property-based tests using hypothesis to verify
that ActionFlow properly delegates action execution to the
provided action_executor callable.

**Feature: webdriver-schema-consolidation, Property 7: Sequence execution delegation**
**Validates: Requirements 3.2, 3.3**
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock
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
_science_python_utils_src = _workspace_root / "SciencePythonUtils" / "src"
_science_modeling_tools_src = _workspace_root / "ScienceModelingTools" / "src"
if _science_python_utils_src.exists() and str(_science_python_utils_src) not in sys.path:
    sys.path.insert(0, str(_science_python_utils_src))
if _science_modeling_tools_src.exists() and str(_science_modeling_tools_src) not in sys.path:
    sys.path.insert(0, str(_science_modeling_tools_src))

from hypothesis import given, strategies as st, settings, assume
import pytest

from science_modeling_tools.automation.schema.action_flow import ActionFlow
from science_modeling_tools.automation.schema.common import (
    ActionSequence,
    Action,
    TargetSpec,
)
from science_modeling_tools.automation.schema.common import ActionResult, ExecutionResult
from science_modeling_tools.automation.schema.action_metadata import ActionMetadataRegistry


# =============================================================================
# Test Strategies
# =============================================================================

# Strategy for generating valid action IDs
action_id_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_"),
    min_size=1,
    max_size=20
).filter(lambda x: x[0].isalpha())

# Strategy for generating valid action types (non-composite)
action_type_strategy = st.sampled_from(["click", "input_text", "scroll"])

# Strategy for generating valid target values
target_value_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_-"),
    min_size=1,
    max_size=20
).filter(lambda x: x[0].isalpha())


@st.composite
def valid_action(draw, action_id: Optional[str] = None):
    """Generate a valid Action with a target."""
    if action_id is None:
        action_id = draw(action_id_strategy)
    
    action_type = draw(action_type_strategy)
    target_value = draw(target_value_strategy)
    
    target = TargetSpec(strategy="id", value=target_value)
    
    return Action(
        id=action_id,
        type=action_type,
        target=target
    )


@st.composite
def valid_action_sequence(draw, num_actions: Optional[int] = None):
    """Generate a valid ActionSequence with unique action IDs."""
    if num_actions is None:
        num_actions = draw(st.integers(min_value=1, max_value=5))
    
    # Generate unique action IDs
    action_ids = []
    for i in range(num_actions):
        action_ids.append(f"action_{i}")
    
    actions = []
    for action_id in action_ids:
        action = draw(valid_action(action_id=action_id))
        actions.append(action)
    
    return ActionSequence(
        id=draw(action_id_strategy),
        actions=actions
    )


# =============================================================================
# Mock Callables for Testing
# =============================================================================

class CallTracker:
    """Tracks calls to action_executor callable."""
    
    def __init__(self):
        self.action_executor_calls = []
        self._mock_result = MagicMock()
    
    def action_executor(self, action_type, action_target, action_args=None):
        """Mock action executor that tracks calls (simplified interface)."""
        self.action_executor_calls.append({
            'action_type': action_type,
            'action_target': action_target,
            'action_args': action_args
        })
        return self._mock_result


# =============================================================================
# Property 7: Action flow execution delegation
# **Feature: webdriver-schema-consolidation, Property 7: Sequence execution delegation**
# **Validates: Requirements 3.2, 3.3**
# =============================================================================

@settings(max_examples=100, deadline=None)
@given(sequence=valid_action_sequence())
def test_action_flow_executor_delegates_to_callables(sequence):
    """Property 7: For any ActionSequence executed via ActionFlow,
    each action's execution SHALL be performed by the provided action_executor.
    
    **Feature: webdriver-schema-consolidation, Property 7: Sequence execution delegation**
    **Validates: Requirements 3.2, 3.3**
    """
    # Create call tracker
    tracker = CallTracker()
    action_metadata = ActionMetadataRegistry()
    
    # Create ActionFlow with tracked callable
    executor = ActionFlow(
        action_executor=tracker.action_executor,
        action_metadata=action_metadata
    )
    
    # Execute the sequence
    result = executor.execute(sequence)
    
    # Verify execution succeeded
    assert result.success, f"Sequence execution should succeed, got error: {result.error}"
    
    # Verify action_executor was called for each action
    assert len(tracker.action_executor_calls) == len(sequence.actions), \
        f"action_executor should be called {len(sequence.actions)} times, " \
        f"but was called {len(tracker.action_executor_calls)} times"
    
    # Verify each action was executed in order
    for i, action in enumerate(sequence.actions):
        executor_call = tracker.action_executor_calls[i]
        assert executor_call['action_type'] == action.type, \
            f"Action {i} type should be '{action.type}', but was '{executor_call['action_type']}'"


@settings(max_examples=100, deadline=None)
@given(sequence=valid_action_sequence())
def test_action_flow_executor_passes_correct_arguments_to_strategy_resolver(sequence):
    """Property 7 (target args): For any ActionSequence, the action_executor
    callable SHALL receive the correct target value.
    
    **Feature: webdriver-schema-consolidation, Property 7: Sequence execution delegation**
    **Validates: Requirements 3.2**
    """
    tracker = CallTracker()
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=tracker.action_executor,
        action_metadata=action_metadata
    )
    
    result = executor.execute(sequence)
    assert result.success, f"Sequence execution should succeed, got error: {result.error}"
    
    # Verify each action_executor call received correct target value
    for i, action in enumerate(sequence.actions):
        call_info = tracker.action_executor_calls[i]
        
        # Verify target value was passed correctly
        expected_target = action.target.value if action.target else None
        assert call_info['action_target'] == expected_target, \
            f"action_executor should receive target '{expected_target}', got '{call_info['action_target']}'"


@settings(max_examples=100, deadline=None)
@given(sequence=valid_action_sequence())
def test_action_flow_executor_passes_resolved_target_to_action_executor(sequence):
    """Property 7 (target pass-through): For any ActionSequence, the action_executor
    callable SHALL receive the target value extracted from TargetSpec.
    
    **Feature: webdriver-schema-consolidation, Property 7: Sequence execution delegation**
    **Validates: Requirements 3.2**
    """
    tracker = CallTracker()
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=tracker.action_executor,
        action_metadata=action_metadata
    )
    
    result = executor.execute(sequence)
    assert result.success, f"Sequence execution should succeed, got error: {result.error}"
    
    # Verify each action_executor call received the target value
    for i, action in enumerate(sequence.actions):
        call_info = tracker.action_executor_calls[i]
        
        if action.target is not None:
            # Should receive the target value string
            assert call_info['action_target'] == action.target.value, \
                f"action_executor should receive target value for action '{action.id}'"
        else:
            # No target means action_target should be None
            assert call_info['action_target'] is None, \
                f"action_executor should receive None for action without target"


@settings(max_examples=100, deadline=None)
@given(sequence=valid_action_sequence())
def test_action_flow_executor_returns_execution_result_with_context(sequence):
    """Property 7 (result): For any ActionSequence, the ActionFlow
    SHALL return an ExecutionResult with the final context.
    
    **Feature: webdriver-schema-consolidation, Property 7: Sequence execution delegation**
    **Validates: Requirements 3.3**
    """
    tracker = CallTracker()
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=tracker.action_executor,
        action_metadata=action_metadata
    )
    
    result = executor.execute(sequence)
    
    # Verify result is an ExecutionResult
    assert isinstance(result, ExecutionResult), \
        f"execute() should return ExecutionResult, got {type(result)}"
    
    # Verify context contains results for all actions
    assert result.context is not None, "ExecutionResult should have a context"
    
    for action in sequence.actions:
        action_result = result.context.get_result(action.id)
        assert action_result is not None, \
            f"Context should contain result for action '{action.id}'"
        assert action_result.success, \
            f"Action '{action.id}' should have succeeded"


@settings(max_examples=100, deadline=None)
@given(
    num_actions=st.integers(min_value=2, max_value=5),
    fail_at_index=st.integers(min_value=0, max_value=4)
)
def test_action_flow_executor_stops_on_action_failure(num_actions, fail_at_index):
    """Property 7 (failure handling): For any ActionSequence where an action fails,
    the ActionFlow SHALL stop execution and return failure result.
    
    **Feature: webdriver-schema-consolidation, Property 7: Sequence execution delegation**
    **Validates: Requirements 3.3**
    """
    assume(fail_at_index < num_actions)
    
    # Create a sequence with known actions
    actions = []
    for i in range(num_actions):
        actions.append(Action(
            id=f"action_{i}",
            type="click",
            target=TargetSpec(strategy="id", value=f"element_{i}")
        ))
    
    sequence = ActionSequence(id="test_sequence", actions=actions)
    
    # Create executor that fails at specific index
    call_count = [0]
    
    def failing_action_executor(action_type, action_target, action_args=None):
        current_index = call_count[0]
        call_count[0] += 1
        
        if current_index == fail_at_index:
            raise Exception(f"Failed at action {current_index}")
        return MagicMock()
    
    action_metadata = ActionMetadataRegistry()
    
    executor = ActionFlow(
        action_executor=failing_action_executor,
        action_metadata=action_metadata
    )
    
    result = executor.execute(sequence)
    
    # Verify execution failed
    assert not result.success, "Sequence execution should fail"
    
    # Verify failed_action_id is set correctly
    assert result.failed_action_id == f"action_{fail_at_index}", \
        f"failed_action_id should be 'action_{fail_at_index}', got '{result.failed_action_id}'"
    
    # Verify only actions up to and including the failed one were executed
    assert call_count[0] == fail_at_index + 1, \
        f"Should have executed {fail_at_index + 1} actions, but executed {call_count[0]}"


if __name__ == '__main__':
    print("Running property-based tests for action flow execution delegation...")
    print()
    
    tests = [
        ("Property 7: ActionFlow delegates to callables",
         test_action_flow_executor_delegates_to_callables),
        ("Property 7: Passes correct arguments to action_executor",
         test_action_flow_executor_passes_correct_arguments_to_strategy_resolver),
        ("Property 7: Passes target value to action_executor",
         test_action_flow_executor_passes_resolved_target_to_action_executor),
        ("Property 7: Returns ExecutionResult with context",
         test_action_flow_executor_returns_execution_result_with_context),
        ("Property 7: Stops on action failure",
         test_action_flow_executor_stops_on_action_failure),
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
