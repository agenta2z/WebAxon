"""Property-based test for message handler queue routing.

This module contains a property-based test using hypothesis to verify
that the message handler sends messages to the correct session-specific queue.

**Feature: agent-debugger-nextgen-completion, Property 1: Message handler sends to correct queue**
**Validates: Requirements 1.1**
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
from unittest.mock import MagicMock, patch


# Strategy for generating valid session IDs
# Session IDs are typically alphanumeric with underscores and timestamps
session_id_strategy = st.text(
    alphabet=st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789_'),
    min_size=1,
    max_size=50
).filter(lambda s: s and not s.startswith('_') and not s.endswith('_'))

# Strategy for generating user messages
message_strategy = st.text(min_size=1, max_size=500)

# Strategy for input queue IDs
input_queue_id_strategy = st.sampled_from([
    'user_input',
    'input_queue',
    'agent_input',
    'chat_input'
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


# **Feature: agent-debugger-nextgen-completion, Property 1: Message handler sends to correct queue**
# **Validates: Requirements 1.1**
@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy,
    message=message_strategy,
    input_queue_id=input_queue_id_strategy
)
def test_message_handler_sends_to_correct_queue(session_id, message, input_queue_id):
    """Property: For any user message and session ID, the message handler SHALL send
    the message to the session-specific input queue with format {input_queue_id}_{session_id}.
    
    This test verifies that:
    1. The message is sent to a queue with the correct format
    2. The queue ID follows the pattern: {input_queue_id}_{session_id}
    3. The message contains the session_id and user_input fields
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    from pathlib import Path
    
    # Create mock queue service
    mock_queue_service = MockQueueService()
    
    # Create a mock get_queue_service function
    def mock_get_queue_service(*args, **kwargs):
        return mock_queue_service
    
    # Create QueueClient with mock
    queue_client = QueueClient(
        testcase_root=Path('/tmp/test'),
        input_queue_id=input_queue_id,
        response_queue_id='agent_response',
        client_control_queue_id='client_control',
        server_control_queue_id='server_control',
        get_queue_service_func=mock_get_queue_service
    )
    
    # Clear any messages from initialization
    mock_queue_service.sent_messages.clear()
    
    # Call send_user_input
    returned_queue_id = queue_client.send_user_input(
        session_id=session_id,
        message=message,
        all_session_ids=[session_id]
    )
    
    # Property 1: The returned queue ID should match the expected format
    expected_queue_id = f"{input_queue_id}_{session_id}"
    assert returned_queue_id == expected_queue_id, (
        f"Expected queue ID '{expected_queue_id}', got '{returned_queue_id}'"
    )
    
    # Property 2: A message should have been sent to the session-specific queue
    session_queue_messages = [
        m for m in mock_queue_service.sent_messages 
        if m['queue_id'] == expected_queue_id
    ]
    assert len(session_queue_messages) == 1, (
        f"Expected exactly 1 message to session queue '{expected_queue_id}', "
        f"got {len(session_queue_messages)}. All messages: {mock_queue_service.sent_messages}"
    )
    
    # Property 3: The message should contain the correct session_id and user_input
    sent_message = session_queue_messages[0]['message']
    assert sent_message.get('session_id') == session_id, (
        f"Message session_id mismatch: expected '{session_id}', got '{sent_message.get('session_id')}'"
    )
    assert sent_message.get('user_input') == message, (
        f"Message user_input mismatch: expected '{message}', got '{sent_message.get('user_input')}'"
    )


def test_message_handler_queue_format_examples():
    """Example-based test to verify queue format with specific cases.
    
    This complements the property test with concrete examples.
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    from pathlib import Path
    
    test_cases = [
        ('session_1', 'Hello world', 'user_input', 'user_input_session_1'),
        ('abc123', 'Test message', 'input_queue', 'input_queue_abc123'),
        ('session_20251201_120000', 'Query', 'user_input', 'user_input_session_20251201_120000'),
    ]
    
    for session_id, message, input_queue_id, expected_queue_id in test_cases:
        mock_queue_service = MockQueueService()
        
        def mock_get_queue_service(*args, **kwargs):
            return mock_queue_service
        
        queue_client = QueueClient(
            testcase_root=Path('/tmp/test'),
            input_queue_id=input_queue_id,
            response_queue_id='agent_response',
            client_control_queue_id='client_control',
            server_control_queue_id='server_control',
            get_queue_service_func=mock_get_queue_service
        )
        
        mock_queue_service.sent_messages.clear()
        
        returned_queue_id = queue_client.send_user_input(
            session_id=session_id,
            message=message,
            all_session_ids=[session_id]
        )
        
        assert returned_queue_id == expected_queue_id, (
            f"Case ({session_id}, {input_queue_id}): "
            f"Expected '{expected_queue_id}', got '{returned_queue_id}'"
        )
        
        print(f"✓ Queue format correct: {expected_queue_id}")


if __name__ == '__main__':
    print("Running property-based tests for message handler queue routing...")
    print("=" * 70)
    print()
    
    # Run example-based test first
    print("1. Running example-based tests...")
    print("-" * 70)
    try:
        test_message_handler_queue_format_examples()
        print()
        print("✓ Example-based tests passed")
    except AssertionError as e:
        print(f"\n✗ Example test failed: {e}")
        sys.exit(1)
    
    print()
    print("2. Running property-based test with 100 random examples...")
    print("-" * 70)
    
    try:
        test_message_handler_sends_to_correct_queue()
        print()
        print("✓ Property test passed: Message handler queue routing verified")
        print("  Messages are sent to correct session-specific queues")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("All property-based tests passed! ✓")
    print()
    print("Summary:")
    print("  - Queue ID format: {input_queue_id}_{session_id}")
    print("  - Messages contain session_id and user_input fields")
    print("  - Property verified across 100 random test cases")
