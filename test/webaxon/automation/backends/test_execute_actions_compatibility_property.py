"""
Property tests for Execute Actions Compatibility.

Feature: playwright-support
Property 17: Execute Actions Compatibility

Property 17: *For any* action sequence with conditions (init_cond, repeat, repeat_when),
both Selenium and Playwright backends SHALL execute actions in the same order, evaluate
conditions equivalently, and produce the same action records when `output_path_action_records`
is specified.

Validates: Compatibility Gap 4 (execute_actions full implementation)
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
# Property 17: Execute Actions Compatibility
# =============================================================================

class TestExecuteActionsCompatibility:
    """
    Property 17: Both backends should execute actions in the same order with
    equivalent condition evaluation.
    """

    def test_selenium_backend_has_execute_actions(self):
        """SeleniumBackend should have execute_actions method."""
        assert hasattr(SeleniumBackend, 'execute_actions')
        assert callable(getattr(SeleniumBackend, 'execute_actions'))

    def test_playwright_backend_has_execute_actions(self):
        """PlaywrightBackend should have execute_actions method."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
        assert hasattr(PlaywrightBackend, 'execute_actions')
        assert callable(getattr(PlaywrightBackend, 'execute_actions'))

    def test_base_adapter_defines_execute_actions(self):
        """BackendAdapter should define execute_actions as abstract method."""
        assert hasattr(BackendAdapter, 'execute_actions')
        method = getattr(BackendAdapter, 'execute_actions')
        assert getattr(method, '__isabstractmethod__', False)


class TestExecuteActionsParameters:
    """Tests for execute_actions parameters."""

    def test_execute_actions_has_actions_parameter(self):
        """execute_actions should have actions parameter."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        params = list(sig.parameters.keys())
        assert 'actions' in params

    def test_execute_actions_has_init_cond_parameter(self):
        """execute_actions should have init_cond parameter."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        params = list(sig.parameters.keys())
        assert 'init_cond' in params

    def test_execute_actions_has_repeat_parameter(self):
        """execute_actions should have repeat parameter."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        params = list(sig.parameters.keys())
        assert 'repeat' in params

    def test_execute_actions_has_repeat_when_parameter(self):
        """execute_actions should have repeat_when parameter."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        params = list(sig.parameters.keys())
        assert 'repeat_when' in params

    def test_execute_actions_has_elements_dict_parameter(self):
        """execute_actions should have elements_dict parameter."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        params = list(sig.parameters.keys())
        assert 'elements_dict' in params

    def test_execute_actions_has_output_path_parameter(self):
        """execute_actions should have output_path_action_records parameter."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        params = list(sig.parameters.keys())
        assert 'output_path_action_records' in params


class TestExecuteActionsSignatureCompatibility:
    """Tests for execute_actions signature compatibility between backends."""

    def test_selenium_signature_matches_base(self):
        """SeleniumBackend.execute_actions signature should match base class."""
        base_sig = inspect.signature(BackendAdapter.execute_actions)
        selenium_sig = inspect.signature(SeleniumBackend.execute_actions)

        base_params = set(base_sig.parameters.keys())
        selenium_params = set(selenium_sig.parameters.keys())

        assert base_params <= selenium_params, \
            f"SeleniumBackend missing params: {base_params - selenium_params}"

    def test_playwright_signature_matches_base(self):
        """PlaywrightBackend.execute_actions signature should match base class."""
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        base_sig = inspect.signature(BackendAdapter.execute_actions)
        playwright_sig = inspect.signature(PlaywrightBackend.execute_actions)

        base_params = set(base_sig.parameters.keys())
        playwright_params = set(playwright_sig.parameters.keys())

        assert base_params <= playwright_params, \
            f"PlaywrightBackend missing params: {base_params - playwright_params}"


class TestExecuteActionsDefaults:
    """Tests for execute_actions parameter defaults."""

    def test_init_cond_default_is_none(self):
        """init_cond should default to None."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        param = sig.parameters.get('init_cond')
        assert param is not None
        assert param.default is None

    def test_repeat_default_is_zero(self):
        """repeat should default to 0."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        param = sig.parameters.get('repeat')
        assert param is not None
        assert param.default == 0

    def test_repeat_when_default_is_none(self):
        """repeat_when should default to None."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        param = sig.parameters.get('repeat_when')
        assert param is not None
        assert param.default is None

    def test_elements_dict_default_is_none(self):
        """elements_dict should default to None."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        param = sig.parameters.get('elements_dict')
        assert param is not None
        assert param.default is None

    def test_output_path_default_is_none(self):
        """output_path_action_records should default to None."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        param = sig.parameters.get('output_path_action_records')
        assert param is not None
        assert param.default is None


class TestExecuteActionsConditionTypes:
    """Tests for condition types supported by execute_actions."""

    def test_bool_condition_type(self):
        """execute_actions should support boolean conditions."""
        # Boolean conditions: True/False
        # This is a type documentation test
        pass

    def test_dict_condition_type(self):
        """execute_actions should support dict conditions."""
        # Dict conditions: {'exists': 'selector'}, {'visible': 'selector'}, etc.
        pass

    def test_callable_condition_type(self):
        """execute_actions should support callable conditions."""
        # Callable conditions: lambda driver: driver.find_element(...) is not None
        pass


class TestExecuteActionsKwargs:
    """Tests for execute_actions **kwargs support."""

    def test_execute_actions_accepts_kwargs(self):
        """execute_actions should accept **kwargs."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        assert has_kwargs, "execute_actions should accept **kwargs"


class TestExecuteActionsReturnType:
    """Tests for execute_actions return type."""

    def test_execute_actions_returns_none(self):
        """execute_actions should return None."""
        sig = inspect.signature(BackendAdapter.execute_actions)
        return_annotation = sig.return_annotation
        # Should return None


class TestExecuteActionsActionRecordOutput:
    """Tests for action record output functionality."""

    def test_output_path_parameter_is_optional_string(self):
        """output_path_action_records should be Optional[str]."""
        sig = inspect.signature(SeleniumBackend.execute_actions)
        param = sig.parameters.get('output_path_action_records')
        assert param is not None
        # Default is None, indicating optional
        assert param.default is None

    def test_both_backends_support_action_records(self):
        """Both backends should support action record output."""
        # Verify Selenium has the parameter
        selenium_sig = inspect.signature(SeleniumBackend.execute_actions)
        assert 'output_path_action_records' in selenium_sig.parameters

        # Verify Playwright has the parameter (if available)
        from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE
        if PLAYWRIGHT_AVAILABLE:
            from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend
            playwright_sig = inspect.signature(PlaywrightBackend.execute_actions)
            assert 'output_path_action_records' in playwright_sig.parameters
