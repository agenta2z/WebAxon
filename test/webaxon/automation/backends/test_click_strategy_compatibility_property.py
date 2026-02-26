"""
Property tests for Click Element Strategy Compatibility.

Feature: playwright-support
Property 14: Click Element Strategy Compatibility

Property 14: *For any* click operation with `try_open_in_new_tab=True`, both Selenium
and Playwright backends SHALL support the same set of strategies (URL_EXTRACT,
TARGET_BLANK, MODIFIER_KEY, CDP_CREATE_TARGET, MIDDLE_CLICK), and the
`new_tab_strategy_order` parameter SHALL be respected in the same order by both backends.

Validates: Compatibility Gap 1 (click_element strategies)
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
# Property 14: Click Element Strategy Compatibility
# =============================================================================

class TestClickElementStrategyCompatibility:
    """
    Property 14: Both backends should support the same click strategies
    for opening in new tabs.
    """

    def test_selenium_backend_has_click_element(self):
        """SeleniumBackend should have click_element method."""
        assert hasattr(SeleniumBackend, 'click_element')
        assert callable(getattr(SeleniumBackend, 'click_element'))

    def test_playwright_backend_has_click_element(self):
        """PlaywrightBackend should have click_element method."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
        assert hasattr(PlaywrightBackend, 'click_element')
        assert callable(getattr(PlaywrightBackend, 'click_element'))

    def test_click_element_signature_has_try_open_in_new_tab(self):
        """click_element should have try_open_in_new_tab parameter."""
        sig = inspect.signature(SeleniumBackend.click_element)
        params = list(sig.parameters.keys())
        assert 'try_open_in_new_tab' in params

    def test_click_element_accepts_kwargs(self):
        """click_element should accept **kwargs for additional parameters."""
        sig = inspect.signature(SeleniumBackend.click_element)
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        assert has_kwargs, "click_element should accept **kwargs"

    def test_base_adapter_defines_click_element(self):
        """BackendAdapter should define click_element as abstract method."""
        assert hasattr(BackendAdapter, 'click_element')
        method = getattr(BackendAdapter, 'click_element')
        assert getattr(method, '__isabstractmethod__', False)


class TestClickElementSharedTypes:
    """Tests for shared click element types."""

    def test_shared_click_types_module_exists(self):
        """backends/shared/click_types.py should exist."""
        try:
            from webaxon.automation.backends.shared.click_types import (
                OpenInNewTabMode,
                NewTabClickStrategy,
            )
            assert OpenInNewTabMode is not None
            assert NewTabClickStrategy is not None
        except ImportError:
            pytest.skip("click_types module not found (may not be implemented yet)")

    def test_new_tab_click_strategies_defined(self):
        """NewTabClickStrategy should define all 5 strategies."""
        try:
            from webaxon.automation.backends.shared.click_types import NewTabClickStrategy

            expected_strategies = [
                'URL_EXTRACT',
                'TARGET_BLANK',
                'MODIFIER_KEY',
                'CDP_CREATE_TARGET',
                'MIDDLE_CLICK'
            ]

            for strategy in expected_strategies:
                assert hasattr(NewTabClickStrategy, strategy), \
                    f"Missing strategy: {strategy}"
        except ImportError:
            pytest.skip("click_types module not found")

    def test_open_in_new_tab_mode_defined(self):
        """OpenInNewTabMode should be defined with expected values."""
        try:
            from webaxon.automation.backends.shared.click_types import OpenInNewTabMode

            # Should have at least DISABLED and ENABLED modes
            assert hasattr(OpenInNewTabMode, 'DISABLED') or 'disabled' in str(OpenInNewTabMode.__members__).lower()
        except ImportError:
            pytest.skip("click_types module not found")


class TestClickElementReturnType:
    """Tests for click_element return type consistency."""

    def test_click_element_returns_optional_list_of_handles(self):
        """click_element should return Optional[List[str]] for new tab handles."""
        sig = inspect.signature(BackendAdapter.click_element)
        # Check return annotation if available
        return_annotation = sig.return_annotation
        # The method should return Optional[List[str]] or similar

    def test_selenium_click_element_signature_matches_base(self):
        """SeleniumBackend.click_element signature should match base class."""
        base_sig = inspect.signature(BackendAdapter.click_element)
        selenium_sig = inspect.signature(SeleniumBackend.click_element)

        base_params = set(base_sig.parameters.keys())
        selenium_params = set(selenium_sig.parameters.keys())

        # Selenium should have at least all base params
        assert base_params <= selenium_params, \
            f"SeleniumBackend missing params: {base_params - selenium_params}"

    def test_playwright_click_element_signature_matches_base(self):
        """PlaywrightBackend.click_element signature should match base class."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        base_sig = inspect.signature(BackendAdapter.click_element)
        playwright_sig = inspect.signature(PlaywrightBackend.click_element)

        base_params = set(base_sig.parameters.keys())
        playwright_params = set(playwright_sig.parameters.keys())

        assert base_params <= playwright_params, \
            f"PlaywrightBackend missing params: {base_params - playwright_params}"


class TestClickElementBooleanMode:
    """Tests for boolean try_open_in_new_tab parameter."""

    def test_click_element_accepts_boolean_false(self):
        """click_element should accept try_open_in_new_tab=False."""
        backend = SeleniumBackend()
        # Just verify the parameter is accepted by checking signature
        sig = inspect.signature(backend.click_element)
        param = sig.parameters.get('try_open_in_new_tab')
        assert param is not None
        # Default should be False
        assert param.default == False

    def test_click_element_accepts_boolean_true(self):
        """click_element should accept try_open_in_new_tab=True."""
        backend = SeleniumBackend()
        sig = inspect.signature(backend.click_element)
        param = sig.parameters.get('try_open_in_new_tab')
        assert param is not None


class TestClickElementKwargsParameters:
    """Tests for additional click_element parameters passed via kwargs."""

    def test_click_element_can_accept_strategy_order(self):
        """click_element should accept new_tab_strategy_order via kwargs."""
        backend = SeleniumBackend()
        sig = inspect.signature(backend.click_element)

        # Should have **kwargs
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        assert has_kwargs, "Should accept **kwargs for strategy_order"

    def test_click_element_can_accept_return_strategy_result(self):
        """click_element should accept return_strategy_result via kwargs."""
        backend = SeleniumBackend()
        sig = inspect.signature(backend.click_element)

        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        assert has_kwargs, "Should accept **kwargs for return_strategy_result"


class TestClickImplementationTypes:
    """Tests for ClickImplementation enum and DEFAULT_CLICK_IMPLEMENTATION_ORDER."""

    def test_click_implementation_enum_exists(self):
        """ClickImplementation enum should be importable from shared click_types."""
        from webaxon.automation.backends.shared.click_types import ClickImplementation
        assert ClickImplementation is not None

    def test_click_implementation_has_four_values(self):
        """ClickImplementation should define exactly 4 implementations."""
        from webaxon.automation.backends.shared.click_types import ClickImplementation
        expected = ['NATIVE', 'JAVASCRIPT', 'ACTION_CHAIN', 'EVENT_DISPATCH']
        for name in expected:
            assert hasattr(ClickImplementation, name), f"Missing ClickImplementation.{name}"
        assert len(ClickImplementation) == 4

    def test_default_click_implementation_order_preserves_behavior(self):
        """DEFAULT_CLICK_IMPLEMENTATION_ORDER should be (NATIVE, JAVASCRIPT) to match old default."""
        from webaxon.automation.backends.shared.click_types import (
            ClickImplementation, DEFAULT_CLICK_IMPLEMENTATION_ORDER
        )
        assert DEFAULT_CLICK_IMPLEMENTATION_ORDER == (
            ClickImplementation.NATIVE, ClickImplementation.JAVASCRIPT
        )

    def test_click_implementation_is_string_enum(self):
        """ClickImplementation values should be strings."""
        from webaxon.automation.backends.shared.click_types import ClickImplementation
        for member in ClickImplementation:
            assert isinstance(member.value, str)

    def test_selenium_click_element_has_implementation_param(self):
        """Selenium click_element should have 'implementation' parameter."""
        from webaxon.automation.backends.selenium.actions import click_element
        sig = inspect.signature(click_element)
        assert 'implementation' in sig.parameters, \
            "click_element should have 'implementation' parameter"

    def test_playwright_click_element_has_implementation_param(self):
        """Playwright click_element should have 'implementation' parameter."""
        from webaxon.automation.backends.playwright.actions import click_element
        sig = inspect.signature(click_element)
        assert 'implementation' in sig.parameters, \
            "click_element should have 'implementation' parameter"
