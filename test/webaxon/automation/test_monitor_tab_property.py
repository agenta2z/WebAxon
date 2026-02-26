"""
Property tests for Monitor Tab Registration and Switch Prevention.

Feature: playwright-support
Property 4: Monitor Tab Registration Consistency
Property 5: Monitor Tab Switch Prevention

Property 4: *For any* window handle string, after calling `register_monitor_tab(handle)`,
the method `is_monitor_tab(handle)` SHALL return True, and `get_action_tabs()` SHALL
NOT include that handle in its result.

Property 5: *For any* handle that has been registered as a monitor tab, calling
`switch_to_action_tab(handle)` SHALL raise a ValueError.

Validates: Requirements 7.1, 7.2, 7.3, 7.4
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
from unittest.mock import MagicMock, patch
from hypothesis import given, strategies as st, settings, assume

from webaxon.automation.web_driver import WebDriver


def create_test_webdriver(tab_handles=None):
    """Create a WebDriver instance with mocked backend for testing."""
    if tab_handles is None:
        tab_handles = ['tab1', 'tab2', 'tab3']

    mock_backend = MagicMock()
    mock_backend.driver_type = 'chrome'
    mock_backend.raw_driver = MagicMock()
    mock_backend.raw_driver.window_handles = tab_handles
    mock_backend.raw_driver.current_window_handle = tab_handles[0] if tab_handles else None
    mock_backend.window_handles = tab_handles
    mock_backend.current_window_handle = tab_handles[0] if tab_handles else None
    type(mock_backend).__name__ = 'SeleniumBackend'

    driver = WebDriver.__new__(WebDriver)
    driver._backend = mock_backend
    driver._driver_type = 'chrome'
    driver._state = None
    driver.state_setting_max_retry = 3
    driver.state_setting_retry_wait = 0.2
    driver._action_configs = {}
    driver._window_infos = {}
    driver._monitor_tabs = set()
    driver._id = "test-webdriver"
    driver._log_level = 0

    return driver, mock_backend


# =============================================================================
# Property 4: Monitor Tab Registration Consistency
# =============================================================================

class TestMonitorTabRegistrationConsistency:
    """
    Property 4: For any window handle string, after calling register_monitor_tab(handle),
    is_monitor_tab(handle) SHALL return True, and get_action_tabs() SHALL NOT include
    that handle.
    """

    @given(handle=st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=48, max_codepoint=122
    )))
    @settings(max_examples=100)
    def test_registered_tab_is_monitor_tab(self, handle):
        """After registration, is_monitor_tab should return True."""
        driver, _ = create_test_webdriver()
        driver.register_monitor_tab(handle)
        assert driver.is_monitor_tab(handle) is True

    @given(handle=st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=48, max_codepoint=122
    )))
    @settings(max_examples=100)
    def test_registered_tab_not_in_action_tabs(self, handle):
        """After registration, handle should not be in get_action_tabs()."""
        driver, mock_backend = create_test_webdriver([handle, 'other_tab'])
        driver.register_monitor_tab(handle)
        action_tabs = driver.get_action_tabs()
        assert handle not in action_tabs

    @given(handles=st.lists(
        st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=48, max_codepoint=122
        )),
        min_size=1, max_size=10, unique=True
    ))
    @settings(max_examples=50)
    def test_multiple_registrations_all_become_monitors(self, handles):
        """Registering multiple handles should make all of them monitor tabs."""
        driver, mock_backend = create_test_webdriver(handles + ['action_tab'])

        for handle in handles:
            driver.register_monitor_tab(handle)

        for handle in handles:
            assert driver.is_monitor_tab(handle) is True
            assert handle not in driver.get_action_tabs()

    def test_registration_is_idempotent(self):
        """Registering the same handle twice should be safe."""
        driver, _ = create_test_webdriver()
        driver.register_monitor_tab('tab1')
        driver.register_monitor_tab('tab1')
        assert driver.is_monitor_tab('tab1') is True
        assert len([h for h in driver._monitor_tabs if h == 'tab1']) == 1

    def test_unregistered_tab_not_monitor(self):
        """Unregistered handles should not be monitor tabs."""
        driver, _ = create_test_webdriver()
        assert driver.is_monitor_tab('tab1') is False

    def test_unregister_removes_from_monitors(self):
        """Unregistering should remove the handle from monitors."""
        driver, _ = create_test_webdriver()
        driver.register_monitor_tab('tab1')
        assert driver.is_monitor_tab('tab1') is True
        driver.unregister_monitor_tab('tab1')
        assert driver.is_monitor_tab('tab1') is False

    @given(handle=st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=48, max_codepoint=122
    )))
    @settings(max_examples=50)
    def test_unregister_returns_to_action_tabs(self, handle):
        """After unregistering, handle should be back in action tabs."""
        driver, mock_backend = create_test_webdriver([handle, 'other_tab'])

        driver.register_monitor_tab(handle)
        assert handle not in driver.get_action_tabs()

        driver.unregister_monitor_tab(handle)
        assert handle in driver.get_action_tabs()

    def test_get_monitor_tabs_returns_all_registered(self):
        """get_monitor_tabs should return all registered monitor tabs."""
        driver, _ = create_test_webdriver()
        driver.register_monitor_tab('monitor1')
        driver.register_monitor_tab('monitor2')

        monitor_tabs = driver.get_monitor_tabs()
        assert set(monitor_tabs) == {'monitor1', 'monitor2'}

    def test_get_monitor_tabs_returns_list(self):
        """get_monitor_tabs should return a list."""
        driver, _ = create_test_webdriver()
        driver.register_monitor_tab('monitor1')

        result = driver.get_monitor_tabs()
        assert isinstance(result, list)


class TestMonitorTabActionTabExclusion:
    """Tests for action tab exclusion of monitor tabs."""

    def test_action_tabs_excludes_all_monitors(self):
        """get_action_tabs should exclude all monitor tabs."""
        driver, mock_backend = create_test_webdriver(['tab1', 'tab2', 'tab3', 'tab4'])

        driver.register_monitor_tab('tab2')
        driver.register_monitor_tab('tab4')

        action_tabs = driver.get_action_tabs()
        assert 'tab1' in action_tabs
        assert 'tab2' not in action_tabs
        assert 'tab3' in action_tabs
        assert 'tab4' not in action_tabs

    def test_all_tabs_as_monitors_gives_empty_action_tabs(self):
        """If all tabs are monitors, action_tabs should be empty."""
        driver, mock_backend = create_test_webdriver(['tab1', 'tab2'])

        driver.register_monitor_tab('tab1')
        driver.register_monitor_tab('tab2')

        action_tabs = driver.get_action_tabs()
        assert action_tabs == []

    def test_no_monitors_gives_all_action_tabs(self):
        """If no monitors registered, all tabs are action tabs."""
        driver, mock_backend = create_test_webdriver(['tab1', 'tab2', 'tab3'])

        action_tabs = driver.get_action_tabs()
        assert action_tabs == ['tab1', 'tab2', 'tab3']


# =============================================================================
# Property 5: Monitor Tab Switch Prevention
# =============================================================================

class TestMonitorTabSwitchPrevention:
    """
    Property 5: For any handle that has been registered as a monitor tab,
    calling switch_to_action_tab(handle) SHALL raise a ValueError.
    """

    @given(handle=st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=48, max_codepoint=122
    )))
    @settings(max_examples=50)
    def test_switch_to_monitor_tab_raises_error(self, handle):
        """Switching to a monitor tab should raise ValueError."""
        driver, mock_backend = create_test_webdriver([handle, 'action_tab'])
        driver.register_monitor_tab(handle)

        with pytest.raises(ValueError) as exc_info:
            driver.switch_to_action_tab(handle)

        assert 'monitor' in str(exc_info.value).lower()

    def test_switch_to_unregistered_tab_succeeds(self):
        """Switching to a non-monitor tab should succeed."""
        driver, mock_backend = create_test_webdriver(['tab1', 'tab2'])

        # Should not raise
        result = driver.switch_to_action_tab('tab1')
        assert result == 'tab1'

    def test_switch_with_none_uses_first_action_tab(self):
        """switch_to_action_tab(None) should use first action tab."""
        driver, mock_backend = create_test_webdriver(['tab1', 'tab2', 'tab3'])
        driver.register_monitor_tab('tab1')

        result = driver.switch_to_action_tab()
        assert result == 'tab2'

    def test_switch_with_none_skips_monitors(self):
        """switch_to_action_tab(None) should skip monitor tabs."""
        driver, mock_backend = create_test_webdriver(['monitor1', 'monitor2', 'action1'])
        driver.register_monitor_tab('monitor1')
        driver.register_monitor_tab('monitor2')

        result = driver.switch_to_action_tab()
        assert result == 'action1'

    def test_switch_with_no_action_tabs_raises_error(self):
        """If no action tabs available, switch should raise ValueError."""
        driver, mock_backend = create_test_webdriver(['tab1'])
        driver.register_monitor_tab('tab1')

        with pytest.raises(ValueError) as exc_info:
            driver.switch_to_action_tab()

        assert 'no action tabs' in str(exc_info.value).lower()

    def test_error_message_contains_handle(self):
        """Error message should contain the handle that was attempted."""
        driver, mock_backend = create_test_webdriver(['monitor_tab', 'action_tab'])
        driver.register_monitor_tab('monitor_tab')

        with pytest.raises(ValueError) as exc_info:
            driver.switch_to_action_tab('monitor_tab')

        assert 'monitor_tab' in str(exc_info.value)

    @given(handles=st.lists(
        st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=48, max_codepoint=122
        )),
        min_size=2, max_size=5, unique=True
    ))
    @settings(max_examples=30)
    def test_switch_consistency_after_multiple_registrations(self, handles):
        """After registering multiple monitors, switch should still work for action tabs."""
        assume(len(handles) >= 2)

        # Use first half as monitors, second half as action tabs
        mid = len(handles) // 2
        monitors = handles[:mid]
        actions = handles[mid:]

        driver, mock_backend = create_test_webdriver(handles)

        for monitor in monitors:
            driver.register_monitor_tab(monitor)

        # Should be able to switch to any action tab
        for action in actions:
            result = driver.switch_to_action_tab(action)
            assert result == action

        # Should NOT be able to switch to any monitor
        for monitor in monitors:
            with pytest.raises(ValueError):
                driver.switch_to_action_tab(monitor)


class TestMonitorTabStateConsistency:
    """Tests for state consistency of monitor tab tracking."""

    def test_internal_set_matches_api(self):
        """Internal _monitor_tabs set should match API responses."""
        driver, _ = create_test_webdriver()

        driver.register_monitor_tab('tab1')
        driver.register_monitor_tab('tab2')

        assert driver._monitor_tabs == {'tab1', 'tab2'}
        assert set(driver.get_monitor_tabs()) == {'tab1', 'tab2'}

    def test_unregister_nonexistent_is_safe(self):
        """Unregistering a non-existent handle should not raise."""
        driver, _ = create_test_webdriver()

        # Should not raise
        driver.unregister_monitor_tab('nonexistent')
        assert driver.is_monitor_tab('nonexistent') is False

    @given(
        to_register=st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5, unique=True),
        to_unregister=st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5, unique=True)
    )
    @settings(max_examples=50)
    def test_register_unregister_sequence(self, to_register, to_unregister):
        """Any sequence of register/unregister should maintain consistency."""
        driver, _ = create_test_webdriver()

        for handle in to_register:
            driver.register_monitor_tab(handle)

        for handle in to_unregister:
            driver.unregister_monitor_tab(handle)

        # Expected monitors are those registered but not unregistered
        expected = set(to_register) - set(to_unregister)
        assert driver._monitor_tabs == expected

        for handle in expected:
            assert driver.is_monitor_tab(handle) is True

        for handle in to_unregister:
            if handle not in to_register or handle in to_unregister:
                # If never registered, or was unregistered
                if handle not in (set(to_register) - set(to_unregister)):
                    assert driver.is_monitor_tab(handle) is False
