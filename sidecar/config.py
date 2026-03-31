"""Configuration for WebAxon Browser Sidecar."""

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WebAxonSidecarConfig:
    """Configuration for the WebAxon browser sidecar server."""

    # Server settings
    # Use 0.0.0.0 to accept connections from Docker containers via host.docker.internal
    host: str = "0.0.0.0"
    port: int = 18800

    # Browser settings
    headless: bool = False
    chrome_version: Optional[int] = None  # Auto-detect if None
    backend: str = "selenium"  # "playwright" or "selenium"

    # Agent settings
    agent_type: str = "DefaultAgent"
    max_steps: int = 50
    agent_timeout: int = 300  # seconds

    # Workspace settings
    workspace: str = field(default_factory=lambda: os.path.expanduser("~/.webaxon/workspace"))

    # Debug settings
    debug_mode: bool = False
    synchronous_agent: bool = True  # For debugging with breakpoints

    @classmethod
    def from_env(cls) -> "WebAxonSidecarConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("WEBAXON_HOST", "127.0.0.1"),
            port=int(os.getenv("WEBAXON_PORT", "18800")),
            headless=os.getenv("WEBAXON_HEADLESS", "false").lower() == "true",
            chrome_version=int(os.getenv("WEBAXON_CHROME_VERSION")) if os.getenv("WEBAXON_CHROME_VERSION") else None,
            backend=os.getenv("WEBAXON_BACKEND", "selenium"),
            agent_type=os.getenv("WEBAXON_AGENT_TYPE", "DefaultAgent"),
            max_steps=int(os.getenv("WEBAXON_MAX_STEPS", "50")),
            agent_timeout=int(os.getenv("WEBAXON_AGENT_TIMEOUT", "300")),
            workspace=os.getenv("WEBAXON_WORKSPACE", os.path.expanduser("~/.webaxon/workspace")),
            debug_mode=os.getenv("WEBAXON_DEBUG", "false").lower() == "true",
            synchronous_agent=os.getenv("WEBAXON_SYNC_AGENT", "true").lower() == "true",
        )


def load_openclaw_config() -> dict:
    """
    Load environment variables from OpenClaw config file.

    Follows the pattern from ai-lab-atlassian-agent to load
    ~/.openclaw/openclaw.json and set environment variables.
    """
    search_paths = [
        "/root/.openclaw/openclaw.json",
        os.path.expanduser("~/.openclaw/openclaw.json"),
    ]

    for config_path in search_paths:
        if os.path.isfile(config_path):
            try:
                with open(config_path) as f:
                    config = json.load(f)

                # Extract and set environment variables
                env_vars = config.get("env", {}).get("vars", {})
                for key, value in env_vars.items():
                    if not os.environ.get(key):
                        os.environ[key] = str(value)

                return config
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load OpenClaw config from {config_path}: {e}")

    return {}


def ensure_workspace(workspace_path: str) -> str:
    """Ensure the workspace directory exists."""
    os.makedirs(workspace_path, exist_ok=True)
    return workspace_path
