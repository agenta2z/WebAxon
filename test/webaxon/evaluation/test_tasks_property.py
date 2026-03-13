"""Property-based tests for task loading (load_tasks).

**Validates: Requirements 6.4**

Tests Property 7: Task loading round-trip with level/limit/offset filtering.
- Round-trip: write tasks to JSONL, load them back, verify all fields match
- Level filtering: only tasks with matching level are returned
- Limit filtering: at most `limit` tasks are returned
- Offset filtering: first `offset` tasks are skipped
- Combined filtering: level + limit + offset work together
- Empty file: loading from an empty file returns empty list
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from webaxon.evaluation.tasks import EvaluationTask, load_tasks

# Import strategies from conftest via sys.path
_conftest_dir = Path(__file__).resolve().parent
if str(_conftest_dir) not in sys.path:
    sys.path.insert(0, str(_conftest_dir))

from conftest import evaluation_task_strategy


# ── Helpers ───────────────────────────────────────────────────────────────────

_level_strategy = st.sampled_from(["easy", "medium", "hard"])


def _write_tasks_jsonl(tasks: list[EvaluationTask], path: Path) -> None:
    """Serialize a list of EvaluationTask to JSONL (matching load_tasks format)."""
    with open(path, "w", encoding="utf-8") as fh:
        for t in tasks:
            obj = {
                "task_id": t.task_id,
                "task": t.task,
                "website": t.start_url,
                "reference_length": t.reference_length,
                "level": t.level,
            }
            fh.write(json.dumps(obj) + "\n")


# ── Property 7: Task loading round-trip ───────────────────────────────────────


class TestTaskLoadingRoundTrip:
    """Write tasks to JSONL, load them back, verify all fields match."""

    @given(tasks=st.lists(evaluation_task_strategy(), min_size=1, max_size=15))
    @settings(max_examples=100)
    def test_round_trip_all_fields_match(self, tasks, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("tasks")
        jsonl_path = tmp_path / "tasks.jsonl"
        _write_tasks_jsonl(tasks, jsonl_path)

        loaded = load_tasks(jsonl_path)

        assert len(loaded) == len(tasks)
        for original, loaded_task in zip(tasks, loaded):
            assert loaded_task.task_id == original.task_id
            assert loaded_task.task == original.task
            assert loaded_task.start_url == original.start_url
            assert loaded_task.reference_length == original.reference_length
            assert loaded_task.level == original.level


class TestLevelFiltering:
    """When level is specified, only tasks with that level are returned."""

    @given(
        tasks=st.lists(evaluation_task_strategy(), min_size=1, max_size=20),
        level=_level_strategy,
    )
    @settings(max_examples=100)
    def test_level_filter_returns_only_matching(self, tasks, level, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("tasks")
        jsonl_path = tmp_path / "tasks.jsonl"
        _write_tasks_jsonl(tasks, jsonl_path)

        loaded = load_tasks(jsonl_path, level=level)

        expected = [t for t in tasks if t.level == level]
        assert len(loaded) == len(expected)
        for t in loaded:
            assert t.level == level


class TestLimitFiltering:
    """When limit is specified, at most limit tasks are returned."""

    @given(
        tasks=st.lists(evaluation_task_strategy(), min_size=1, max_size=20),
        limit=st.integers(min_value=0, max_value=25),
    )
    @settings(max_examples=100)
    def test_limit_caps_result_count(self, tasks, limit, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("tasks")
        jsonl_path = tmp_path / "tasks.jsonl"
        _write_tasks_jsonl(tasks, jsonl_path)

        loaded = load_tasks(jsonl_path, limit=limit)

        assert len(loaded) <= limit
        assert len(loaded) == min(limit, len(tasks))


class TestOffsetFiltering:
    """When offset is specified, the first offset tasks are skipped."""

    @given(
        tasks=st.lists(evaluation_task_strategy(), min_size=1, max_size=20),
        offset=st.integers(min_value=0, max_value=25),
    )
    @settings(max_examples=100)
    def test_offset_skips_first_n(self, tasks, offset, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("tasks")
        jsonl_path = tmp_path / "tasks.jsonl"
        _write_tasks_jsonl(tasks, jsonl_path)

        loaded = load_tasks(jsonl_path, offset=offset)

        expected = tasks[offset:]
        assert len(loaded) == len(expected)
        for original, loaded_task in zip(expected, loaded):
            assert loaded_task.task_id == original.task_id


class TestCombinedFiltering:
    """Level + limit + offset work together correctly."""

    @given(
        tasks=st.lists(evaluation_task_strategy(), min_size=1, max_size=20),
        level=_level_strategy,
        limit=st.integers(min_value=0, max_value=25),
        offset=st.integers(min_value=0, max_value=25),
    )
    @settings(max_examples=100)
    def test_combined_level_limit_offset(self, tasks, level, limit, offset, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("tasks")
        jsonl_path = tmp_path / "tasks.jsonl"
        _write_tasks_jsonl(tasks, jsonl_path)

        loaded = load_tasks(jsonl_path, level=level, limit=limit, offset=offset)

        # Manually compute expected result
        level_filtered = [t for t in tasks if t.level == level]
        offset_applied = level_filtered[offset:]
        expected = offset_applied[:limit]

        assert len(loaded) == len(expected)
        for orig, got in zip(expected, loaded):
            assert got.task_id == orig.task_id
            assert got.task == orig.task
            assert got.start_url == orig.start_url
            assert got.reference_length == orig.reference_length
            assert got.level == orig.level


class TestEmptyFile:
    """Loading from an empty file returns empty list."""

    def test_empty_file_returns_empty_list(self, tmp_path):
        jsonl_path = tmp_path / "tasks.jsonl"
        jsonl_path.write_text("", encoding="utf-8")

        loaded = load_tasks(jsonl_path)
        assert loaded == []

    def test_whitespace_only_file_returns_empty_list(self, tmp_path):
        jsonl_path = tmp_path / "tasks.jsonl"
        jsonl_path.write_text("  \n\n  \n", encoding="utf-8")

        loaded = load_tasks(jsonl_path)
        assert loaded == []
