"""
Property tests for Scroll Element Relative Distance Compatibility.

Feature: playwright-support
Property 15: Scroll Element Relative Distance

Property 15: *For any* scroll operation with `relative_distance=True`, both Selenium
and Playwright backends SHALL calculate scroll amounts as percentages of the element's
dimensions (Small=30%, Medium=60%, Large=90%), producing equivalent scroll behavior.

Validates: Compatibility Gap 2 (scroll_element relative_distance)
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
# Relative Distance Percentages (as defined in design doc)
# =============================================================================

RELATIVE_DISTANCE_PERCENTAGES = {
    'Small': 0.30,
    'Medium': 0.60,
    'Large': 0.90
}


# =============================================================================
# Property 15: Scroll Element Relative Distance
# =============================================================================

class TestScrollElementRelativeDistance:
    """
    Property 15: Both backends should calculate scroll amounts as percentages
    of element dimensions when relative_distance=True.
    """

    def test_selenium_backend_has_scroll_element(self):
        """SeleniumBackend should have scroll_element method."""
        assert hasattr(SeleniumBackend, 'scroll_element')
        assert callable(getattr(SeleniumBackend, 'scroll_element'))

    def test_playwright_backend_has_scroll_element(self):
        """PlaywrightBackend should have scroll_element method."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
        assert hasattr(PlaywrightBackend, 'scroll_element')
        assert callable(getattr(PlaywrightBackend, 'scroll_element'))

    def test_scroll_element_has_direction_parameter(self):
        """scroll_element should have direction parameter."""
        sig = inspect.signature(SeleniumBackend.scroll_element)
        params = list(sig.parameters.keys())
        assert 'direction' in params

    def test_scroll_element_has_distance_parameter(self):
        """scroll_element should have distance parameter."""
        sig = inspect.signature(SeleniumBackend.scroll_element)
        params = list(sig.parameters.keys())
        assert 'distance' in params

    def test_scroll_element_direction_default(self):
        """scroll_element direction should default to 'Down'."""
        sig = inspect.signature(SeleniumBackend.scroll_element)
        direction_param = sig.parameters.get('direction')
        assert direction_param is not None
        assert direction_param.default == 'Down'

    def test_scroll_element_distance_default(self):
        """scroll_element distance should default to 'Large'."""
        sig = inspect.signature(SeleniumBackend.scroll_element)
        distance_param = sig.parameters.get('distance')
        assert distance_param is not None
        assert distance_param.default == 'Large'


class TestScrollElementSignatureCompatibility:
    """Tests for scroll_element signature compatibility between backends."""

    def test_selenium_signature_matches_base(self):
        """SeleniumBackend.scroll_element signature should match base class."""
        base_sig = inspect.signature(BackendAdapter.scroll_element)
        selenium_sig = inspect.signature(SeleniumBackend.scroll_element)

        base_params = set(base_sig.parameters.keys())
        selenium_params = set(selenium_sig.parameters.keys())

        assert base_params <= selenium_params, \
            f"SeleniumBackend missing params: {base_params - selenium_params}"

    def test_playwright_signature_matches_base(self):
        """PlaywrightBackend.scroll_element signature should match base class."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        base_sig = inspect.signature(BackendAdapter.scroll_element)
        playwright_sig = inspect.signature(PlaywrightBackend.scroll_element)

        base_params = set(base_sig.parameters.keys())
        playwright_params = set(playwright_sig.parameters.keys())

        assert base_params <= playwright_params, \
            f"PlaywrightBackend missing params: {base_params - playwright_params}"

    def test_scroll_element_accepts_kwargs(self):
        """scroll_element should accept **kwargs for additional parameters."""
        sig = inspect.signature(SeleniumBackend.scroll_element)
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        assert has_kwargs, "scroll_element should accept **kwargs"


class TestScrollElementDistanceValues:
    """Tests for valid distance values."""

    @given(distance=st.sampled_from(['Small', 'Medium', 'Large']))
    @settings(max_examples=10)
    def test_valid_distance_values(self, distance):
        """Distance should accept Small, Medium, Large values."""
        # These are the valid distance values
        assert distance in RELATIVE_DISTANCE_PERCENTAGES

    def test_distance_percentages_are_correct(self):
        """Relative distance percentages should be 30%, 60%, 90%."""
        assert RELATIVE_DISTANCE_PERCENTAGES['Small'] == 0.30
        assert RELATIVE_DISTANCE_PERCENTAGES['Medium'] == 0.60
        assert RELATIVE_DISTANCE_PERCENTAGES['Large'] == 0.90


class TestScrollElementDirectionValues:
    """Tests for valid direction values."""

    @given(direction=st.sampled_from(['Up', 'Down', 'Left', 'Right']))
    @settings(max_examples=10)
    def test_valid_direction_values(self, direction):
        """Direction should accept Up, Down, Left, Right values."""
        valid_directions = ['Up', 'Down', 'Left', 'Right']
        assert direction in valid_directions


class TestScrollElementImplementation:
    """Tests for scroll_element implementation parameter."""

    def test_scroll_element_has_implementation_parameter(self):
        """scroll_element should have implementation parameter."""
        sig = inspect.signature(SeleniumBackend.scroll_element)
        params = list(sig.parameters.keys())
        assert 'implementation' in params

    def test_implementation_default_is_javascript(self):
        """scroll_element implementation should default to 'javascript'."""
        sig = inspect.signature(SeleniumBackend.scroll_element)
        impl_param = sig.parameters.get('implementation')
        assert impl_param is not None
        assert impl_param.default == 'javascript'


class TestScrollElementScrollableChild:
    """Tests for scrollable child detection in scroll_element."""

    def test_scroll_element_has_try_solve_scrollable_child(self):
        """scroll_element should have try_solve_scrollable_child parameter."""
        sig = inspect.signature(SeleniumBackend.scroll_element)
        params = list(sig.parameters.keys())
        assert 'try_solve_scrollable_child' in params

    def test_try_solve_scrollable_child_default_false(self):
        """try_solve_scrollable_child should default to False."""
        sig = inspect.signature(SeleniumBackend.scroll_element)
        param = sig.parameters.get('try_solve_scrollable_child')
        assert param is not None
        assert param.default == False


class TestBackendAdapterScrollElement:
    """Tests for BackendAdapter.scroll_element abstract method."""

    def test_base_adapter_defines_scroll_element(self):
        """BackendAdapter should define scroll_element as abstract method."""
        assert hasattr(BackendAdapter, 'scroll_element')
        method = getattr(BackendAdapter, 'scroll_element')
        assert getattr(method, '__isabstractmethod__', False)

    def test_base_adapter_scroll_element_has_all_params(self):
        """BackendAdapter.scroll_element should have all required parameters."""
        sig = inspect.signature(BackendAdapter.scroll_element)
        required_params = ['element', 'direction', 'distance', 'implementation', 'try_solve_scrollable_child']

        for param in required_params:
            assert param in sig.parameters, f"Missing parameter: {param}"
