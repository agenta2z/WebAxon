"""
Test cleanup functionality for ActionTesterManager.

Verifies that the browser is properly terminated when the application exits.
"""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch, MagicMock
import importlib

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add WebAgent/src to path
webagent_src = project_root / "WebAgent" / "src"
if str(webagent_src) not in sys.path:
    sys.path.insert(0, str(webagent_src))


class TestActionTesterCleanup(unittest.TestCase):
    """Test cleanup functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear any previously imported modules
        if 'webaxon.devsuite.agent_debugger_nextgen.action_tester.manager' in sys.modules:
            del sys.modules['webaxon.devsuite.agent_debugger_nextgen.action_tester.manager']
    
    def tearDown(self):
        """Clean up."""
        pass
    
    def test_cleanup_registered_on_init(self):
        """Test that cleanup handler is registered with atexit on initialization."""
        with patch('atexit.register') as mock_register:
            # Import after patching
            from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
            
            manager = ActionTesterManager()
            
            # Verify atexit.register was called with the cleanup method
            self.assertTrue(mock_register.called)
            # Find the call that registered _cleanup
            cleanup_registered = False
            for call in mock_register.call_args_list:
                if call[0] and hasattr(call[0][0], '__name__') and call[0][0].__name__ == '_cleanup':
                    cleanup_registered = True
                    break
            self.assertTrue(cleanup_registered, "Cleanup method should be registered with atexit")
    
    def test_cleanup_terminates_browser_gracefully(self):
        """Test that cleanup terminates browser gracefully when driver exists."""
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        
        manager = ActionTesterManager()
        
        # Create a mock driver
        mock_driver = Mock()
        manager.driver = mock_driver
        manager.is_browser_active = True
        manager.tests = {'test1': Mock()}
        manager.active_test_id = 'test1'
        
        # Call cleanup
        manager._cleanup()
        
        # Verify driver.quit() was called
        mock_driver.quit.assert_called_once()
        
        # Verify state was cleared
        self.assertIsNone(manager.driver)
        self.assertFalse(manager.is_browser_active)
        self.assertEqual(len(manager.tests), 0)
        self.assertIsNone(manager.active_test_id)
    
    def test_cleanup_handles_quit_failure(self):
        """Test that cleanup handles graceful shutdown failure and tries force kill."""
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        
        manager = ActionTesterManager()
        
        # Create a mock driver that fails on quit
        mock_driver = Mock()
        mock_driver.quit.side_effect = Exception("Quit failed")
        
        # Create mock process
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is still running
        mock_driver.service = Mock()
        mock_driver.service.process = mock_process
        
        manager.driver = mock_driver
        manager.is_browser_active = True
        
        # Call cleanup
        manager._cleanup()
        
        # Verify quit was attempted
        mock_driver.quit.assert_called_once()
        
        # Verify force termination was attempted
        mock_process.terminate.assert_called_once()
        
        # Verify state was cleared even after failure
        self.assertIsNone(manager.driver)
        self.assertFalse(manager.is_browser_active)
    
    def test_cleanup_handles_force_kill_when_terminate_fails(self):
        """Test that cleanup tries kill() if terminate() doesn't stop the process."""
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        
        manager = ActionTesterManager()
        
        # Create a mock driver that fails on quit
        mock_driver = Mock()
        mock_driver.quit.side_effect = Exception("Quit failed")
        
        # Create mock process that doesn't terminate
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is still running after terminate
        mock_driver.service = Mock()
        mock_driver.service.process = mock_process
        
        manager.driver = mock_driver
        
        # Call cleanup
        with patch('time.sleep'):  # Mock sleep to speed up test
            manager._cleanup()
        
        # Verify terminate and kill were both called
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        
        # Verify state was cleared
        self.assertIsNone(manager.driver)
    
    def test_cleanup_does_nothing_when_no_driver(self):
        """Test that cleanup does nothing when no driver exists."""
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        
        manager = ActionTesterManager()
        manager.driver = None
        
        # Call cleanup - should not raise any errors
        manager._cleanup()
        
        # Verify state remains clean
        self.assertIsNone(manager.driver)
        self.assertFalse(manager.is_browser_active)
    
    def test_cleanup_handles_all_exceptions_gracefully(self):
        """Test that cleanup handles all exceptions without crashing."""
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager
        
        manager = ActionTesterManager()
        
        # Create a mock driver that fails on everything
        mock_driver = Mock()
        mock_driver.quit.side_effect = Exception("Quit failed")
        mock_driver.service = Mock()
        mock_driver.service.process = None  # No process to kill
        
        manager.driver = mock_driver
        
        # Call cleanup - should not raise any errors
        try:
            manager._cleanup()
        except Exception as e:
            self.fail(f"Cleanup raised an exception: {e}")
        
        # Verify state was cleared
        self.assertIsNone(manager.driver)
        self.assertFalse(manager.is_browser_active)


if __name__ == '__main__':
    unittest.main()
