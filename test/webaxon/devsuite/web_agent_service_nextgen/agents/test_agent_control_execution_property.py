"""Property-based test for agent control execution.

This module contains property-based tests using hypothesis to verify
that agent_control messages execute the requested control action and
send an acknowledgment response.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
from unittest.mock import Mock, MagicMock
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

# Strategy for generating valid control commands
control_commands = st.sampled_from(['stop', 'pause', 'continue', 'step'])


def create_agent_control_message(session_id, control):
    """Helper to create a properly formatted agent_control message."""
    return {
        'type': 'agent_control',
        'message': {
            'session_id': session_id,
            'control': control
        },
        'timestamp': timestamp()
    }


# Feature: web-agent-service-modularization, Property 21: Agent Control Execution
# Validates: Requirements 6.5
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_id=session_ids,
    control_command=control_commands
)
def test_agent_control_execution_with_interactive(session_id, control_command):
    """Property: For any agent_control message with a valid control command,
    the system should execute the control action and send an acknowledgment.
    
    This test verifies that the agent_control handler executes control commands
    as specified in Requirement 6.5. The test ensures that:
    
    1. The control command is applied to the agent's interactive interface
    2. An acknowledgment response is sent
    3. The response contains all required fields: session_id, control, success
    4. The response has the correct type field
    5. The response includes a timestamp
    6. The success flag correctly reflects whether the control was applied
    7. All valid control commands (stop, pause, continue, step) are supported
    
    The test uses mocked interactive interfaces to verify that control
    commands are properly dispatched without requiring full agent infrastructure.
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
        
        # Create session with mocked interactive interface
        session_info = session_manager.get_or_create(session_id, create_immediately=True)
        
        # Create mock interactive interface with control methods
        mock_interactive = MagicMock()
        mock_interactive.stop = Mock()
        mock_interactive.pause = Mock()
        mock_interactive.resume = Mock()
        mock_interactive.step = Mock()
        
        # Update session with mock interactive
        session_manager.update_session(
            session_id=session_id,
            interactive=mock_interactive
        )
        
        # Create and dispatch agent_control message
        message = create_agent_control_message(session_id, control_command)
        message_handlers.dispatch(message)
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "agent_control handler should send an acknowledgment response"
        
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
        assert response['type'] == 'agent_control_response', \
            f"Response type should be 'agent_control_response', got {response['type']}"
        
        # Verify session_id is in response
        assert 'session_id' in response, \
            "Response must have 'session_id' field for correlation"
        assert response['session_id'] == session_id, \
            f"Response session_id should match request: expected {session_id}, got {response['session_id']}"
        
        # Verify control is in response
        assert 'control' in response, \
            "Response must have 'control' field (Requirement 6.5)"
        assert response['control'] == control_command, \
            f"Response control should match request: expected {control_command}, got {response['control']}"
        
        # Verify success flag is in response
        assert 'success' in response, \
            "Response must have 'success' flag (Requirement 6.5)"
        assert isinstance(response['success'], bool), \
            f"success should be a boolean, got {type(response['success'])}"
        
        # Verify success is True (since we have a valid interactive interface)
        assert response['success'] is True, \
            f"Control should succeed when interactive interface exists, got success={response['success']}"
        
        # Verify timestamp is in response
        assert 'timestamp' in response, \
            "Response must have 'timestamp' field"
        assert isinstance(response['timestamp'], str), \
            f"timestamp should be a string, got {type(response['timestamp'])}"
        
        # Verify that the correct control method was called on the interactive interface
        if control_command == 'stop':
            mock_interactive.stop.assert_called_once()
            mock_interactive.pause.assert_not_called()
            mock_interactive.resume.assert_not_called()
            mock_interactive.step.assert_not_called()
        elif control_command == 'pause':
            mock_interactive.stop.assert_not_called()
            mock_interactive.pause.assert_called_once()
            mock_interactive.resume.assert_not_called()
            mock_interactive.step.assert_not_called()
        elif control_command == 'continue':
            mock_interactive.stop.assert_not_called()
            mock_interactive.pause.assert_not_called()
            mock_interactive.resume.assert_called_once()
            mock_interactive.step.assert_not_called()
        elif control_command == 'step':
            mock_interactive.stop.assert_not_called()
            mock_interactive.pause.assert_not_called()
            mock_interactive.resume.assert_not_called()
            mock_interactive.step.assert_called_once()


# Feature: web-agent-service-modularization, Property 21: Agent Control Execution
# Validates: Requirements 6.5
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_id=session_ids,
    control_command=control_commands
)
def test_agent_control_execution_without_interactive(session_id, control_command):
    """Property: For any agent_control message when no interactive interface exists,
    the system should send an acknowledgment with success=False.
    
    This test verifies that the agent_control handler gracefully handles the case
    when an agent doesn't have an interactive interface. The test ensures that:
    
    1. The handler doesn't crash when interactive is None
    2. An acknowledgment response is still sent
    3. The success flag is False
    4. The response format is correct
    5. The handler maintains robustness in edge cases
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
        
        # Create session WITHOUT interactive interface
        session_info = session_manager.get_or_create(session_id, create_immediately=True)
        # Don't set interactive - it should be None
        
        # Create and dispatch agent_control message
        message = create_agent_control_message(session_id, control_command)
        
        # Dispatch should not crash
        try:
            message_handlers.dispatch(message)
        except Exception as e:
            raise AssertionError(
                f"Handler should not crash when interactive is None: {e}"
            ) from e
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "Handler should send acknowledgment even when interactive is None"
        
        # Get the response
        _, response = responses[-1]
        
        # Verify response has all required fields
        assert 'type' in response
        assert response['type'] == 'agent_control_response'
        assert 'session_id' in response
        assert response['session_id'] == session_id
        assert 'control' in response
        assert response['control'] == control_command
        assert 'success' in response
        assert 'timestamp' in response
        
        # Verify success is False (since no interactive interface)
        assert response['success'] is False, \
            f"Control should fail when interactive interface doesn't exist, got success={response['success']}"


# Feature: web-agent-service-modularization, Property 21: Agent Control Execution
# Validates: Requirements 6.5
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_id=session_ids,
    control_command=control_commands
)
def test_agent_control_execution_nonexistent_session(session_id, control_command):
    """Property: For any agent_control message for a nonexistent session,
    the system should send an acknowledgment with success=False.
    
    This test verifies that the agent_control handler gracefully handles the case
    when a session doesn't exist. The test ensures that:
    
    1. The handler doesn't crash when session doesn't exist
    2. An acknowledgment response is still sent
    3. The success flag is False
    4. The response format is correct
    5. The handler maintains robustness for invalid session IDs
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
        
        # Don't create any session - send control for nonexistent session
        
        # Create and dispatch agent_control message
        message = create_agent_control_message(session_id, control_command)
        
        # Dispatch should not crash
        try:
            message_handlers.dispatch(message)
        except Exception as e:
            raise AssertionError(
                f"Handler should not crash for nonexistent session: {e}"
            ) from e
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "Handler should send acknowledgment even for nonexistent session"
        
        # Get the response
        _, response = responses[-1]
        
        # Verify response has all required fields
        assert 'type' in response
        assert response['type'] == 'agent_control_response'
        assert 'session_id' in response
        assert response['session_id'] == session_id
        assert 'control' in response
        assert response['control'] == control_command
        assert 'success' in response
        assert 'timestamp' in response
        
        # Verify success is False (since session doesn't exist)
        assert response['success'] is False, \
            f"Control should fail for nonexistent session, got success={response['success']}"


# Feature: web-agent-service-modularization, Property 21: Agent Control Execution
# Validates: Requirements 6.5
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    session_id=session_ids,
    control_command=control_commands
)
def test_agent_control_execution_with_error(session_id, control_command):
    """Property: For any agent_control message where the control method raises an exception,
    the system should handle the error gracefully and send an acknowledgment with success=False.
    
    This test verifies that the agent_control handler is resilient to errors
    in the interactive interface. The test ensures that:
    
    1. The handler doesn't crash when control methods raise exceptions
    2. An acknowledgment response is still sent
    3. The success flag is False when an error occurs
    4. The error is logged if a debugger is available
    5. The handler maintains robustness in error conditions
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
        
        # Create session with mocked interactive interface that raises errors
        session_info = session_manager.get_or_create(session_id, create_immediately=True)
        
        # Create mock interactive interface that raises exceptions
        mock_interactive = MagicMock()
        mock_interactive.stop = Mock(side_effect=Exception("Stop failed"))
        mock_interactive.pause = Mock(side_effect=Exception("Pause failed"))
        mock_interactive.resume = Mock(side_effect=Exception("Resume failed"))
        mock_interactive.step = Mock(side_effect=Exception("Step failed"))
        
        # Update session with mock interactive
        session_manager.update_session(
            session_id=session_id,
            interactive=mock_interactive
        )
        
        # Create and dispatch agent_control message
        message = create_agent_control_message(session_id, control_command)
        
        # Dispatch should not crash even when control method raises exception
        try:
            message_handlers.dispatch(message)
        except Exception as e:
            raise AssertionError(
                f"Handler should not crash when control method raises exception: {e}"
            ) from e
        
        # Verify that a response was sent
        assert len(responses) > 0, \
            "Handler should send acknowledgment even when control method fails"
        
        # Get the response
        _, response = responses[-1]
        
        # Verify response has all required fields
        assert 'type' in response
        assert response['type'] == 'agent_control_response'
        assert 'session_id' in response
        assert response['session_id'] == session_id
        assert 'control' in response
        assert response['control'] == control_command
        assert 'success' in response
        assert 'timestamp' in response
        
        # Verify success is False (since control method raised exception)
        assert response['success'] is False, \
            f"Control should fail when control method raises exception, got success={response['success']}"


# Feature: web-agent-service-modularization, Property 21: Agent Control Execution
# Validates: Requirements 6.5
def test_agent_control_execution_invalid_control():
    """Property: For any agent_control message with an invalid control command,
    the system should send an acknowledgment with success=False.
    
    This test verifies that the agent_control handler gracefully handles
    invalid control commands. The test ensures that:
    
    1. The handler doesn't crash for unknown control commands
    2. An acknowledgment response is still sent
    3. The success flag is False for invalid commands
    4. The response format is correct
    5. The handler validates control commands
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
        
        # Create session with mocked interactive interface
        session_id = 'test_session'
        session_info = session_manager.get_or_create(session_id, create_immediately=True)
        
        mock_interactive = MagicMock()
        mock_interactive.stop = Mock()
        mock_interactive.pause = Mock()
        mock_interactive.resume = Mock()
        mock_interactive.step = Mock()
        
        session_manager.update_session(
            session_id=session_id,
            interactive=mock_interactive
        )
        
        # Test with invalid control commands
        # Note: The handler returns early if control is missing/None/empty, so no response is sent
        # We test that it doesn't crash and that valid invalid commands get a response
        invalid_controls = ['invalid', 'restart', 'kill', 123]
        
        for invalid_control in invalid_controls:
            responses.clear()
            
            # Create message with invalid control
            message = {
                'type': 'agent_control',
                'message': {
                    'session_id': session_id,
                    'control': invalid_control
                },
                'timestamp': timestamp()
            }
            
            # Dispatch should not crash
            try:
                message_handlers.dispatch(message)
            except Exception as e:
                raise AssertionError(
                    f"Handler should not crash for invalid control '{invalid_control}': {e}"
                ) from e
            
            # Verify that a response was sent
            assert len(responses) > 0, \
                f"Handler should send acknowledgment for invalid control '{invalid_control}'"
            
            # Get the response
            _, response = responses[-1]
            
            # Verify response has all required fields
            assert 'type' in response
            assert 'session_id' in response
            assert 'control' in response
            assert 'success' in response
            assert 'timestamp' in response
            
            # Verify success is False for invalid control
            assert response['success'] is False, \
                f"Control should fail for invalid command '{invalid_control}', got success={response['success']}"
            
            # Verify no control methods were called
            mock_interactive.stop.assert_not_called()
            mock_interactive.pause.assert_not_called()
            mock_interactive.resume.assert_not_called()
            mock_interactive.step.assert_not_called()
        
        # Test that empty/None control doesn't crash (but doesn't send response)
        for empty_control in ['', None]:
            responses.clear()
            
            message = {
                'type': 'agent_control',
                'message': {
                    'session_id': session_id,
                    'control': empty_control
                },
                'timestamp': timestamp()
            }
            
            # Dispatch should not crash
            try:
                message_handlers.dispatch(message)
            except Exception as e:
                raise AssertionError(
                    f"Handler should not crash for empty control '{empty_control}': {e}"
                ) from e
            
            # No response is expected for empty/None control (handler returns early)
            # This is acceptable behavior - the handler validates input


if __name__ == '__main__':
    print("Running property-based test for agent control execution...")
    print("Testing that agent_control messages execute control actions and send acknowledgments...")
    print("Testing with 100 random combinations of session IDs and control commands...")
    print()
    
    try:
        test_agent_control_execution_with_interactive()
        print("✓ Property test 1 passed: Agent control execution with interactive verified")
        print("  Control commands are applied to interactive interface")
        print("  Acknowledgment responses are sent")
        print("  All required fields are present in response")
        print("  Success flag correctly reflects execution")
        print()
        
        test_agent_control_execution_without_interactive()
        print("✓ Property test 2 passed: Agent control execution without interactive verified")
        print("  Handler doesn't crash when interactive is None")
        print("  Acknowledgment is sent with success=False")
        print("  Response format is correct")
        print()
        
        test_agent_control_execution_nonexistent_session()
        print("✓ Property test 3 passed: Agent control execution for nonexistent session verified")
        print("  Handler doesn't crash for nonexistent session")
        print("  Acknowledgment is sent with success=False")
        print("  Response format is correct")
        print()
        
        test_agent_control_execution_with_error()
        print("✓ Property test 4 passed: Agent control execution with error verified")
        print("  Handler doesn't crash when control method raises exception")
        print("  Acknowledgment is sent with success=False")
        print("  Error is handled gracefully")
        print()
        
        test_agent_control_execution_invalid_control()
        print("✓ Property test 5 passed: Agent control execution with invalid control verified")
        print("  Handler doesn't crash for invalid control commands")
        print("  Acknowledgment is sent with success=False")
        print("  No control methods are called for invalid commands")
        print()
        
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("All property-based tests passed! ✓")
