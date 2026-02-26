"""Property-based test for template version sync response.

This module contains property-based tests using hypothesis to verify
that sync_session_template_version messages produce responses containing
the current template_version for the specified session.
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

# Strategy for generating template versions
# Template versions can be empty string (default) or version strings like "v1.0", "v2.1", etc.
template_versions = st.one_of(
    st.just(''),  # Empty string for default version
    st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='.-_'),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip())
)


def create_sync_session_template_version_message(session_id, template_version):
    """Helper to create a properly formatted sync_session_template_version message."""
    return {
        'type': 'sync_session_template_version',
        'message': {
            'session_id': session_id,
            'template_version': template_version
        },
        'timestamp': timestamp()
    }


# Feature: web-agent-service-modularization, Property 20: Template Version Sync Response
# Validates: Requirements 6.4
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_id=session_ids,
    template_version=template_versions
)
def test_template_version_sync_response_completeness(session_id, template_version):
    """Property: For any sync_session_template_version message with a valid session_id,
    the response should contain the current template_version for that session.
    
    This test verifies that the sync_session_template_version handler produces complete
    responses as specified in Requirement 6.4. The test ensures that:
    
    1. The response contains a 'template_version' field
    2. The template_version field matches what was set in the session
    3. The response includes the session_id for correlation
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
        
        # Create and dispatch sync_session_template_version message
        message = create_sync_session_template_version_message(session_id, template_version)
        message_handlers.dispatch(message)
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "sync_session_template_version handler should send a response"
        
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
        assert response['type'] == 'sync_session_template_version_response', \
            f"Response type should be 'sync_session_template_version_response', got {response['type']}"
        
        # Verify session_id is in response
        assert 'session_id' in response, \
            "Response must have 'session_id' field for correlation"
        assert response['session_id'] == session_id, \
            f"Response session_id should match request: expected {session_id}, got {response['session_id']}"
        
        # Verify template_version is in response
        assert 'template_version' in response, \
            "Response must have 'template_version' field (Requirement 6.4)"
        assert isinstance(response['template_version'], str), \
            f"template_version should be a string, got {type(response['template_version'])}"
        assert response['template_version'] == template_version, \
            f"Response template_version should match what was set: expected '{template_version}', got '{response['template_version']}'"
        
        # Verify timestamp is in response
        assert 'timestamp' in response, \
            "Response must have 'timestamp' field"
        assert isinstance(response['timestamp'], str), \
            f"timestamp should be a string, got {type(response['timestamp'])}"


# Feature: web-agent-service-modularization, Property 20: Template Version Sync Response
# Validates: Requirements 6.4
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_id=session_ids,
    initial_version=template_versions,
    updated_version=template_versions
)
def test_template_version_sync_response_updates(session_id, initial_version, updated_version):
    """Property: For any session, multiple sync_session_template_version calls
    should reflect the most recent template version.
    
    This test verifies that the sync_session_template_version handler correctly
    updates and returns the current template version. The test ensures that:
    
    1. Initial sync sets the template version
    2. Subsequent sync with different version updates the template version
    3. The response always reflects the current template version
    4. Template version changes are properly persisted in session state
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
        
        # Send first sync_session_template_version message
        message1 = create_sync_session_template_version_message(session_id, initial_version)
        message_handlers.dispatch(message1)
        
        # Get first response
        _, response1 = responses[-1]
        
        # Verify first response has correct template version
        assert response1['template_version'] == initial_version, \
            f"First response should have initial version: expected '{initial_version}', got '{response1['template_version']}'"
        
        # Send second sync_session_template_version message with different version
        message2 = create_sync_session_template_version_message(session_id, updated_version)
        message_handlers.dispatch(message2)
        
        # Get second response
        _, response2 = responses[-1]
        
        # Verify second response has updated template version
        assert response2['template_version'] == updated_version, \
            f"Second response should have updated version: expected '{updated_version}', got '{response2['template_version']}'"
        
        # Verify both responses have all required fields
        for response in [response1, response2]:
            assert 'type' in response
            assert 'session_id' in response
            assert 'template_version' in response
            assert 'timestamp' in response
        
        # Verify session_id is consistent
        assert response1['session_id'] == response2['session_id'] == session_id, \
            "session_id should remain consistent across multiple sync calls"


# Feature: web-agent-service-modularization, Property 20: Template Version Sync Response
# Validates: Requirements 6.4
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_id=session_ids
)
def test_template_version_sync_response_without_version(session_id):
    """Property: For any sync_session_template_version message without template_version,
    the response should still contain the template_version field (empty string for default).
    
    This test verifies that the handler works correctly even when template_version
    is not provided in the message (edge case). The test ensures that:
    
    1. The handler doesn't crash when template_version is missing
    2. The response still contains the template_version field
    3. The template_version defaults to empty string
    4. The response is properly formatted
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
        
        # Create message without template_version
        message = {
            'type': 'sync_session_template_version',
            'message': {
                'session_id': session_id
                # No template_version field
            },
            'timestamp': timestamp()
        }
        
        # Dispatch should not crash
        try:
            message_handlers.dispatch(message)
        except Exception as e:
            raise AssertionError(
                f"Handler should not crash when template_version is missing: {e}"
            ) from e
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "Handler should send a response even when template_version is missing"
        
        # Get the response
        _, response = responses[-1]
        
        # Verify response has all required fields
        assert 'type' in response
        assert 'session_id' in response
        assert 'template_version' in response, \
            "Response must have template_version field even when not provided in message"
        assert 'timestamp' in response
        
        # Verify template_version is empty string (default)
        assert response['template_version'] == '', \
            f"When template_version not provided, should default to empty string, got '{response['template_version']}'"


# Feature: web-agent-service-modularization, Property 20: Template Version Sync Response
# Validates: Requirements 6.4
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_ids_and_versions=st.lists(
        st.tuples(session_ids, template_versions),
        min_size=1,
        max_size=10,
        unique_by=lambda x: x[0]  # Unique session IDs
    )
)
def test_template_version_sync_response_multiple_sessions(session_ids_and_versions):
    """Property: For any set of sessions with different template versions,
    each session should maintain its own independent template version.
    
    This test verifies that template versions are properly isolated per session.
    The test ensures that:
    
    1. Each session can have a different template version
    2. Setting template version for one session doesn't affect others
    3. Each session's template version is correctly returned in sync responses
    4. Template version isolation is maintained across multiple sessions
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
        
        # Set template version for each session
        for session_id, template_version in session_ids_and_versions:
            message = create_sync_session_template_version_message(session_id, template_version)
            message_handlers.dispatch(message)
        
        # Verify each session has correct template version
        # We'll sync each session again and verify the response
        for i, (session_id, expected_version) in enumerate(session_ids_and_versions):
            # Clear responses
            responses.clear()
            
            # Sync this session
            message = create_sync_session_template_version_message(session_id, expected_version)
            message_handlers.dispatch(message)
            
            # Get response
            _, response = responses[-1]
            
            # Verify this session has its own template version
            assert response['session_id'] == session_id, \
                f"Response should be for session {session_id}"
            assert response['template_version'] == expected_version, \
                f"Session {session_id} should have template version '{expected_version}', got '{response['template_version']}'"
        
        # Verify all sessions still have their correct versions
        # (no cross-contamination)
        for session_id, expected_version in session_ids_and_versions:
            session = session_manager.get(session_id)
            assert session is not None, \
                f"Session {session_id} should exist"
            assert session.info.template_version == expected_version, \
                f"Session {session_id} should maintain template version '{expected_version}', got '{session.info.template_version}'"


if __name__ == '__main__':
    print("Running property-based test for template version sync response...")
    print("Testing that sync_session_template_version responses contain template_version...")
    print("Testing with 100 random combinations of session IDs and template versions...")
    print()
    
    try:
        test_template_version_sync_response_completeness()
        print("✓ Property test 1 passed: Template version sync response completeness verified")
        print("  All responses contain template_version field")
        print("  Response fields have correct types and values")
        print("  Response format matches protocol specification")
        print()
        
        test_template_version_sync_response_updates()
        print("✓ Property test 2 passed: Template version sync response updates verified")
        print("  Template version updates are properly reflected in responses")
        print("  Multiple syncs correctly update the template version")
        print("  Session state is properly maintained")
        print()
        
        test_template_version_sync_response_without_version()
        print("✓ Property test 3 passed: Template version sync response without version verified")
        print("  Handler works correctly when template_version is missing")
        print("  Response still contains template_version field")
        print("  Default empty string is used when not provided")
        print()
        
        test_template_version_sync_response_multiple_sessions()
        print("✓ Property test 4 passed: Template version sync response multiple sessions verified")
        print("  Each session maintains its own template version")
        print("  Template versions are properly isolated per session")
        print("  No cross-contamination between sessions")
        print()
        
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("All property-based tests passed! ✓")
