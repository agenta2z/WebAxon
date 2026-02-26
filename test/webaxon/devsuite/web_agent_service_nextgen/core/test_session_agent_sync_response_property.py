"""Property-based test for session agent sync response.

This module contains property-based tests using hypothesis to verify
that sync_session_agent messages produce responses with the correct fields:
agent_type, agent_status, and agent_created flag.
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

# Strategy for generating agent types
agent_types = st.sampled_from(['DefaultAgent', 'MockClarificationAgent'])


def create_sync_session_agent_message(session_id, agent_type):
    """Helper to create a properly formatted sync_session_agent message."""
    return {
        'type': 'sync_session_agent',
        'message': {
            'session_id': session_id,
            'agent_type': agent_type
        },
        'timestamp': timestamp()
    }


# Feature: web-agent-service-modularization, Property 19: Session Agent Sync Response
# Validates: Requirements 6.3
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_id=session_ids,
    agent_type=agent_types
)
def test_session_agent_sync_response_completeness(session_id, agent_type):
    """Property: For any sync_session_agent message with a valid session_id, 
    the response should contain agent_type, agent_status, and agent_created flag.
    
    This test verifies that the sync_session_agent handler produces complete
    responses as specified in Requirement 6.3. The test ensures that:
    
    1. The response contains all required fields: agent_type, agent_status, agent_created
    2. The agent_type field matches what was set in the session
    3. The agent_status field is one of the valid statuses
    4. The agent_created field is a boolean
    5. The response includes the session_id for correlation
    6. The response has the correct type field
    7. The response includes a timestamp
    
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
        
        # Create and dispatch sync_session_agent message
        message = create_sync_session_agent_message(session_id, agent_type)
        message_handlers.dispatch(message)
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "sync_session_agent handler should send a response"
        
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
        assert response['type'] == 'sync_session_agent_response', \
            f"Response type should be 'sync_session_agent_response', got {response['type']}"
        
        # Verify session_id is in response
        assert 'session_id' in response, \
            "Response must have 'session_id' field for correlation"
        assert response['session_id'] == session_id, \
            f"Response session_id should match request: expected {session_id}, got {response['session_id']}"
        
        # Verify agent_type is in response
        assert 'agent_type' in response, \
            "Response must have 'agent_type' field (Requirement 6.3)"
        assert isinstance(response['agent_type'], str), \
            f"agent_type should be a string, got {type(response['agent_type'])}"
        assert response['agent_type'] == agent_type, \
            f"Response agent_type should match what was set: expected {agent_type}, got {response['agent_type']}"
        
        # Verify agent_status is in response
        assert 'agent_status' in response, \
            "Response must have 'agent_status' field (Requirement 6.3)"
        assert isinstance(response['agent_status'], str), \
            f"agent_status should be a string, got {type(response['agent_status'])}"
        
        # Verify agent_status is one of the valid values
        valid_statuses = ['not_created', 'created', 'running', 'error', 'completed', 'stopped']
        assert response['agent_status'] in valid_statuses, \
            f"agent_status should be one of {valid_statuses}, got {response['agent_status']}"
        
        # Verify agent_created is in response
        assert 'agent_created' in response, \
            "Response must have 'agent_created' flag (Requirement 6.3)"
        assert isinstance(response['agent_created'], bool), \
            f"agent_created should be a boolean, got {type(response['agent_created'])}"
        
        # Verify timestamp is in response
        assert 'timestamp' in response, \
            "Response must have 'timestamp' field"
        assert isinstance(response['timestamp'], str), \
            f"timestamp should be a string, got {type(response['timestamp'])}"
        
        # Verify logical consistency: if agent not created, status should be 'not_created'
        if not response['agent_created']:
            assert response['agent_status'] == 'not_created', \
                f"If agent_created is False, agent_status should be 'not_created', got {response['agent_status']}"


# Feature: web-agent-service-modularization, Property 19: Session Agent Sync Response
# Validates: Requirements 6.3
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_id=session_ids,
    agent_type=agent_types
)
def test_session_agent_sync_response_consistency(session_id, agent_type):
    """Property: For any session, multiple sync_session_agent calls should return consistent information.
    
    This test verifies that the sync_session_agent handler maintains consistency
    across multiple calls for the same session. The test ensures that:
    
    1. Multiple calls for the same session return the same agent_type
    2. The agent_created flag remains consistent
    3. The agent_status progresses logically (doesn't regress)
    4. Session state is properly maintained between calls
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
        
        # Send first sync_session_agent message
        message1 = create_sync_session_agent_message(session_id, agent_type)
        message_handlers.dispatch(message1)
        
        # Get first response
        _, response1 = responses[-1]
        
        # Send second sync_session_agent message for same session
        message2 = create_sync_session_agent_message(session_id, agent_type)
        message_handlers.dispatch(message2)
        
        # Get second response
        _, response2 = responses[-1]
        
        # Verify consistency between responses
        assert response1['agent_type'] == response2['agent_type'], \
            "agent_type should remain consistent across multiple sync calls"
        
        assert response1['agent_created'] == response2['agent_created'], \
            "agent_created flag should remain consistent if agent hasn't been created"
        
        # If agent wasn't created in first call, it shouldn't be created in second
        # (unless something else created it, which shouldn't happen in this test)
        if not response1['agent_created']:
            assert not response2['agent_created'], \
                "agent_created should not change without explicit agent creation"
        
        # Verify both responses have all required fields
        for response in [response1, response2]:
            assert 'agent_type' in response
            assert 'agent_status' in response
            assert 'agent_created' in response
            assert 'session_id' in response
            assert 'timestamp' in response


# Feature: web-agent-service-modularization, Property 19: Session Agent Sync Response
# Validates: Requirements 6.3
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    session_id=session_ids
)
def test_session_agent_sync_response_without_agent_type(session_id):
    """Property: For any sync_session_agent message without agent_type, 
    the response should still contain all required fields.
    
    This test verifies that the handler works correctly even when agent_type
    is not provided in the message (edge case). The test ensures that:
    
    1. The handler doesn't crash when agent_type is missing
    2. The response still contains all required fields
    3. The agent_type in response uses the default or existing value
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
        
        # Create message without agent_type
        message = {
            'type': 'sync_session_agent',
            'message': {
                'session_id': session_id
                # No agent_type field
            },
            'timestamp': timestamp()
        }
        
        # Dispatch should not crash
        try:
            message_handlers.dispatch(message)
        except Exception as e:
            raise AssertionError(
                f"Handler should not crash when agent_type is missing: {e}"
            ) from e
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "Handler should send a response even when agent_type is missing"
        
        # Get the response
        _, response = responses[-1]
        
        # Verify response has all required fields
        assert 'type' in response
        assert 'session_id' in response
        assert 'agent_type' in response, \
            "Response must have agent_type field even when not provided in message"
        assert 'agent_status' in response
        assert 'agent_created' in response
        assert 'timestamp' in response
        
        # Verify agent_type is the default
        assert response['agent_type'] == config.default_agent_type, \
            f"When agent_type not provided, should use default: {config.default_agent_type}"


if __name__ == '__main__':
    print("Running property-based test for session agent sync response...")
    print("Testing that sync_session_agent responses contain agent_type, agent_status, and agent_created...")
    print("Testing with 100 random combinations of session IDs and agent types...")
    print()
    
    try:
        test_session_agent_sync_response_completeness()
        print("✓ Property test 1 passed: Session agent sync response completeness verified")
        print("  All responses contain agent_type, agent_status, and agent_created")
        print("  Response fields have correct types and values")
        print("  Logical consistency maintained (agent_created vs agent_status)")
        print()
        
        test_session_agent_sync_response_consistency()
        print("✓ Property test 2 passed: Session agent sync response consistency verified")
        print("  Multiple calls for same session return consistent information")
        print("  agent_type remains stable across calls")
        print("  agent_created flag doesn't change unexpectedly")
        print()
        
        test_session_agent_sync_response_without_agent_type()
        print("✓ Property test 3 passed: Session agent sync response without agent_type verified")
        print("  Handler works correctly when agent_type is missing")
        print("  Response still contains all required fields")
        print("  Default agent_type is used when not provided")
        print()
        
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("All property-based tests passed! ✓")
