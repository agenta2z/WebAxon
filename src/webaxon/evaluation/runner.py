"""Generic evaluation runner — agent-agnostic.

Orchestrates task loading, adapter invocation, and result export.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from .config import EvaluationConfig
from .export import export_result
from .protocol import EvalAgentAdapter, EvalResult
from .tasks import EvaluationTask

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Run evaluation tasks through an :class:`EvalAgentAdapter`."""

    def __init__(
        self,
        adapter: EvalAgentAdapter,
        config: EvaluationConfig,
    ) -> None:
        self.adapter = adapter
        self.config = config

    # ------------------------------------------------------------------
    # Single task
    # ------------------------------------------------------------------

    def run_task(self, task: EvaluationTask) -> Dict[str, Any]:
        """Run a single evaluation task and export the result.

        Returns the result dict written to ``result.json``.
        """
        # Adapt max_steps based on task reference_length
        max_steps = self.config.max_steps
        if task.reference_length > 0:
            max_steps = max(max_steps, task.reference_length * 2)

        output_dir = Path(self.config.output_dir)
        trajectory_dir = output_dir / task.task_id / "trajectory"
        trajectory_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Running task %s (max_steps=%d): %s",
            task.task_id,
            max_steps,
            task.task[:100],
        )

        start_time = time.time()
        try:
            result = self.adapter.run_task(
                goal=task.task,
                start_url=task.start_url,
                max_steps=max_steps,
                trajectory_dir=trajectory_dir,
            )
        except Exception as exc:
            logger.error("Task %s failed: %s", task.task_id, exc, exc_info=True)
            result = EvalResult(
                answer=f"Error: {exc}",
                confidence=0.0,
                action_history=[],
                action_history_readable=[],
                thoughts=[f"Error: {exc}"],
                raw_generations=[],
                screenshot_paths=[],
                duration_seconds=time.time() - start_time,
                error=str(exc),
            )

        result_dict = export_result(task, result, output_dir)

        logger.info(
            "Task %s completed: confidence=%.2f, steps=%d, duration=%.1fs",
            task.task_id,
            result.confidence,
            len(result.action_history_readable),
            result.duration_seconds,
        )

        return result_dict

    # ------------------------------------------------------------------
    # Dataset run
    # ------------------------------------------------------------------

    def run_dataset(self, tasks: List[EvaluationTask]) -> Path:
        """Run all tasks sequentially, writing ``answers.jsonl``.

        Returns the path to the answers file.
        """
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        answers_path = output_dir / "answers.jsonl"

        logger.info("Starting dataset run: %d tasks → %s", len(tasks), output_dir)

        with open(answers_path, "w", encoding="utf-8") as fh:
            for i, task in enumerate(tasks, 1):
                logger.info("=== Task %d/%d: %s ===", i, len(tasks), task.task_id)

                try:
                    result_dict = self.run_task(task)
                except Exception as exc:
                    logger.error(
                        "Task %s failed unexpectedly: %s",
                        task.task_id,
                        exc,
                        exc_info=True,
                    )
                    result_dict = {
                        "task_id": task.task_id,
                        "error": str(exc),
                        "confidence": 0.0,
                    }

                # Write answer line
                answer_line = {
                    "id": task.task_id,
                    "answer": result_dict.get("final_result_response", ""),
                    "confidence": result_dict.get("confidence", 0.0),
                }
                fh.write(json.dumps(answer_line, ensure_ascii=False) + "\n")
                fh.flush()

                # Cleanup between tasks
                try:
                    self.adapter.cleanup()
                except Exception as exc:
                    logger.warning(
                        "Adapter cleanup after task %s failed: %s",
                        task.task_id,
                        exc,
                    )

        logger.info("Dataset run complete. Answers: %s", answers_path)
        return answers_path
