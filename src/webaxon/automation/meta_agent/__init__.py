"""Web-specific meta-agent components for WebAgent."""

from webaxon.automation.meta_agent.web_normalizer_config import WEB_ACTION_TYPE_MAP
from webaxon.automation.meta_agent.web_pipeline import create_web_meta_agent_pipeline
from webaxon.automation.meta_agent.web_target_converter import WebTargetConverter

__all__ = [
    "WEB_ACTION_TYPE_MAP",
    "WebTargetConverter",
    "create_web_meta_agent_pipeline",
]
