"""
Unit tests for WebTargetConverter.

Tests cover:
- Element with data-testid produces data-testid selector first
- Element with only class produces xpath/css
- Element with no stable attributes falls back to agent
- Selector matching multiple elements is discarded
- Strategy priority ordering in output
- html_before / html_after fallback
- __id__ extraction from various target formats
"""

import pytest

from agent_foundation.automation.meta_agent.models import TraceStep
from agent_foundation.automation.meta_agent.target_converter import (
    TargetSpec,
    TargetSpecWithFallback,
)
from webaxon.automation.meta_agent.web_target_converter import WebTargetConverter


@pytest.fixture
def converter():
    return WebTargetConverter()


# ------------------------------------------------------------------
# HTML fixtures
# ------------------------------------------------------------------

SIMPLE_HTML = """
<html><body>
  <button __id__="elem_1" data-testid="submit-btn" id="submit">Submit</button>
  <input __id__="elem_2" data-qa="search-input" type="text" />
  <div __id__="elem_3" class="card-item">Card content</div>
  <span __id__="elem_4">Just text</span>
  <div __id__="elem_5" aria-label="Close dialog" role="button">X</div>
</body></html>
"""

DUPLICATE_CLASS_HTML = """
<html><body>
  <div __id__="elem_1" class="item">First</div>
  <div class="item">Second</div>
  <div class="item">Third</div>
</body></html>
"""

NO_ATTRS_HTML = """
<html><body>
  <div __id__="elem_1"><span>inner</span></div>
</body></html>
"""


def _make_step(target, html_before=None, html_after=None, reasoning=None):
    return TraceStep(
        action_type="click",
        target=target,
        html_before=html_before,
        html_after=html_after,
        reasoning=reasoning,
    )


# ------------------------------------------------------------------
# Tests: data-testid / data-qa selectors
# ------------------------------------------------------------------


class TestDataAttributes:
    def test_data_testid_element(self, converter):
        step = _make_step("__id__=elem_1", html_before=SIMPLE_HTML)
        result = converter.convert(step)

        assert isinstance(result, TargetSpecWithFallback)
        strategy_names = [s.strategy for s in result.strategies]
        assert "data-testid" in strategy_names

    def test_data_qa_element(self, converter):
        step = _make_step("__id__=elem_2", html_before=SIMPLE_HTML)
        result = converter.convert(step)

        strategy_names = [s.strategy for s in result.strategies]
        assert "data-qa" in strategy_names

    def test_data_testid_before_id(self, converter):
        """data-testid should appear before id in priority order."""
        step = _make_step("__id__=elem_1", html_before=SIMPLE_HTML)
        result = converter.convert(step)

        strategy_names = [s.strategy for s in result.strategies]
        if "data-testid" in strategy_names and "id" in strategy_names:
            assert strategy_names.index("data-testid") < strategy_names.index("id")


# ------------------------------------------------------------------
# Tests: native id
# ------------------------------------------------------------------


class TestNativeId:
    def test_element_with_id(self, converter):
        step = _make_step("__id__=elem_1", html_before=SIMPLE_HTML)
        result = converter.convert(step)

        strategy_names = [s.strategy for s in result.strategies]
        assert "id" in strategy_names
        id_spec = next(s for s in result.strategies if s.strategy == "id")
        assert id_spec.value == "#submit"


# ------------------------------------------------------------------
# Tests: aria selector
# ------------------------------------------------------------------


class TestAriaSelector:
    def test_element_with_aria_label_and_role(self, converter):
        step = _make_step("__id__=elem_5", html_before=SIMPLE_HTML)
        result = converter.convert(step)

        strategy_names = [s.strategy for s in result.strategies]
        assert "aria" in strategy_names
        aria_spec = next(s for s in result.strategies if s.strategy == "aria")
        assert "aria-label" in aria_spec.value
        assert "Close dialog" in aria_spec.value
        assert "button" in aria_spec.value


# ------------------------------------------------------------------
# Tests: xpath with text
# ------------------------------------------------------------------


class TestXpathText:
    def test_element_with_text_content(self, converter):
        step = _make_step("__id__=elem_4", html_before=SIMPLE_HTML)
        result = converter.convert(step)

        strategy_names = [s.strategy for s in result.strategies]
        assert "xpath-text" in strategy_names
        xpath_spec = next(s for s in result.strategies if s.strategy == "xpath-text")
        assert "Just text" in xpath_spec.value


# ------------------------------------------------------------------
# Tests: uniqueness validation (discard non-unique selectors)
# ------------------------------------------------------------------


class TestUniqueness:
    def test_duplicate_class_discarded(self, converter):
        """CSS/xpath-class selectors matching multiple elements should be discarded."""
        step = _make_step("__id__=elem_1", html_before=DUPLICATE_CLASS_HTML)
        result = converter.convert(step)

        strategy_names = [s.strategy for s in result.strategies]
        # The class "item" appears 3 times, so css and xpath-class should be discarded
        assert "css" not in strategy_names
        assert "xpath-class" not in strategy_names


# ------------------------------------------------------------------
# Tests: agent fallback
# ------------------------------------------------------------------


class TestAgentFallback:
    def test_no_stable_attributes(self, converter):
        """Element with no stable attributes falls back to agent."""
        step = _make_step(
            "__id__=elem_1",
            html_before=NO_ATTRS_HTML,
            reasoning="Click the container div",
        )
        result = converter.convert(step)

        # Should have at least the agent fallback
        assert len(result.strategies) >= 1
        # If only agent, check it
        if len(result.strategies) == 1:
            assert result.strategies[0].strategy == "agent"
            assert "container div" in result.strategies[0].value

    def test_no_html_snapshots(self, converter):
        """No HTML available → agent fallback."""
        step = _make_step("__id__=elem_1", reasoning="Click the button")
        result = converter.convert(step)

        assert len(result.strategies) == 1
        assert result.strategies[0].strategy == "agent"

    def test_non_id_target(self, converter):
        """Target that isn't __id__ → agent fallback."""
        step = _make_step("some_other_target", html_before=SIMPLE_HTML)
        result = converter.convert(step)

        assert len(result.strategies) == 1
        assert result.strategies[0].strategy == "agent"

    def test_element_not_found_in_html(self, converter):
        """__id__ not present in HTML → agent fallback."""
        step = _make_step("__id__=nonexistent", html_before=SIMPLE_HTML)
        result = converter.convert(step)

        assert len(result.strategies) == 1
        assert result.strategies[0].strategy == "agent"


# ------------------------------------------------------------------
# Tests: html_before / html_after fallback
# ------------------------------------------------------------------


class TestHtmlFallback:
    def test_uses_html_after_when_before_missing(self, converter):
        step = _make_step("__id__=elem_1", html_after=SIMPLE_HTML)
        result = converter.convert(step)

        # Should still find the element and produce selectors
        strategy_names = [s.strategy for s in result.strategies]
        assert len(strategy_names) > 0
        assert "agent" not in strategy_names or len(strategy_names) > 1


# ------------------------------------------------------------------
# Tests: strategy priority ordering
# ------------------------------------------------------------------


class TestStrategyOrdering:
    def test_strategies_follow_priority(self, converter):
        """All strategies in output should follow STRATEGY_PRIORITY order."""
        step = _make_step("__id__=elem_1", html_before=SIMPLE_HTML)
        result = converter.convert(step)

        priority = WebTargetConverter.STRATEGY_PRIORITY
        strategy_names = [s.strategy for s in result.strategies]

        for i in range(len(strategy_names) - 1):
            idx_a = priority.index(strategy_names[i])
            idx_b = priority.index(strategy_names[i + 1])
            assert idx_a < idx_b, (
                f"{strategy_names[i]} should come before {strategy_names[i+1]}"
            )


# ------------------------------------------------------------------
# Tests: __id__ extraction
# ------------------------------------------------------------------


class TestFrameworkIdExtraction:
    def test_string_with_prefix(self):
        assert WebTargetConverter._extract_framework_id("__id__=elem_42") == "elem_42"

    def test_string_without_prefix(self):
        assert WebTargetConverter._extract_framework_id("some_target") is None

    def test_dict_target(self):
        target = {"strategy": "__id__", "value": "elem_42"}
        assert WebTargetConverter._extract_framework_id(target) == "elem_42"

    def test_dict_non_id_strategy(self):
        target = {"strategy": "css", "value": ".btn"}
        assert WebTargetConverter._extract_framework_id(target) is None

    def test_none_target(self):
        assert WebTargetConverter._extract_framework_id(None) is None

    def test_dataclass_target(self):
        spec = TargetSpec(strategy="__id__", value="elem_42")
        assert WebTargetConverter._extract_framework_id(spec) == "elem_42"
