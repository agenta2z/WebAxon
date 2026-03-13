"""Agent-agnostic evaluation protocol and result types.

This module defines the contract that any web agent must implement to be
evaluated against benchmarks like Online-Mind2Web. The protocol is intentionally
minimal — adapters for specific agents live in the ``adapters`` subpackage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Protocol, runtime_checkable


@dataclass
class EvalResult:
    """Standard evaluation result — agent-agnostic."""

    answer: str
    """Final answer or completion message from the agent."""

    confidence: float
    """Confidence score in [0.0, 1.0]."""

    action_history: List[str]
    """Raw action representations (typically JSON strings)."""

    action_history_readable: List[str]
    """Human-readable action descriptions (e.g. ``CLICK [target=42]``)."""

    thoughts: List[str]
    """Agent reasoning / chain-of-thought entries."""

    raw_generations: List[str]
    """Raw LLM outputs before parsing."""

    screenshot_paths: List[Path]
    """Ordered per-step screenshot file paths in *trajectory_dir*."""

    duration_seconds: float
    """Wall-clock duration of the agent run."""

    error: Optional[str] = None
    """Error message if the run failed, ``None`` otherwise."""

    metadata: dict = field(default_factory=dict)
    """Adapter-specific metadata (e.g. session_dir)."""


@runtime_checkable
class EvalAgentAdapter(Protocol):
    """Protocol for plugging any web agent into the evaluation framework."""

    name: str

    def run_task(
        self,
        goal: str,
        start_url: str,
        max_steps: int,
        trajectory_dir: Path,
    ) -> EvalResult:
        """Run the agent on a single task.

        The adapter MUST save per-step screenshots into *trajectory_dir*
        using the naming convention ``{N}_screenshot.png``.
        """
        ...

    def cleanup(self) -> None:
        """Release resources (browser, temp dirs, etc.)."""
        ...
