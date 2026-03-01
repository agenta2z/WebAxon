"""
WebAgent Action Configuration and Selenium Utilities

Provides:
- WebAgentAction class that extends ActionTypeMetadata from ScienceModelingTools
  with backward-compatible properties for existing WebAgent/Selenium code
- DEFAULT_ACTION_CONFIGS loaded from ActionMetadataRegistry defaults

The authoritative source of truth is the Python code in action_metadata.py.
"""

from pathlib import Path
from types import MappingProxyType
from typing import Dict, List, Optional, Tuple

from agent_foundation.automation.schema.action_metadata import (
    ActionTypeMetadata,
    ActionMetadataRegistry,
    ActionMemoryMode,
    # Import action name constants from base class
    ACTION_NAME_CLICK,
    ACTION_NAME_INPUT_TEXT,
    ACTION_NAME_APPEND_TEXT,
    ACTION_NAME_SCROLL,
    ACTION_NAME_SCROLL_UP_TO_ELEMENT,
    ACTION_NAME_VISIT_URL,
    ACTION_NAME_WAIT,
    ACTION_NAME_NO_OP,
    ACTION_NAME_INPUT_AND_SUBMIT,
)


__all__ = [
    'WebAgentAction',
    'DEFAULT_ACTION_CONFIGS',
    'ActionMemoryMode',
    'ACTION_NAME_CLICK',
    'ACTION_NAME_INPUT_TEXT',
    'ACTION_NAME_APPEND_TEXT',
    'ACTION_NAME_SCROLL',
    'ACTION_NAME_SCROLL_UP_TO_ELEMENT',
    'ACTION_NAME_VISIT_URL',
    'ACTION_NAME_WAIT',
    'ACTION_NAME_NO_OP',
    'ACTION_NAME_INPUT_AND_SUBMIT',
]


class WebAgentAction(ActionTypeMetadata):
    """
    WebAgent-specific extension of ActionTypeMetadata.
    
    Inherits all functionality from base ActionTypeMetadata while providing
    backward compatibility properties for existing WebAgent/Selenium code.
    
    Memory Mode Constraints (inherited from base):
    - If base_memory_mode is NONE, incremental_change_mode must be NONE
    - If base_memory_mode is TARGET, incremental_change_mode must be TARGET or NONE
    - If base_memory_mode is FULL, incremental_change_mode can be FULL, TARGET, or NONE
    
    Composite Action:
    - composite_action specifies if this action should be decomposed into multiple sub-actions
    - composite_steps property provides backward-compatible tuple format access
    """
    
    @property
    def composite_steps(self) -> Optional[List[Tuple[str, int]]]:
        """
        Get composite steps in tuple format for backward compatibility.
        
        Converts from base CompositeActionStep format to tuple format.
        This property allows existing code that expects composite_steps as
        List[Tuple[str, int]] to continue working without modification.
        
        Returns:
            List of (action_type, element_index) tuples, or None if not a composite action.
        """
        if self.composite_action is not None and self.composite_action.steps:
            return [(step.action, step.element_index) 
                    for step in self.composite_action.steps]
        return None



def _load_default_action_configs() -> Dict[str, WebAgentAction]:
    """
    Load WebAgentAction instances from the base ActionMetadataRegistry.
    
    Uses the ActionMetadataRegistry defaults (defined in action_metadata.py) as the
    single source of truth for action metadata. Converts ActionTypeMetadata instances
    to WebAgentAction for backward compatibility.
    
    Returns:
        Dictionary mapping action names to WebAgentAction instances.
    """
    configs: Dict[str, WebAgentAction] = {}
    
    # Load from base registry defaults (Python code is the source of truth)
    registry = ActionMetadataRegistry()
    for action_name in registry.list_actions():
        metadata = registry.get_metadata(action_name)
        if metadata:
            configs[action_name] = WebAgentAction(**metadata.model_dump())
    
    return configs


# Load default configurations
_DEFAULT_ACTION_CONFIGS = _load_default_action_configs()

# Make DEFAULT_ACTION_CONFIGS read-only
DEFAULT_ACTION_CONFIGS = MappingProxyType(_DEFAULT_ACTION_CONFIGS)
