"""
Test sidebar test list callbacks for Action Tester.

Verifies that the sidebar test list functionality works correctly.
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


class TestSidebarCallbacks:
    """Test sidebar test list callbacks."""
    
    def test_create_test_list_panel_empty(self):
        """Test creating test list panel with no tests."""
        from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_test_list_panel
        
        panel = create_test_list_panel([], None)
        assert panel is not None
        # Should have the "No tests" message
        assert len(panel.children) >= 1
    
    def test_create_test_list_panel_with_tests(self):
        """Test creating test list panel with tests."""
        from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_test_list_panel
        
        tests = [
            {
                'test_id': 'test1',
                'test_name': 'Test 1',
                'is_active': True,
                'created_at': '2024-01-01 10:00:00'
            },
            {
                'test_id': 'test2', 
                'test_name': 'Test 2',
                'is_active': False,
                'created_at': '2024-01-01 11:00:00'
            }
        ]
        
        panel = create_test_list_panel(tests, 'test1')
        assert panel is not None
        # Should have test items
        assert len(panel.children) >= 2
    
    def test_test_list_panel_has_pattern_matching_ids(self):
        """Test that test list panel creates pattern-matching IDs for callbacks."""
        from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_test_list_panel
        
        tests = [
            {
                'test_id': 'test1',
                'test_name': 'Test 1', 
                'is_active': True,
                'created_at': '2024-01-01 10:00:00'
            }
        ]
        
        panel = create_test_list_panel(tests, 'test1')
        
        # Search for pattern-matching IDs in the component tree
        found_test_item = False
        found_close_btn = False
        
        def search_component(component):
            nonlocal found_test_item, found_close_btn
            if hasattr(component, 'id'):
                comp_id = component.id
                if isinstance(comp_id, dict):
                    if comp_id.get('type') == 'test-item':
                        found_test_item = True
                    elif comp_id.get('type') == 'test-close-btn':
                        found_close_btn = True
            if hasattr(component, 'children'):
                children = component.children
                if isinstance(children, list):
                    for child in children:
                        search_component(child)
                elif children is not None:
                    search_component(children)
        
        search_component(panel)
        
        assert found_test_item, "Should have test-item pattern-matching ID"
        assert found_close_btn, "Should have test-close-btn pattern-matching ID"
    
    def test_manager_close_test_method_exists(self):
        """Test that ActionTesterManager has close_test method."""
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        
        manager = ActionTesterManager()
        
        # Create a test first
        mock_driver = MagicMock()
        mock_driver.window_handles = ['handle1']
        mock_driver.execute_script = MagicMock(return_value=None)
        
        manager.driver = mock_driver
        manager.is_browser_active = True
        
        test_id = manager.create_test("Test 1")
        
        # Verify close_test method exists and works
        assert hasattr(manager, 'close_test'), "Manager should have close_test method"
        
        # Close the test
        manager.close_test(test_id)
        
        # Test should be removed
        tests = manager.get_test_list()
        assert len(tests) == 0
        
        # Cleanup
        manager.tests.clear()
        manager.driver = None
        manager.is_browser_active = False
    
    def test_manager_get_test_list_returns_correct_format(self):
        """Test that get_test_list returns the expected format for the UI."""
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        
        manager = ActionTesterManager()
        
        # Create tests
        mock_driver = MagicMock()
        mock_driver.window_handles = ['handle1', 'handle2']
        mock_driver.execute_script = MagicMock(return_value=None)
        
        manager.driver = mock_driver
        manager.is_browser_active = True
        
        test_id1 = manager.create_test("Test 1")
        test_id2 = manager.create_test("Test 2")
        
        # Switch to test 2
        manager.switch_to_test(test_id2)
        
        # Get test list
        tests = manager.get_test_list()
        
        assert len(tests) == 2
        
        # Check format
        for test in tests:
            assert 'test_id' in test
            assert 'test_name' in test
            assert 'is_active' in test
            assert 'created_at' in test
        
        # Check active test
        active_tests = [t for t in tests if t['is_active']]
        assert len(active_tests) == 1
        assert active_tests[0]['test_id'] == test_id2
        
        # Cleanup
        manager.tests.clear()
        manager.driver = None
        manager.is_browser_active = False
    
    def test_test_list_container_exists_in_layout(self):
        """Test that the test list container exists in the main layout."""
        from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_action_tester_tab_layout
        
        layout = create_action_tester_tab_layout()
        
        # Search for the test list container in the component tree
        found_test_list_container = False
        
        def search_component(component, target_id):
            nonlocal found_test_list_container
            if hasattr(component, 'id') and component.id == target_id:
                found_test_list_container = True
                return
            if hasattr(component, 'children'):
                children = component.children
                if isinstance(children, list):
                    for child in children:
                        search_component(child, target_id)
                elif children is not None:
                    search_component(children, target_id)
        
        search_component(layout, 'action-tester-test-list')
        
        assert found_test_list_container, "Layout should contain action-tester-test-list container"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
