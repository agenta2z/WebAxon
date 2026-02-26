"""Property-based test for periodic cleanup execution.

This module contains property-based tests using hypothesis to verify
that the SessionMonitor performs periodic cleanup of idle sessions
when the cleanup interval has elapsed.
"""
import sys
import resolve_path  # Setup import paths

import time
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

# Add parent directory to path
from hypothesis import given, strategies as st, settings, assume
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_monitor import AgentSessionMonitor


# Mock queue service for testing
class MockQueueService:
    """Mock queue service for testing."""
    
    def __init__(self):
        self.messages: Dict[str, List[Dict[str, Any]]] = {}
    
    def put(self, queue_id: str, message: Dict[str, Any]) -> None:
        """Store message in the specified queue."""
        if queue_id not in self.messages:
            self.messages[queue_id] = []
        self.messages[queue_id].append(message)
    
    def get(self, queue_id: str, blocking: bool = True) -> Any:
        """Get message from queue (returns None for testing)."""
        return None
    
    def close(self) -> None:
        """Close the queue service."""
        pass


# Feature: web-agent-service-modularization, Property 30: Periodic Cleanup Execution
# Validates: Requirements 8.4
@settings(max_examples=100, deadline=None)
@given(
    # Generate cleanup interval (in seconds)
    cleanup_interval=st.integers(min_value=1, max_value=10),
    # Generate time elapsed since last cleanup
    time_elapsed=st.integers(min_value=0, max_value=20),
    # Generate number of monitoring cycles to run
    num_cycles=st.integers(min_value=1, max_value=5),
)
def test_periodic_cleanup_execution(cleanup_interval, time_elapsed, num_cycles):
    """Property: For any monitoring cycle when the cleanup interval has elapsed,
    idle session cleanup should be performed.
    
    This test verifies that:
    1. Cleanup is performed when time_elapsed >= cleanup_interval
    2. Cleanup is NOT performed when time_elapsed < cleanup_interval
    3. Cleanup updates the last_cleanup_time
    4. Multiple monitoring cycles respect the interval
    5. Cleanup is called on SessionManager.cleanup_idle_sessions()
    6. Errors during cleanup don't crash the monitoring cycle
    
    Test strategy:
    - Create SessionMonitor with specific cleanup_interval
    - Mock time.time() to control elapsed time
    - Run periodic_cleanup() and verify cleanup is called appropriately
    - Test multiple cycles to ensure interval is respected
    - Test error resilience
    """
    # Filter out edge cases
    assume(cleanup_interval >= 1)
    assume(num_cycles >= 1)
    
    # Create temporary directory for logs
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create config with specific cleanup interval
        config = ServiceConfig()
        config.cleanup_check_interval = cleanup_interval
        
        # Create mock queue service
        queue_service = MockQueueService()
        
        # Create session manager
        session_manager = SessionManager(id='test', log_name='Test', logger=[print], always_add_logging_based_logger=False, config=config, queue_service=queue_service, service_log_dir=temp_dir)
        
        # Create mock agent factory
        agent_factory = Mock(spec=AgentFactory)
        
        # Create session monitor
        session_monitor = AgentSessionMonitor(
            session_manager,
            queue_service,
            config,
            agent_factory,
            Mock()
        )
        
        # Mock the cleanup_idle_sessions method to track calls
        cleanup_call_count = 0
        original_cleanup = session_manager.cleanup_idle_sessions
        
        def mock_cleanup():
            nonlocal cleanup_call_count
            cleanup_call_count += 1
            # Call original to ensure it works
            original_cleanup()
        
        session_manager.cleanup_idle_sessions = mock_cleanup
        
        # Test 1: Cleanup should be performed when interval has elapsed
        if time_elapsed >= cleanup_interval:
            # Set the last cleanup time to simulate elapsed time
            session_monitor._last_cleanup_time = time.time() - time_elapsed
            
            # Reset call count
            cleanup_call_count = 0
            
            # Run periodic cleanup
            session_monitor.periodic_cleanup()
            
            # Verify cleanup was called
            assert cleanup_call_count == 1, \
                f"Expected cleanup to be called once when {time_elapsed}s >= {cleanup_interval}s, but was called {cleanup_call_count} times"
            
            # Verify last_cleanup_time was updated
            current_time = time.time()
            time_since_cleanup = current_time - session_monitor._last_cleanup_time
            assert time_since_cleanup < 1.0, \
                f"Expected last_cleanup_time to be updated to current time, but {time_since_cleanup}s have passed"
        
        # Test 2: Cleanup should NOT be performed when interval has not elapsed
        if time_elapsed < cleanup_interval:
            # Set the last cleanup time to simulate elapsed time
            session_monitor._last_cleanup_time = time.time() - time_elapsed
            
            # Reset call count
            cleanup_call_count = 0
            
            # Run periodic cleanup
            session_monitor.periodic_cleanup()
            
            # Verify cleanup was NOT called
            assert cleanup_call_count == 0, \
                f"Expected cleanup NOT to be called when {time_elapsed}s < {cleanup_interval}s, but was called {cleanup_call_count} times"
        
        # Test 3: Multiple monitoring cycles respect the interval
        # Reset to start fresh
        session_monitor._last_cleanup_time = time.time()
        cleanup_call_count = 0
        
        # Run multiple cycles without advancing time
        for i in range(num_cycles):
            session_monitor.periodic_cleanup()
        
        # Cleanup should only be called once (on first cycle if interval elapsed)
        # Since we just reset the time, it shouldn't be called at all
        assert cleanup_call_count == 0, \
            f"Expected cleanup NOT to be called when running {num_cycles} cycles without time advancing"
        
        # Test 4: Cleanup is called after interval in multiple cycles
        cleanup_call_count = 0
        expected_cleanups = 0
        
        for i in range(num_cycles):
            # Advance time by cleanup_interval + 1 second
            session_monitor._last_cleanup_time = time.time() - (cleanup_interval + 1)
            
            # Run periodic cleanup
            session_monitor.periodic_cleanup()
            
            expected_cleanups += 1
        
        # Verify cleanup was called for each cycle where interval elapsed
        assert cleanup_call_count == expected_cleanups, \
            f"Expected cleanup to be called {expected_cleanups} times across {num_cycles} cycles, but was called {cleanup_call_count} times"
        
        # Test 5: Error resilience - cleanup errors don't crash monitoring
        def failing_cleanup():
            raise RuntimeError("Simulated cleanup error")
        
        session_manager.cleanup_idle_sessions = failing_cleanup
        
        # Set time to trigger cleanup
        session_monitor._last_cleanup_time = time.time() - (cleanup_interval + 1)
        
        # This should not raise an exception
        try:
            session_monitor.periodic_cleanup()
            # If we get here, error was handled gracefully
            error_handled = True
        except Exception as e:
            error_handled = False
            raise AssertionError(f"periodic_cleanup should handle errors gracefully, but raised: {e}")
        
        assert error_handled, "periodic_cleanup should handle cleanup errors gracefully"
        
        # Test 6: Verify cleanup is part of run_monitoring_cycle
        # Reset to working cleanup
        session_manager.cleanup_idle_sessions = mock_cleanup
        cleanup_call_count = 0
        
        # Set time to trigger cleanup
        session_monitor._last_cleanup_time = time.time() - (cleanup_interval + 1)
        
        # Run full monitoring cycle
        session_monitor.run_monitoring_cycle()
        
        # Verify cleanup was called as part of the cycle
        assert cleanup_call_count == 1, \
            f"Expected cleanup to be called once during run_monitoring_cycle, but was called {cleanup_call_count} times"
        
        # Test 7: Verify exact interval boundary
        # Test at exactly the interval boundary
        session_monitor._last_cleanup_time = time.time() - cleanup_interval
        cleanup_call_count = 0
        
        session_monitor.periodic_cleanup()
        
        # At exactly the interval, cleanup should be performed (>=)
        assert cleanup_call_count == 1, \
            f"Expected cleanup to be called when elapsed time equals interval exactly"
        
        # Test just before the interval
        session_monitor._last_cleanup_time = time.time() - (cleanup_interval - 0.1)
        cleanup_call_count = 0
        
        session_monitor.periodic_cleanup()
        
        # Just before interval, cleanup should NOT be performed
        assert cleanup_call_count == 0, \
            f"Expected cleanup NOT to be called when elapsed time is just before interval"
    
    finally:
        # Cleanup temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors


if __name__ == '__main__':
    print("Running property-based test for periodic cleanup execution...")
    print("Testing with 100 random configurations...")
    print()
    
    try:
        test_periodic_cleanup_execution()
        print("✓ Property test passed: Periodic cleanup execution verified")
        print("  Cleanup is performed when interval has elapsed")
        print("  Cleanup is NOT performed when interval has not elapsed")
        print("  last_cleanup_time is updated after cleanup")
        print("  Multiple monitoring cycles respect the interval")
        print("  cleanup_idle_sessions() is called on SessionManager")
        print("  Errors during cleanup are handled gracefully")
        print("  Cleanup is part of run_monitoring_cycle()")
        print("  Exact interval boundary is handled correctly")
        print()
        print("  Test parameters varied:")
        print("    - Cleanup interval: 1 to 10 seconds")
        print("    - Time elapsed: 0 to 20 seconds")
        print("    - Number of cycles: 1 to 5")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("All property-based tests passed! ✓")
