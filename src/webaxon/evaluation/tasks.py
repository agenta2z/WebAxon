"""Lightweight task loading for Online-Mind2Web and similar benchmarks.

No torch / transformers dependency — reads preprocessed JSONL only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class EvaluationTask:
    """A single evaluation task."""

    task_id: str
    task: str
    start_url: str
    reference_length: int = 0
    level: str = "medium"


def load_tasks(
    tasks_path: Path,
    *,
    level: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[EvaluationTask]:
    """Load evaluation tasks from a JSONL file.

    Each line must be a JSON object with at least ``task_id``, ``task``,
    and ``website`` (used as *start_url*).  Optional fields:
    ``reference_length``, ``level``.

    Parameters
    ----------
    tasks_path:
        Path to a ``.jsonl`` file.
    level:
        If provided, only tasks matching this difficulty level are returned.
    limit:
        Maximum number of tasks to return (after filtering and offset).
    offset:
        Number of tasks to skip before returning results.
    """
    tasks: List[EvaluationTask] = []

    with open(tasks_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)

            task_level = obj.get("level", "medium")
            if level is not None and task_level != level:
                continue

            tasks.append(
                EvaluationTask(
                    task_id=str(obj["task_id"]),
                    task=obj["task"],
                    start_url=obj.get("website", obj.get("start_url", "")),
                    reference_length=int(obj.get("reference_length", 0)),
                    level=task_level,
                )
            )

    # Apply offset and limit
    tasks = tasks[offset:]
    if limit is not None:
        tasks = tasks[:limit]

    return tasks
