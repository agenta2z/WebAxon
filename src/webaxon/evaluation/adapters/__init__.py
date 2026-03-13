"""Evaluation adapter registry.

Simple import-based lookup — no over-engineered registry pattern.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from webaxon.evaluation.protocol import EvalAgentAdapter


def get_adapter(name: str, **kwargs: Any) -> "EvalAgentAdapter":
    """Look up and instantiate an evaluation adapter by name."""
    if name == "webaxon":
        from .webaxon_adapter import WebAxonAdapter

        return WebAxonAdapter(**kwargs)
    raise ValueError(f"Unknown adapter: {name!r}. Available: 'webaxon'")
