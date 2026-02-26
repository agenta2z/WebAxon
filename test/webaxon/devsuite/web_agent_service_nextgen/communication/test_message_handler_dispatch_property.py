"""Property-based test for message handler dispatch.

This module contains property-based tests using hypothesis to verify
that control messages are dispatched through MessageHandlers.dispatch()
and routed to the correct handlers.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile

# Add parent directory to path
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig, AgentSessionManager
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.communication import MessageHandlers
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from rich_python_utils.datetime_utils.common import timestamp


# Strategy for generating valid message types
valid_message_types = st.sampled_from([
    'sync_active_sessions',
    'sync_session_agent',
    'sync_session_template_version',
    'agent_control'
])

# Strategy for generating session IDs
session_ids = st.text(min_size=1, max_size=50).filter(lambda x: x.strip())

# Strategy for generating agent types
agent_types = st.sampled_from(['DefaultAgent', 'MockClarificationAgent'])

# Strategy for generating control commands
control_commands = st.sampled_from(['stop', 'pause', 'continue', 'step'])

# Strategy for generating template versions
template_versions = st.text(min_size=0, max_size=20)


def create_message(message_type, **kwargs):
    """Helper to create a properly formatted message."""
    message = {
        'type': message_type,
        'message': kwargs,
        'timestamp': timestamp()
    }
    return message


# Feature: web-agent-service-modularization, Property 17: Message Handler Dispatch
# Validates: Requirements 6.1
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    message_type=valid_message_types,
    session_id=session_ids,
    agent_type=agent_types,
    control_command=control_commands,
    template_version=template_versions
)
def test_message_handler_dispatch(message_type, session_id, agent_type, control_command, template_version):
    """Property: For any control message received, it should be dispatched through MessageHandlers.dispatch().
    
    This test verifies that message handling is centralized through the dispatch
    method as specified in Requirement 6.1. The test ensures that:
    
    1. All control messages go through MessageHandlers.dispatch()
    2. Messages are correctly routed to their specific handlers
    3. Each handler is called with the correct message
    4. Unknown message types are handled gracefully
    5. The dispatch mechanism doesn't crash on any valid message format
    
    The test uses mocking to verify that the correct handler methods are called
    for each message type without requiring full service infrastructure.
    """
    # Create a temporary directory for templates
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
        
        # Create mock queue service
        mock_queue_service = Mock()
        mock_queue_service.put = Mock()
        mock_queue_service.get = Mock(return_value=None)
        
        # Create session manager with mocked dependencies
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
        
        # Verify that MessageHandlers has a dispatch method
        assert hasattr(message_handlers, 'dispatch'), \
            "MessageHandlers must have dispatch method for centralized message handling"
        
        assert callable(message_handlers.dispatch), \
            "MessageHandlers.dispatch must be callable"
        
        # Create a message based on the message type
        if message_type == 'sync_active_sessions':
            message = create_message(message_type, active_sessions=[session_id])
        elif message_type == 'sync_session_agent':
            message = create_message(message_type, session_id=session_id, agent_type=agent_type)
        elif message_type == 'sync_session_template_version':
            message = create_message(message_type, session_id=session_id, template_version=template_version)
        elif message_type == 'agent_control':
            message = create_message(message_type, session_id=session_id, control=control_command)
        else:
            # Should not happen with our strategy, but handle it
            message = create_message(message_type)
        
        # Mock the individual handler methods to verify they're called
        with patch.object(message_handlers, 'handle_sync_active_sessions') as mock_sync_active:
            with patch.object(message_handlers, 'handle_sync_session_agent') as mock_sync_agent:
                with patch.object(message_handlers, 'handle_sync_session_template_version') as mock_sync_template:
                    with patch.object(message_handlers, 'handle_agent_control') as mock_agent_control:
                        
                        # Dispatch the message
                        try:
                            message_handlers.dispatch(message)
                        except Exception as e:
                            raise AssertionError(
                                f"MessageHandlers.dispatch should not raise exception for valid message: {e}"
                            ) from e
                        
                        # Verify that the correct handler was called
                        if message_type == 'sync_active_sessions':
                            mock_sync_active.assert_called_once_with(message)
                            mock_sync_agent.assert_not_called()
                            mock_sync_template.assert_not_called()
                            mock_agent_control.assert_not_called()
                        elif message_type == 'sync_session_agent':
                            mock_sync_active.assert_not_called()
                            mock_sync_agent.assert_called_once_with(message)
                            mock_sync_template.assert_not_called()
                            mock_agent_control.assert_not_called()
                        elif message_type == 'sync_session_template_version':
                            mock_sync_active.assert_not_called()
                            mock_sync_agent.assert_not_called()
                            mock_sync_template.assert_called_once_with(message)
                            mock_agent_control.assert_not_called()
                        elif message_type == 'agent_control':
                            mock_sync_active.assert_not_called()
                            mock_sync_agent.assert_not_called()
                            mock_sync_template.assert_not_called()
                            mock_agent_control.assert_called_once_with(message)
        
        # Test that unknown message types are handled gracefully
        unknown_message = create_message('unknown_message_type', data='test')
        
        try:
            message_handlers.dispatch(unknown_message)
            # Should not raise an exception
        except Exception as e:
            raise AssertionError(
                f"MessageHandlers.dispatch should handle unknown message types gracefully: {e}"
            ) from e
        
        # Test that invalid message formats are handled gracefully
        invalid_messages = [
            None,
            "not a dict",
            123,
            [],
            {'no_type_field': 'value'}
        ]
        
        for invalid_msg in invalid_messages:
            try:
                message_handlers.dispatch(invalid_msg)
                # Should not raise an exception
            except Exception as e:
                raise AssertionError(
                    f"MessageHandlers.dispatch should handle invalid message formats gracefully: {e}"
                ) from e
        
        # Verify that all handler methods exist
        handler_methods = [
            'handle_sync_active_sessions',
            'handle_sync_session_agent',
            'handle_sync_session_template_version',
            'handle_agent_control'
        ]
        
        for method_name in handler_methods:
            assert hasattr(message_handlers, method_name), \
                f"MessageHandlers must have {method_name} method"
            assert callable(getattr(message_handlers, method_name)), \
                f"MessageHandlers.{method_name} must be callable"


# Feature: web-agent-service-modularization, Property 17: Message Handler Dispatch
# Validates: Requirements 6.1
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    message_type=valid_message_types,
    session_id=session_ids
)
def test_dispatch_calls_correct_handler(message_type, session_id):
    """Property: For any message type, dispatch should route to the correct handler.
    
    This is a focused test that verifies the routing logic in dispatch()
    without testing the full handler implementation. It ensures that:
    
    1. Each message type maps to exactly one handler
    2. The handler is called with the original message
    3. No other handlers are called
    4. The dispatch mechanism is deterministic
    """
    # Create minimal mocked components
    mock_session_manager = Mock()
    mock_agent_factory = Mock()
    mock_queue_service = Mock()
    config = ServiceConfig()
    
    # Create message handlers
    message_handlers = MessageHandlers(
        session_manager=mock_session_manager,
        agent_factory=mock_agent_factory,
        queue_service=mock_queue_service,
        config=config
    )
    
    # Create a simple message
    message = {
        'type': message_type,
        'message': {'session_id': session_id},
        'timestamp': timestamp()
    }
    
    # Mock all handler methods
    with patch.object(message_handlers, 'handle_sync_active_sessions') as mock_h1:
        with patch.object(message_handlers, 'handle_sync_session_agent') as mock_h2:
            with patch.object(message_handlers, 'handle_sync_session_template_version') as mock_h3:
                with patch.object(message_handlers, 'handle_agent_control') as mock_h4:
                    
                    # Dispatch the message
                    message_handlers.dispatch(message)
                    
                    # Count how many handlers were called
                    handlers_called = sum([
                        mock_h1.called,
                        mock_h2.called,
                        mock_h3.called,
                        mock_h4.called
                    ])
                    
                    # Verify exactly one handler was called
                    assert handlers_called == 1, \
                        f"Dispatch should call exactly one handler, but called {handlers_called}"
                    
                    # Verify the correct handler was called with the message
                    if message_type == 'sync_active_sessions':
                        mock_h1.assert_called_once_with(message)
                    elif message_type == 'sync_session_agent':
                        mock_h2.assert_called_once_with(message)
                    elif message_type == 'sync_session_template_version':
                        mock_h3.assert_called_once_with(message)
                    elif message_type == 'agent_control':
                        mock_h4.assert_called_once_with(message)


if __name__ == '__main__':
    print("Running property-based test for message handler dispatch...")
    print("Testing that control messages are dispatched through MessageHandlers.dispatch()...")
    print("Testing with 100 random combinations of message types and parameters...")
    print()
    
    try:
        test_message_handler_dispatch()
        print("✓ Property test 1 passed: Message handler dispatch verified")
        print("  All control messages go through MessageHandlers.dispatch()")
        print("  Messages are correctly routed to their handlers")
        print("  Unknown message types are handled gracefully")
        print("  Invalid message formats don't crash the system")
        print()
        
        test_dispatch_calls_correct_handler()
        print("✓ Property test 2 passed: Dispatch routing verified")
        print("  Each message type routes to exactly one handler")
        print("  Handlers receive the original message")
        print("  Routing is deterministic and correct")
        print()
        
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("All property-based tests passed! ✓")
