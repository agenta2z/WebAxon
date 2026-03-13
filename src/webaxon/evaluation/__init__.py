"""WebAxon Evaluation Framework.

Agent-agnostic evaluation runner for web navigation benchmarks.
"""

from .config import EvaluationConfig
from .protocol import EvalAgentAdapter, EvalResult
from .runner import EvaluationRunner
from .tasks import EvaluationTask, load_tasks

__all__ = [
    "EvalAgentAdapter",
    "EvalResult",
    "EvaluationConfig",
    "EvaluationRunner",
    "EvaluationTask",
    "load_tasks",
]
