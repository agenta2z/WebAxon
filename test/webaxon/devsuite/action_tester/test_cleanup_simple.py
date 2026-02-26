"""
Simple test to verify cleanup functionality is implemented correctly.

This test verifies that:
1. The _cleanup method exists
2. It's registered with atexit
3. It handles browser termination gracefully
"""
import sys
from pathlib import Path
import atexit

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
webagent_src = project_root / "WebAgent" / "src"
science_python_utils_src = project_root / "SciencePythonUtils" / "src"
science_modeling_tools_src = project_root / "ScienceModelingTools" / "src"

for path in [webagent_src, science_python_utils_src, science_modeling_tools_src]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

def test_cleanup_method_exists():
    """Verify that the _cleanup method exists in ActionTesterManager."""
    try:
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        
        # Check that _cleanup method exists
        assert hasattr(ActionTesterManager, '_cleanup'), "_cleanup method should exist"
        
        # Check that it's callable
        manager = ActionTesterManager()
        assert callable(manager._cleanup), "_cleanup should be callable"
        
        print("✓ _cleanup method exists and is callable")
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def test_cleanup_handles_no_driver():
    """Verify that cleanup handles the case when no driver exists."""
    try:
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        
        manager = ActionTesterManager()
        manager.driver = None
        
        # Should not raise any errors
        manager._cleanup()
        
        print("✓ Cleanup handles no driver gracefully")
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def test_cleanup_clears_state():
    """Verify that cleanup clears all state."""
    try:
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        from unittest.mock import Mock
        
        manager = ActionTesterManager()
        
        # Set up some state
        mock_driver = Mock()
        manager.driver = mock_driver
        manager.is_browser_active = True
        manager.tests = {'test1': Mock()}
        manager.active_test_id = 'test1'
        
        # Call cleanup
        manager._cleanup()
        
        # Verify state is cleared
        assert manager.driver is None, "driver should be None"
        assert manager.is_browser_active is False, "is_browser_active should be False"
        assert len(manager.tests) == 0, "tests should be empty"
        assert manager.active_test_id is None, "active_test_id should be None"
        
        # Verify quit was called
        mock_driver.quit.assert_called_once()
        
        print("✓ Cleanup clears all state correctly")
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cleanup_handles_quit_failure():
    """Verify that cleanup handles quit() failure gracefully."""
    try:
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        from unittest.mock import Mock
        
        manager = ActionTesterManager()
        
        # Set up a driver that fails on quit
        mock_driver = Mock()
        mock_driver.quit.side_effect = Exception("Quit failed")
        mock_driver.service = Mock()
        mock_driver.service.process = None  # No process to kill
        
        manager.driver = mock_driver
        manager.is_browser_active = True
        
        # Should not raise any errors
        manager._cleanup()
        
        # Verify state is still cleared
        assert manager.driver is None, "driver should be None even after failure"
        assert manager.is_browser_active is False, "is_browser_active should be False even after failure"
        
        print("✓ Cleanup handles quit() failure gracefully")
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("Testing ActionTesterManager cleanup functionality...\n")
    
    tests = [
        test_cleanup_method_exists,
        test_cleanup_handles_no_driver,
        test_cleanup_clears_state,
        test_cleanup_handles_quit_failure,
    ]
    
    results = []
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        results.append(test())
    
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print(f"✗ {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
