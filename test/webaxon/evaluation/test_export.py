"""Unit tests for export_result() extended fields and raw_model_generations."""

import json
from pathlib import Path

import pytest

from webaxon.evaluation.export import export_result
from webaxon.evaluation.protocol import EvalResult
from webaxon.evaluation.tasks import EvaluationTask


def _make_task(task_id: str = "task_001") -> EvaluationTask:
    return EvaluationTask(
        task_id=task_id,
        task="Find the price of item X",
        start_url="https://example.com",
        reference_length=5,
        level="easy",
    )


def _make_result(
    raw_generations: list | None = None,
    error: str | None = None,
) -> EvalResult:
    return EvalResult(
        answer="done",
        confidence=0.9,
        action_history=["act1"],
        action_history_readable=["CLICK [target=1]"],
        thoughts=["thinking"],
        raw_generations=raw_generations or [],
        screenshot_paths=[Path("0_screenshot.png")],
        duration_seconds=10.0,
        error=error,
    )


class TestBackwardCompatibility:
    """Calling export_result without extended kwargs produces identical output."""

    def test_no_extended_fields_produces_same_keys(self, tmp_path: Path):
        task = _make_task()
        result = _make_result()
        rd = export_result(task, result, tmp_path)

        expected_keys = {
            "task_id", "task", "start_url",
            "action_history", "action_history_raw",
            "thoughts", "raw_generations",
            "final_result_response", "confidence",
            "duration_seconds", "num_steps", "num_screenshots",
        }
        assert set(rd.keys()) == expected_keys

    def test_no_raw_generations_file_when_empty(self, tmp_path: Path):
        task = _make_task()
        result = _make_result(raw_generations=[])
        export_result(task, result, tmp_path)
        assert not (tmp_path / task.task_id / "raw_model_generations.json").exists()

    def test_result_json_written(self, tmp_path: Path):
        task = _make_task()
        result = _make_result()
        export_result(task, result, tmp_path)
        rp = tmp_path / task.task_id / "result.json"
        assert rp.exists()
        data = json.loads(rp.read_text(encoding="utf-8"))
        assert data["task_id"] == "task_001"


class TestExtendedFields:
    """Non-None extended kwargs appear in result dict."""

    def test_single_extended_field(self, tmp_path: Path):
        task = _make_task()
        result = _make_result()
        rd = export_result(task, result, tmp_path, clarified_plan="my plan")
        assert rd["clarified_plan"] == "my plan"

    def test_multiple_extended_fields(self, tmp_path: Path):
        task = _make_task()
        result = _make_result()
        rd = export_result(
            task, result, tmp_path,
            done_criteria="all items found",
            must_have=["price", "name"],
            observer_summary="observed 3 steps",
        )
        assert rd["done_criteria"] == "all items found"
        assert rd["must_have"] == ["price", "name"]
        assert rd["observer_summary"] == "observed 3 steps"

    def test_none_fields_excluded(self, tmp_path: Path):
        task = _make_task()
        result = _make_result()
        rd = export_result(
            task, result, tmp_path,
            clarified_plan="plan",
            done_criteria=None,
        )
        assert "clarified_plan" in rd
        assert "done_criteria" not in rd

    def test_all_extended_fields(self, tmp_path: Path):
        task = _make_task()
        result = _make_result()
        rd = export_result(
            task, result, tmp_path,
            clarified_plan="plan",
            done_criteria="criteria",
            response_type="text",
            response_format="json",
            must_have=["a"],
            must_avoid=["b"],
            in_scope="scope_in",
            out_scope="scope_out",
            assumptions="assume",
            clarifier_dialogue=["q1", "a1"],
            clarifier_contract={"key": "val"},
            observer_summary="summary",
            observer_window_range=(0, 5),
            reflection_history=["r1"],
            judge_history=["j1"],
            answer_draft="draft",
            answer_judge_history=["aj1"],
        )
        assert rd["clarified_plan"] == "plan"
        assert rd["must_have"] == ["a"]
        assert rd["clarifier_contract"] == {"key": "val"}
        assert rd["observer_window_range"] == (0, 5)
        assert rd["answer_judge_history"] == ["aj1"]

    def test_extended_fields_persisted_to_json(self, tmp_path: Path):
        task = _make_task()
        result = _make_result()
        export_result(task, result, tmp_path, answer_draft="my draft")
        rp = tmp_path / task.task_id / "result.json"
        data = json.loads(rp.read_text(encoding="utf-8"))
        assert data["answer_draft"] == "my draft"


class TestRawModelGenerations:
    """raw_model_generations.json written separately when non-empty."""

    def test_written_when_non_empty(self, tmp_path: Path):
        task = _make_task()
        result = _make_result(raw_generations=["gen1", "gen2"])
        export_result(task, result, tmp_path)
        rgp = tmp_path / task.task_id / "raw_model_generations.json"
        assert rgp.exists()
        data = json.loads(rgp.read_text(encoding="utf-8"))
        assert data == ["gen1", "gen2"]

    def test_not_written_when_empty(self, tmp_path: Path):
        task = _make_task()
        result = _make_result(raw_generations=[])
        export_result(task, result, tmp_path)
        rgp = tmp_path / task.task_id / "raw_model_generations.json"
        assert not rgp.exists()
