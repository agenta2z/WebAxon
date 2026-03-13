"""Property-based tests for trajectory capture module.

**Validates: Requirements 6.5**

Properties tested:
- format_action_readable() produces valid (non-empty) strings for any valid action dict
- _collect_screenshots() returns paths sorted by step number
"""

from __future__ import annotations

import sys
from pathlib import Path

# Path resolution for imports
_current_file = Path(__file__).resolve()
_current_path = _current_file.parent
while _current_path.name != "test" and _current_path.parent != _current_path:
    _current_path = _current_path.parent
_src_dir = _current_path.parent / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from webaxon.evaluation.adapters.trajectory_capture import (
    format_action_readable,
    _collect_screenshots,
    _extract_step_number,
)


# ── Strategies ────────────────────────────────────────────────────────────────

_KNOWN_ACTION_TYPES = [
    "visit_url",
    "click",
    "input_text",
    "input_and_submit",
    "append_text",
    "scroll",
    "scroll_up_to_element",
    "wait",
    "no_op",
    "search",
]

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    max_size=80,
)


@st.composite
def action_entry_strategy(draw):
    """Generate a valid action dict with a known or unknown action type."""
    use_known = draw(st.booleans())
    if use_known:
        action_type = draw(st.sampled_from(_KNOWN_ACTION_TYPES))
    else:
        action_type = draw(st.text(min_size=1, max_size=30).filter(lambda s: s.strip()))

    target = draw(_safe_text)
    entry = {"type": action_type, "target": target}

    # Optionally add args dict for actions that use it
    if draw(st.booleans()):
        args = {}
        if action_type in ("visit_url",):
            args["url"] = draw(st.text(min_size=1, max_size=60))
        if action_type in ("input_text", "input_and_submit", "append_text"):
            args["text"] = draw(st.text(max_size=100))
        if action_type == "scroll":
            args["direction"] = draw(st.sampled_from(["up", "down", "left", "right"]))
        entry["args"] = args

    return entry


@st.composite
def step_numbers_strategy(draw):
    """Generate a sorted list of unique non-negative step numbers."""
    nums = draw(
        st.lists(
            st.integers(min_value=0, max_value=50),
            min_size=0,
            max_size=15,
            unique=True,
        )
    )
    return sorted(nums)


# ── Property: format_action_readable() produces valid strings ─────────────────


class TestFormatActionReadableProperty:
    """format_action_readable() always returns a non-empty string.

    **Validates: Requirements 6.5**
    """

    @given(action_entry=action_entry_strategy())
    @settings(max_examples=100)
    def test_produces_non_empty_string(self, action_entry):
        """For any valid action dict, the output is a non-empty string."""
        result = format_action_readable(action_entry)
        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert len(result) > 0, "format_action_readable() returned empty string"

    @given(action_entry=action_entry_strategy())
    @settings(max_examples=100)
    def test_known_types_produce_expected_prefix(self, action_entry):
        """Known action types produce output starting with the expected prefix."""
        result = format_action_readable(action_entry)
        action_type = action_entry.get("type", "unknown")

        prefix_map = {
            "visit_url": "NAVIGATE",
            "click": "CLICK",
            "input_text": "INPUT",
            "input_and_submit": "INPUT_SUBMIT",
            "append_text": "APPEND",
            "scroll": "SCROLL",
            "scroll_up_to_element": "SCROLL_TO",
            "wait": "WAIT",
            "no_op": "NO_OP",
            "search": "SEARCH",
        }

        if action_type in prefix_map:
            expected_prefix = prefix_map[action_type]
            assert result.startswith(expected_prefix), (
                f"Expected '{expected_prefix}' prefix for type '{action_type}', got: {result!r}"
            )


# ── Property: _collect_screenshots() returns sorted paths ─────────────────────


class TestCollectScreenshotsSortedProperty:
    """_collect_screenshots() returns paths sorted by step number.

    **Validates: Requirements 6.5**
    """

    @given(step_numbers=step_numbers_strategy())
    @settings(max_examples=100)
    def test_returns_sorted_by_step_number(self, step_numbers, tmp_path_factory):
        """For any set of screenshot files, returned paths are sorted by step number."""
        traj_dir = tmp_path_factory.mktemp("traj")

        # Create screenshot files in arbitrary order
        for step in reversed(step_numbers):
            png_path = traj_dir / f"{step}_screenshot.png"
            png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

        result = _collect_screenshots(traj_dir)

        # Verify sorted order
        extracted = [_extract_step_number(p.name) for p in result]
        assert extracted == sorted(extracted), (
            f"Screenshots not sorted: {extracted}"
        )

    @given(step_numbers=step_numbers_strategy())
    @settings(max_examples=100)
    def test_all_input_files_present_in_output(self, step_numbers, tmp_path_factory):
        """All created screenshot files appear in the output."""
        traj_dir = tmp_path_factory.mktemp("traj2")

        for step in step_numbers:
            png_path = traj_dir / f"{step}_screenshot.png"
            png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

        result = _collect_screenshots(traj_dir)
        result_steps = {_extract_step_number(p.name) for p in result}

        for step in step_numbers:
            assert step in result_steps, f"Step {step} missing from output"

    def test_empty_directory_returns_empty(self, tmp_path):
        """An empty directory returns an empty list."""
        result = _collect_screenshots(tmp_path)
        assert result == []

    def test_nonexistent_directory_returns_empty(self, tmp_path):
        """A non-existent directory returns an empty list."""
        result = _collect_screenshots(tmp_path / "nonexistent")
        assert result == []
