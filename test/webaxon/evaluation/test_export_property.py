"""Property-based tests for extended export_result().

**Validates: Requirements 6.3**

Properties tested:
- Property 5: Backward compatibility — no extended kwargs → only base keys
- Property 6: Extended fields included only when not None
- raw_model_generations.json written when non-empty
- result.json is always valid JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from webaxon.evaluation.export import export_result
from webaxon.evaluation.protocol import EvalResult
from webaxon.evaluation.tasks import EvaluationTask

# Import strategies from conftest via sys.path
_conftest_dir = Path(__file__).resolve().parent
if str(_conftest_dir) not in sys.path:
    sys.path.insert(0, str(_conftest_dir))

from conftest import eval_result_strategy, evaluation_task_strategy


# ── Constants ─────────────────────────────────────────────────────────────────

_BASE_KEYS = {
    "task_id",
    "task",
    "start_url",
    "action_history",
    "action_history_raw",
    "thoughts",
    "raw_generations",
    "final_result_response",
    "confidence",
    "duration_seconds",
    "num_steps",
    "num_screenshots",
}

# Keys that may appear conditionally from EvalResult itself (not extended)
_CONDITIONAL_BASE_KEYS = {"error", "metadata"}

_EXTENDED_FIELD_NAMES = [
    "clarified_plan",
    "done_criteria",
    "response_type",
    "response_format",
    "must_have",
    "must_avoid",
    "in_scope",
    "out_scope",
    "assumptions",
    "clarifier_dialogue",
    "clarifier_contract",
    "observer_summary",
    "observer_window_range",
    "reflection_history",
    "judge_history",
    "answer_draft",
    "answer_judge_history",
]


# ── Strategies for extended fields ────────────────────────────────────────────

_extended_str_value = st.text(min_size=1, max_size=50).filter(lambda s: s.strip())
_extended_list_value = st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=5)

_EXTENDED_FIELD_STRATEGIES = {
    "clarified_plan": _extended_str_value,
    "done_criteria": _extended_str_value,
    "response_type": _extended_str_value,
    "response_format": _extended_str_value,
    "must_have": _extended_list_value,
    "must_avoid": _extended_list_value,
    "in_scope": _extended_str_value,
    "out_scope": _extended_str_value,
    "assumptions": _extended_str_value,
    "clarifier_dialogue": _extended_list_value,
    "clarifier_contract": st.dictionaries(
        st.text(min_size=1, max_size=10), st.text(max_size=20), min_size=1, max_size=3,
    ),
    "observer_summary": _extended_str_value,
    "observer_window_range": st.lists(
        st.integers(min_value=0, max_value=100), min_size=2, max_size=2,
    ),
    "reflection_history": _extended_list_value,
    "judge_history": _extended_list_value,
    "answer_draft": _extended_str_value,
    "answer_judge_history": _extended_list_value,
}


@st.composite
def extended_kwargs_strategy(draw):
    """Generate a dict of extended kwargs where each field is randomly None or a value.

    Returns (kwargs_dict, expected_present_keys).
    """
    kwargs = {}
    present_keys = set()
    for name in _EXTENDED_FIELD_NAMES:
        include = draw(st.booleans())
        if include:
            kwargs[name] = draw(_EXTENDED_FIELD_STRATEGIES[name])
            present_keys.add(name)
        else:
            kwargs[name] = None
    return kwargs, present_keys



# ── Property 5: Backward compatibility ────────────────────────────────────────


class TestBackwardCompatibilityProperty:
    """Calling export_result() without extended kwargs produces only base keys.

    **Validates: Requirements 6.3** — Property 5
    """

    @given(
        task=evaluation_task_strategy(),
        result=eval_result_strategy(),
    )
    @settings(max_examples=100)
    def test_no_extended_kwargs_only_base_keys(self, task, result, tmp_path_factory):
        """Without extended kwargs, result dict has only base keys
        (plus conditional error/metadata from EvalResult)."""
        tmp_path = tmp_path_factory.mktemp("compat")
        rd = export_result(task, result, tmp_path)

        allowed_keys = _BASE_KEYS | _CONDITIONAL_BASE_KEYS
        assert set(rd.keys()) <= allowed_keys, (
            f"Unexpected keys: {set(rd.keys()) - allowed_keys}"
        )
        # All base keys must be present
        assert _BASE_KEYS <= set(rd.keys()), (
            f"Missing base keys: {_BASE_KEYS - set(rd.keys())}"
        )
        # No extended field key should be present
        for ext_key in _EXTENDED_FIELD_NAMES:
            assert ext_key not in rd, f"Extended key '{ext_key}' should not be present"


# ── Property 6: Extended fields included only when not None ───────────────────


class TestExtendedFieldsOnlyWhenNotNone:
    """For any combination of extended kwargs, only non-None ones appear.

    **Validates: Requirements 6.3** — Property 6
    """

    @given(
        task=evaluation_task_strategy(),
        result=eval_result_strategy(),
        ext=extended_kwargs_strategy(),
    )
    @settings(max_examples=100)
    def test_non_none_fields_present_none_fields_absent(
        self, task, result, ext, tmp_path_factory,
    ):
        """Non-None extended kwargs appear in result dict; None ones do not."""
        tmp_path = tmp_path_factory.mktemp("extended")
        kwargs, present_keys = ext
        rd = export_result(task, result, tmp_path, **kwargs)

        for name in _EXTENDED_FIELD_NAMES:
            if name in present_keys:
                assert name in rd, f"Expected '{name}' in result dict"
                assert rd[name] == kwargs[name]
            else:
                assert name not in rd, f"'{name}' should not be in result dict (was None)"


# ── raw_model_generations.json written when non-empty ─────────────────────────


class TestRawModelGenerationsWritten:
    """raw_model_generations.json is written separately when raw_generations is non-empty.

    **Validates: Requirements 6.3**
    """

    @given(
        task=evaluation_task_strategy(),
        result=eval_result_strategy(),
    )
    @settings(max_examples=100)
    def test_raw_generations_file_written_iff_non_empty(
        self, task, result, tmp_path_factory,
    ):
        """raw_model_generations.json exists iff result.raw_generations is non-empty."""
        tmp_path = tmp_path_factory.mktemp("rawgen")
        export_result(task, result, tmp_path)
        raw_gen_path = tmp_path / task.task_id / "raw_model_generations.json"

        if result.raw_generations:
            assert raw_gen_path.exists(), "raw_model_generations.json should exist"
            data = json.loads(raw_gen_path.read_text(encoding="utf-8"))
            assert data == result.raw_generations
        else:
            assert not raw_gen_path.exists(), "raw_model_generations.json should not exist"


# ── result.json is always valid JSON ──────────────────────────────────────────


class TestResultJsonAlwaysValid:
    """The written result.json is always valid JSON.

    **Validates: Requirements 6.3**
    """

    @given(
        task=evaluation_task_strategy(),
        result=eval_result_strategy(),
        ext=extended_kwargs_strategy(),
    )
    @settings(max_examples=100)
    def test_result_json_is_valid(self, task, result, ext, tmp_path_factory):
        """result.json can always be parsed as valid JSON."""
        tmp_path = tmp_path_factory.mktemp("validjson")
        kwargs, _ = ext
        export_result(task, result, tmp_path, **kwargs)
        result_path = tmp_path / task.task_id / "result.json"
        assert result_path.exists()
        # Must not raise
        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert data["task_id"] == task.task_id
