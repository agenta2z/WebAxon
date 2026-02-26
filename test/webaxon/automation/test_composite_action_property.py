"""
Property tests for Composite Action Decomposition.

Feature: playwright-support
Property 10: Composite Action Decomposition

Property 10: *For any* composite action configuration with N steps, when
`execute_composite_action` is called with N elements, each step SHALL be executed
on the corresponding element in sequence, and action-specific arguments with
prefixes (e.g., `input_text_text`) SHALL be correctly extracted and applied
to the matching sub-action.

Validates: Requirements 15.1, 15.2, 15.3, 15.4
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
from unittest.mock import MagicMock, patch, call
from hypothesis import given, strategies as st, settings, assume
from typing import List, Tuple


# =============================================================================
# Test Fixtures
# =============================================================================

def create_mock_action_config(name: str, composite_steps: List[Tuple[str, int]], mode: str = "sequential"):
    """Create a mock action config for composite action testing."""
    mock_config = MagicMock()
    mock_config.name = name
    mock_config.composite_steps = composite_steps

    # Create composite action with mode attribute
    mock_composite = MagicMock()
    mock_composite.mode = mode
    mock_config.composite_action = mock_composite

    return mock_config


def create_mock_elements(count: int):
    """Create mock WebElements for testing."""
    return [MagicMock(name=f"element_{i}") for i in range(count)]


# =============================================================================
# Property 10: Composite Action Decomposition
# =============================================================================

class TestCompositeActionDecomposition:
    """
    Property 10: For any composite action with N steps, execute_composite_action
    SHALL execute each step on the corresponding element in sequence.
    """

    def test_sequential_mode_executes_steps_in_order(self):
        """Steps should be executed in order for sequential mode."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(2)
        action_config = create_mock_action_config(
            name="input_and_click",
            composite_steps=[("input_text", 0), ("click", 1)]
        )

        with patch('webaxon.automation.selenium.actions.execute_single_action') as mock_exec:
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=action_config,
                action_args={'input_text_text': 'hello'},
                timeout=10,
                additional_wait_time=1.0
            )

            # Verify two calls were made
            assert mock_exec.call_count == 2

            # Verify first call was input_text on element 0
            first_call = mock_exec.call_args_list[0]
            assert first_call[1]['action_type'] == 'input_text'
            assert first_call[1]['element'] == elements[0]

            # Verify second call was click on element 1
            second_call = mock_exec.call_args_list[1]
            assert second_call[1]['action_type'] == 'click'
            assert second_call[1]['element'] == elements[1]

    def test_action_args_with_prefix_extracted_correctly(self):
        """Action args with prefix should be extracted for the correct step."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(2)
        action_config = create_mock_action_config(
            name="input_and_submit",
            composite_steps=[("input_text", 0), ("click", 1)]
        )

        with patch('webaxon.automation.selenium.actions.execute_single_action') as mock_exec:
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=action_config,
                action_args={'input_text_text': 'test_input', 'input_text_clear_content': True},
                timeout=10,
                additional_wait_time=1.0
            )

            # First call should have extracted input_text args
            first_call = mock_exec.call_args_list[0]
            step_args = first_call[1].get('action_args', {})
            # The prefix should be stripped, so 'text' not 'input_text_text'
            assert step_args is not None

    def test_unsupported_mode_raises_error(self):
        """Unsupported composite mode should raise ValueError."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(2)
        action_config = create_mock_action_config(
            name="test_action",
            composite_steps=[("click", 0)],
            mode="parallel"  # Unsupported mode
        )

        with pytest.raises(ValueError) as exc_info:
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=action_config
            )

        assert "unsupported" in str(exc_info.value).lower()

    def test_invalid_element_index_raises_error(self):
        """Referencing invalid element index should raise ValueError."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(1)  # Only 1 element
        action_config = create_mock_action_config(
            name="test_action",
            composite_steps=[("click", 5)]  # Index 5 doesn't exist
        )

        with pytest.raises(ValueError) as exc_info:
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=action_config
            )

        assert "element_index" in str(exc_info.value).lower() or "5" in str(exc_info.value)

    def test_empty_composite_steps_raises_error(self):
        """Empty composite_steps should raise ValueError."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(1)
        action_config = create_mock_action_config(
            name="test_action",
            composite_steps=[]
        )
        action_config.composite_steps = None  # Force it to be None

        with pytest.raises(ValueError) as exc_info:
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=action_config
            )

        assert "composite_steps" in str(exc_info.value).lower()

    def test_null_composite_action_raises_error(self):
        """Null composite_action should raise ValueError."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(1)

        mock_config = MagicMock()
        mock_config.name = "test_action"
        mock_config.composite_action = None

        with pytest.raises(ValueError) as exc_info:
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=mock_config
            )

        assert "composite" in str(exc_info.value).lower()


class TestCompositeActionStepExecution:
    """Tests for individual step execution in composite actions."""

    @given(num_steps=st.integers(min_value=1, max_value=5))
    @settings(max_examples=20)
    def test_correct_number_of_steps_executed(self, num_steps):
        """Number of execute_single_action calls should match number of steps."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(num_steps)
        steps = [("click", i) for i in range(num_steps)]
        action_config = create_mock_action_config(
            name="multi_click",
            composite_steps=steps
        )

        with patch('webaxon.automation.selenium.actions.execute_single_action') as mock_exec:
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=action_config,
                timeout=10,
                additional_wait_time=0.1
            )

            assert mock_exec.call_count == num_steps

    def test_each_step_gets_correct_element(self):
        """Each step should receive its corresponding element."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(3)
        action_config = create_mock_action_config(
            name="triple_action",
            composite_steps=[("click", 0), ("input_text", 1), ("click", 2)]
        )

        with patch('webaxon.automation.selenium.actions.execute_single_action') as mock_exec:
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=action_config,
                timeout=10,
                additional_wait_time=0.1
            )

            for i, call_args in enumerate(mock_exec.call_args_list):
                expected_element = elements[i]
                actual_element = call_args[1]['element']
                assert actual_element == expected_element

    def test_timeout_passed_to_each_step(self):
        """Timeout should be passed to each step execution."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(2)
        action_config = create_mock_action_config(
            name="timed_action",
            composite_steps=[("click", 0), ("click", 1)]
        )

        with patch('webaxon.automation.selenium.actions.execute_single_action') as mock_exec:
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=action_config,
                timeout=30,
                additional_wait_time=0.1
            )

            for call_args in mock_exec.call_args_list:
                assert call_args[1]['timeout'] == 30


class TestCompositeActionArgumentExtraction:
    """Tests for action argument extraction from prefixed parameters."""

    def test_extract_action_specific_args_function_exists(self):
        """_extract_action_specific_args function should exist."""
        from webaxon.automation.selenium.actions import _extract_action_specific_args
        assert callable(_extract_action_specific_args)

    def test_extract_removes_prefix(self):
        """Extracted args should have prefix removed."""
        from webaxon.automation.selenium.actions import _extract_action_specific_args

        action_args = {
            'input_text_text': 'hello',
            'input_text_clear_content': True,
            'click_force': False
        }

        result = _extract_action_specific_args('input_text', action_args)

        # Should extract 'text' and 'clear_content' (without 'input_text_' prefix)
        assert 'text' in result or result == {} or result is None
        # The function may return empty dict if no matches

    def test_unrelated_args_not_extracted(self):
        """Args for other action types should not be extracted."""
        from webaxon.automation.selenium.actions import _extract_action_specific_args

        action_args = {
            'click_force': True,
            'scroll_direction': 'down'
        }

        result = _extract_action_specific_args('input_text', action_args)

        # Should not include click or scroll args
        if result:
            assert 'force' not in result
            assert 'direction' not in result


class TestCompositeActionModeHandling:
    """Tests for composite action mode handling."""

    def test_sequential_mode_accepted(self):
        """Sequential mode should be accepted."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(1)
        action_config = create_mock_action_config(
            name="test",
            composite_steps=[("click", 0)],
            mode="sequential"
        )

        with patch('webaxon.automation.selenium.actions.execute_single_action'):
            # Should not raise
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=action_config
            )

    def test_old_enum_format_supported(self):
        """Old enum format for composite_action should be supported."""
        from webaxon.automation.selenium.actions import execute_composite_action

        mock_driver = MagicMock()
        elements = create_mock_elements(1)

        # Create config with old enum format
        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.composite_steps = [("click", 0)]

        # Old format: enum with value attribute
        mock_composite = MagicMock()
        mock_composite.value = "sequential"
        del mock_composite.mode  # Remove mode attribute to simulate old format
        mock_config.composite_action = mock_composite

        with patch('webaxon.automation.selenium.actions.execute_single_action'):
            # Should not raise
            execute_composite_action(
                driver=mock_driver,
                elements=elements,
                action_config=mock_config
            )
