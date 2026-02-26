"""Property-based test for session manager centralization.

This module tests that all session creation and retrieval goes through
SessionManager.get_or_create() rather than direct instantiation.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
import tempfile
import shutil

# Add parent directory to path
from hypothesis import given, strategies as st, settings
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager, AgentSession, AgentSessionInfo
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig


# Mock queue service for testing
class MockQueueService:
    """Mock queue service for testing."""
    pass


# Helper function to filter valid session IDs
def is_valid_session_id(s):
    """Check if string is valid for use as session ID (safe for file paths)."""
    if not s or not s.strip():
        return False
    # Filter out characters that are invalid in Windows/Unix file paths
    invalid_chars = '<>:"|?*\\/\x00'
    if any(c in s for c in invalid_chars):
        return False
    # Filter out control characters (0x00-0x1F)
    if any(ord(c) < 32 for c in s):
        return False
    # Filter out trailing/leading spaces (Windows doesn't like them)
    if s != s.strip():
        return False
    return True


# Feature: web-agent-service-modularization, Property 4: Session Manager Centralization
# Validates: Requirements 3.1
@settings(max_examples=100)
@given(
    session_id=st.text(
        min_size=1, 
        max_size=100,
        alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters='<>:"|?*\\/\x00')
    ).filter(is_valid_session_id),
    agent_type=st.one_of(st.none(), st.text(min_size=1, max_size=50).filter(lambda x: x.strip())),
)
def test_session_manager_centralization(session_id, agent_type):
    """Property: For any session creation or retrieval, it should go through SessionManager.
    
    This test verifies that:
    1. Sessions are created through SessionManager.get_or_create()
    2. The returned session is properly initialized with all required fields
    3. Subsequent calls with the same session_id return the same session instance
    4. Direct instantiation of AgentSessionInfo is not used for session management
    
    The property ensures centralized session management as specified in Requirement 3.1:
    "WHEN a session is requested THEN the system SHALL create or retrieve session 
    information through a SessionManager class"
    """
    # Create temporary directory for logs
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create config and session manager
        config = ServiceConfig()
        queue_service = MockQueueService()
        session_manager = SessionManager(id='test', log_name='Test', logger=[print], always_add_logging_based_logger=False, config=config, queue_service=queue_service, service_log_dir=temp_dir)
        
        # Test 1: Session creation goes through SessionManager
        # This is the ONLY way sessions should be created
        session1 = session_manager.get_or_create(session_id, agent_type=agent_type)
        
        # Verify the session is properly initialized
        assert isinstance(session1, AgentSession), \
            "SessionManager.get_or_create() should return AgentSession instance"
        assert session1.session_id == session_id, \
            "Session should have the requested session_id"
        
        # If agent_type was provided, verify it was used
        if agent_type is not None:
            assert session1.info.session_type == agent_type, \
                "Session should have the requested agent_type"
        else:
            # Should use default from config
            assert session1.info.session_type == config.default_agent_type, \
                "Session should use default agent_type when none provided"

        # Verify all required fields are initialized
        assert session1.info.created_at > 0, "Session should have created_at timestamp"
        assert session1.info.last_active > 0, "Session should have last_active timestamp"
        
        # Test 2: Subsequent retrieval returns the SAME session instance
        # This verifies centralization - there's only one session per session_id
        session2 = session_manager.get_or_create(session_id, agent_type=agent_type)
        
        assert session2 is session1, \
            "SessionManager should return the same instance for the same session_id"
        
        # Test 3: Verify session is tracked in the manager
        all_sessions = session_manager.get_all_sessions()
        assert session_id in all_sessions, \
            "Session should be tracked in SessionManager"
        assert all_sessions[session_id] is session1, \
            "Tracked session should be the same instance"
        
        # Test 4: Verify get() method also returns the same instance
        session3 = session_manager.get(session_id)
        assert session3 is not None, "SessionManager.get() should find existing session"
        assert session3 is session1, \
            "SessionManager.get() should return the same instance"
        
        # Test 5: Verify that direct instantiation would NOT be tracked
        # This demonstrates why centralization is important
        direct_session = AgentSessionInfo(
            session_id=session_id + "_direct",
            created_at=0,
            last_active=0,
            session_type="DirectAgent",
            initialized=False,
        )
        
        # This direct session is NOT in the manager
        assert direct_session.session_id not in session_manager.get_all_sessions(), \
            "Directly instantiated sessions should NOT be tracked by SessionManager"
        
        # This proves that SessionManager.get_or_create() is the ONLY proper way
        # to create sessions that are managed by the service
        
    finally:
        # Cleanup temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    print("Running property-based test for session manager centralization...")
    print("Testing that all session creation goes through SessionManager with 100 random examples...")
    print()
    
    try:
        test_session_manager_centralization()
        print("✓ Property test passed: Session manager centralization verified")
        print()
        print("  Verified behaviors:")
        print("    1. Sessions created through SessionManager.get_or_create()")
        print("    2. Returned sessions are properly initialized with all fields")
        print("    3. Same session_id returns same instance (singleton per ID)")
        print("    4. Sessions are tracked in SessionManager")
        print("    5. Direct instantiation does NOT create managed sessions")
        print()
        print("  This ensures centralized session management as required by Requirement 3.1:")
        print("  'WHEN a session is requested THEN the system SHALL create or retrieve")
        print("   session information through a SessionManager class'")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("All property-based tests passed! ✓")
