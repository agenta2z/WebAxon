"""Property test: convert_all applies convert to exactly the steps where
should_convert returns True (Property 1 from decoupling plan).

**Validates:** TargetConverterBase contract — convert_all correctly filters
via should_convert and delegates to convert.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from agent_foundation.automation.meta_agent.models import TraceStep
from agent_foundation.automation.meta_agent.target_converter import (
    TargetConverterBase,
    TargetSpecWithFallback,
)

from webaxon.automation.meta_agent.web_target_converter import WebTargetConverter


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_TARGETS = st.one_of(
    st.none(),
    st.just(""),
    st.just("#btn"),
    st.just("__id__abc123"),
    st.just("__id__xyz789"),
    st.just("div.main"),
    st.just("[data-testid='submit']"),
)


@st.composite
def trace_steps_list(draw, min_size: int = 1, max_size: int = 8):
    """Generate a list of TraceSteps with varied targets."""
    count = draw(st.integers(min_value=min_size, max_value=max_size))
    action_types = ["click", "input_text", "scroll", "wait", "visit_url"]
    return [
        TraceStep(
            action_type=draw(st.sampled_from(action_types)),
            target=draw(_TARGETS),
        )
        for _ in range(count)
    ]


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(steps=trace_steps_list())
def test_convert_all_calls_convert_for_each_should_convert_step(
    steps: list[TraceStep],
):
    """Property 1: convert_all applies convert to every step where
    should_convert returns True, and leaves others unchanged.
    """
    converter = WebTargetConverter()

    # Record which steps should be converted
    convertible_indices = [
        i for i, step in enumerate(steps)
        if converter.should_convert(step)
    ]
    non_convertible_indices = [
        i for i, step in enumerate(steps)
        if not converter.should_convert(step)
    ]

    # Save original targets for non-convertible steps
    original_targets = {i: steps[i].target for i in non_convertible_indices}

    # Patch convert to return a known sentinel
    sentinel = TargetSpecWithFallback(strategies=[])
    with patch.object(converter, "convert", return_value=sentinel) as mock_convert:
        converter.convert_all(steps)

    # Verify convert was called exactly for should_convert==True steps
    assert mock_convert.call_count == len(convertible_indices), (
        f"Expected {len(convertible_indices)} convert calls, "
        f"got {mock_convert.call_count}"
    )

    # Verify convertible steps got the sentinel target
    for i in convertible_indices:
        assert steps[i].target is sentinel, (
            f"Step {i} should have been converted but wasn't"
        )

    # Verify non-convertible steps are unchanged
    for i in non_convertible_indices:
        assert steps[i].target is original_targets[i], (
            f"Step {i} should not have been converted but target changed"
        )


@settings(max_examples=50, deadline=None)
@given(steps=trace_steps_list())
def test_should_convert_only_matches_id_prefixed_targets(
    steps: list[TraceStep],
):
    """Property 1 corollary: WebTargetConverter.should_convert only returns
    True for string targets starting with '__id__'.
    """
    converter = WebTargetConverter()

    for step in steps:
        result = converter.should_convert(step)
        if result:
            assert isinstance(step.target, str), (
                f"should_convert returned True for non-string target: {step.target!r}"
            )
            assert step.target.startswith("__id__"), (
                f"should_convert returned True for non-__id__ target: {step.target!r}"
            )
        else:
            # Either not a string or doesn't start with __id__
            if isinstance(step.target, str):
                assert not step.target.startswith("__id__"), (
                    f"should_convert returned False for __id__ target: {step.target!r}"
                )
