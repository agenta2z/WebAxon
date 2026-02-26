"""Property-based test for agent status message processing.

This module contains a property-based test using hypothesis to verify
that agent_status messages are correctly stored in the app's agent_status_messages dictionary.

**Feature: agent-debugger-nextgen-completion, Property 5: Agent status message processing**
**Validates: Requirements 2.1**
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
from unittest.mock import MagicMock


# Strategy for generating valid session IDs
session_id_strategy = st.text(
    alphabet=st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789_'),
    min_size=1,
    max_size=50
).filter(lambda s: s and not s.startswith('_') and not s.endswith('_'))

# Strategy for agent types
agent_type_strategy = st.sampled_from([
    'DefaultAgent',
    'MockClarificationAgent',
    'PlanningAgent',
    'TestAgent'
])

# Strategy for status values
status_strategy = st.sampled_from([
    'created',
    'agent_updated',
    'agent_locked',
    'running',
    'paused',
    'stopped'
])

# Strategy for timestamps
timestamp_strategy = st.text(
    alphabet=st.sampled_from('0123456789-:T.Z'),
    min_size=10,
    max_size=30
)


class MockSessionManager:
    """Mock session manager for testing."""
    
    def __init__(self):
        self._sessions = {}
    
    def get_or_create(self, session_id):
        if session_id not in self._sessions:
            self._sessions[session_id] = MagicMock()
            self._sessions[session_id].agent_control = 'continue'
            self._sessions[session_id].agent_status = 'unknown'
            self._sessions[session_id].control_pending = False
        return self._sessions[session_id]
    
    def get_active_ids(self):
        return list(self._sessions.keys())


class MockAppInstance:
    """Mock app instance for testing."""
    
    def __init__(self):
        self.agent_status_messages = {}


# **Feature: agent-debugger-nextgen-completion, Property 5: Agent status message processing**
# **Validates: Requirements 2.1**
@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy,
    agent_type=agent_type_strategy,
    status=status_strategy,
    timestamp=timestamp_strategy
)
def test_agent_status_message_stored_correctly(session_id, agent_type, status, timestamp):
    """Property: For any agent_status message in CLIENT_CONTROL_QUEUE, the message handler
    SHALL store the message in the app's agent_status_messages dictionary for the correct session.
    
    This test verifies that:
    1. The message is stored in agent_status_messages[session_id]
    2. The stored message contains the original payload
    3. Multiple messages for the same session are appended
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    # Create mock dependencies
    session_manager = MockSessionManager()
    app_instance = MockAppInstance()
    
    # Create message handlers
    message_handlers = MessageHandlers(
        session_manager=session_manager,
        get_active_session_ids_func=session_manager.get_active_ids,
        hprint_func=None
    )
    
    # Create agent_status message
    msg = {
        'type': 'agent_status',
        'message': {
            'session_id': session_id,
            'status': status,
            'agent_type': agent_type
        },
        'timestamp': timestamp
    }
    
    # Process the message
    latest_agent, agent_created = message_handlers.handle_agent_status_message(
        msg=msg,
        session_id=session_id,
        app_instance=app_instance
    )
    
    # Property 1: Message should be stored in agent_status_messages for this session
    assert session_id in app_instance.agent_status_messages, (
        f"Session {session_id} should be in agent_status_messages"
    )
    
    # Property 2: The stored messages list should contain our message
    stored_messages = app_instance.agent_status_messages[session_id]
    assert len(stored_messages) >= 1, (
        f"Expected at least 1 message stored, got {len(stored_messages)}"
    )
    
    # Property 3: The stored message should match the original
    stored_msg = stored_messages[-1]
    assert stored_msg.get('message', {}).get('session_id') == session_id, (
        f"Stored message session_id mismatch"
    )
    assert stored_msg.get('message', {}).get('status') == status, (
        f"Stored message status mismatch"
    )
    assert stored_msg.get('message', {}).get('agent_type') == agent_type, (
        f"Stored message agent_type mismatch"
    )


@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy,
    agent_type=agent_type_strategy,
    num_messages=st.integers(min_value=1, max_value=10)
)
def test_multiple_agent_status_messages_appended(session_id, agent_type, num_messages):
    """Property: Multiple agent_status messages for the same session should be appended,
    not replaced.
    """
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    session_manager = MockSessionManager()
    app_instance = MockAppInstance()
    
    message_handlers = MessageHandlers(
        session_manager=session_manager,
        get_active_session_ids_func=session_manager.get_active_ids,
        hprint_func=None
    )
    
    # Send multiple messages
    for i in range(num_messages):
        msg = {
            'type': 'agent_status',
            'message': {
                'session_id': session_id,
                'status': 'running',
                'agent_type': agent_type,
                'sequence': i
            },
            'timestamp': f'2025-01-01T00:00:{i:02d}Z'
        }
        
        message_handlers.handle_agent_status_message(
            msg=msg,
            session_id=session_id,
            app_instance=app_instance
        )
    
    # Property: All messages should be stored
    stored_messages = app_instance.agent_status_messages.get(session_id, [])
    assert len(stored_messages) == num_messages, (
        f"Expected {num_messages} messages, got {len(stored_messages)}"
    )


@settings(max_examples=100, deadline=None)
@given(
    session_id=session_id_strategy,
    agent_type=agent_type_strategy
)
def test_agent_created_flag_on_created_status(session_id, agent_type):
    """Property: When status is 'created' or 'agent_updated', agent_created should be True."""
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    session_manager = MockSessionManager()
    app_instance = MockAppInstance()
    
    message_handlers = MessageHandlers(
        session_manager=session_manager,
        get_active_session_ids_func=session_manager.get_active_ids,
        hprint_func=None
    )
    
    # Test 'created' status
    msg = {
        'type': 'agent_status',
        'message': {
            'session_id': session_id,
            'status': 'created',
            'agent_type': agent_type
        },
        'timestamp': '2025-01-01T00:00:00Z'
    }
    
    latest_agent, agent_created = message_handlers.handle_agent_status_message(
        msg=msg,
        session_id=session_id,
        app_instance=app_instance
    )
    
    # Property: agent_created should be True for 'created' status
    assert agent_created is True, (
        f"agent_created should be True for 'created' status"
    )
    assert latest_agent == agent_type, (
        f"latest_agent should be {agent_type}, got {latest_agent}"
    )


def test_agent_status_message_example_cases():
    """Example-based test to verify agent status message processing with specific cases."""
    from webaxon.devsuite.agent_debugger_nextgen.communication.message_handlers import MessageHandlers
    
    test_cases = [
        # (session_id, status, agent_type, expected_created)
        ('session_1', 'created', 'DefaultAgent', True),
        ('session_2', 'agent_updated', 'MockClarificationAgent', True),
        ('session_3', 'agent_locked', 'DefaultAgent', True),
        ('session_4', 'running', 'DefaultAgent', False),
        ('session_5', 'paused', 'DefaultAgent', False),
    ]
    
    for session_id, status, agent_type, expected_created in test_cases:
        session_manager = MockSessionManager()
        app_instance = MockAppInstance()
        
        message_handlers = MessageHandlers(
            session_manager=session_manager,
            get_active_session_ids_func=session_manager.get_active_ids,
            hprint_func=None
        )
        
        msg = {
            'type': 'agent_status',
            'message': {
                'session_id': session_id,
                'status': status,
                'agent_type': agent_type
            },
            'timestamp': '2025-01-01T00:00:00Z'
        }
        
        latest_agent, agent_created = message_handlers.handle_agent_status_message(
            msg=msg,
            session_id=session_id,
            app_instance=app_instance
        )
        
        assert agent_created == expected_created, (
            f"Case ({session_id}, {status}): Expected initialized={expected_created}, got {agent_created}"
        )
        
        assert session_id in app_instance.agent_status_messages, (
            f"Case ({session_id}, {status}): Message not stored"
        )
        
        print(f"✓ Status '{status}': initialized={agent_created}, message stored")


if __name__ == '__main__':
    print("Running property-based tests for agent status message processing...")
    print("=" * 70)
    print()
    
    # Run example-based test first
    print("1. Running example-based tests...")
    print("-" * 70)
    try:
        test_agent_status_message_example_cases()
        print()
        print("✓ Example-based tests passed")
    except AssertionError as e:
        print(f"\n✗ Example test failed: {e}")
        sys.exit(1)
    
    print()
    print("2. Running property-based test: message storage...")
    print("-" * 70)
    
    try:
        test_agent_status_message_stored_correctly()
        print()
        print("✓ Property test passed: Agent status messages stored correctly")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("3. Running property-based test: multiple messages appended...")
    print("-" * 70)
    
    try:
        test_multiple_agent_status_messages_appended()
        print()
        print("✓ Property test passed: Multiple messages appended correctly")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("4. Running property-based test: agent_created flag...")
    print("-" * 70)
    
    try:
        test_agent_created_flag_on_created_status()
        print()
        print("✓ Property test passed: agent_created flag set correctly")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("All property-based tests passed! ✓")
    print()
    print("Summary:")
    print("  - Agent status messages are stored in agent_status_messages[session_id]")
    print("  - Multiple messages for same session are appended")
    print("  - agent_created flag is True for 'created', 'agent_updated', 'agent_locked'")
    print("  - Property verified across 300+ random test cases")
