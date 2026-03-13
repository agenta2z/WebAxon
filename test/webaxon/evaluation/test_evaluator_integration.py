"""Integration test for evaluator pipeline.

Validates: Requirements 6.7

Verifies the full evaluator pipeline works end-to-end:
- scoring.run_eval() → evaluator.run.parallel_eval() → auto_eval()
- Mock EvalLLMEngine with canned responses
- Synthetic sanitized run directories (result.json + trajectory screenshots)
- Threading via parallel_process_by_pool + ThreadPool (num_worker=2)
- Eval results JSONL written with expected scores
"""

import json
import os
from pathlib import Path
from typing import Dict, List

import pytest

from webaxon.evaluation.evaluator.utils import EvalLLMEngine
from webaxon.evaluation.scoring import run_eval


# ---------------------------------------------------------------------------
# Mock EvalLLMEngine
# ---------------------------------------------------------------------------

class MockEvalEngine:
    """A mock EvalLLMEngine that returns canned scores.

    Implements generate(messages) -> List[str] as required by the protocol.
    Returns "Status: Success" or "Status: Failure" based on configuration.
    """

    def __init__(self, default_response: str = "Thoughts: Looks good.\nStatus: Success"):
        self._default_response = default_response
        self.call_count = 0

    def generate(self, messages: List[Dict], **kwargs) -> List[str]:
        self.call_count += 1
        return [self._default_response]


# Verify MockEvalEngine satisfies the protocol at import time
assert isinstance(MockEvalEngine(), EvalLLMEngine)


# ---------------------------------------------------------------------------
# Helpers — synthetic run directories
# ---------------------------------------------------------------------------

def _create_fake_png(path: Path) -> None:
    """Write a minimal valid PNG file (1x1 white pixel)."""
    # Minimal PNG: 8-byte signature + IHDR + IDAT + IEND
    # Using a real tiny PNG so PIL can open it
    import struct
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB
    ihdr = _chunk(b"IHDR", ihdr_data)
    raw_data = b"\x00\xff\xff\xff"  # filter byte + RGB white pixel
    idat = _chunk(b"IDAT", zlib.compress(raw_data))
    iend = _chunk(b"IEND", b"")

    path.write_bytes(signature + ihdr + idat + iend)


def _create_synthetic_run(
    runs_dir: Path,
    task_id: str,
    task_description: str = "Find the price of item X",
    num_screenshots: int = 2,
    action_history: List[str] = None,
    final_result_response: str = "The price is $10",
) -> Path:
    """Create a synthetic run directory with result.json and trajectory screenshots."""
    task_dir = runs_dir / task_id
    traj_dir = task_dir / "trajectory"
    traj_dir.mkdir(parents=True, exist_ok=True)

    if action_history is None:
        action_history = [f"CLICK [target={i}]" for i in range(1, num_screenshots + 1)]

    result = {
        "task": task_description,
        "task_id": task_id,
        "action_history": action_history,
        "thoughts": ["thinking step 1", "thinking step 2"],
        "final_result_response": final_result_response,
    }
    (task_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")

    # Create fake screenshot PNGs
    for i in range(num_screenshots):
        _create_fake_png(traj_dir / f"{i}_screenshot.png")

    return task_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSingleWorkerPipeline:
    """Verify basic pipeline works with num_worker=1."""

    def test_run_eval_single_task_success(self, tmp_path):
        """Single task evaluated as success produces correct JSONL output."""
        runs_dir = tmp_path / "runs"
        _create_synthetic_run(runs_dir, "task_001")

        engine = MockEvalEngine("Thoughts: Task completed.\nStatus: Success")
        factory = lambda: engine

        run_eval(
            runs_dir=runs_dir,
            engine_factory=factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=1,
        )

        # Check that eval results JSONL was written
        eval_dir = tmp_path / "runs_eval"
        jsonl_path = eval_dir / "Autonomous_eval_score_threshold_3_auto_eval_results.json"
        assert jsonl_path.exists(), f"Expected JSONL at {jsonl_path}"

        lines = [l for l in jsonl_path.read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 1

        result = json.loads(lines[0])
        assert result["task_id"] == "task_001"
        assert result["predicted_label"] == 1  # Success
        assert "evaluation_details" in result
        assert result["evaluation_details"]["predicted_label"] == 1

    def test_run_eval_single_task_failure(self, tmp_path):
        """Single task evaluated as failure produces predicted_label=0."""
        runs_dir = tmp_path / "runs"
        _create_synthetic_run(runs_dir, "task_002")

        engine = MockEvalEngine("Thoughts: Task not done.\nStatus: Failure")
        factory = lambda: engine

        run_eval(
            runs_dir=runs_dir,
            engine_factory=factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=1,
        )

        eval_dir = tmp_path / "runs_eval"
        jsonl_path = eval_dir / "Autonomous_eval_score_threshold_3_auto_eval_results.json"
        lines = [l for l in jsonl_path.read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 1

        result = json.loads(lines[0])
        assert result["task_id"] == "task_002"
        assert result["predicted_label"] == 0  # Failure

    def test_run_eval_multiple_tasks(self, tmp_path):
        """Multiple tasks are all evaluated."""
        runs_dir = tmp_path / "runs"
        for i in range(3):
            _create_synthetic_run(runs_dir, f"task_{i:03d}", task_description=f"Task {i}")

        factory = lambda: MockEvalEngine("Thoughts: OK.\nStatus: Success")

        run_eval(
            runs_dir=runs_dir,
            engine_factory=factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=1,
        )

        eval_dir = tmp_path / "runs_eval"
        jsonl_path = eval_dir / "Autonomous_eval_score_threshold_3_auto_eval_results.json"
        lines = [l for l in jsonl_path.read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 3

        task_ids = {json.loads(l)["task_id"] for l in lines}
        assert task_ids == {"task_000", "task_001", "task_002"}


class TestMultiWorkerPipeline:
    """Verify threading via parallel_process_by_pool + ThreadPool works."""

    def test_run_eval_with_two_workers(self, tmp_path):
        """Multiple tasks evaluated with num_worker=2 using ThreadPool."""
        runs_dir = tmp_path / "runs"
        for i in range(4):
            _create_synthetic_run(runs_dir, f"task_{i:03d}", task_description=f"Task {i}")

        call_counts = []

        def counting_factory():
            eng = MockEvalEngine("Thoughts: Done.\nStatus: Success")
            call_counts.append(eng)
            return eng

        run_eval(
            runs_dir=runs_dir,
            engine_factory=counting_factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=2,
        )

        # Verify results were written for all tasks
        eval_dir = tmp_path / "runs_eval"
        jsonl_path = eval_dir / "Autonomous_eval_score_threshold_3_auto_eval_results.json"
        lines = [l for l in jsonl_path.read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 4

        task_ids = {json.loads(l)["task_id"] for l in lines}
        assert task_ids == {"task_000", "task_001", "task_002", "task_003"}

        # Verify all results are success
        for line in lines:
            assert json.loads(line)["predicted_label"] == 1

    def test_threading_creates_separate_engines(self, tmp_path):
        """Each worker thread creates its own engine via the factory."""
        runs_dir = tmp_path / "runs"
        for i in range(4):
            _create_synthetic_run(runs_dir, f"task_{i:03d}", task_description=f"Task {i}")

        engines_created = []

        def tracking_factory():
            eng = MockEvalEngine("Thoughts: OK.\nStatus: Success")
            engines_created.append(eng)
            return eng

        run_eval(
            runs_dir=runs_dir,
            engine_factory=tracking_factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=2,
        )

        # With 2 workers, the factory should be called at least 2 times
        # (one per worker thread)
        assert len(engines_created) >= 2

        # All tasks should still be evaluated
        eval_dir = tmp_path / "runs_eval"
        jsonl_path = eval_dir / "Autonomous_eval_score_threshold_3_auto_eval_results.json"
        lines = [l for l in jsonl_path.read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 4


class TestEvalResultsJSONL:
    """Verify eval results JSONL is written with expected scores."""

    def test_jsonl_contains_required_fields(self, tmp_path):
        """Each JSONL line has task_id, predicted_label, evaluation_details."""
        runs_dir = tmp_path / "runs"
        _create_synthetic_run(runs_dir, "task_001")

        factory = lambda: MockEvalEngine("Thoughts: Good.\nStatus: Success")

        run_eval(
            runs_dir=runs_dir,
            engine_factory=factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=1,
        )

        eval_dir = tmp_path / "runs_eval"
        jsonl_path = eval_dir / "Autonomous_eval_score_threshold_3_auto_eval_results.json"
        result = json.loads(jsonl_path.read_text().strip())

        # Required fields
        assert "task_id" in result
        assert "predicted_label" in result
        assert "evaluation_details" in result
        assert "input_text" in result
        assert "system_msg" in result
        assert "task" in result

    def test_jsonl_preserves_original_result_fields(self, tmp_path):
        """Original result.json fields are preserved in eval output."""
        runs_dir = tmp_path / "runs"
        _create_synthetic_run(
            runs_dir,
            "task_001",
            task_description="Buy a laptop",
            action_history=["CLICK [target=1]", "INPUT [target=2] 'laptop'"],
            final_result_response="Found laptop for $999",
        )

        factory = lambda: MockEvalEngine("Thoughts: Correct.\nStatus: Success")

        run_eval(
            runs_dir=runs_dir,
            engine_factory=factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=1,
        )

        eval_dir = tmp_path / "runs_eval"
        jsonl_path = eval_dir / "Autonomous_eval_score_threshold_3_auto_eval_results.json"
        result = json.loads(jsonl_path.read_text().strip())

        assert result["task"] == "Buy a laptop"
        assert result["final_result_response"] == "Found laptop for $999"

    def test_custom_output_path(self, tmp_path):
        """run_eval respects custom output_path."""
        runs_dir = tmp_path / "runs"
        _create_synthetic_run(runs_dir, "task_001")

        custom_output = tmp_path / "my_eval_output"
        factory = lambda: MockEvalEngine("Thoughts: OK.\nStatus: Success")

        run_eval(
            runs_dir=runs_dir,
            engine_factory=factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=1,
            output_path=custom_output,
        )

        jsonl_path = custom_output / "Autonomous_eval_score_threshold_3_auto_eval_results.json"
        assert jsonl_path.exists()


class TestSanitizationIntegration:
    """Verify that run_eval sanitizes runs before evaluation."""

    def test_infra_failures_excluded_from_eval(self, tmp_path):
        """Tasks with infra failures are sanitized out before evaluation."""
        runs_dir = tmp_path / "runs"

        # Good task
        _create_synthetic_run(runs_dir, "task_good", task_description="Good task")

        # Bad task with infra failure
        _create_synthetic_run(
            runs_dir,
            "task_bad",
            task_description="Bad task",
            final_result_response="net::ERR_CONNECTION_RESET happened",
        )

        factory = lambda: MockEvalEngine("Thoughts: OK.\nStatus: Success")

        run_eval(
            runs_dir=runs_dir,
            engine_factory=factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=1,
        )

        # Only the good task should be evaluated
        eval_dir = tmp_path / "runs_eval"
        jsonl_path = eval_dir / "Autonomous_eval_score_threshold_3_auto_eval_results.json"
        lines = [l for l in jsonl_path.read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 1
        assert json.loads(lines[0])["task_id"] == "task_good"

    def test_sanitized_dir_created(self, tmp_path):
        """run_eval creates a sanitized directory."""
        runs_dir = tmp_path / "runs"
        _create_synthetic_run(runs_dir, "task_001")

        factory = lambda: MockEvalEngine("Thoughts: OK.\nStatus: Success")

        run_eval(
            runs_dir=runs_dir,
            engine_factory=factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=1,
        )

        sanitized_dir = tmp_path / "runs_sanitized"
        assert sanitized_dir.exists()
        assert (sanitized_dir / "task_001" / "result.json").exists()


class TestEdgeCases:
    """Edge cases for the evaluator pipeline."""

    def test_no_valid_tasks_after_sanitization(self, tmp_path):
        """If all tasks are infra failures, evaluation completes with no output."""
        runs_dir = tmp_path / "runs"
        _create_synthetic_run(
            runs_dir,
            "task_bad",
            final_result_response="AIGatewayRequestError: timeout",
        )

        factory = lambda: MockEvalEngine("Thoughts: OK.\nStatus: Success")

        # Should not raise — just no tasks to evaluate
        run_eval(
            runs_dir=runs_dir,
            engine_factory=factory,
            mode="Autonomous_eval",
            score_threshold=3,
            num_worker=1,
        )

    def test_missing_runs_dir_raises(self, tmp_path):
        """run_eval raises FileNotFoundError for missing runs_dir."""
        factory = lambda: MockEvalEngine()

        with pytest.raises(FileNotFoundError):
            run_eval(
                runs_dir=tmp_path / "nonexistent",
                engine_factory=factory,
                mode="Autonomous_eval",
            )

    def test_none_engine_factory_raises(self, tmp_path):
        """run_eval raises ValueError when engine_factory is None."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        with pytest.raises(ValueError, match="engine_factory is required"):
            run_eval(
                runs_dir=runs_dir,
                engine_factory=None,
                mode="Autonomous_eval",
            )
