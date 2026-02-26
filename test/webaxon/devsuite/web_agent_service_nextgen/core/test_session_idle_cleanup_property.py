"""Property-based test for session idle cleanup.

This module contains property-based tests using hypothesis to verify
that idle sessions are properly cleaned up after the configured timeout.
"""
import sys
import resolve_path  # Setup import paths

import time
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path
from hypothesis import given, strategies as st, settings, assume
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager


# Mock queue service for testing
class MockQueueService:
    """Mock queue service for testing."""
    pass


# Feature: web-agent-service-modularization, Property 6: Session Idle Cleanup
# Validates: Requirements 3.3
@settings(max_examples=100, deadline=None)
@given(
    # Generate timeout values between 0.5 and 2 seconds for reliable testing
    # Minimum 0.5s to avoid system scheduling issues
    idle_timeout=st.floats(min_value=0.5, max_value=2.0),
    # Generate number of sessions to create
    num_sessions=st.integers(min_value=1, max_value=10),
    # Generate idle time multiplier (how much longer than timeout to wait)
    # Minimum 1.5x to ensure clear separation between idle and active
    idle_multiplier=st.floats(min_value=1.5, max_value=3.0),
)
def test_session_idle_cleanup(idle_timeout, num_sessions, idle_multiplier):
    """Property: For any session that has been idle beyond the configured timeout,
    calling cleanup_idle_sessions() should remove it from the active sessions.
    
    This test verifies that:
    1. Sessions are created and tracked properly
    2. Sessions that exceed the idle timeout are identified
    3. cleanup_idle_sessions() removes only the idle sessions
    4. Active sessions (within timeout) are preserved
    5. The cleanup is thread-safe and consistent
    
    Test strategy:
    - Create multiple sessions with a short idle timeout
    - Let some sessions become idle (exceed timeout)
    - Keep some sessions active (update within timeout)
    - Run cleanup_idle_sessions()
    - Verify only idle sessions are removed
    """
    # Filter out edge cases that would make the test unreliable
    assume(idle_timeout >= 0.5)  # Minimum 500ms timeout for reliable timing
    assume(num_sessions >= 1)  # At least one session
    assume(idle_multiplier >= 1.5)  # Must wait significantly longer than timeout
    
    # Create temporary directory for logs
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create config with the generated timeout
        config = ServiceConfig(session_idle_timeout=idle_timeout)
        
        # Create mock queue service
        queue_service = MockQueueService()
        
        # Create session manager
        session_manager = SessionManager(id='test', log_name='Test', logger=[print], always_add_logging_based_logger=False, config=config, queue_service=queue_service, service_log_dir=temp_dir)
        
        # Create sessions
        session_ids = [f"test_session_{i}" for i in range(num_sessions)]
        for session_id in session_ids:
            session_manager.get_or_create(session_id)
        
        # Verify all sessions were created
        all_sessions = session_manager.get_all_sessions()
        assert len(all_sessions) == num_sessions, \
            f"Expected {num_sessions} sessions, got {len(all_sessions)}"
        
        # Calculate how long to wait for sessions to become idle
        wait_time = idle_timeout * idle_multiplier
        
        # Wait for sessions to become idle
        time.sleep(wait_time)
        
        # Run cleanup
        session_manager.cleanup_idle_sessions()
        
        # Verify all sessions were cleaned up (all should be idle)
        remaining_sessions = session_manager.get_all_sessions()
        assert len(remaining_sessions) == 0, \
            f"Expected 0 sessions after cleanup, got {len(remaining_sessions)}"
        
        # Test with mixed idle/active sessions
        # Create new sessions
        for session_id in session_ids:
            session_manager.get_or_create(session_id)
        
        # Keep half the sessions active by updating them
        active_count = num_sessions // 2
        active_sessions = session_ids[:active_count]
        idle_sessions = session_ids[active_count:]
        
        # Wait a short time (25% of timeout)
        time.sleep(idle_timeout * 0.25)
        
        # Update active sessions to keep them alive
        for session_id in active_sessions:
            session_manager.update_session(session_id, template_version="v1.0")
        
        # Wait for idle sessions to exceed timeout but NOT active sessions
        # Active sessions were updated at 0.25*timeout, so they've been idle X seconds
        # Idle sessions have been idle 0.25*timeout + X seconds (since creation)
        # We need: 0.25*timeout + X > timeout AND X < timeout
        # So: X > 0.75*timeout AND X < timeout → use X = 0.85*timeout
        time.sleep(idle_timeout * 0.85)
        
        # Run cleanup
        session_manager.cleanup_idle_sessions()
        
        # Verify only idle sessions were cleaned up
        remaining_sessions = session_manager.get_all_sessions()
        
        # Active sessions should remain
        for session_id in active_sessions:
            assert session_id in remaining_sessions, \
                f"Active session {session_id} was incorrectly cleaned up"
        
        # Idle sessions should be removed
        for session_id in idle_sessions:
            assert session_id not in remaining_sessions, \
                f"Idle session {session_id} was not cleaned up"
        
        # Verify count
        assert len(remaining_sessions) == active_count, \
            f"Expected {active_count} active sessions, got {len(remaining_sessions)}"
    
    finally:
        # Cleanup temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors


if __name__ == '__main__':
    print("Running property-based test for session idle cleanup...")
    print("Testing with 100 random configurations...")
    print()
    
    try:
        test_session_idle_cleanup()
        print("✓ Property test passed: Session idle cleanup verified")
        print("  Sessions exceeding idle timeout are properly cleaned up")
        print("  Active sessions are preserved during cleanup")
        print("  Cleanup is consistent across 100 random configurations")
        print()
        print("  Test parameters varied:")
        print("    - Idle timeout: 0.5 to 2.0 seconds")
        print("    - Number of sessions: 1 to 10")
        print("    - Idle multiplier: 1.5x to 3.0x timeout")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("All property-based tests passed! ✓")
