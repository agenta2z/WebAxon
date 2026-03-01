"""
Property-based test for target conversion fallback chain ordering.

Feature: meta-agent-workflow, Property 8: Target strategy conversion produces fallback chain

*For any* element with a ``__id__`` target and an HTML snapshot, the
WebTargetConverter SHALL produce a TargetSpecWithFallback with
strategies ordered by the stability priority
(data-qa > data-testid > id > aria > xpath-text > xpath-class > css > agent).

**Validates: Requirements 3.2, 3.4**
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from agent_foundation.automation.meta_agent.models import TraceStep
from webaxon.automation.meta_agent.web_target_converter import WebTargetConverter


# ---------------------------------------------------------------------------
# Hypothesis strategies for generating HTML pages
# ---------------------------------------------------------------------------

_ATTR_CHARS = st.characters(
    whitelist_categories=("L", "N"),
    whitelist_characters=("-", "_"),
)

_ATTR_VALUE = st.text(alphabet=_ATTR_CHARS, min_size=1, max_size=20)

_TAG_NAMES = st.sampled_from(["div", "span", "button", "a", "p", "li"])


def _build_element(tag: str, attrs: dict, framework_id: str, text: str) -> str:
    """Build an HTML element string with __id__ and given attributes."""
    parts = [f"<{tag}", f' __id__="{framework_id}"']
    for k, v in attrs.items():
        parts.append(f' {k}="{v}"')
    parts.append(f">{text}</{tag}>")
    return "".join(parts)


@st.composite
def html_page_with_unique_target(draw):
    """
    Generate an HTML page containing a single target element with __id__
    and a random subset of attributes (data-qa, data-testid, id,
    aria-label, class, role, text content).

    The element is the *only* element in the page so that every generated
    selector is guaranteed to be unique, letting us focus purely on
    ordering rather than uniqueness filtering.

    Returns ``(html_string, framework_id)``.
    """
    tag = draw(_TAG_NAMES)
    framework_id = "elem_" + draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=10,
        )
    )

    attrs: dict[str, str] = {}

    # Each attribute is independently present or absent
    if draw(st.booleans()):
        attrs["data-qa"] = draw(_ATTR_VALUE)
    if draw(st.booleans()):
        attrs["data-testid"] = draw(_ATTR_VALUE)
    if draw(st.booleans()):
        attrs["id"] = draw(_ATTR_VALUE)
    if draw(st.booleans()):
        attrs["aria-label"] = draw(_ATTR_VALUE)
    if draw(st.booleans()):
        attrs["role"] = draw(st.sampled_from(["button", "link", "textbox", "dialog"]))
    if draw(st.booleans()):
        attrs["class"] = draw(_ATTR_VALUE)

    text = draw(st.text(alphabet=_ATTR_CHARS, min_size=1, max_size=30))

    element = _build_element(tag, attrs, framework_id, text)
    html = f"<html><body>{element}</body></html>"
    return html, framework_id


# ---------------------------------------------------------------------------
# Property 8: Target strategy conversion produces fallback chain
# ---------------------------------------------------------------------------

# The canonical priority list from the converter.
_PRIORITY = WebTargetConverter.STRATEGY_PRIORITY


def _priority_index(strategy_name: str) -> int:
    """Return the index of *strategy_name* in the priority list."""
    return _PRIORITY.index(strategy_name)


class TestTargetFallbackChainProperty:
    """
    Property 8: Target strategy conversion produces fallback chain

    *For any* element with a ``__id__`` target and an HTML snapshot, the
    WebTargetConverter SHALL produce a TargetSpecWithFallback with
    strategies ordered by the stability priority
    (data-qa > data-testid > id > aria > xpath-text > xpath-class > css > agent).

    **Validates: Requirements 3.2, 3.4**
    """

    @given(data=html_page_with_unique_target())
    @settings(max_examples=200)
    def test_strategies_ordered_by_priority(self, data):
        """
        For any element with __id__ target and HTML snapshot, the output
        strategies are ordered according to STRATEGY_PRIORITY — i.e. for
        every consecutive pair (s_i, s_{i+1}), the priority index of s_i
        is less than the priority index of s_{i+1}.
        """
        html, framework_id = data
        converter = WebTargetConverter()

        step = TraceStep(
            action_type="click",
            target=f"__id__={framework_id}",
            html_before=html,
        )
        result = converter.convert(step)

        strategy_names = [s.strategy for s in result.strategies]

        for i in range(len(strategy_names) - 1):
            idx_current = _priority_index(strategy_names[i])
            idx_next = _priority_index(strategy_names[i + 1])
            assert idx_current < idx_next, (
                f"Strategy ordering violated: {strategy_names[i]!r} "
                f"(priority {idx_current}) appears before "
                f"{strategy_names[i + 1]!r} (priority {idx_next}). "
                f"Full chain: {strategy_names}"
            )

    @given(data=html_page_with_unique_target())
    @settings(max_examples=200)
    def test_all_strategies_are_from_priority_list(self, data):
        """
        Every strategy name in the output is a member of the canonical
        STRATEGY_PRIORITY list.
        """
        html, framework_id = data
        converter = WebTargetConverter()

        step = TraceStep(
            action_type="click",
            target=f"__id__={framework_id}",
            html_before=html,
        )
        result = converter.convert(step)

        allowed = set(_PRIORITY)
        for spec in result.strategies:
            assert spec.strategy in allowed, (
                f"Strategy {spec.strategy!r} is not in STRATEGY_PRIORITY: {_PRIORITY}"
            )

    @given(data=html_page_with_unique_target())
    @settings(max_examples=200)
    def test_agent_fallback_is_always_last_if_present(self, data):
        """
        If the 'agent' strategy appears in the output, it is always the
        last entry in the fallback chain.
        """
        html, framework_id = data
        converter = WebTargetConverter()

        step = TraceStep(
            action_type="click",
            target=f"__id__={framework_id}",
            html_before=html,
        )
        result = converter.convert(step)

        strategy_names = [s.strategy for s in result.strategies]
        if "agent" in strategy_names:
            assert strategy_names[-1] == "agent", (
                f"'agent' strategy is not last in the chain: {strategy_names}"
            )
