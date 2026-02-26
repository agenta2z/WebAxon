"""Property-based test for active sessions sync response.

This module contains property-based tests using hypothesis to verify
that sync_active_sessions messages produce responses containing a list
of all currently active session IDs.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
from unittest.mock import Mock
import tempfile

# Add parent directory to path
from hypothesis import given, strategies as st, settings, HealthCheck
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig, AgentSessionManager
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.communication import MessageHandlers
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from rich_python_utils.datetime_utils.common import timestamp


# Strategy for generating session IDs (filesystem-safe)
# Only use alphanumeric characters, underscores, and hyphens to avoid filesystem issues
session_ids = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-'),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip() and x[0] not in '-_')

# Strategy for generating lists of session IDs
session_id_lists = st.lists(session_ids, min_size=0, max_size=10, unique=True)


def create_sync_active_sessions_message():
    """Helper to create a properly formatted sync_active_sessions message."""
    return {
        'type': 'sync_active_sessions',
        'message': {},
        'timestamp': timestamp()
    }


# Feature: web-agent-service-modularization, Property 18: Active Sessions Sync Response
# Validates: Requirements 6.2
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_ids_to_create=session_id_lists
)
def test_active_sessions_sync_response_completeness(session_ids_to_create):
    """Property: For any sync_active_sessions message, the response should contain 
    a list of all currently active session IDs.
    
    This test verifies that the sync_active_sessions handler produces complete
    responses as specified in Requirement 6.2. The test ensures that:
    
    1. The response contains an 'active_sessions' field with a list
    2. The list contains all session IDs that were created
    3. The list doesn't contain session IDs that weren't created
    4. The response has the correct type field
    5. The response includes a timestamp
    6. The response format matches the expected protocol
    
    The test uses real SessionManager and MessageHandlers to verify the
    actual response format without mocking the response structure.
    """
    # Create a temporary directory for templates and logs
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir) / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal template structure
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            subdir_path = template_dir / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
            (subdir_path / 'default.hbs').write_text('{{input}}')
        
        # Create template manager
        template_manager = TemplateManager(
            templates=str(template_dir),
            template_formatter=handlebars_template_format
        )
        
        # Create service config
        config = ServiceConfig()
        
        # Create mock queue service that captures responses
        responses = []
        
        def mock_put(queue_id, message):
            responses.append((queue_id, message))
        
        mock_queue_service = Mock()
        mock_queue_service.put = mock_put
        mock_queue_service.get = Mock(return_value=None)
        
        # Create session manager with real dependencies
        service_log_dir = Path(temp_dir) / '_runtime'
        service_log_dir.mkdir(parents=True, exist_ok=True)
        session_manager = AgentSessionManager(
            id='test', log_name='Test', logger=[print],
            always_add_logging_based_logger=False,
            config=config,
            queue_service=mock_queue_service,
            service_log_dir=service_log_dir,
        )
        
        # Create agent factory
        agent_factory = AgentFactory(template_manager, config, testcase_root=Path(temp_dir))
        
        # Create message handlers
        message_handlers = MessageHandlers(
            session_manager=session_manager,
            agent_factory=agent_factory,
            queue_service=mock_queue_service,
            config=config
        )
        
        # Create sessions
        for session_id in session_ids_to_create:
            session_manager.get_or_create(session_id, create_immediately=True)
        
        # Create and dispatch sync_active_sessions message
        message = create_sync_active_sessions_message()
        message_handlers.dispatch(message)
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "sync_active_sessions handler should send a response"
        
        # Get the response
        queue_id, response = responses[-1]
        
        # Verify response was sent to correct queue
        assert queue_id == config.client_control_queue_id, \
            f"Response should be sent to client_control_queue, got {queue_id}"
        
        # Verify response is a dictionary
        assert isinstance(response, dict), \
            f"Response should be a dictionary, got {type(response)}"
        
        # Verify response type
        assert 'type' in response, \
            "Response must have 'type' field"
        assert response['type'] == 'sync_active_sessions_response', \
            f"Response type should be 'sync_active_sessions_response', got {response['type']}"
        
        # Verify active_sessions is in response
        assert 'active_sessions' in response, \
            "Response must have 'active_sessions' field (Requirement 6.2)"
        
        # Verify active_sessions is a list
        assert isinstance(response['active_sessions'], list), \
            f"active_sessions should be a list, got {type(response['active_sessions'])}"
        
        # Verify all created sessions are in the response
        response_session_ids = set(response['active_sessions'])
        expected_session_ids = set(session_ids_to_create)
        
        assert response_session_ids == expected_session_ids, \
            f"Response should contain all active sessions. Expected {expected_session_ids}, got {response_session_ids}"
        
        # Verify each session ID in the list is a string
        for session_id in response['active_sessions']:
            assert isinstance(session_id, str), \
                f"Each session ID should be a string, got {type(session_id)}"
        
        # Verify timestamp is in response
        assert 'timestamp' in response, \
            "Response must have 'timestamp' field"
        assert isinstance(response['timestamp'], str), \
            f"timestamp should be a string, got {type(response['timestamp'])}"


# Feature: web-agent-service-modularization, Property 18: Active Sessions Sync Response
# Validates: Requirements 6.2
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    initial_sessions=session_id_lists,
    additional_sessions=session_id_lists
)
def test_active_sessions_sync_response_updates(initial_sessions, additional_sessions):
    """Property: For any sync_active_sessions message, the response should reflect 
    the current state of active sessions, including newly created sessions.
    
    This test verifies that the sync_active_sessions handler returns up-to-date
    information about active sessions. The test ensures that:
    
    1. Initial sync returns only initially created sessions
    2. After creating more sessions, sync returns all sessions
    3. The response updates dynamically as sessions are created
    4. No duplicate session IDs appear in the response
    """
    # Create a temporary directory for templates and logs
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir) / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal template structure
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            subdir_path = template_dir / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
            (subdir_path / 'default.hbs').write_text('{{input}}')
        
        # Create template manager
        template_manager = TemplateManager(
            templates=str(template_dir),
            template_formatter=handlebars_template_format
        )
        
        # Create service config
        config = ServiceConfig()
        
        # Create mock queue service that captures responses
        responses = []
        
        def mock_put(queue_id, message):
            responses.append((queue_id, message))
        
        mock_queue_service = Mock()
        mock_queue_service.put = mock_put
        mock_queue_service.get = Mock(return_value=None)
        
        # Create session manager with real dependencies
        service_log_dir = Path(temp_dir) / '_runtime'
        service_log_dir.mkdir(parents=True, exist_ok=True)
        session_manager = AgentSessionManager(
            id='test', log_name='Test', logger=[print],
            always_add_logging_based_logger=False,
            config=config,
            queue_service=mock_queue_service,
            service_log_dir=service_log_dir,
        )
        
        # Create agent factory
        agent_factory = AgentFactory(template_manager, config, testcase_root=Path(temp_dir))
        
        # Create message handlers
        message_handlers = MessageHandlers(
            session_manager=session_manager,
            agent_factory=agent_factory,
            queue_service=mock_queue_service,
            config=config
        )
        
        # Create initial sessions
        for session_id in initial_sessions:
            session_manager.get_or_create(session_id, create_immediately=True)
        
        # First sync
        message1 = create_sync_active_sessions_message()
        message_handlers.dispatch(message1)
        
        # Get first response
        _, response1 = responses[-1]
        
        # Verify first response contains initial sessions
        response1_session_ids = set(response1['active_sessions'])
        expected1_session_ids = set(initial_sessions)
        
        assert response1_session_ids == expected1_session_ids, \
            f"First sync should return initial sessions. Expected {expected1_session_ids}, got {response1_session_ids}"
        
        # Create additional sessions (filter out duplicates)
        new_sessions = [s for s in additional_sessions if s not in initial_sessions]
        for session_id in new_sessions:
            session_manager.get_or_create(session_id, create_immediately=True)
        
        # Second sync
        message2 = create_sync_active_sessions_message()
        message_handlers.dispatch(message2)
        
        # Get second response
        _, response2 = responses[-1]
        
        # Verify second response contains all sessions
        response2_session_ids = set(response2['active_sessions'])
        expected2_session_ids = set(initial_sessions + new_sessions)
        
        assert response2_session_ids == expected2_session_ids, \
            f"Second sync should return all sessions. Expected {expected2_session_ids}, got {response2_session_ids}"
        
        # Verify no duplicates in response
        assert len(response2['active_sessions']) == len(response2_session_ids), \
            "Response should not contain duplicate session IDs"


# Feature: web-agent-service-modularization, Property 18: Active Sessions Sync Response
# Validates: Requirements 6.2
def test_active_sessions_sync_response_empty():
    """Property: For any sync_active_sessions message when no sessions exist,
    the response should contain an empty list.
    
    This test verifies that the sync_active_sessions handler correctly handles
    the case when no sessions are active. The test ensures that:
    
    1. The response is sent even when no sessions exist
    2. The active_sessions field is an empty list (not None or missing)
    3. The response format is correct
    4. The handler doesn't crash on empty session state
    """
    # Create a temporary directory for templates and logs
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir) / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal template structure
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            subdir_path = template_dir / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
            (subdir_path / 'default.hbs').write_text('{{input}}')
        
        # Create template manager
        template_manager = TemplateManager(
            templates=str(template_dir),
            template_formatter=handlebars_template_format
        )
        
        # Create service config
        config = ServiceConfig()
        
        # Create mock queue service that captures responses
        responses = []
        
        def mock_put(queue_id, message):
            responses.append((queue_id, message))
        
        mock_queue_service = Mock()
        mock_queue_service.put = mock_put
        mock_queue_service.get = Mock(return_value=None)
        
        # Create session manager with real dependencies
        service_log_dir = Path(temp_dir) / '_runtime'
        service_log_dir.mkdir(parents=True, exist_ok=True)
        session_manager = AgentSessionManager(
            id='test', log_name='Test', logger=[print],
            always_add_logging_based_logger=False,
            config=config,
            queue_service=mock_queue_service,
            service_log_dir=service_log_dir,
        )
        
        # Create agent factory
        agent_factory = AgentFactory(template_manager, config, testcase_root=Path(temp_dir))
        
        # Create message handlers
        message_handlers = MessageHandlers(
            session_manager=session_manager,
            agent_factory=agent_factory,
            queue_service=mock_queue_service,
            config=config
        )
        
        # Don't create any sessions
        
        # Send sync_active_sessions message
        message = create_sync_active_sessions_message()
        
        # Dispatch should not crash
        try:
            message_handlers.dispatch(message)
        except Exception as e:
            raise AssertionError(
                f"Handler should not crash when no sessions exist: {e}"
            ) from e
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "Handler should send a response even when no sessions exist"
        
        # Get the response
        _, response = responses[-1]
        
        # Verify response has all required fields
        assert 'type' in response
        assert response['type'] == 'sync_active_sessions_response'
        
        assert 'active_sessions' in response, \
            "Response must have active_sessions field even when empty"
        
        # Verify active_sessions is an empty list
        assert isinstance(response['active_sessions'], list), \
            f"active_sessions should be a list, got {type(response['active_sessions'])}"
        
        assert len(response['active_sessions']) == 0, \
            f"active_sessions should be empty when no sessions exist, got {response['active_sessions']}"
        
        assert 'timestamp' in response


# Feature: web-agent-service-modularization, Property 18: Active Sessions Sync Response
# Validates: Requirements 6.2
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    sessions_to_create=session_id_lists,
    sessions_to_cleanup=st.data()
)
def test_active_sessions_sync_response_after_cleanup(sessions_to_create, sessions_to_cleanup):
    """Property: For any sync_active_sessions message after session cleanup,
    the response should only contain sessions that haven't been cleaned up.
    
    This test verifies that the sync_active_sessions handler correctly reflects
    session cleanup operations. The test ensures that:
    
    1. Cleaned up sessions are not included in the response
    2. Remaining sessions are still included
    3. The response updates dynamically as sessions are cleaned up
    4. The handler maintains consistency between session state and response
    """
    # Skip if no sessions to create
    if len(sessions_to_create) == 0:
        return
    
    # Select a subset of sessions to cleanup
    sessions_to_cleanup_list = sessions_to_cleanup.draw(
        st.lists(
            st.sampled_from(sessions_to_create),
            min_size=0,
            max_size=len(sessions_to_create),
            unique=True
        )
    )
    
    # Create a temporary directory for templates and logs
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir) / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal template structure
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            subdir_path = template_dir / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
            (subdir_path / 'default.hbs').write_text('{{input}}')
        
        # Create template manager
        template_manager = TemplateManager(
            templates=str(template_dir),
            template_formatter=handlebars_template_format
        )
        
        # Create service config
        config = ServiceConfig()
        
        # Create mock queue service that captures responses
        responses = []
        
        def mock_put(queue_id, message):
            responses.append((queue_id, message))
        
        mock_queue_service = Mock()
        mock_queue_service.put = mock_put
        mock_queue_service.get = Mock(return_value=None)
        
        # Create session manager with real dependencies
        service_log_dir = Path(temp_dir) / '_runtime'
        service_log_dir.mkdir(parents=True, exist_ok=True)
        session_manager = AgentSessionManager(
            id='test', log_name='Test', logger=[print],
            always_add_logging_based_logger=False,
            config=config,
            queue_service=mock_queue_service,
            service_log_dir=service_log_dir,
        )
        
        # Create agent factory
        agent_factory = AgentFactory(template_manager, config, testcase_root=Path(temp_dir))
        
        # Create message handlers
        message_handlers = MessageHandlers(
            session_manager=session_manager,
            agent_factory=agent_factory,
            queue_service=mock_queue_service,
            config=config
        )
        
        # Create all sessions
        for session_id in sessions_to_create:
            session_manager.get_or_create(session_id, create_immediately=True)
        
        # Cleanup selected sessions
        for session_id in sessions_to_cleanup_list:
            session_manager.cleanup_session(session_id)
        
        # Sync after cleanup
        message = create_sync_active_sessions_message()
        message_handlers.dispatch(message)
        
        # Get the response
        _, response = responses[-1]
        
        # Verify response contains only remaining sessions
        response_session_ids = set(response['active_sessions'])
        expected_session_ids = set(sessions_to_create) - set(sessions_to_cleanup_list)
        
        assert response_session_ids == expected_session_ids, \
            f"Response should only contain sessions that weren't cleaned up. Expected {expected_session_ids}, got {response_session_ids}"
        
        # Verify cleaned up sessions are not in response
        for session_id in sessions_to_cleanup_list:
            assert session_id not in response['active_sessions'], \
                f"Cleaned up session {session_id} should not be in active_sessions"


if __name__ == '__main__':
    print("Running property-based test for active sessions sync response...")
    print("Testing that sync_active_sessions responses contain all active session IDs...")
    print("Testing with 100 random combinations of session configurations...")
    print()
    
    try:
        test_active_sessions_sync_response_completeness()
        print("✓ Property test 1 passed: Active sessions sync response completeness verified")
        print("  All responses contain active_sessions list")
        print("  Response includes all created sessions")
        print("  Response format is correct")
        print()
        
        test_active_sessions_sync_response_updates()
        print("✓ Property test 2 passed: Active sessions sync response updates verified")
        print("  Response reflects current state of sessions")
        print("  Newly created sessions appear in subsequent syncs")
        print("  No duplicate session IDs in response")
        print()
        
        test_active_sessions_sync_response_empty()
        print("✓ Property test 3 passed: Active sessions sync response empty case verified")
        print("  Handler works correctly when no sessions exist")
        print("  Response contains empty list (not None)")
        print("  Response format is correct")
        print()
        
        test_active_sessions_sync_response_after_cleanup()
        print("✓ Property test 4 passed: Active sessions sync response after cleanup verified")
        print("  Cleaned up sessions are not included in response")
        print("  Remaining sessions are still included")
        print("  Response updates dynamically with cleanup")
        print()
        
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("All property-based tests passed! ✓")
