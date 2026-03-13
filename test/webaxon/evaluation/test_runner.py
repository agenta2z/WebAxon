"""Unit tests for EvaluationRunner with mocked adapter.

Validates: Requirements 6.6
- run_task() delegates to adapter and calls export_result()
- run_dataset() writes answers.jsonl
- Error handling
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from webaxon.evaluation.config import EvaluationConfig
from webaxon.evaluation.protocol import EvalAgentAdapter, EvalResult
from webaxon.evaluation.runner import EvaluationRunner
from webaxon.evaluation.tasks import EvaluationTask


def _make_adapter(result: EvalResult) -> MagicMock:
    """Create a mock adapter that returns the given result."""
    adapter = MagicMock(spec=EvalAgentAdapter)
    adapter.name = "mock"
    adapter.run_task.return_value = result
    adapter.cleanup.return_value = None
    return adapter


class TestRunTask:
    """run_task() delegates to adapter and calls export_result()."""

    def test_delegates_to_adapter(self, sample_task, sample_result, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        runner.run_task(sample_task)

        adapter.run_task.assert_called_once()
        call_kwargs = adapter.run_task.call_args
        assert call_kwargs.kwargs["goal"] == sample_task.task
        assert call_kwargs.kwargs["start_url"] == sample_task.start_url

    def test_calls_export_result(self, sample_task, sample_result, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        runner.run_task(sample_task)

        result_json = tmp_path / sample_task.task_id / "result.json"
        assert result_json.exists()
        data = json.loads(result_json.read_text(encoding="utf-8"))
        assert data["task_id"] == sample_task.task_id
        assert data["final_result_response"] == sample_result.answer

    def test_returns_result_dict(self, sample_task, sample_result, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        result_dict = runner.run_task(sample_task)

        assert isinstance(result_dict, dict)
        assert result_dict["task_id"] == sample_task.task_id
        assert result_dict["confidence"] == sample_result.confidence

    def test_max_steps_adapts_to_reference_length(self, sample_task, sample_result, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path, max_steps=10)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        # sample_task has reference_length=5, so max_steps = max(10, 5*2) = 10
        runner.run_task(sample_task)

        call_kwargs = adapter.run_task.call_args
        assert call_kwargs.kwargs["max_steps"] == 10

    def test_max_steps_scales_with_large_reference(self, sample_result, tmp_path):
        task = EvaluationTask(
            task_id="task_big",
            task="Big task",
            start_url="https://example.com",
            reference_length=50,
            level="hard",
        )
        config = EvaluationConfig(output_dir=tmp_path, max_steps=10)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        runner.run_task(task)

        call_kwargs = adapter.run_task.call_args
        # max(10, 50*2) = 100
        assert call_kwargs.kwargs["max_steps"] == 100

    def test_creates_trajectory_dir(self, sample_task, sample_result, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        runner.run_task(sample_task)

        trajectory_dir = tmp_path / sample_task.task_id / "trajectory"
        assert trajectory_dir.is_dir()


class TestRunDataset:
    """run_dataset() writes answers.jsonl."""

    def test_writes_answers_jsonl(self, sample_task, sample_result, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        answers_path = runner.run_dataset([sample_task])

        assert answers_path == tmp_path / "answers.jsonl"
        assert answers_path.exists()

    def test_answers_jsonl_content(self, sample_task, sample_result, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        answers_path = runner.run_dataset([sample_task])

        lines = answers_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["id"] == sample_task.task_id
        assert entry["answer"] == sample_result.answer
        assert entry["confidence"] == sample_result.confidence

    def test_multiple_tasks(self, sample_result, tmp_path):
        tasks = [
            EvaluationTask(task_id=f"t{i}", task=f"Task {i}", start_url="https://example.com")
            for i in range(3)
        ]
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        answers_path = runner.run_dataset(tasks)

        lines = answers_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        ids = [json.loads(line)["id"] for line in lines]
        assert ids == ["t0", "t1", "t2"]

    def test_calls_cleanup_after_each_task(self, sample_result, tmp_path):
        tasks = [
            EvaluationTask(task_id=f"t{i}", task=f"Task {i}", start_url="https://example.com")
            for i in range(2)
        ]
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        runner.run_dataset(tasks)

        assert adapter.cleanup.call_count == 2

    def test_empty_task_list(self, sample_result, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        runner = EvaluationRunner(adapter, config)

        answers_path = runner.run_dataset([])

        assert answers_path.exists()
        assert answers_path.read_text(encoding="utf-8") == ""


class TestErrorHandling:
    """Errors from the adapter are handled gracefully."""

    def test_run_task_catches_adapter_exception(self, sample_task, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = MagicMock(spec=EvalAgentAdapter)
        adapter.name = "mock"
        adapter.run_task.side_effect = RuntimeError("Browser crashed")
        runner = EvaluationRunner(adapter, config)

        result_dict = runner.run_task(sample_task)

        assert "Error" in result_dict["final_result_response"]
        assert result_dict["error"] == "Browser crashed"
        assert result_dict["confidence"] == 0.0

    def test_run_dataset_catches_run_task_exception(self, tmp_path):
        """If run_task itself raises (not the adapter), dataset still continues."""
        task = EvaluationTask(
            task_id="fail_task", task="Fail", start_url="https://example.com"
        )
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = MagicMock(spec=EvalAgentAdapter)
        adapter.name = "mock"
        # Adapter raises, which run_task catches internally
        adapter.run_task.side_effect = RuntimeError("Crash")
        runner = EvaluationRunner(adapter, config)

        answers_path = runner.run_dataset([task])

        lines = answers_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["id"] == "fail_task"
        assert entry["confidence"] == 0.0

    def test_cleanup_failure_does_not_stop_dataset(self, sample_result, tmp_path):
        tasks = [
            EvaluationTask(task_id=f"t{i}", task=f"Task {i}", start_url="https://example.com")
            for i in range(2)
        ]
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = _make_adapter(sample_result)
        adapter.cleanup.side_effect = RuntimeError("Cleanup failed")
        runner = EvaluationRunner(adapter, config)

        answers_path = runner.run_dataset(tasks)

        lines = answers_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2  # Both tasks completed despite cleanup failures

    def test_error_result_has_zero_steps(self, sample_task, tmp_path):
        config = EvaluationConfig(output_dir=tmp_path)
        adapter = MagicMock(spec=EvalAgentAdapter)
        adapter.name = "mock"
        adapter.run_task.side_effect = ValueError("Invalid input")
        runner = EvaluationRunner(adapter, config)

        result_dict = runner.run_task(sample_task)

        assert result_dict["num_steps"] == 0
        assert result_dict["num_screenshots"] == 0
