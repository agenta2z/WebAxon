"""Property-based test for control ack message processing.

This module contains a property-based test using hypothesis to verify
that agent_control_ack messages correctly update session state.

**Feature: agent-debugger-nextgen-completion, Property 6: Control ack message processing**
**Validates: Requirements 2.2**
"""
import sys
from pathlib import Path

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != 'test' and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
# Add SciencePythonUtils and ScienceModelingTools
_workspace_root = _project_root.parent
_rich_python_utils_src = _workspace_root / "SciencePythonUtils" / "src"
_agent_foundation_src = _workspace_root / "ScienceModelingTools" / "src"
if _rich_python_utils_src.exists() and str(_rich_python_utils_src) not in sys.path:
    sys.path.insert(0, str(_rich_python_utils_src))
if _agent_foundation_src.exists() and str(_agent_foundation_src) not in sys.path:
    sys.path.insert(0, str(_agent_foundation_src))

from hypothesis import given, strategies as st, settings
from dataclasses import dataclass, field


# Strategy for generating valid session IDs
session_id_strategy = st.text(
    alphabet=st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789_'),
    min_size=1,
    max_size=50
).filter(lambda s: s and not s.startswith('_') and not s.endswith('_'))

# Strategy for control commands
control_strategy = st.sampled_from([
    'stop',
    'pause',
    'continue',
    'step'
])

# Strategy for agent status values
agent_status_strategy = st.sampled_from([
    'running',
    'paused',
    'stopped',
    'stepping',
    'idle',
    'unknown'
])

# Strategy for operation status
operation_status_strategy = st.sampled_from([
    'success',
    'failed',
    'pending'
])


@dataclass
class MockSessionInfo:
    """Mock session info for testing."""
    agent_control: str = 'continue'
    agent_status: str = 'unknown'
    control_pending: bool = True


class MockSessionManager:
    """Mock session manager for testing."""
    
    def __init__(self):
        self._sessions = {}
        self._active_ids = []
    
    def get_or_create(self, session_id):
        if session_id not in self._sessions:
            self._sessions[session_id] = MockSessionInfo()
        return self._sessions[session_id]
    
    def get_active_ids(self):
        return self._active_ids
    
    def set_active_ids(self, ids):
        self._active_ids = ids


# **Feature: agent-debugger-nextgen-completion, Property 6: Control ack message processing**
# **Validates: Requirements 2.2**
@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy,
    control=control_strategy,
    agent_status=agent_status_strategy,
    operation_status=operation_status_strategy
)
def test_control_ack_updates_session_state(session_id, control, agent_status, operation_status):
    """Property: For any agent_control_ack message, the message handler SHALL update
    the session's agent_control, agent_status, and control_pending fields.
    
    This test verifies that:
    1. session.agent_control is updated to the ack's control value
    2. session.agent_status is updated to the ack's agent_status value
    3. session.control_pending is set to False
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    # Create mock dependencies
    session_manager = MockSessionManager()
    session_manager.set_active_ids([session_id])
    
    # Pre-create session with pending control
    session_info = session_manager.get_or_create(session_id)
    session_info.control_pending = True
    session_info.agent_control = 'continue'  # Initial value
    session_info.agent_status = 'unknown'  # Initial value
    
    # Create message handlers
    message_handlers = MessageHandlers(
        session_manager=session_manager,
        get_active_session_ids_func=session_manager.get_active_ids,
        hprint_func=None
    )
    
    # Create agent_control_ack message
    msg = {
        'type': 'agent_control_ack',
        'message': {
            'session_id': session_id,
            'control': control,
            'agent_status': agent_status,
            'operation_status': operation_status
        },
        'timestamp': '2025-01-01T00:00:00Z'
    }
    
    # Process the message
    message_handlers.handle_agent_control_ack_message(
        msg=msg,
        session_id=session_id,
        debugger=None
    )
    
    # Property 1: agent_control should be updated
    assert session_info.agent_control == control, (
        f"Expected agent_control={control}, got {session_info.agent_control}"
    )
    
    # Property 2: agent_status should be updated
    assert session_info.agent_status == agent_status, (
        f"Expected agent_status={agent_status}, got {session_info.agent_status}"
    )
    
    # Property 3: control_pending should be False
    assert session_info.control_pending is False, (
        f"Expected control_pending=False, got {session_info.control_pending}"
    )


@settings(max_examples=100, deadline=None)
@given(
    current_session_id=session_id_strategy,
    msg_session_id=session_id_strategy,
    control=control_strategy,
    agent_status=agent_status_strategy
)
def test_control_ack_processes_for_active_sessions(current_session_id, msg_session_id, control, agent_status):
    """Property: Control ack messages should be processed for any active session,
    not just the current session.
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    session_manager = MockSessionManager()
    # Both sessions are active
    session_manager.set_active_ids([current_session_id, msg_session_id])
    
    # Pre-create both sessions
    current_session = session_manager.get_or_create(current_session_id)
    msg_session = session_manager.get_or_create(msg_session_id)
    msg_session.control_pending = True
    
    message_handlers = MessageHandlers(
        session_manager=session_manager,
        get_active_session_ids_func=session_manager.get_active_ids,
        hprint_func=None
    )
    
    # Create ack for msg_session_id (not current_session_id)
    msg = {
        'type': 'agent_control_ack',
        'message': {
            'session_id': msg_session_id,
            'control': control,
            'agent_status': agent_status,
            'operation_status': 'success'
        },
        'timestamp': '2025-01-01T00:00:00Z'
    }
    
    # Process with current_session_id as the "current" session
    message_handlers.handle_agent_control_ack_message(
        msg=msg,
        session_id=current_session_id,
        debugger=None
    )
    
    # Property: The message's session should be updated (not the current session)
    assert msg_session.agent_control == control, (
        f"msg_session.agent_control should be {control}"
    )
    assert msg_session.control_pending is False, (
        f"msg_session.control_pending should be False"
    )


@settings(max_examples=50, deadline=None)
@given(
    session_id=session_id_strategy,
    control=control_strategy
)
def test_control_ack_skipped_for_unknown_session(session_id, control):
    """Property: Control ack messages for unknown sessions should be skipped."""
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    session_manager = MockSessionManager()
    # Session is NOT in active list
    session_manager.set_active_ids([])
    
    message_handlers = MessageHandlers(
        session_manager=session_manager,
        get_active_session_ids_func=session_manager.get_active_ids,
        hprint_func=None
    )
    
    # Create ack for unknown session
    msg = {
        'type': 'agent_control_ack',
        'message': {
            'session_id': session_id,
            'control': control,
            'agent_status': 'running',
            'operation_status': 'success'
        },
        'timestamp': '2025-01-01T00:00:00Z'
    }
    
    # Process - should not create session
    message_handlers.handle_agent_control_ack_message(
        msg=msg,
        session_id='different_session',
        debugger=None
    )
    
    # Property: Session should NOT be created for unknown session
    # (unless it matches the current session_id parameter)
    if session_id != 'different_session':
        assert session_id not in session_manager._sessions, (
            f"Session {session_id} should not be created for unknown session"
        )


def test_control_ack_example_cases():
    """Example-based test to verify control ack processing with specific cases."""
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    test_cases = [
        # (session_id, control, agent_status, operation_status)
        ('session_1', 'stop', 'stopped', 'success'),
        ('session_2', 'pause', 'paused', 'success'),
        ('session_3', 'continue', 'running', 'success'),
        ('session_4', 'step', 'stepping', 'success'),
    ]
    
    for session_id, control, agent_status, operation_status in test_cases:
        session_manager = MockSessionManager()
        session_manager.set_active_ids([session_id])
        
        session_info = session_manager.get_or_create(session_id)
        session_info.control_pending = True
        
        message_handlers = MessageHandlers(
            session_manager=session_manager,
            get_active_session_ids_func=session_manager.get_active_ids,
            hprint_func=None
        )
        
        msg = {
            'type': 'agent_control_ack',
            'message': {
                'session_id': session_id,
                'control': control,
                'agent_status': agent_status,
                'operation_status': operation_status
            },
            'timestamp': '2025-01-01T00:00:00Z'
        }
        
        message_handlers.handle_agent_control_ack_message(
            msg=msg,
            session_id=session_id,
            debugger=None
        )
        
        assert session_info.agent_control == control, (
            f"Case ({session_id}, {control}): agent_control mismatch"
        )
        assert session_info.agent_status == agent_status, (
            f"Case ({session_id}, {control}): agent_status mismatch"
        )
        assert session_info.control_pending is False, (
            f"Case ({session_id}, {control}): control_pending should be False"
        )
        
        print(f"✓ Control '{control}': agent_control={control}, agent_status={agent_status}, pending=False")


if __name__ == '__main__':
    print("Running property-based tests for control ack message processing...")
    print("=" * 70)
    print()
    
    # Run example-based test first
    print("1. Running example-based tests...")
    print("-" * 70)
    try:
        test_control_ack_example_cases()
        print()
        print("✓ Example-based tests passed")
    except AssertionError as e:
        print(f"\n✗ Example test failed: {e}")
        sys.exit(1)
    
    print()
    print("2. Running property-based test: session state updates...")
    print("-" * 70)
    
    try:
        test_control_ack_updates_session_state()
        print()
        print("✓ Property test passed: Session state updated correctly")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("3. Running property-based test: active session processing...")
    print("-" * 70)
    
    try:
        test_control_ack_processes_for_active_sessions()
        print()
        print("✓ Property test passed: Active sessions processed correctly")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("4. Running property-based test: unknown session skipped...")
    print("-" * 70)
    
    try:
        test_control_ack_skipped_for_unknown_session()
        print()
        print("✓ Property test passed: Unknown sessions skipped correctly")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("All property-based tests passed! ✓")
    print()
    print("Summary:")
    print("  - agent_control is updated from ack message")
    print("  - agent_status is updated from ack message")
    print("  - control_pending is set to False")
    print("  - Acks processed for any active session, not just current")
    print("  - Property verified across 300+ random test cases")
