"""Property-based test for control command format.

This module contains a property-based test using hypothesis to verify
that control commands are sent with the correct format.

**Feature: agent-debugger-nextgen-completion, Property 8: Control command format**
**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
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


# **Feature: agent-debugger-nextgen-completion, Property 8: Control command format**
# **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy,
    control=control_strategy
)
def test_control_command_format(session_id, control):
    """Property: For any control command (stop, pause, continue, step), the sent message
    SHALL have type "agent_control" with the correct control value in the message payload.
    
    This test verifies that:
    1. The message type is "agent_control"
    2. The message payload contains the session_id
    3. The message payload contains the correct control value
    4. The message has a timestamp
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    
    # Create mock queue service
    mock_queue_service = MockQueueService()
    
    def mock_get_queue_service(*args, **kwargs):
        return mock_queue_service
    
    # Create QueueClient with mock
    queue_client = QueueClient(
        testcase_root=Path('/tmp/test'),
        input_queue_id='user_input',
        response_queue_id='agent_response',
        client_control_queue_id='client_control',
        server_control_queue_id='server_control',
        get_queue_service_func=mock_get_queue_service
    )
    
    # Clear any messages from initialization
    mock_queue_service.sent_messages.clear()
    
    # Send control command
    queue_client.send_agent_control(session_id, control)
    
    # Find the control message
    control_messages = [
        m for m in mock_queue_service.sent_messages
        if m['queue_id'] == 'server_control' and
           m['message'].get('type') == 'agent_control'
    ]
    
    # Property 1: Exactly one agent_control message should be sent
    assert len(control_messages) == 1, (
        f"Expected exactly 1 agent_control message, got {len(control_messages)}"
    )
    
    msg = control_messages[0]['message']
    
    # Property 2: Message type should be "agent_control"
    assert msg.get('type') == 'agent_control', (
        f"Expected type='agent_control', got '{msg.get('type')}'"
    )
    
    # Property 3: Message payload should contain session_id
    payload = msg.get('message', {})
    assert payload.get('session_id') == session_id, (
        f"Expected session_id='{session_id}', got '{payload.get('session_id')}'"
    )
    
    # Property 4: Message payload should contain correct control value
    assert payload.get('control') == control, (
        f"Expected control='{control}', got '{payload.get('control')}'"
    )
    
    # Property 5: Message should have a timestamp
    assert 'timestamp' in msg, (
        "Message should have a timestamp"
    )


@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy
)
def test_all_control_commands_have_same_format(session_id):
    """Property: All control commands (stop, pause, continue, step) should have
    the same message format structure.
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    
    controls = ['stop', 'pause', 'continue', 'step']
    
    for control in controls:
        mock_queue_service = MockQueueService()
        
        def mock_get_queue_service(*args, **kwargs):
            return mock_queue_service
        
        queue_client = QueueClient(
            testcase_root=Path('/tmp/test'),
            input_queue_id='user_input',
            response_queue_id='agent_response',
            client_control_queue_id='client_control',
            server_control_queue_id='server_control',
            get_queue_service_func=mock_get_queue_service
        )
        
        mock_queue_service.sent_messages.clear()
        queue_client.send_agent_control(session_id, control)
        
        # Find the control message
        control_messages = [
            m for m in mock_queue_service.sent_messages
            if m['message'].get('type') == 'agent_control'
        ]
        
        assert len(control_messages) == 1, (
            f"Control '{control}': Expected 1 message, got {len(control_messages)}"
        )
        
        msg = control_messages[0]['message']
        
        # Verify structure
        assert 'type' in msg, f"Control '{control}': Missing 'type'"
        assert 'message' in msg, f"Control '{control}': Missing 'message'"
        assert 'timestamp' in msg, f"Control '{control}': Missing 'timestamp'"
        assert 'session_id' in msg['message'], f"Control '{control}': Missing 'session_id' in payload"
        assert 'control' in msg['message'], f"Control '{control}': Missing 'control' in payload"


def test_control_command_format_examples():
    """Example-based test to verify control command format with specific cases."""
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    
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
        
        queue_client = QueueClient(
            testcase_root=Path('/tmp/test'),
            input_queue_id='user_input',
            response_queue_id='agent_response',
            client_control_queue_id='client_control',
            server_control_queue_id='server_control',
            get_queue_service_func=mock_get_queue_service
        )
        
        mock_queue_service.sent_messages.clear()
        queue_client.send_agent_control(session_id, control)
        
        # Find the control message
        control_messages = [
            m for m in mock_queue_service.sent_messages
            if m['message'].get('type') == 'agent_control'
        ]
        
        assert len(control_messages) == 1, (
            f"Case ({session_id}, {control}): Expected 1 message"
        )
        
        msg = control_messages[0]['message']
        assert msg['type'] == 'agent_control'
        assert msg['message']['session_id'] == session_id
        assert msg['message']['control'] == control
        assert 'timestamp' in msg
        
        print(f"✓ Control '{control}': type=agent_control, session_id={session_id}, control={control}")


if __name__ == '__main__':
    print("Running property-based tests for control command format...")
    print("=" * 70)
    print()
    
    # Run example-based test first
    print("1. Running example-based tests...")
    print("-" * 70)
    try:
        test_control_command_format_examples()
        print()
        print("✓ Example-based tests passed")
    except AssertionError as e:
        print(f"\n✗ Example test failed: {e}")
        sys.exit(1)
    
    print()
    print("2. Running property-based test: control command format...")
    print("-" * 70)
    
    try:
        test_control_command_format()
        print()
        print("✓ Property test passed: Control command format verified")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("3. Running property-based test: all controls have same format...")
    print("-" * 70)
    
    try:
        test_all_control_commands_have_same_format()
        print()
        print("✓ Property test passed: All controls have consistent format")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("All property-based tests passed! ✓")
    print()
    print("Summary:")
    print("  - Message type is 'agent_control'")
    print("  - Payload contains session_id and control")
    print("  - All controls (stop, pause, continue, step) have same format")
    print("  - Property verified across 200+ random test cases")
