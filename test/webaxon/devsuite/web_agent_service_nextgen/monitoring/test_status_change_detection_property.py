"""Property-based test for status change detection.

This module contains property-based tests using hypothesis to verify
that the SessionMonitor detects agent status changes and sends
acknowledgment messages to the control queue.
"""
import sys
import resolve_path  # Setup import paths

import time
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any

# Add parent directory to path
from hypothesis import given, strategies as st, settings, assume
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager, AgentSession
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_monitor import AgentSessionMonitor


# Mock queue service for testing
class MockQueueService:
    """Mock queue service that tracks put operations."""
    
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
    
    def get_messages(self, queue_id: str) -> List[Dict[str, Any]]:
        """Get all messages sent to a queue."""
        return self.messages.get(queue_id, [])
    
    def clear(self) -> None:
        """Clear all messages."""
        self.messages.clear()


# Feature: web-agent-service-modularization, Property 28: Status Change Detection
# Validates: Requirements 8.2
@settings(max_examples=100, deadline=None)
@given(
    # Generate number of sessions to test
    num_sessions=st.integers(min_value=1, max_value=5),
    # Generate different status transitions to test
    status_sequence=st.lists(
        st.sampled_from(['not_created', 'ready', 'running', 'stopped']),
        min_size=2,
        max_size=5
    ),
)
def test_status_change_detection(num_sessions, status_sequence):
    """Property: For any agent status change, the SessionMonitor should detect it
    and send an acknowledgment to the control queue.
    
    This test verifies that:
    1. SessionMonitor detects when agent status changes
    2. An acknowledgment message is sent to the server control queue
    3. The acknowledgment contains the correct session_id and new status
    4. The session's last_agent_status is updated after detection
    5. Multiple sessions can have status changes detected independently
    6. Status changes are detected across multiple monitoring cycles
    
    Test strategy:
    - Create multiple sessions with agents
    - Simulate status changes by updating agent state
    - Run check_status_changes()
    - Verify acknowledgment messages are sent to control queue
    - Verify last_agent_status is updated in session info
    """
    # Filter out edge cases
    assume(num_sessions >= 1)
    assume(len(status_sequence) >= 2)
    
    # Create temporary directory for logs
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create config
        config = ServiceConfig()
        
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
        
        # Create sessions with mock agents
        session_ids = [f"test_session_{i}" for i in range(num_sessions)]
        
        for session_id in session_ids:
            # Create session
            session = session_manager.get_or_create(session_id)

            # Create mock agent
            mock_agent = Mock()
            mock_agent.status = 'ready'

            # Update session with agent
            session_manager.update_session(
                session_id,
                agent=mock_agent,
                initialized=True,
                last_agent_status=None  # No previous status
            )

        # Test status changes for each session
        for session_id in session_ids:
            session = session_manager.get(session_id)
            
            # Filter out 'not_created' from status sequence since we start with agent created
            # We'll test 'not_created' separately
            valid_statuses = [s for s in status_sequence if s != 'not_created']
            
            # Skip if no valid status transitions
            if len(valid_statuses) == 0:
                continue
            
            # Simulate status changes through the sequence
            for new_status in valid_statuses:
                # Get current status
                current_status = session.info.last_agent_status
                
                # Skip if status hasn't changed
                if current_status == new_status:
                    continue
                
                # Update agent to simulate status change
                if new_status == 'running':
                    # Create mock thread
                    mock_thread = Mock()
                    mock_thread.is_alive.return_value = True
                    session_manager.update_session(
                        session_id,
                        agent_thread=mock_thread
                    )
                elif new_status == 'stopped':
                    # Create mock thread that's not alive
                    mock_thread = Mock()
                    mock_thread.is_alive.return_value = False
                    session_manager.update_session(
                        session_id,
                        agent_thread=mock_thread
                    )
                elif new_status == 'ready':
                    # No thread means ready
                    session_manager.update_session(
                        session_id,
                        agent_thread=None
                    )
                
                # Clear previous messages
                queue_service.clear()
                
                # Run status change detection
                session_monitor.check_status_changes()
                
                # Get messages sent to control queue
                control_messages = queue_service.get_messages(
                    config.server_control_queue_id
                )
                
                # Verify acknowledgment was sent
                assert len(control_messages) >= 1, \
                    f"Expected at least 1 ack message for session {session_id}, got {len(control_messages)}"
                
                # Find the ack for this session
                session_acks = [
                    msg for msg in control_messages
                    if msg.get('session_id') == session_id
                ]
                
                assert len(session_acks) >= 1, \
                    f"Expected ack for session {session_id}, got {len(session_acks)}"
                
                # Verify ack message format
                ack = session_acks[0]
                assert ack.get('type') == 'agent_status_change', \
                    f"Expected type 'agent_status_change', got {ack.get('type')}"
                assert ack.get('session_id') == session_id, \
                    f"Expected session_id {session_id}, got {ack.get('session_id')}"
                assert ack.get('status') == new_status, \
                    f"Expected status {new_status}, got {ack.get('status')}"
                assert 'timestamp' in ack, \
                    "Ack message should contain timestamp"
                
                # Verify last_agent_status was updated
                updated_session = session_manager.get(session_id)
                assert updated_session.info.last_agent_status == new_status, \
                    f"Expected last_agent_status to be {new_status}, got {updated_session.info.last_agent_status}"

                # Update session reference
                session = updated_session
        
        # Test that initialized=False prevents acknowledgments
        # Create a new session without an agent
        test_session_id = "test_no_agent"
        session = session_manager.get_or_create(test_session_id)
        session_manager.update_session(
            test_session_id,
            agent=None,
            initialized=False
        )
        
        # Clear messages
        queue_service.clear()
        
        # Run status change detection
        session_monitor.check_status_changes()
        
        # Get messages sent to control queue
        control_messages = queue_service.get_messages(
            config.server_control_queue_id
        )
        
        # Find acks for this session
        session_acks = [
            msg for msg in control_messages
            if msg.get('session_id') == test_session_id
        ]
        
        # No ack should be sent when agent is not created
        assert len(session_acks) == 0, \
            f"No ack should be sent when agent is not created"
        
        # Test that no acknowledgment is sent when status doesn't change
        for session_id in session_ids:
            session = session_manager.get(session_id)

            # Skip if agent not created
            if not session.info.initialized:
                continue
            
            # Clear messages
            queue_service.clear()
            
            # Run status change detection (status should be same)
            session_monitor.check_status_changes()
            
            # Get messages sent to control queue
            control_messages = queue_service.get_messages(
                config.server_control_queue_id
            )
            
            # Find acks for this session
            session_acks = [
                msg for msg in control_messages
                if msg.get('session_id') == session_id
            ]
            
            # No ack should be sent when status hasn't changed
            assert len(session_acks) == 0, \
                f"No ack should be sent when status hasn't changed for session {session_id}"
    
    finally:
        # Cleanup temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors


if __name__ == '__main__':
    print("Running property-based test for status change detection...")
    print("Testing with 100 random configurations...")
    print()
    
    try:
        test_status_change_detection()
        print("✓ Property test passed: Status change detection verified")
        print("  SessionMonitor detects agent status changes")
        print("  Acknowledgment messages are sent to control queue")
        print("  Acknowledgments contain correct session_id and status")
        print("  last_agent_status is updated after detection")
        print("  Multiple sessions are handled independently")
        print("  No acks sent when status hasn't changed")
        print()
        print("  Test parameters varied:")
        print("    - Number of sessions: 1 to 5")
        print("    - Status sequences: 2 to 5 transitions")
        print("    - Status values: not_created, ready, running, stopped")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("All property-based tests passed! ✓")
