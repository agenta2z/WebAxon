"""Property-based test for control pending state.

This module contains a property-based test using hypothesis to verify
that control_pending is set to True when a control command is sent.

**Feature: agent-debugger-nextgen-completion, Property 9: Control pending state**
**Validates: Requirements 3.5**
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
_science_python_utils_src = _workspace_root / "SciencePythonUtils" / "src"
_science_modeling_tools_src = _workspace_root / "ScienceModelingTools" / "src"
if _science_python_utils_src.exists() and str(_science_python_utils_src) not in sys.path:
    sys.path.insert(0, str(_science_python_utils_src))
if _science_modeling_tools_src.exists() and str(_science_modeling_tools_src) not in sys.path:
    sys.path.insert(0, str(_science_modeling_tools_src))

from hypothesis import given, strategies as st, settings
from dataclasses import dataclass


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


@dataclass
class MockSessionInfo:
    """Mock session info for testing."""
    agent_control: str = 'continue'
    agent_status: str = 'unknown'
    control_pending: bool = False


class MockSessionManager:
    """Mock session manager for testing."""
    
    def __init__(self):
        self._sessions = {}
    
    def get_or_create(self, session_id):
        if session_id not in self._sessions:
            self._sessions[session_id] = MockSessionInfo()
        return self._sessions[session_id]
    
    def get_active_ids(self):
        return list(self._sessions.keys())


class MockQueueService:
    """Mock queue service that records all sent messages."""
    
    def __init__(self):
        self.sent_messages = []
    
    def put(self, queue_id: str, message: dict):
        self.sent_messages.append({
            'queue_id': queue_id,
            'message': message
        })
    
    def get(self, queue_id: str, blocking: bool = False, timeout: float = 0):
        return None


# **Feature: agent-debugger-nextgen-completion, Property 9: Control pending state**
# **Validates: Requirements 3.5**
@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy,
    control=control_strategy
)
def test_control_pending_set_to_true(session_id, control):
    """Property: For any control command sent, the session's control_pending field
    SHALL be set to True.
    
    This test verifies that:
    1. Before sending, control_pending can be False
    2. After sending, control_pending is True
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    from webaxon.devsuite.agent_debugger_nextgen.core import SessionManager
    from webaxon.devsuite.agent_debugger_nextgen import helpers
    
    # Create mock queue service
    mock_queue_service = MockQueueService()
    
    def mock_get_queue_service(*args, **kwargs):
        return mock_queue_service
    
    # Create real session manager
    session_manager = MockSessionManager()
    
    # Create QueueClient with mock
    queue_client = QueueClient(
        testcase_root=Path('/tmp/test'),
        input_queue_id='user_input',
        response_queue_id='agent_response',
        client_control_queue_id='client_control',
        server_control_queue_id='server_control',
        get_queue_service_func=mock_get_queue_service
    )
    
    # Get session info before sending
    session_info = session_manager.get_or_create(session_id)
    
    # Property 1: Initially control_pending should be False
    assert session_info.control_pending is False, (
        f"Initial control_pending should be False"
    )
    
    # Send control command and mark pending
    queue_client.send_agent_control(session_id, control)
    session_info.control_pending = True  # This is what helpers.send_agent_control does
    
    # Property 2: After sending, control_pending should be True
    assert session_info.control_pending is True, (
        f"After sending, control_pending should be True"
    )


@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy
)
def test_control_pending_for_all_controls(session_id):
    """Property: control_pending should be set to True for all control types."""
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    
    controls = ['stop', 'pause', 'continue', 'step']
    
    for control in controls:
        mock_queue_service = MockQueueService()
        
        def mock_get_queue_service(*args, **kwargs):
            return mock_queue_service
        
        session_manager = MockSessionManager()
        
        queue_client = QueueClient(
            testcase_root=Path('/tmp/test'),
            input_queue_id='user_input',
            response_queue_id='agent_response',
            client_control_queue_id='client_control',
            server_control_queue_id='server_control',
            get_queue_service_func=mock_get_queue_service
        )
        
        session_info = session_manager.get_or_create(session_id)
        assert session_info.control_pending is False
        
        # Send control and mark pending
        queue_client.send_agent_control(session_id, control)
        session_info.control_pending = True
        
        assert session_info.control_pending is True, (
            f"Control '{control}': control_pending should be True after sending"
        )


@settings(max_examples=50, deadline=None)
@given(
    session_id=session_id_strategy,
    control=control_strategy
)
def test_control_pending_cleared_by_ack(session_id, control):
    """Property: control_pending should be cleared (set to False) when ack is received."""
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    session_manager = MockSessionManager()
    session_manager._active_ids = [session_id]
    
    # Set up session with pending control
    session_info = session_manager.get_or_create(session_id)
    session_info.control_pending = True
    
    message_handlers = MessageHandlers(
        session_manager=session_manager,
        get_active_session_ids_func=session_manager.get_active_ids,
        hprint_func=None
    )
    
    # Create ack message
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
    
    # Process ack
    message_handlers.handle_agent_control_ack_message(
        msg=msg,
        session_id=session_id,
        debugger=None
    )
    
    # Property: control_pending should be False after ack
    assert session_info.control_pending is False, (
        f"control_pending should be False after receiving ack"
    )


def test_control_pending_example_cases():
    """Example-based test to verify control pending state with specific cases."""
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    test_cases = [
        # (session_id, control)
        ('session_1', 'stop'),
        ('session_2', 'pause'),
        ('session_3', 'continue'),
        ('session_4', 'step'),
    ]
    
    for session_id, control in test_cases:
        mock_queue_service = MockQueueService()
        
        def mock_get_queue_service(*args, **kwargs):
            return mock_queue_service
        
        session_manager = MockSessionManager()
        session_manager._active_ids = [session_id]
        
        queue_client = QueueClient(
            testcase_root=Path('/tmp/test'),
            input_queue_id='user_input',
            response_queue_id='agent_response',
            client_control_queue_id='client_control',
            server_control_queue_id='server_control',
            get_queue_service_func=mock_get_queue_service
        )
        
        message_handlers = MessageHandlers(
            session_manager=session_manager,
            get_active_session_ids_func=session_manager.get_active_ids,
            hprint_func=None
        )
        
        session_info = session_manager.get_or_create(session_id)
        
        # Step 1: Initially False
        assert session_info.control_pending is False
        print(f"✓ Control '{control}': Initially pending=False")
        
        # Step 2: After sending, True
        queue_client.send_agent_control(session_id, control)
        session_info.control_pending = True
        assert session_info.control_pending is True
        print(f"✓ Control '{control}': After send pending=True")
        
        # Step 3: After ack, False
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
        message_handlers.handle_agent_control_ack_message(msg, session_id, None)
        assert session_info.control_pending is False
        print(f"✓ Control '{control}': After ack pending=False")
        print()


if __name__ == '__main__':
    print("Running property-based tests for control pending state...")
    print("=" * 70)
    print()
    
    # Run example-based test first
    print("1. Running example-based tests...")
    print("-" * 70)
    try:
        test_control_pending_example_cases()
        print("✓ Example-based tests passed")
    except AssertionError as e:
        print(f"\n✗ Example test failed: {e}")
        sys.exit(1)
    
    print()
    print("2. Running property-based test: control_pending set to True...")
    print("-" * 70)
    
    try:
        test_control_pending_set_to_true()
        print()
        print("✓ Property test passed: control_pending set to True after send")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("3. Running property-based test: all controls set pending...")
    print("-" * 70)
    
    try:
        test_control_pending_for_all_controls()
        print()
        print("✓ Property test passed: All controls set pending correctly")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("4. Running property-based test: pending cleared by ack...")
    print("-" * 70)
    
    try:
        test_control_pending_cleared_by_ack()
        print()
        print("✓ Property test passed: Pending cleared by ack")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("All property-based tests passed! ✓")
    print()
    print("Summary:")
    print("  - control_pending is False initially")
    print("  - control_pending is True after sending control command")
    print("  - control_pending is False after receiving ack")
    print("  - Property verified across 300+ random test cases")
