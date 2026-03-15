"""Evaluation configuration — agent-agnostic."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


@dataclass
class EvaluationConfig:
    """Configuration for an evaluation run.

    Adapter-specific settings (e.g. ``testcase_root``, ``chrome_version``)
    are passed via *adapter_config* and forwarded to the adapter constructor.
    """

    adapter_name: str = "webaxon"
    """Which adapter to use (looked up via ``adapters.get_adapter``)."""

    adapter_config: Dict[str, Any] = field(default_factory=dict)
    """Keyword arguments forwarded to the adapter constructor."""

    max_steps: int = 50
    """Default maximum number of agent steps (LLM turns) per task."""

    agent_timeout: int = 600
    """Wall-clock timeout in seconds per task."""

    stay_on_start_url: bool = True
    """Whether to constrain the agent to the start URL's site."""

    output_dir: Path = field(default_factory=lambda: Path("_eval_runs"))
    """Root directory for evaluation outputs."""
