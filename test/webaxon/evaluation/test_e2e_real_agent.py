"""End-to-end integration test: real WebAxon agent + real evaluator.

Runs a single easy task from the Online-Mind2Web dataset through the full
pipeline:

1. Load one real task from the dataset
2. Run the WebAxon agent (real browser, real LLM)
3. Verify the agent produced valid output (result.json + trajectory/)
4. Run the evaluator on the output (real LLM scoring)
5. Verify the evaluation produced a score

Prerequisites:
- Chrome browser installed
- LLM API key set (OPENAI_API_KEY or ANTHROPIC_API_KEY)
- WebAxon workspace directory exists
- Network access to target website

Usage::

    # Run with OpenAI (default)
    pytest test_e2e_real_agent.py -m e2e --run-e2e -v

    # Run with Claude
    pytest test_e2e_real_agent.py -m e2e --run-e2e -v --eval-inferencer claude --eval-model claude-sonnet-4-5-20250929

    # Override workspace
    pytest test_e2e_real_agent.py -m e2e --run-e2e -v --webaxon-workspace /path/to/workspace
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Easy task with short reference_length — good for smoke testing
_E2E_TASK = {
    "task_id": "ade4c09ad3fdb1607209750924cd232f",
    "task": "Compare available plans for the AeroAPI on Flightaware.",
    "start_url": "https://www.flightaware.com/",
    "reference_length": 4,
    "level": "easy",
}

_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "online_mind2web"
    / "processed"
    / "tasks.jsonl"
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def workspace_path(request) -> Path:
    """Resolve the WebAxon workspace directory."""
    custom = request.config.getoption("--webaxon-workspace")
    if custom:
        p = Path(custom)
    else:
        # Default: relative to WebAxon package
        p = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "webaxon"
            / "devsuite"
            / "web_agent_service_nextgen"
            / "_workspace"
        )
    if not p.is_dir():
        pytest.skip(f"Workspace not found: {p}")
    return p


@pytest.fixture(scope="module")
def e2e_output_dir(tmp_path_factory) -> Path:
    """Shared output directory for the entire e2e test module."""
    return tmp_path_factory.mktemp("e2e_runs")


@pytest.fixture(scope="module")
def eval_inferencer(request) -> str:
    return request.config.getoption("--eval-inferencer")


@pytest.fixture(scope="module")
def eval_model(request) -> Optional[str]:
    return request.config.getoption("--eval-model")


@pytest.fixture(scope="module")
def agent_type(request) -> str:
    return request.config.getoption("--agent-type")


@pytest.fixture(scope="module")
def headless(request) -> bool:
    return request.config.getoption("--headless")


@pytest.fixture(scope="module")
def e2e_task():
    """Load the e2e task — try from dataset first, fall back to hardcoded."""
    from webaxon.evaluation.tasks import EvaluationTask

    # Try to load from the real dataset to ensure consistency
    if _DATASET_PATH.exists():
        from webaxon.evaluation.tasks import load_tasks

        tasks = load_tasks(_DATASET_PATH)
        for t in tasks:
            if t.task_id == _E2E_TASK["task_id"]:
                return t

    # Fall back to hardcoded
    return EvaluationTask(**_E2E_TASK)


@pytest.fixture(scope="module")
def agent_run_result(
    workspace_path, e2e_output_dir, e2e_task, agent_type, headless
):
    """Run the real agent on the e2e task. Shared across tests in this module.

    This fixture is expensive (minutes), so it's module-scoped — the agent
    runs once and all tests in this module validate different aspects of the output.
    """
    from webaxon.evaluation.adapters.webaxon_adapter import WebAxonAdapter
    from webaxon.evaluation.config import EvaluationConfig
    from webaxon.evaluation.runner import EvaluationRunner

    adapter = WebAxonAdapter(
        testcase_root=workspace_path,
        agent_type=agent_type,
        headless=headless,
        agent_timeout=300,
    )

    config = EvaluationConfig(
        adapter_name="webaxon",
        max_steps=30,
        agent_timeout=300,
        output_dir=e2e_output_dir,
    )

    runner = EvaluationRunner(adapter=adapter, config=config)

    try:
        result_dict = runner.run_task(e2e_task)
    finally:
        adapter.cleanup()

    return result_dict


# ---------------------------------------------------------------------------
# Tests — Agent Run
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.timeout(600)
class TestAgentRun:
    """Validate the real agent produces expected outputs."""

    def test_result_json_created(self, agent_run_result, e2e_output_dir, e2e_task):
        """Agent run creates result.json with required fields."""
        result_path = e2e_output_dir / e2e_task.task_id / "result.json"
        assert result_path.exists(), f"result.json not found at {result_path}"

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["task_id"] == e2e_task.task_id
        assert data["task"] == e2e_task.task
        assert "action_history" in data
        assert "final_result_response" in data
        assert "duration_seconds" in data

    def test_trajectory_screenshots_captured(self, agent_run_result, e2e_output_dir, e2e_task):
        """Agent captures at least one trajectory screenshot."""
        # Screenshots may be in session_dir/screenshots/ (save_screenshots_to_session=True)
        # or in trajectory_dir (legacy).  Check metadata.screenshot_dir first.
        screenshot_dir = (agent_run_result.get("metadata") or {}).get("screenshot_dir", "")
        if screenshot_dir and Path(screenshot_dir).is_dir():
            screenshot_path = Path(screenshot_dir)
        else:
            screenshot_path = e2e_output_dir / e2e_task.task_id / "trajectory"

        assert screenshot_path.exists(), f"Screenshot dir not found at {screenshot_path}"

        screenshots = list(screenshot_path.glob("*_screenshot.png"))
        assert len(screenshots) >= 1, "Expected at least one screenshot"

    def test_result_has_answer(self, agent_run_result):
        """Agent produces a non-empty final_result_response."""
        answer = agent_run_result.get("final_result_response", "")
        assert answer, "Expected non-empty final_result_response"

    def test_no_crash_error(self, agent_run_result):
        """Agent run completed without a crash error."""
        error = agent_run_result.get("error")
        assert error is None, f"Agent run crashed with error: {error}"

    def test_result_has_positive_duration(self, agent_run_result):
        """Agent run has positive duration."""
        duration = agent_run_result.get("duration_seconds", 0)
        assert duration > 0, "Expected positive duration"

    def test_result_dict_matches_file(self, agent_run_result, e2e_output_dir, e2e_task):
        """The returned dict matches what's written to result.json."""
        result_path = e2e_output_dir / e2e_task.task_id / "result.json"
        file_data = json.loads(result_path.read_text(encoding="utf-8"))
        assert file_data["task_id"] == agent_run_result["task_id"]
        assert file_data["final_result_response"] == agent_run_result["final_result_response"]


# ---------------------------------------------------------------------------
# Tests — Evaluator
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.timeout(300)
class TestEvaluator:
    """Run the real evaluator on the agent's output and validate results."""

    def test_run_eval_produces_results(
        self,
        agent_run_result,
        e2e_output_dir,
        eval_inferencer,
        eval_model,
    ):
        """Evaluator produces a score for the agent run."""
        from webaxon.evaluation.evaluator.utils import InferencerEngine
        from webaxon.evaluation.scoring import run_eval

        # Determine model and build engine_factory
        if eval_inferencer == "claude":
            if not os.environ.get("ANTHROPIC_API_KEY"):
                pytest.skip("ANTHROPIC_API_KEY not set")
            from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer

            model_id = eval_model or "claude-sonnet-4-5-20250929"
            engine_factory = lambda: InferencerEngine(
                ClaudeApiInferencer(model_id=model_id)
            )
        else:
            if not os.environ.get("OPENAI_API_KEY"):
                pytest.skip("OPENAI_API_KEY not set")
            from agent_foundation.common.inferencers.api_inferencers.openai_api_inferencer import OpenaiApiInferencer

            model_id = eval_model or "gpt-4o"
            engine_factory = lambda: InferencerEngine(
                OpenaiApiInferencer(model_id=model_id)
            )

        eval_output = e2e_output_dir / "eval_results"

        run_eval(
            runs_dir=e2e_output_dir,
            engine_factory=engine_factory,
            mode="WebJudge_Online_Mind2Web_eval",
            score_threshold=3,
            num_worker=1,
            output_path=eval_output,
        )

        # Find the eval results JSONL
        jsonl_files = list(eval_output.glob("*auto_eval_results.json"))
        assert jsonl_files, f"No eval results found in {eval_output}"

        jsonl_path = jsonl_files[0]
        lines = [l for l in jsonl_path.read_text().strip().split("\n") if l.strip()]
        assert len(lines) >= 1, "Expected at least one eval result"

        result = json.loads(lines[0])
        assert "predicted_label" in result, "Eval result missing predicted_label"
        assert result["predicted_label"] in (0, 1), (
            f"predicted_label should be 0 or 1, got {result['predicted_label']}"
        )
        assert "evaluation_details" in result, "Eval result missing evaluation_details"

        logger.info(
            "E2E eval result: task=%s, predicted_label=%d",
            result.get("task_id", "?"),
            result["predicted_label"],
        )
