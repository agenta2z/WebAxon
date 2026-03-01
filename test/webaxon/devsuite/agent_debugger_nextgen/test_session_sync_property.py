"""Property-based test for session sync on message submission.

This module contains a property-based test using hypothesis to verify
that the message handler calls sync_active_sessions with the provided session IDs.

**Feature: agent-debugger-nextgen-completion, Property 3: Session sync on message submission**
**Validates: Requirements 1.4**
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

# Strategy for generating lists of session IDs (1 to 10 sessions)
session_ids_list_strategy = st.lists(
    session_id_strategy,
    min_size=1,
    max_size=10,
    unique=True
)

# Strategy for generating user messages
message_strategy = st.text(min_size=1, max_size=500)


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


# **Feature: agent-debugger-nextgen-completion, Property 3: Session sync on message submission**
# **Validates: Requirements 1.4**
@settings(max_examples=100, deadline=None)
@given(
    all_session_ids=session_ids_list_strategy,
    message=message_strategy
)
def test_session_sync_on_message_submission(all_session_ids, message):
    """Property: For any message handler invocation with a list of session IDs,
    the handler SHALL call sync_active_sessions with that list.
    
    This test verifies that:
    1. A sync_active_sessions message is sent to the server control queue
    2. The message contains all provided session IDs
    3. The message has the correct type "sync_active_sessions"
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
    
    # Use the first session ID as the current session
    current_session_id = all_session_ids[0]
    
    # Call send_user_input which should trigger sync_active_sessions
    queue_client.send_user_input(
        session_id=current_session_id,
        message=message,
        all_session_ids=all_session_ids
    )
    
    # Property 1: A sync_active_sessions message should have been sent
    sync_messages = [
        m for m in mock_queue_service.sent_messages
        if m['queue_id'] == 'server_control' and 
           m['message'].get('type') == 'sync_active_sessions'
    ]
    
    assert len(sync_messages) >= 1, (
        f"Expected at least 1 sync_active_sessions message, got {len(sync_messages)}. "
        f"All messages: {mock_queue_service.sent_messages}"
    )
    
    # Property 2: The sync message should contain all provided session IDs
    sync_message = sync_messages[0]['message']
    synced_sessions = sync_message.get('message', {}).get('active_sessions', [])
    
    assert set(synced_sessions) == set(all_session_ids), (
        f"Session IDs mismatch: expected {set(all_session_ids)}, "
        f"got {set(synced_sessions)}"
    )
    
    # Property 3: The message should have a timestamp
    assert 'timestamp' in sync_message, (
        "sync_active_sessions message should have a timestamp"
    )


@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy,
    message=message_strategy
)
def test_session_sync_with_single_session(session_id, message):
    """Property: When all_session_ids is not provided, sync_active_sessions
    should be called with a list containing just the current session_id.
    
    This tests the fallback behavior when no explicit session list is provided.
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    
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
    
    # Call send_user_input without all_session_ids (should default to [session_id])
    queue_client.send_user_input(
        session_id=session_id,
        message=message,
        all_session_ids=None  # Not provided
    )
    
    # Find sync_active_sessions message
    sync_messages = [
        m for m in mock_queue_service.sent_messages
        if m['queue_id'] == 'server_control' and 
           m['message'].get('type') == 'sync_active_sessions'
    ]
    
    assert len(sync_messages) >= 1, (
        f"Expected at least 1 sync_active_sessions message"
    )
    
    # Should contain just the current session_id
    sync_message = sync_messages[0]['message']
    synced_sessions = sync_message.get('message', {}).get('active_sessions', [])
    
    assert synced_sessions == [session_id], (
        f"Expected [{session_id}], got {synced_sessions}"
    )


def test_session_sync_example_cases():
    """Example-based test to verify session sync with specific cases."""
    from webaxon.devsuite.agent_debugger_nextgen.communication.queue_client import QueueClient
    
    test_cases = [
        # (all_session_ids, message, description)
        (['session_1'], 'Hello', 'Single session'),
        (['session_1', 'session_2'], 'Test', 'Two sessions'),
        (['a', 'b', 'c', 'd', 'e'], 'Multi', 'Five sessions'),
        (['session_20251201_120000', 'session_20251201_120001'], 'Timestamped', 'Timestamped sessions'),
    ]
    
    for all_session_ids, message, description in test_cases:
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
        
        queue_client.send_user_input(
            session_id=all_session_ids[0],
            message=message,
            all_session_ids=all_session_ids
        )
        
        # Find sync message
        sync_messages = [
            m for m in mock_queue_service.sent_messages
            if m['queue_id'] == 'server_control' and 
               m['message'].get('type') == 'sync_active_sessions'
        ]
        
        assert len(sync_messages) >= 1, f"Case '{description}': No sync message sent"
        
        synced_sessions = sync_messages[0]['message'].get('message', {}).get('active_sessions', [])
        assert set(synced_sessions) == set(all_session_ids), (
            f"Case '{description}': Expected {all_session_ids}, got {synced_sessions}"
        )
        
        print(f"✓ {description}: sync_active_sessions called with {all_session_ids}")


if __name__ == '__main__':
    print("Running property-based tests for session sync on message submission...")
    print("=" * 70)
    print()
    
    # Run example-based test first
    print("1. Running example-based tests...")
    print("-" * 70)
    try:
        test_session_sync_example_cases()
        print()
        print("✓ Example-based tests passed")
    except AssertionError as e:
        print(f"\n✗ Example test failed: {e}")
        sys.exit(1)
    
    print()
    print("2. Running property-based test with 100 random examples (multiple sessions)...")
    print("-" * 70)
    
    try:
        test_session_sync_on_message_submission()
        print()
        print("✓ Property test passed: Session sync with multiple sessions verified")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("3. Running property-based test with 100 random examples (single session fallback)...")
    print("-" * 70)
    
    try:
        test_session_sync_with_single_session()
        print()
        print("✓ Property test passed: Session sync with single session fallback verified")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("All property-based tests passed! ✓")
    print()
    print("Summary:")
    print("  - sync_active_sessions is called on every message submission")
    print("  - All provided session IDs are included in the sync message")
    print("  - Fallback to [session_id] when all_session_ids is not provided")
    print("  - Property verified across 200 random test cases")
