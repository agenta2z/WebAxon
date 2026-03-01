"""
MVP Tests for Action Sequence Schema System

Tests basic functionality of loading and validating action sequences.
"""

import sys
from pathlib import Path

# Add project root to path
# Path: test_mvp.py -> schema -> automation -> webaxon -> test -> WebAgent -> workspace root
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
webagent_src = project_root / "WebAgent" / "src"
rich_python_utils_src = project_root / "SciencePythonUtils" / "src"
agent_foundation_src = project_root / "ScienceModelingTools" / "src"

for path in [webagent_src, rich_python_utils_src, agent_foundation_src]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest

from webaxon.automation.schema import (
    load_sequence,
    load_sequence_from_string,
    ActionSequence,
    Action,
    TargetSpec,
    ActionMetadataRegistry,
)


# Get examples directory - navigate from test/webaxon/automation/schema to src/webaxon/automation/schema/examples
EXAMPLES_DIR = Path(__file__).parent.parent.parent.parent.parent / "src" / "webaxon" / "automation" / "schema" / "examples"


def test_load_mvp_basic_json():
    """Test loading basic MVP JSON file."""
    sequence = load_sequence(EXAMPLES_DIR / "mvp_basic.json")
    
    assert sequence.version == "1.0"
    assert sequence.id == "mvp_basic_test"
    assert len(sequence.actions) == 5
    
    # Check first action (visit_url)
    assert sequence.actions[0].id == "visit_page"
    assert sequence.actions[0].type == "visit_url"
    assert sequence.actions[0].target == "https://example.com"
    
    # Check action with explicit strategy
    assert sequence.actions[1].id == "click_by_id"
    assert sequence.actions[1].type == "click"
    assert isinstance(sequence.actions[1].target, TargetSpec)
    assert sequence.actions[1].target.strategy == "id"
    assert sequence.actions[1].target.value == "submit-button"
    
    # Check action with args
    assert sequence.actions[2].id == "input_by_xpath"
    assert sequence.actions[2].type == "input_text"
    assert sequence.actions[2].args["text"] == "test_user"
    
    # Check wait action
    assert sequence.actions[4].id == "wait_a_moment"
    assert sequence.actions[4].type == "wait"
    assert sequence.actions[4].args["seconds"] == 1


def test_load_mvp_simple_json():
    """Test loading simple MVP JSON file with description."""
    sequence = load_sequence(EXAMPLES_DIR / "mvp_simple.json")
    
    assert sequence.version == "1.0"
    assert sequence.id == "mvp_simple_test"
    assert len(sequence.actions) == 5
    
    # Check action with description (should fail gracefully in MVP)
    last_action = sequence.actions[4]
    assert last_action.id == "find_by_description_example"
    assert last_action.type == "click"
    assert isinstance(last_action.target, TargetSpec)
    assert last_action.target.description == "the first search result link"


def test_load_sequence_from_string():
    """Test loading sequence from JSON string."""
    json_str = '''
    {
        "version": "1.0",
        "id": "test_sequence",
        "actions": [
            {
                "id": "action1",
                "type": "click",
                "target": "button1"
            }
        ]
    }
    '''
    
    sequence = load_sequence_from_string(json_str)
    assert sequence.id == "test_sequence"
    assert len(sequence.actions) == 1
    assert sequence.actions[0].id == "action1"


def test_action_metadata_registry():
    """Test action metadata registry."""
    registry = ActionMetadataRegistry()
    
    # Check default actions are loaded
    assert "click" in registry.metadata
    assert "input_text" in registry.metadata
    assert "visit_url" in registry.metadata
    assert "wait" in registry.metadata
    
    # Check default strategies
    # Note: default_strategy changed from "id" to "__id__" per action-metadata-consolidation spec
    # FRAMEWORK_ID is the framework-assigned unique identifier strategy (value='__id__')
    from agent_foundation.automation.schema.action_metadata import TargetStrategy
    assert registry.get_default_strategy("click") == TargetStrategy.FRAMEWORK_ID
    assert registry.get_default_strategy("input_text") == TargetStrategy.FRAMEWORK_ID
    assert registry.get_default_strategy("visit_url") == TargetStrategy.LITERAL
    assert registry.get_default_strategy("wait") is None
    
    # Check requires_target
    assert registry.requires_target("click") is True
    assert registry.requires_target("wait") is False


def test_action_metadata_from_file():
    """Test loading action metadata from JSON file."""
    metadata_file = EXAMPLES_DIR / "custom_action_metadata.json"
    registry = ActionMetadataRegistry(metadata_file=str(metadata_file))
    
    # Check custom actions are loaded
    assert "custom_hover" in registry.metadata
    assert "custom_double_click" in registry.metadata
    
    # Check custom default strategies
    assert registry.get_default_strategy("custom_hover") == "css"
    assert registry.get_default_strategy("custom_double_click") == "xpath"


def test_action_sequence_validation():
    """Test action sequence validation."""
    # Valid sequence
    sequence = ActionSequence(
        id="test",
        actions=[
            Action(id="a1", type="click", target="button1")
        ]
    )
    assert sequence.id == "test"
    
    # Empty actions should fail
    with pytest.raises(ValueError, match="at least one action"):
        ActionSequence(id="test", actions=[])
    
    # Duplicate action IDs should fail
    with pytest.raises(ValueError, match="Duplicate action IDs"):
        ActionSequence(
            id="test",
            actions=[
                Action(id="a1", type="click", target="button1"),
                Action(id="a1", type="click", target="button2")
            ]
        )


def test_target_spec_validation():
    """Test target spec validation."""
    # Valid with value
    target = TargetSpec(strategy="id", value="button1")
    assert target.strategy == "id"
    assert target.value == "button1"
    
    # Valid with description only
    target = TargetSpec(description="the submit button")
    assert target.description == "the submit button"
    
    # Invalid: neither value nor description
    with pytest.raises(ValueError, match="at least 'value' or 'description'"):
        TargetSpec(strategy="id")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
