"""Property-based tests for scoring module: sanitization and infra failure detection.

**Validates: Requirements 6.2**

Properties tested:
- Property 3: Sanitization preserves non-failed runs exactly
- Property 4: Infrastructure failure detection is pattern-based
- Sanitization excludes failed runs
- write_retry_tasks produces correct subset
- Sanitization copies snapshot_text.txt files
- Sanitization excludes _post_ screenshots
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Stub out heavy optional dependencies before importing scoring module.
# The evaluator sub-package transitively imports PIL and bs4 which may not
# be installed in the test environment.
for _mod_name in ("PIL", "PIL.Image", "bs4", "BeautifulSoup", "beautifulsoup4"):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from webaxon.evaluation.scoring import (
    _is_infra_failure,
    _SKIP_PATTERNS,
    sanitize_runs,
    write_retry_tasks,
)


# ── Strategies ────────────────────────────────────────────────────────────────

# Safe text that does NOT contain any skip pattern substring
def _safe_text() -> st.SearchStrategy[str]:
    """Generate text guaranteed not to match any _SKIP_PATTERNS entry."""
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Z"),
            blacklist_characters="\x00",
        ),
        min_size=0,
        max_size=80,
    ).filter(lambda s: not any(pat in s for pat in _SKIP_PATTERNS))


# Windows reserved device names that cannot be used as directory names
_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})

# Task ID strategy — simple alphanumeric identifiers (excluding Windows reserved names)
_task_id = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
).filter(lambda s: s.upper() not in _WINDOWS_RESERVED)

# Strategy for a skip pattern
_skip_pattern = st.sampled_from(_SKIP_PATTERNS)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_run_dir(
    base: Path,
    task_id: str,
    final_result_response: str = "Task completed",
    thoughts: list | None = None,
    screenshots: list[str] | None = None,
    snapshot_texts: list[str] | None = None,
) -> Path:
    """Create a synthetic run directory with result.json and trajectory files."""
    task_dir = base / task_id
    traj_dir = task_dir / "trajectory"
    traj_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "final_result_response": final_result_response,
        "thoughts": thoughts or [],
    }
    (task_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")

    # Create screenshot files
    for name in (screenshots or ["0_screenshot.png"]):
        (traj_dir / name).write_bytes(b"\x89PNG_fake")

    # Create snapshot text files
    for name in (snapshot_texts or []):
        (traj_dir / name).write_text("DOM content", encoding="utf-8")

    return task_dir


def _create_tasks_jsonl(path: Path, task_ids: list[str]) -> None:
    """Write a tasks.jsonl file with entries for the given task IDs."""
    with path.open("w", encoding="utf-8") as f:
        for tid in task_ids:
            row = {
                "task_id": tid,
                "confirmed_task": f"Do something for {tid}",
                "website": "https://example.com",
                "reference_length": 5,
                "level": "easy",
            }
            f.write(json.dumps(row) + "\n")


# ── Property 3: Sanitization preserves non-failed runs exactly ────────────────


class TestSanitizationPreservesNonFailedRuns:
    """Property 3: For any set of runs where none match skip patterns,
    all runs are copied to the sanitized directory."""

    @given(
        task_ids=st.lists(
            _task_id,
            min_size=1,
            max_size=5,
            unique=True,
        ),
        safe_responses=st.lists(
            _safe_text(),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_all_non_failed_runs_are_preserved(
        self, task_ids: list[str], safe_responses: list[str], tmp_path_factory
    ):
        tmp_path = tmp_path_factory.mktemp("sanitize")
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        sanitized_dir = tmp_path / "sanitized"

        # Pad responses to match task_ids length
        responses = [safe_responses[i % len(safe_responses)] for i in range(len(task_ids))]

        for tid, resp in zip(task_ids, responses):
            _create_run_dir(runs_dir, tid, final_result_response=resp)

        skipped = sanitize_runs(runs_dir, sanitized_dir, overwrite=True)

        # No runs should be skipped
        assert skipped == [], f"Expected no skips but got: {skipped}"

        # All task dirs should be present in sanitized output
        sanitized_tasks = {d.name for d in sanitized_dir.iterdir() if d.is_dir()}
        assert sanitized_tasks == set(task_ids)

        # Each sanitized run should have result.json
        for tid in task_ids:
            assert (sanitized_dir / tid / "result.json").exists()

    @given(task_id=_task_id, safe_text=_safe_text())
    @settings(max_examples=100)
    def test_result_json_content_preserved(
        self, task_id: str, safe_text: str, tmp_path_factory
    ):
        tmp_path = tmp_path_factory.mktemp("preserve")
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        sanitized_dir = tmp_path / "sanitized"

        _create_run_dir(runs_dir, task_id, final_result_response=safe_text)
        sanitize_runs(runs_dir, sanitized_dir, overwrite=True)

        original = json.loads((runs_dir / task_id / "result.json").read_text())
        copied = json.loads((sanitized_dir / task_id / "result.json").read_text())
        assert original == copied


# ── Property 4: Infrastructure failure detection is pattern-based ─────────────


class TestInfraFailureDetectionPatternBased:
    """Property 4: For any result.json containing a _SKIP_PATTERNS substring
    in final_result_response or last thought, _is_infra_failure() returns True."""

    @given(
        pattern=_skip_pattern,
        prefix=_safe_text(),
        suffix=_safe_text(),
    )
    @settings(max_examples=100)
    def test_pattern_in_final_result_detected(
        self, pattern: str, prefix: str, suffix: str, tmp_path_factory
    ):
        tmp_path = tmp_path_factory.mktemp("infra")
        result_path = tmp_path / "result.json"
        data = {
            "final_result_response": f"{prefix}{pattern}{suffix}",
            "thoughts": [],
        }
        result_path.write_text(json.dumps(data), encoding="utf-8")

        assert _is_infra_failure(result_path) is True

    @given(
        pattern=_skip_pattern,
        prefix=_safe_text(),
        suffix=_safe_text(),
    )
    @settings(max_examples=100)
    def test_pattern_in_last_thought_detected(
        self, pattern: str, prefix: str, suffix: str, tmp_path_factory
    ):
        tmp_path = tmp_path_factory.mktemp("infra_thought")
        result_path = tmp_path / "result.json"
        data = {
            "final_result_response": "All good",
            "thoughts": ["first thought", f"{prefix}{pattern}{suffix}"],
        }
        result_path.write_text(json.dumps(data), encoding="utf-8")

        assert _is_infra_failure(result_path) is True

    @given(safe_final=_safe_text(), safe_thought=_safe_text())
    @settings(max_examples=100)
    def test_no_pattern_means_no_failure(
        self, safe_final: str, safe_thought: str, tmp_path_factory
    ):
        tmp_path = tmp_path_factory.mktemp("no_infra")
        result_path = tmp_path / "result.json"
        data = {
            "final_result_response": safe_final,
            "thoughts": [safe_thought],
        }
        result_path.write_text(json.dumps(data), encoding="utf-8")

        assert _is_infra_failure(result_path) is False


# ── Sanitization excludes failed runs ─────────────────────────────────────────


class TestSanitizationExcludesFailedRuns:
    """For runs that DO match skip patterns, they are excluded from sanitized dir."""

    @given(
        good_ids=st.lists(_task_id, min_size=1, max_size=3, unique=True),
        bad_ids=st.lists(_task_id, min_size=1, max_size=3, unique=True),
        pattern=_skip_pattern,
    )
    @settings(max_examples=100)
    def test_failed_runs_excluded_good_runs_kept(
        self,
        good_ids: list[str],
        bad_ids: list[str],
        pattern: str,
        tmp_path_factory,
    ):
        # Ensure no overlap between good and bad IDs
        assume(not set(good_ids) & set(bad_ids))

        tmp_path = tmp_path_factory.mktemp("exclude")
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        sanitized_dir = tmp_path / "sanitized"

        for tid in good_ids:
            _create_run_dir(runs_dir, tid, final_result_response="Task completed OK")

        for tid in bad_ids:
            _create_run_dir(runs_dir, tid, final_result_response=f"Error: {pattern}")

        skipped = sanitize_runs(runs_dir, sanitized_dir, overwrite=True)

        assert set(skipped) == set(bad_ids)

        sanitized_tasks = {d.name for d in sanitized_dir.iterdir() if d.is_dir()}
        assert sanitized_tasks == set(good_ids)


# ── write_retry_tasks produces correct subset ─────────────────────────────────


class TestWriteRetryTasksCorrectSubset:
    """The output JSONL contains exactly the tasks whose IDs are in the excluded list."""

    @given(
        all_ids=st.lists(_task_id, min_size=2, max_size=8, unique=True),
        data=st.data(),
    )
    @settings(max_examples=100)
    def test_retry_tasks_match_excluded_ids(
        self, all_ids: list[str], data, tmp_path_factory
    ):
        # Pick a random subset to exclude
        excluded_ids = data.draw(
            st.lists(
                st.sampled_from(all_ids),
                min_size=1,
                max_size=len(all_ids),
                unique=True,
            )
        )

        tmp_path = tmp_path_factory.mktemp("retry")
        tasks_jsonl = tmp_path / "tasks.jsonl"
        output_path = tmp_path / "retry.jsonl"

        _create_tasks_jsonl(tasks_jsonl, all_ids)

        written = write_retry_tasks(excluded_ids, tasks_jsonl, output_path)

        assert written == len(excluded_ids)

        # Verify the output contains exactly the excluded IDs
        written_ids = []
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    written_ids.append(row["task_id"])

        assert set(written_ids) == set(excluded_ids)

    @given(all_ids=st.lists(_task_id, min_size=1, max_size=5, unique=True))
    @settings(max_examples=100)
    def test_empty_excluded_writes_nothing(
        self, all_ids: list[str], tmp_path_factory
    ):
        tmp_path = tmp_path_factory.mktemp("retry_empty")
        tasks_jsonl = tmp_path / "tasks.jsonl"
        output_path = tmp_path / "retry.jsonl"

        _create_tasks_jsonl(tasks_jsonl, all_ids)

        written = write_retry_tasks([], tasks_jsonl, output_path)

        assert written == 0


# ── Sanitization copies snapshot_text.txt files ──────────────────────────────


class TestSanitizationCopiesSnapshotText:
    """Valid runs with *_snapshot_text.txt files have them copied."""

    @given(
        task_id=_task_id,
        num_snapshots=st.integers(min_value=1, max_value=4),
    )
    @settings(max_examples=100)
    def test_snapshot_text_files_copied(
        self, task_id: str, num_snapshots: int, tmp_path_factory
    ):
        tmp_path = tmp_path_factory.mktemp("snapshot")
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        sanitized_dir = tmp_path / "sanitized"

        snapshot_names = [f"{i}_snapshot_text.txt" for i in range(num_snapshots)]
        _create_run_dir(
            runs_dir,
            task_id,
            final_result_response="Task completed",
            snapshot_texts=snapshot_names,
        )

        sanitize_runs(runs_dir, sanitized_dir, overwrite=True)

        dest_traj = sanitized_dir / task_id / "trajectory"
        for name in snapshot_names:
            assert (dest_traj / name).exists(), f"Missing snapshot: {name}"
            assert (dest_traj / name).read_text() == "DOM content"


# ── Sanitization excludes _post_ screenshots ─────────────────────────────────


class TestSanitizationExcludesPostScreenshots:
    """Post-action screenshots (_post_ in name) are not copied."""

    @given(
        task_id=_task_id,
        num_steps=st.integers(min_value=1, max_value=4),
    )
    @settings(max_examples=100)
    def test_post_screenshots_excluded(
        self, task_id: str, num_steps: int, tmp_path_factory
    ):
        tmp_path = tmp_path_factory.mktemp("post")
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        sanitized_dir = tmp_path / "sanitized"

        # Create both regular and _post_ screenshots
        screenshots = []
        for i in range(num_steps):
            screenshots.append(f"{i}_screenshot.png")
            screenshots.append(f"{i}_post_screenshot.png")

        _create_run_dir(
            runs_dir,
            task_id,
            final_result_response="Task completed",
            screenshots=screenshots,
        )

        sanitize_runs(runs_dir, sanitized_dir, overwrite=True)

        dest_traj = sanitized_dir / task_id / "trajectory"

        # Regular screenshots should be present
        for i in range(num_steps):
            assert (dest_traj / f"{i}_screenshot.png").exists()

        # Post screenshots should NOT be present
        for i in range(num_steps):
            assert not (dest_traj / f"{i}_post_screenshot.png").exists()
