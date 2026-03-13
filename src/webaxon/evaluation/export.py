"""Export evaluation results in Online-Mind2Web format.

The output format is compatible with the WebJudge evaluator at
``evaluators/online_mind2web/run_eval.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .protocol import EvalResult
from .tasks import EvaluationTask


def export_result(
    task: EvaluationTask,
    result: EvalResult,
    output_dir: Path,
    *,
    clarified_plan: Optional[str] = None,
    done_criteria: Optional[str] = None,
    response_type: Optional[str] = None,
    response_format: Optional[str] = None,
    must_have: Optional[List[str]] = None,
    must_avoid: Optional[List[str]] = None,
    in_scope: Optional[str] = None,
    out_scope: Optional[str] = None,
    assumptions: Optional[str] = None,
    clarifier_dialogue: Optional[List[str]] = None,
    clarifier_contract: Optional[Any] = None,
    observer_summary: Optional[str] = None,
    observer_window_range: Optional[Any] = None,
    reflection_history: Optional[List[str]] = None,
    judge_history: Optional[List[str]] = None,
    answer_draft: Optional[str] = None,
    answer_judge_history: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Write ``result.json`` compatible with the Online-Mind2Web evaluator.

    Directory layout produced::

        output_dir/
          {task_id}/
            result.json
            trajectory/
              0_screenshot.png
              0_post_screenshot.png
              ...
            raw_model_generations.json  (written when raw_generations is non-empty)

    Extended keyword arguments (e.g. ``clarified_plan``, ``observer_summary``)
    are included in ``result.json`` only when their value is not ``None``.
    Calling without any extended kwargs produces output identical to the
    original implementation (backward compatible).

    Returns the result dict that was written.
    """
    task_dir = output_dir / task.task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    result_dict: Dict[str, Any] = {
        "task_id": task.task_id,
        "task": task.task,
        "start_url": task.start_url,
        "action_history": result.action_history_readable,
        "action_history_raw": result.action_history,
        "thoughts": result.thoughts,
        "raw_generations": result.raw_generations,
        "final_result_response": result.answer,
        "confidence": result.confidence,
        "duration_seconds": result.duration_seconds,
        "num_steps": len(result.action_history_readable),
        "num_screenshots": len(result.screenshot_paths),
    }

    if result.error:
        result_dict["error"] = result.error

    if result.metadata:
        result_dict["metadata"] = result.metadata

    # Include non-None extended fields.
    _extended = {
        "clarified_plan": clarified_plan,
        "done_criteria": done_criteria,
        "response_type": response_type,
        "response_format": response_format,
        "must_have": must_have,
        "must_avoid": must_avoid,
        "in_scope": in_scope,
        "out_scope": out_scope,
        "assumptions": assumptions,
        "clarifier_dialogue": clarifier_dialogue,
        "clarifier_contract": clarifier_contract,
        "observer_summary": observer_summary,
        "observer_window_range": observer_window_range,
        "reflection_history": reflection_history,
        "judge_history": judge_history,
        "answer_draft": answer_draft,
        "answer_judge_history": answer_judge_history,
    }
    for _name, _val in _extended.items():
        if _val is not None:
            result_dict[_name] = _val

    # Write result.json
    result_path = task_dir / "result.json"
    result_path.write_text(
        json.dumps(result_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Write raw_model_generations.json separately when non-empty.
    if result.raw_generations:
        raw_gen_path = task_dir / "raw_model_generations.json"
        raw_gen_path.write_text(
            json.dumps(result.raw_generations, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return result_dict
