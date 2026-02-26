"""
Unit Tests for WebDriver Monitor Tab Tracking

Tests the monitor tab tracking functionality in WebDriver:
- register_monitor_tab()
- unregister_monitor_tab()
- is_monitor_tab()
- get_action_tabs()
- get_monitor_tabs()
- switch_to_action_tab()

These tests use mocked Selenium driver to isolate WebDriver behavior.

**Feature: monitor-action**
**Requirements: 2.3, 4.4, 4.5**
"""

# Path resolution - must be first
import sys
from pathlib import Path

# Configuration
PIVOT_FOLDER_NAME = 'test'  # The folder name we're inside of

# Get absolute path to this file
current_file = Path(__file__).resolve()

# Navigate up to find the pivot folder (test directory)
current_path = current_file.parent
while current_path.name != PIVOT_FOLDER_NAME and current_path.parent != current_path:
    current_path = current_path.parent

if current_path.name != PIVOT_FOLDER_NAME:
    raise RuntimeError(f"Could not find '{PIVOT_FOLDER_NAME}' folder in path hierarchy")

# WebAgent root is parent of test/ directory
webagent_root = current_path.parent

# Add src directory to path for webaxon imports
src_dir = webagent_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Add science packages if they exist (for tests that need them)
projects_root = webagent_root.parent
science_python_utils_src = projects_root / "SciencePythonUtils" / "src"
science_modeling_tools_src = projects_root / "ScienceModelingTools" / "src"

for path_item in [science_python_utils_src, science_modeling_tools_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# Test Fixtures
# =============================================================================

def create_test_webdriver_with_tabs(tab_handles=None):
    """
    Create a WebDriver instance with mocked Selenium driver for testing.
    
    Args:
        tab_handles: List of window handles to simulate. Defaults to ['tab1', 'tab2', 'tab3']
    
    Returns:
        Tuple of (WebDriver instance, mock Selenium driver)
    """
    from webaxon.automation.web_driver import WebDriver
    
    if tab_handles is None:
        tab_handles = ['tab1', 'tab2', 'tab3']
    
    mock_selenium_driver = MagicMock()
    mock_selenium_driver.window_handles = tab_handles
    mock_selenium_driver.current_window_handle = tab_handles[0] if tab_handles else None
    
    with patch('webaxon.automation.web_driver.get_driver', return_value=mock_selenium_driver):
        webdriver = WebDriver.__new__(WebDriver)
        webdriver._driver = mock_selenium_driver
        webdriver._action_configs = {}
        webdriver._window_infos = {}
        webdriver._state = None
        webdriver.state_setting_max_retry = 3
        webdriver.state_setting_retry_wait = 0.2
        webdriver._id = "test-webdriver"
        webdriver._log_level = 0
        webdriver._monitor_tabs = set()  # Initialize monitor tabs tracking
    
    return webdriver, mock_selenium_driver


# =============================================================================
# Task 6.1: Test register_monitor_tab() adds handle to tracking set
# =============================================================================

class TestRegisterMonitorTab:
    """Tests for register_monitor_tab() method."""
    
    def test_register_adds_handle_to_set(self):
        """register_monitor_tab() should add the handle to _monitor_tabs set."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        webdriver.register_monitor_tab('monitor_tab_1')
        
        assert 'monitor_tab_1' in webdriver._monitor_tabs
    
    def test_register_multiple_handles(self):
        """register_monitor_tab() should allow registering multiple handles."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        webdriver.register_monitor_tab('monitor_tab_1')
        webdriver.register_monitor_tab('monitor_tab_2')
        
        assert 'monitor_tab_1' in webdriver._monitor_tabs
        assert 'monitor_tab_2' in webdriver._monitor_tabs
        assert len(webdriver._monitor_tabs) == 2
    
    def test_register_same_handle_twice_is_idempotent(self):
        """Registering the same handle twice should not create duplicates."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        webdriver.register_monitor_tab('monitor_tab_1')
        webdriver.register_monitor_tab('monitor_tab_1')
        
        assert len(webdriver._monitor_tabs) == 1


# =============================================================================
# Task 6.2: Test unregister_monitor_tab() removes handle from tracking set
# =============================================================================

class TestUnregisterMonitorTab:
    """Tests for unregister_monitor_tab() method."""
    
    def test_unregister_removes_handle_from_set(self):
        """unregister_monitor_tab() should remove the handle from _monitor_tabs set."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        webdriver.register_monitor_tab('monitor_tab_1')
        webdriver.unregister_monitor_tab('monitor_tab_1')
        
        assert 'monitor_tab_1' not in webdriver._monitor_tabs
    
    def test_unregister_nonexistent_handle_is_safe(self):
        """unregister_monitor_tab() should not raise error for non-existent handle."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        # Should not raise any exception
        webdriver.unregister_monitor_tab('nonexistent_handle')
        
        assert len(webdriver._monitor_tabs) == 0
    
    def test_unregister_leaves_other_handles(self):
        """unregister_monitor_tab() should only remove the specified handle."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        webdriver.register_monitor_tab('monitor_tab_1')
        webdriver.register_monitor_tab('monitor_tab_2')
        webdriver.unregister_monitor_tab('monitor_tab_1')
        
        assert 'monitor_tab_1' not in webdriver._monitor_tabs
        assert 'monitor_tab_2' in webdriver._monitor_tabs


# =============================================================================
# Task 6.3: Test is_monitor_tab() returns correct boolean
# =============================================================================

class TestIsMonitorTab:
    """Tests for is_monitor_tab() method."""
    
    def test_returns_true_for_registered_tab(self):
        """is_monitor_tab() should return True for registered monitor tabs."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        webdriver.register_monitor_tab('monitor_tab_1')
        
        assert webdriver.is_monitor_tab('monitor_tab_1') is True
    
    def test_returns_false_for_unregistered_tab(self):
        """is_monitor_tab() should return False for non-monitor tabs."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        assert webdriver.is_monitor_tab('regular_tab') is False
    
    def test_returns_false_after_unregister(self):
        """is_monitor_tab() should return False after tab is unregistered."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        webdriver.register_monitor_tab('monitor_tab_1')
        webdriver.unregister_monitor_tab('monitor_tab_1')
        
        assert webdriver.is_monitor_tab('monitor_tab_1') is False


# =============================================================================
# Task 6.4: Test get_action_tabs() excludes monitor tabs
# =============================================================================

class TestGetActionTabs:
    """Tests for get_action_tabs() method."""
    
    def test_returns_all_tabs_when_no_monitors(self):
        """get_action_tabs() should return all tabs when no monitor tabs registered."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1', 'tab2', 'tab3'])
        
        action_tabs = webdriver.get_action_tabs()
        
        assert action_tabs == ['tab1', 'tab2', 'tab3']
    
    def test_excludes_monitor_tabs(self):
        """get_action_tabs() should exclude registered monitor tabs."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1', 'tab2', 'tab3'])
        
        webdriver.register_monitor_tab('tab2')
        action_tabs = webdriver.get_action_tabs()
        
        assert action_tabs == ['tab1', 'tab3']
        assert 'tab2' not in action_tabs
    
    def test_excludes_multiple_monitor_tabs(self):
        """get_action_tabs() should exclude all registered monitor tabs."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1', 'tab2', 'tab3', 'tab4'])
        
        webdriver.register_monitor_tab('tab2')
        webdriver.register_monitor_tab('tab4')
        action_tabs = webdriver.get_action_tabs()
        
        assert action_tabs == ['tab1', 'tab3']
    
    def test_returns_empty_when_all_are_monitors(self):
        """get_action_tabs() should return empty list when all tabs are monitors."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1', 'tab2'])
        
        webdriver.register_monitor_tab('tab1')
        webdriver.register_monitor_tab('tab2')
        action_tabs = webdriver.get_action_tabs()
        
        assert action_tabs == []


# =============================================================================
# Task 6.5: Test get_monitor_tabs() returns only monitor tabs
# =============================================================================

class TestGetMonitorTabs:
    """Tests for get_monitor_tabs() method."""
    
    def test_returns_empty_when_no_monitors(self):
        """get_monitor_tabs() should return empty list when no monitors registered."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        monitor_tabs = webdriver.get_monitor_tabs()
        
        assert monitor_tabs == []
    
    def test_returns_registered_monitor_tabs(self):
        """get_monitor_tabs() should return all registered monitor tabs."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        webdriver.register_monitor_tab('monitor1')
        webdriver.register_monitor_tab('monitor2')
        monitor_tabs = webdriver.get_monitor_tabs()
        
        assert set(monitor_tabs) == {'monitor1', 'monitor2'}
    
    def test_returns_list_not_set(self):
        """get_monitor_tabs() should return a list, not a set."""
        webdriver, _ = create_test_webdriver_with_tabs()
        
        webdriver.register_monitor_tab('monitor1')
        monitor_tabs = webdriver.get_monitor_tabs()
        
        assert isinstance(monitor_tabs, list)


# =============================================================================
# Task 6.6: Test switch_to_action_tab() raises ValueError for monitor tab handle
# =============================================================================

class TestSwitchToActionTabRaisesError:
    """Tests for switch_to_action_tab() error handling."""
    
    def test_raises_valueerror_for_monitor_tab(self):
        """switch_to_action_tab() should raise ValueError when given a monitor tab handle."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1', 'tab2'])
        
        webdriver.register_monitor_tab('tab2')
        
        with pytest.raises(ValueError) as exc_info:
            webdriver.switch_to_action_tab('tab2')
        
        assert 'monitor tab' in str(exc_info.value).lower()
        assert 'tab2' in str(exc_info.value)
    
    def test_raises_valueerror_when_no_action_tabs(self):
        """switch_to_action_tab() should raise ValueError when no action tabs available."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1'])
        
        webdriver.register_monitor_tab('tab1')
        
        with pytest.raises(ValueError) as exc_info:
            webdriver.switch_to_action_tab()
        
        assert 'no action tabs' in str(exc_info.value).lower()


# =============================================================================
# Task 6.7: Test switch_to_action_tab() with None uses first action tab
# =============================================================================

class TestSwitchToActionTabWithNone:
    """Tests for switch_to_action_tab() with None parameter."""
    
    def test_switches_to_first_action_tab(self):
        """switch_to_action_tab(None) should switch to first available action tab."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1', 'tab2', 'tab3'])
        
        result = webdriver.switch_to_action_tab()
        
        mock_driver.switch_to.window.assert_called_once_with('tab1')
        assert result == 'tab1'
    
    def test_skips_monitor_tabs_when_finding_first(self):
        """switch_to_action_tab(None) should skip monitor tabs when finding first action tab."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1', 'tab2', 'tab3'])
        
        webdriver.register_monitor_tab('tab1')
        result = webdriver.switch_to_action_tab()
        
        mock_driver.switch_to.window.assert_called_once_with('tab2')
        assert result == 'tab2'
    
    def test_switches_to_specific_action_tab(self):
        """switch_to_action_tab(handle) should switch to the specified action tab."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1', 'tab2', 'tab3'])
        
        result = webdriver.switch_to_action_tab('tab3')
        
        mock_driver.switch_to.window.assert_called_once_with('tab3')
        assert result == 'tab3'
    
    def test_returns_handle_of_switched_tab(self):
        """switch_to_action_tab() should return the handle of the tab switched to."""
        webdriver, mock_driver = create_test_webdriver_with_tabs(['tab1', 'tab2'])
        
        result = webdriver.switch_to_action_tab('tab2')
        
        assert result == 'tab2'
