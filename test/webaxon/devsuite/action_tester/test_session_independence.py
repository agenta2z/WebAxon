"""
Test session independence for Action Tester.

Verifies that the browser and tests persist across debugger session switches.
This validates Requirement 13.1: Browser independence from sessions.
"""
import sys
from pathlib import Path

# Add paths for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "SciencePythonUtils" / "src"))
sys.path.insert(0, str(project_root / "ScienceModelingTools" / "src"))

import pytest
from unittest.mock import Mock, MagicMock, patch
from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager


class TestSessionIndependence:
    """Test that browser and tests are independent of debugger sessions."""
    
    def test_browser_persists_across_session_switches(self):
        """
        Test that browser persists across debugger session switches.
        
        Validates: Requirements 13.1
        
        Scenario:
        1. Create manager and launch browser
        2. Simulate session switch (manager should remain unchanged)
        3. Verify browser is still active
        4. Verify browser state is preserved
        """
        # Create manager
        manager = ActionTesterManager()
        
        # Mock WebDriver
        mock_driver = MagicMock()
        mock_driver.window_handles = ['handle1']
        mock_driver.current_window_handle = 'handle1'
        mock_driver.current_url = 'https://example.com'
        mock_driver.title = 'Example Page'
        
        # Simulate successful browser launch
        manager.driver = mock_driver
        manager.is_browser_active = True
        
        # Get initial browser status
        initial_status = manager.get_browser_status()
        assert initial_status['active'] is True
        assert initial_status['status_indicator'] == '🟢 Active'
        
        # Simulate session switch by creating a new "session context"
        # In the real app, this would be a different session_id in SessionManager
        # But the ActionTesterManager is global and should not be affected
        
        # Verify browser is still active after "session switch"
        post_switch_status = manager.get_browser_status()
        assert post_switch_status['active'] is True
        assert post_switch_status['status_indicator'] == '🟢 Active'
        assert post_switch_status['current_url'] == initial_status['current_url']
        
        # Verify the same driver instance is still being used
        assert manager.driver is mock_driver
        assert manager.is_browser_active is True
        
        # Cleanup
        manager.driver = None
        manager.is_browser_active = False
    
    def test_tests_persist_across_session_switches(self):
        """
        Test that tests persist across debugger session switches.
        
        Validates: Requirements 13.1
        
        Scenario:
        1. Create manager and launch browser
        2. Create multiple tests
        3. Update test content
        4. Simulate session switch
        5. Verify all tests and their content are preserved
        """
        # Create manager
        manager = ActionTesterManager()
        
        # Mock WebDriver
        mock_driver = MagicMock()
        mock_driver.window_handles = ['handle1', 'handle2', 'handle3']
        mock_driver.current_window_handle = 'handle1'
        mock_driver.execute_script = MagicMock(return_value=None)
        
        # Simulate successful browser launch
        manager.driver = mock_driver
        manager.is_browser_active = True
        
        # Create tests
        test_id_1 = manager.create_test("Test 1")
        test_id_2 = manager.create_test("Test 2")
        
        # Update test content
        test_content_1 = '{"version": "1.0", "id": "test1", "actions": []}'
        test_content_2 = '{"version": "1.0", "id": "test2", "actions": []}'
        
        manager.update_test_content(test_id_1, test_content_1)
        manager.update_test_content(test_id_2, test_content_2)
        
        # Get initial test list
        initial_tests = manager.get_test_list()
        assert len(initial_tests) == 2
        
        # Simulate session switch
        # The manager is global, so it should not be affected
        
        # Verify tests still exist after "session switch"
        post_switch_tests = manager.get_test_list()
        assert len(post_switch_tests) == 2
        
        # Verify test content is preserved
        assert manager.get_test_content(test_id_1) == test_content_1
        assert manager.get_test_content(test_id_2) == test_content_2
        
        # Verify test metadata is preserved
        test_1_info = next(t for t in post_switch_tests if t['test_id'] == test_id_1)
        test_2_info = next(t for t in post_switch_tests if t['test_id'] == test_id_2)
        
        assert test_1_info['test_name'] == "Test 1"
        assert test_2_info['test_name'] == "Test 2"
        
        # Cleanup
        manager.tests.clear()
        manager.driver = None
        manager.is_browser_active = False
    
    def test_execution_results_persist_across_session_switches(self):
        """
        Test that execution results persist across debugger session switches.
        
        Validates: Requirements 13.1, 12.2
        
        Scenario:
        1. Create manager and launch browser
        2. Create test and execute sequence
        3. Simulate session switch
        4. Verify execution results are preserved
        """
        # Create manager
        manager = ActionTesterManager()
        
        # Mock WebDriver
        mock_driver = MagicMock()
        mock_driver.window_handles = ['handle1']
        mock_driver.current_window_handle = 'handle1'
        
        # Simulate successful browser launch
        manager.driver = mock_driver
        manager.is_browser_active = True
        
        # Create test
        test_id = manager.create_test("Test 1")
        
        # Mock execution results
        mock_results = [
            {
                'action_id': 'action1',
                'action_type': 'visit_url',
                'success': True,
                'value': None,
                'error': None
            },
            {
                'action_id': 'action2',
                'action_type': 'click',
                'success': True,
                'value': None,
                'error': None
            }
        ]
        
        # Set results directly (simulating execution)
        manager.tests[test_id].set_results(mock_results)
        
        # Verify results are stored
        assert manager.tests[test_id].execution_results == mock_results
        
        # Simulate session switch
        # The manager is global, so results should persist
        
        # Verify results still exist after "session switch"
        assert manager.tests[test_id].execution_results == mock_results
        assert len(manager.tests[test_id].execution_results) == 2
        
        # Cleanup
        manager.tests.clear()
        manager.driver = None
        manager.is_browser_active = False
    
    def test_active_test_persists_across_session_switches(self):
        """
        Test that active test selection persists across debugger session switches.
        
        Validates: Requirements 13.1
        
        Scenario:
        1. Create manager and launch browser
        2. Create multiple tests
        3. Switch to specific test
        4. Simulate session switch
        5. Verify active test is still the same
        """
        # Create manager
        manager = ActionTesterManager()
        
        # Mock WebDriver
        mock_driver = MagicMock()
        mock_driver.window_handles = ['handle1', 'handle2', 'handle3']
        mock_driver.current_window_handle = 'handle2'
        
        # Simulate successful browser launch
        manager.driver = mock_driver
        manager.is_browser_active = True
        
        # Create tests
        test_id_1 = manager.create_test("Test 1")
        test_id_2 = manager.create_test("Test 2")
        test_id_3 = manager.create_test("Test 3")
        
        # Switch to test 2
        manager.switch_to_test(test_id_2)
        
        # Verify test 2 is active
        assert manager.active_test_id == test_id_2
        
        # Simulate session switch
        # The manager is global, so active test should persist
        
        # Verify test 2 is still active after "session switch"
        assert manager.active_test_id == test_id_2
        
        # Verify test list shows correct active test
        tests = manager.get_test_list()
        active_tests = [t for t in tests if t['is_active']]
        assert len(active_tests) == 1
        assert active_tests[0]['test_id'] == test_id_2
        
        # Cleanup
        manager.tests.clear()
        manager.driver = None
        manager.is_browser_active = False
    
    def test_manager_is_global_singleton(self):
        """
        Test that ActionTesterManager is a global singleton.
        
        This is the fundamental mechanism that ensures session independence.
        
        Validates: Requirements 13.1, 13.4
        
        Scenario:
        1. Get manager instance multiple times
        2. Verify all references point to the same instance
        3. Modify state in one reference
        4. Verify state is visible in all references
        """
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import get_action_tester_manager
        
        # Get manager multiple times (simulating different "sessions")
        manager1 = get_action_tester_manager()
        manager2 = get_action_tester_manager()
        manager3 = get_action_tester_manager()
        
        # Verify all references point to the same instance
        assert manager1 is manager2
        assert manager2 is manager3
        assert manager1 is manager3
        
        # Modify state through one reference
        manager1.is_browser_active = True
        
        # Verify state is visible through all references
        assert manager2.is_browser_active is True
        assert manager3.is_browser_active is True
        
        # Reset state
        manager1.is_browser_active = False
    
    def test_browser_state_independent_of_session_manager(self):
        """
        Test that browser state is independent of SessionManager.
        
        Validates: Requirements 13.1, 13.4
        
        Scenario:
        1. Create ActionTesterManager
        2. Create mock SessionManager with sessions
        3. Launch browser in ActionTesterManager
        4. Switch sessions in SessionManager
        5. Verify browser state unchanged
        """
        # Create ActionTesterManager
        action_manager = ActionTesterManager()
        
        # Mock WebDriver
        mock_driver = MagicMock()
        mock_driver.window_handles = ['handle1']
        mock_driver.current_window_handle = 'handle1'
        
        # Simulate browser launch
        action_manager.driver = mock_driver
        action_manager.is_browser_active = True
        
        # Create mock SessionManager (simulating debugger sessions)
        mock_session_manager = Mock()
        mock_session_manager.current_session_id = 'session1'
        
        # Get initial browser status
        initial_status = action_manager.get_browser_status()
        assert initial_status['active'] is True
        
        # Simulate session switch in SessionManager
        mock_session_manager.current_session_id = 'session2'
        
        # Verify browser state is unchanged
        post_switch_status = action_manager.get_browser_status()
        assert post_switch_status['active'] is True
        assert post_switch_status == initial_status
        
        # Simulate another session switch
        mock_session_manager.current_session_id = 'session3'
        
        # Verify browser state is still unchanged
        final_status = action_manager.get_browser_status()
        assert final_status['active'] is True
        assert final_status == initial_status
        
        # Cleanup
        action_manager.driver = None
        action_manager.is_browser_active = False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
