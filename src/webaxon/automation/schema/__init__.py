"""
Action Sequence Schema System for WebAgent

This package provides Selenium-specific implementations and re-exports
the generic automation schema from agent_foundation.

Key Components:
- Core (from agent_foundation): models, action_metadata, loader, executor, context
- WebAgent-specific: WebAgentAction, DEFAULT_ACTION_CONFIGS
"""

# Re-export from agent_foundation for backward compatibility

# ActionFlow from agent_foundation
from agent_foundation.automation.schema import (
    # Models
    Action,
    # Protocols
    ActionExecutor,
    ActionFlow,
    # Action Metadata
    ActionMetadataRegistry,
    # Context and Results
    ActionResult,
    ActionSequence,
    ActionTypeMetadata,
    CompositeActionConfig,
    CompositeActionStep,
    ExecutionResult,
    ExecutionRuntime,
    # Loader
    load_sequence,
    load_sequence_from_string,
    TargetSpec,
    TargetSpecWithFallback,
    TargetStrategy,
)

# WebAgent-specific action configuration and Selenium utilities
from webaxon.automation.schema.webagent_action import (
    ACTION_NAME_APPEND_TEXT,
    ACTION_NAME_CLICK,
    ACTION_NAME_INPUT_AND_SUBMIT,
    ACTION_NAME_INPUT_TEXT,
    ACTION_NAME_NO_OP,
    ACTION_NAME_SCROLL,
    ACTION_NAME_SCROLL_UP_TO_ELEMENT,
    ACTION_NAME_VISIT_URL,
    ACTION_NAME_WAIT,
    ActionMemoryMode,
    DEFAULT_ACTION_CONFIGS,
    WebAgentAction,
)

__all__ = [
    # Models
    "Action",
    "ActionSequence",
    "TargetSpec",
    "TargetSpecWithFallback",
    "TargetStrategy",
    # Context and Results
    "ActionResult",
    "ExecutionRuntime",
    "ExecutionResult",
    # Action Metadata
    "ActionMetadataRegistry",
    "ActionTypeMetadata",
    "CompositeActionConfig",
    "CompositeActionStep",
    # Loader
    "load_sequence",
    "load_sequence_from_string",
    # Executor
    "ActionFlow",
    # Protocols
    "ActionExecutor",
    # WebAgent Action Configuration
    "WebAgentAction",
    "DEFAULT_ACTION_CONFIGS",
    "ActionMemoryMode",
    "ACTION_NAME_CLICK",
    "ACTION_NAME_INPUT_TEXT",
    "ACTION_NAME_APPEND_TEXT",
    "ACTION_NAME_SCROLL",
    "ACTION_NAME_SCROLL_UP_TO_ELEMENT",
    "ACTION_NAME_VISIT_URL",
    "ACTION_NAME_WAIT",
    "ACTION_NAME_NO_OP",
    "ACTION_NAME_INPUT_AND_SUBMIT",
]

__version__ = "1.0.0"
