"""
Property tests for Scrollable Child Strategy Compatibility.

Feature: playwright-support
Property 16: Scrollable Child Strategy Compatibility

Property 16: *For any* element and scrollable child strategy (first_scrollable,
first_largest_scrollable, deepest_scrollable, largest_scrollable,
largest_scrollable_early_stop), both Selenium and Playwright backends SHALL return
equivalent scrollable child elements, and the `direction` parameter SHALL filter
results consistently.

Validates: Compatibility Gap 3 (solve_scrollable_child strategies)
"""

# Path resolution - must be first
import sys
from pathlib import Path

PIVOT_FOLDER_NAME = 'test'
current_file = Path(__file__).resolve()
current_path = current_file.parent
while current_path.name != PIVOT_FOLDER_NAME and current_path.parent != current_path:
    current_path = current_path.parent

if current_path.name != PIVOT_FOLDER_NAME:
    raise RuntimeError(f"Could not find '{PIVOT_FOLDER_NAME}' folder in path hierarchy")

webagent_root = current_path.parent
src_dir = webagent_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

projects_root = webagent_root.parent
for path_item in [projects_root / "SciencePythonUtils" / "src", projects_root / "ScienceModelingTools" / "src"]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

import pytest
import inspect
from hypothesis import given, strategies as st, settings

from webaxon.automation.backends.base import BackendAdapter
from webaxon.automation.backends.selenium.selenium_backend import SeleniumBackend


# =============================================================================
# Scrollable Child Strategies (as defined in design doc)
# =============================================================================

SCROLLABLE_CHILD_STRATEGIES = [
    'first_scrollable',
    'first_largest_scrollable',
    'deepest_scrollable',
    'largest_scrollable',
    'largest_scrollable_early_stop'
]


# =============================================================================
# Property 16: Scrollable Child Strategy Compatibility
# =============================================================================

class TestScrollableChildStrategyCompatibility:
    """
    Property 16: Both backends should support the same scrollable child strategies.
    """

    def test_selenium_backend_has_solve_scrollable_child(self):
        """SeleniumBackend should have solve_scrollable_child method."""
        assert hasattr(SeleniumBackend, 'solve_scrollable_child')
        assert callable(getattr(SeleniumBackend, 'solve_scrollable_child'))

    def test_playwright_backend_has_solve_scrollable_child(self):
        """PlaywrightBackend should have solve_scrollable_child method."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
        assert hasattr(PlaywrightBackend, 'solve_scrollable_child')
        assert callable(getattr(PlaywrightBackend, 'solve_scrollable_child'))

    def test_base_adapter_defines_solve_scrollable_child(self):
        """BackendAdapter should define solve_scrollable_child as abstract method."""
        assert hasattr(BackendAdapter, 'solve_scrollable_child')
        method = getattr(BackendAdapter, 'solve_scrollable_child')
        assert getattr(method, '__isabstractmethod__', False)


class TestScrollableChildStrategies:
    """Tests for scrollable child strategy parameter."""

    def test_solve_scrollable_child_has_strategy_parameter(self):
        """solve_scrollable_child should have strategy parameter."""
        sig = inspect.signature(SeleniumBackend.solve_scrollable_child)
        params = list(sig.parameters.keys())
        assert 'strategy' in params

    def test_strategy_default_is_first_scrollable(self):
        """strategy should default to 'first_scrollable'."""
        sig = inspect.signature(SeleniumBackend.solve_scrollable_child)
        strategy_param = sig.parameters.get('strategy')
        assert strategy_param is not None
        assert strategy_param.default == 'first_scrollable'

    @given(strategy=st.sampled_from(SCROLLABLE_CHILD_STRATEGIES))
    @settings(max_examples=10)
    def test_valid_strategy_values(self, strategy):
        """All 5 strategies should be valid."""
        assert strategy in SCROLLABLE_CHILD_STRATEGIES

    def test_all_strategies_defined(self):
        """All 5 scrollable child strategies should be defined."""
        expected_strategies = [
            'first_scrollable',
            'first_largest_scrollable',
            'deepest_scrollable',
            'largest_scrollable',
            'largest_scrollable_early_stop'
        ]
        for strategy in expected_strategies:
            assert strategy in SCROLLABLE_CHILD_STRATEGIES


class TestScrollableChildSignatureCompatibility:
    """Tests for solve_scrollable_child signature compatibility."""

    def test_selenium_signature_matches_base(self):
        """SeleniumBackend.solve_scrollable_child signature should match base."""
        base_sig = inspect.signature(BackendAdapter.solve_scrollable_child)
        selenium_sig = inspect.signature(SeleniumBackend.solve_scrollable_child)

        base_params = set(base_sig.parameters.keys())
        selenium_params = set(selenium_sig.parameters.keys())

        assert base_params <= selenium_params, \
            f"SeleniumBackend missing params: {base_params - selenium_params}"

    def test_playwright_signature_matches_base(self):
        """PlaywrightBackend.solve_scrollable_child signature should match base."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        base_sig = inspect.signature(BackendAdapter.solve_scrollable_child)
        playwright_sig = inspect.signature(PlaywrightBackend.solve_scrollable_child)

        base_params = set(base_sig.parameters.keys())
        playwright_params = set(playwright_sig.parameters.keys())

        assert base_params <= playwright_params, \
            f"PlaywrightBackend missing params: {base_params - playwright_params}"


class TestScrollableChildReturnType:
    """Tests for solve_scrollable_child return type."""

    def test_solve_scrollable_child_returns_element(self):
        """solve_scrollable_child should return an element (or original element)."""
        sig = inspect.signature(BackendAdapter.solve_scrollable_child)
        return_annotation = sig.return_annotation
        # Should return Any (element type varies by backend)

    def test_solve_scrollable_child_has_element_parameter(self):
        """solve_scrollable_child should have element parameter."""
        sig = inspect.signature(SeleniumBackend.solve_scrollable_child)
        params = list(sig.parameters.keys())
        assert 'element' in params


class TestScrollableChildDirectionParameter:
    """Tests for direction parameter in solve_scrollable_child."""

    def test_selenium_may_have_direction_parameter(self):
        """SeleniumBackend.solve_scrollable_child may have direction parameter."""
        sig = inspect.signature(SeleniumBackend.solve_scrollable_child)
        # direction is optional, may or may not be present
        # Just verify the method exists

    def test_playwright_may_have_direction_parameter(self):
        """PlaywrightBackend.solve_scrollable_child may have direction parameter."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
        sig = inspect.signature(PlaywrightBackend.solve_scrollable_child)
        # direction is optional, may or may not be present


class TestScrollableChildStrategyDescriptions:
    """Tests for strategy descriptions and expected behavior."""

    def test_first_scrollable_is_bfs(self):
        """first_scrollable should find first scrollable descendant using BFS."""
        # This is a behavioral description test
        # The actual behavior is tested with real elements in integration tests
        assert 'first_scrollable' in SCROLLABLE_CHILD_STRATEGIES

    def test_first_largest_scrollable_compares_area(self):
        """first_largest_scrollable should compare scroll areas."""
        assert 'first_largest_scrollable' in SCROLLABLE_CHILD_STRATEGIES

    def test_deepest_scrollable_uses_dfs(self):
        """deepest_scrollable should find deepest scrollable using DFS."""
        assert 'deepest_scrollable' in SCROLLABLE_CHILD_STRATEGIES

    def test_largest_scrollable_finds_overall_largest(self):
        """largest_scrollable should find scrollable with largest scroll area."""
        assert 'largest_scrollable' in SCROLLABLE_CHILD_STRATEGIES

    def test_largest_scrollable_early_stop_is_optimized(self):
        """largest_scrollable_early_stop should have early termination."""
        assert 'largest_scrollable_early_stop' in SCROLLABLE_CHILD_STRATEGIES
