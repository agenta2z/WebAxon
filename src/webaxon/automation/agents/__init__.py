"""
WebAgent automation agents module.

Contains specialized inferencers and agent components for web automation.

Components:
    - FindElementInferencer: One-inference agent for LLM-based element finding
    - FindElementInferenceConfig: Configuration for FindElementInferencer
    - create_action_agent: Factory function for creating action agents with sensible defaults
"""

from webaxon.automation.agents.find_element_inferencer import (
    FindElementInferencer,
    FindElementInferenceConfig,
)
from webaxon.automation.agents.action_agent_factory import create_action_agent

__all__ = ["FindElementInferencer", "FindElementInferenceConfig", "create_action_agent"]
