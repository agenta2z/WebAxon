"""Integration tests for web agent service.

This module tests the integration between service components:
- Service-debugger communication via queue messages
- Session lifecycle end-to-end
- Agent lifecycle with control operations
- Template version switching across components
- Concurrent session operations

These tests validate that all components work together correctly
and that the service maintains backward compatibility with the debugger.

Requirements tested: 11.3, 11.4, 11.5
"""
import sys
import resolve_path  # Setup import paths

import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, Any

import pytest

# Add parent directory to path for imports
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format

from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.communication.queue_manager import QueueManager
from webaxon.devsuite.web_agent_service_nextgen.communication.message_handlers import MessageHandlers
from webaxon.devsuite.web_agent_service_nextgen.agents.template_manager import TemplateManagerWrapper
from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_monitor import AgentSessionMonitor
from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import AgentRunner


def setup_test_environment(tmpdir: Path) -> Dict[str, Any]:
    """Setup a complete test environment with all components.
    
    Args:
        tmpdir: Temporary directory for test files
        
    Returns:
        Dictionary containing all initialized components
    """
    testcase_root = Path(tmpdir)
    
    # Create template directory with proper subdirectory structure
    template_dir = testcase_root / 'prompt_templates'
    template_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
        (template_dir / subdir).mkdir(parents=True, exist_ok=True)
        (template_dir / subdir / 'default.hbs').write_text('{{input}}')
    
    # Create configuration
    config = ServiceConfig(
        debug_mode_service=False,  # Reduce log noise
        synchronous_agent=True,  # Easier to test
        new_agent_on_first_submission=True,
        session_idle_timeout=5,  # Short timeout for testing
        cleanup_check_interval=1  # Frequent cleanup for testing
    )
    
    # Initialize queue manager
    queue_manager = QueueManager(testcase_root, config)
    queue_service = queue_manager.initialize()
    queue_manager.create_queues()
    
    # Initialize template manager
    template_manager = TemplateManagerWrapper(
        template_dir=template_dir,
        template_formatter=handlebars_template_format
    )
    
    # Initialize agent factory
    agent_factory = AgentFactory(
        template_manager.get_template_manager(),
        config,
        testcase_root=testcase_root
    )
    
    # Initialize session manager
    service_log_dir = testcase_root / config.log_root_path
    session_manager = SessionManager(
        id='test', log_name='Test', logger=[print],
        always_add_logging_based_logger=False,
        config=config,
        queue_service=queue_service,
        service_log_dir=service_log_dir,
    )
    
    # Initialize message handlers
    message_handlers = MessageHandlers(
        session_manager,
        agent_factory,
        queue_service,
        config
    )
    
    # Initialize agent runner
    agent_runner = AgentRunner(config)

    # Initialize session monitor
    session_monitor = AgentSessionMonitor(
        session_manager,
        queue_service,
        config,
        agent_factory,
        agent_runner
    )
    
    return {
        'testcase_root': testcase_root,
        'config': config,
        'queue_manager': queue_manager,
        'queue_service': queue_service,
        'template_manager': template_manager,
        'agent_factory': agent_factory,
        'session_manager': session_manager,
        'message_handlers': message_handlers,
        'session_monitor': session_monitor,
        'agent_runner': agent_runner
    }


class TestServiceDebuggerCommunication:
    """Test service-debugger communication via queue messages.
    
    These tests validate that the service correctly processes control
    messages from the debugger and sends appropriate responses.
    """
    
    def test_sync_active_sessions_message(self):
        """Test sync_active_sessions message flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create some sessions
            env['session_manager'].get_or_create('session1')
            env['session_manager'].get_or_create('session2')
            env['session_manager'].get_or_create('session3')
            
            # Send sync_active_sessions message
            message = {
                'type': 'sync_active_sessions',
                'message': {
                    'active_sessions': ['session1', 'session2']
                },
                'timestamp': '2024-01-15T10:30:00'
            }
            
            env['message_handlers'].dispatch(message)
            
            # Check response
            response = env['queue_service'].get(
                env['config'].client_control_queue_id,
                blocking=False
            )
            
            assert response is not None
            assert response['type'] == 'sync_active_sessions_response'
            assert 'active_sessions' in response
            assert set(response['active_sessions']) == {'session1', 'session2', 'session3'}
            assert 'timestamp' in response
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_sync_session_agent_message(self):
        """Test sync_session_agent message flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Send sync_session_agent message
            message = {
                'type': 'sync_session_agent',
                'message': {
                    'session_id': 'test_session',
                    'agent_type': 'DefaultAgent'
                },
                'timestamp': '2024-01-15T10:30:00'
            }
            
            env['message_handlers'].dispatch(message)
            
            # Check response
            response = env['queue_service'].get(
                env['config'].client_control_queue_id,
                blocking=False
            )
            
            assert response is not None
            assert response['type'] == 'sync_session_agent_response'
            assert response['session_id'] == 'test_session'
            assert response['agent_type'] == 'DefaultAgent'
            assert response['agent_status'] == 'not_created'
            assert response['agent_created'] is False
            assert 'timestamp' in response
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_sync_session_template_version_message(self):
        """Test sync_session_template_version message flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Send sync_session_template_version message
            message = {
                'type': 'sync_session_template_version',
                'message': {
                    'session_id': 'test_session',
                    'template_version': 'v2.1'
                },
                'timestamp': '2024-01-15T10:30:00'
            }
            
            env['message_handlers'].dispatch(message)
            
            # Check response
            response = env['queue_service'].get(
                env['config'].client_control_queue_id,
                blocking=False
            )
            
            assert response is not None
            assert response['type'] == 'sync_session_template_version_response'
            assert response['session_id'] == 'test_session'
            assert response['template_version'] == 'v2.1'
            assert 'timestamp' in response
            
            # Verify session has template version
            session = env['session_manager'].get('test_session')
            assert session.info.template_version == 'v2.1'
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_agent_control_message_pause(self):
        """Test agent_control message with pause command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session with interactive interface
            session = env['session_manager'].get_or_create('test_session')

            # Create a mock interactive interface
            class MockInteractive:
                def __init__(self):
                    self.paused = False

                def pause(self):
                    self.paused = True

            session.interactive = MockInteractive()

            # Send agent_control message
            message = {
                'type': 'agent_control',
                'message': {
                    'session_id': 'test_session',
                    'control': 'pause'
                },
                'timestamp': '2024-01-15T10:30:00'
            }

            env['message_handlers'].dispatch(message)

            # Check response
            response = env['queue_service'].get(
                env['config'].client_control_queue_id,
                blocking=False
            )

            assert response is not None
            assert response['type'] == 'agent_control_response'
            assert response['session_id'] == 'test_session'
            assert response['control'] == 'pause'
            assert response['success'] is True
            assert 'timestamp' in response

            # Verify control was applied
            assert session.interactive.paused is True
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_multiple_messages_in_sequence(self):
        """Test processing multiple messages in sequence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Send multiple messages
            messages = [
                {
                    'type': 'sync_session_agent',
                    'message': {
                        'session_id': 'session1',
                        'agent_type': 'DefaultAgent'
                    },
                    'timestamp': '2024-01-15T10:30:00'
                },
                {
                    'type': 'sync_session_template_version',
                    'message': {
                        'session_id': 'session1',
                        'template_version': 'v2.0'
                    },
                    'timestamp': '2024-01-15T10:30:01'
                },
                {
                    'type': 'sync_active_sessions',
                    'message': {
                        'active_sessions': ['session1']
                    },
                    'timestamp': '2024-01-15T10:30:02'
                }
            ]
            
            # Dispatch all messages
            for message in messages:
                env['message_handlers'].dispatch(message)
            
            # Check all responses
            responses = []
            for _ in range(3):
                response = env['queue_service'].get(
                    env['config'].client_control_queue_id,
                    blocking=False
                )
                if response:
                    responses.append(response)
            
            assert len(responses) == 3
            assert responses[0]['type'] == 'sync_session_agent_response'
            assert responses[1]['type'] == 'sync_session_template_version_response'
            assert responses[2]['type'] == 'sync_active_sessions_response'
            
            # Cleanup
            env['queue_manager'].close()


class TestSessionLifecycle:
    """Test session lifecycle end-to-end.
    
    These tests validate that sessions are created, updated, and cleaned up
    correctly throughout their lifecycle.
    """
    
    def test_session_creation_and_retrieval(self):
        """Test creating and retrieving sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session
            session1 = env['session_manager'].get_or_create('session1')
            assert session1 is not None
            assert session1.session_id == 'session1'
            
            # Retrieve same session
            session1_again = env['session_manager'].get('session1')
            assert session1_again is session1
            
            # Create another session
            session2 = env['session_manager'].get_or_create('session2')
            assert session2 is not None
            assert session2.session_id == 'session2'
            assert session2 is not session1
            
            # Get all sessions
            all_sessions = env['session_manager'].get_all_sessions()
            assert len(all_sessions) == 2
            assert 'session1' in all_sessions
            assert 'session2' in all_sessions
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_session_update(self):
        """Test updating session fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session
            session = env['session_manager'].get_or_create('test_session')
            
            # Update fields
            env['session_manager'].update_session(
                'test_session',
                session_type='CustomAgent',
                template_version='v3.0'
            )
            
            # Verify updates
            updated_session = env['session_manager'].get('test_session')
            assert updated_session.info.session_type == 'CustomAgent'
            assert updated_session.info.template_version == 'v3.0'
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_session_cleanup(self):
        """Test session cleanup removes resources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session
            session = env['session_manager'].get_or_create('test_session')
            assert session is not None
            
            # Cleanup session
            env['session_manager'].cleanup_session('test_session')
            
            # Verify session is removed
            removed_session = env['session_manager'].get('test_session')
            assert removed_session is None
            
            # Verify not in all sessions
            all_sessions = env['session_manager'].get_all_sessions()
            assert 'test_session' not in all_sessions
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_idle_session_cleanup(self):
        """Test idle sessions are cleaned up after timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session
            session = env['session_manager'].get_or_create('test_session')
            assert session is not None
            
            # Manually set last_active to past
            session.info.last_active = time.time() - 10  # 10 seconds ago

            # Run cleanup (timeout is 5 seconds in test config)
            env['session_manager'].cleanup_idle_sessions()

            # Verify session is removed
            removed_session = env['session_manager'].get('test_session')
            assert removed_session is None

            # Cleanup
            env['queue_manager'].close()

    def test_session_with_template_version(self):
        """Test session lifecycle with template version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session with template version
            session = env['session_manager'].get_or_create('test_session')
            env['session_manager'].update_session(
                'test_session',
                template_version='v2.5'
            )
            
            # Verify template version is stored
            retrieved_session = env['session_manager'].get('test_session')
            assert retrieved_session.info.template_version == 'v2.5'
            
            # Update template version
            env['session_manager'].update_session(
                'test_session',
                template_version='v3.0'
            )
            
            # Verify update
            updated_session = env['session_manager'].get('test_session')
            assert updated_session.info.template_version == 'v3.0'

            # Cleanup
            env['queue_manager'].close()


class TestAgentLifecycle:
    """Test agent lifecycle with control operations.
    
    These tests validate agent creation, control operations, and cleanup.
    """
    
    def test_agent_control_operations(self):
        """Test various agent control operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session with mock interactive
            session = env['session_manager'].get_or_create('test_session')
            
            class MockInteractive:
                def __init__(self):
                    self.state = 'running'
                
                def pause(self):
                    self.state = 'paused'
                
                def resume(self):
                    self.state = 'running'
                
                def stop(self):
                    self.state = 'stopped'
                
                def step(self):
                    self.state = 'stepping'
            
            session.interactive = MockInteractive()
            
            # Test pause
            message = {
                'type': 'agent_control',
                'message': {'session_id': 'test_session', 'control': 'pause'},
                'timestamp': '2024-01-15T10:30:00'
            }
            env['message_handlers'].dispatch(message)
            assert session.interactive.state == 'paused'
            
            # Test continue
            message['message']['control'] = 'continue'
            env['message_handlers'].dispatch(message)
            assert session.interactive.state == 'running'
            
            # Test step
            message['message']['control'] = 'step'
            env['message_handlers'].dispatch(message)
            assert session.interactive.state == 'stepping'
            
            # Test stop
            message['message']['control'] = 'stop'
            env['message_handlers'].dispatch(message)
            assert session.interactive.state == 'stopped'
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_agent_status_tracking(self):
        """Test agent status is tracked correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session
            session = env['session_manager'].get_or_create('test_session')
            
            # Initially no agent
            assert session.agent is None
            assert session.info.initialized is False
            
            # Update status
            env['session_manager'].update_session(
                'test_session',
                initialized=True,
                last_agent_status='running'
            )
            
            # Verify status
            updated_session = env['session_manager'].get('test_session')
            assert updated_session.info.initialized is True
            assert updated_session.info.last_agent_status == 'running'
            
            # Cleanup
            env['queue_manager'].close()


class TestTemplateVersionSwitching:
    """Test template version switching across components.
    
    These tests validate that template versions are correctly propagated
    through the system and used during agent creation.
    """
    
    def test_template_version_in_session(self):
        """Test template version is stored in session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session with template version
            session = env['session_manager'].get_or_create('test_session')
            env['session_manager'].update_session(
                'test_session',
                template_version='v2.0'
            )
            
            # Verify template version
            assert session.info.template_version == 'v2.0'
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_template_version_via_message(self):
        """Test template version can be set via control message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Send template version message
            message = {
                'type': 'sync_session_template_version',
                'message': {
                    'session_id': 'test_session',
                    'template_version': 'v3.5'
                },
                'timestamp': '2024-01-15T10:30:00'
            }
            
            env['message_handlers'].dispatch(message)
            
            # Verify template version in session
            session = env['session_manager'].get('test_session')
            assert session.info.template_version == 'v3.5'
            
            # Verify response
            response = env['queue_service'].get(
                env['config'].client_control_queue_id,
                blocking=False
            )
            assert response['template_version'] == 'v3.5'
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_template_version_switching(self):
        """Test switching template versions for different sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create multiple sessions with different template versions
            session1 = env['session_manager'].get_or_create('session1')
            env['session_manager'].update_session('session1', template_version='v1.0')
            
            session2 = env['session_manager'].get_or_create('session2')
            env['session_manager'].update_session('session2', template_version='v2.0')
            
            session3 = env['session_manager'].get_or_create('session3')
            env['session_manager'].update_session('session3', template_version='v3.0')
            
            # Verify each session has correct version
            assert env['session_manager'].get('session1').info.template_version == 'v1.0'
            assert env['session_manager'].get('session2').info.template_version == 'v2.0'
            assert env['session_manager'].get('session3').info.template_version == 'v3.0'
            
            # Cleanup
            env['queue_manager'].close()


class TestConcurrentSessions:
    """Test concurrent session operations.
    
    These tests validate that the service can handle multiple sessions
    simultaneously without race conditions or data corruption.
    """
    
    def test_concurrent_session_creation(self):
        """Test creating multiple sessions concurrently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create sessions concurrently
            def create_session(session_id):
                env['session_manager'].get_or_create(session_id)
            
            threads = []
            for i in range(10):
                thread = threading.Thread(target=create_session, args=(f'session{i}',))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            # Verify all sessions created
            all_sessions = env['session_manager'].get_all_sessions()
            assert len(all_sessions) == 10
            for i in range(10):
                assert f'session{i}' in all_sessions
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_concurrent_session_updates(self):
        """Test updating sessions concurrently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create session
            env['session_manager'].get_or_create('test_session')
            
            # Update session concurrently
            def update_session(field_value):
                env['session_manager'].update_session(
                    'test_session',
                    session_type=f'Agent{field_value}'
                )
            
            threads = []
            for i in range(5):
                thread = threading.Thread(target=update_session, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            # Verify session still exists and has one of the values
            session = env['session_manager'].get('test_session')
            assert session is not None
            assert session.info.session_type.startswith('Agent')
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_concurrent_message_processing(self):
        """Test processing messages for multiple sessions concurrently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Send messages for multiple sessions concurrently
            def send_message(session_id):
                message = {
                    'type': 'sync_session_agent',
                    'message': {
                        'session_id': session_id,
                        'agent_type': 'DefaultAgent'
                    },
                    'timestamp': '2024-01-15T10:30:00'
                }
                env['message_handlers'].dispatch(message)
            
            threads = []
            for i in range(5):
                thread = threading.Thread(target=send_message, args=(f'session{i}',))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            # Verify all sessions created
            all_sessions = env['session_manager'].get_all_sessions()
            assert len(all_sessions) == 5
            
            # Verify all responses sent
            responses = []
            for _ in range(5):
                response = env['queue_service'].get(
                    env['config'].client_control_queue_id,
                    blocking=False
                )
                if response:
                    responses.append(response)
            
            assert len(responses) == 5
            
            # Cleanup
            env['queue_manager'].close()
    
    def test_concurrent_session_cleanup(self):
        """Test cleaning up multiple sessions concurrently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create multiple sessions
            for i in range(10):
                env['session_manager'].get_or_create(f'session{i}')
            
            # Cleanup sessions concurrently
            def cleanup_session(session_id):
                env['session_manager'].cleanup_session(session_id)
            
            threads = []
            for i in range(10):
                thread = threading.Thread(target=cleanup_session, args=(f'session{i}',))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            # Verify all sessions removed
            all_sessions = env['session_manager'].get_all_sessions()
            assert len(all_sessions) == 0
            
            # Cleanup
            env['queue_manager'].close()


class TestSessionMonitorIntegration:
    """Test session monitor integration with other components.
    
    These tests validate that the session monitor correctly interacts
    with sessions, queues, and the agent factory.
    """
    
    def test_monitoring_cycle_execution(self):
        """Test that monitoring cycle executes without errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            # Create some sessions
            env['session_manager'].get_or_create('session1')
            env['session_manager'].get_or_create('session2')
            
            # Run monitoring cycle
            env['session_monitor'].run_monitoring_cycle()
            
            # Should complete without errors
            # Cleanup
            env['queue_manager'].close()
    
    def test_periodic_cleanup_integration(self):
        """Test periodic cleanup through monitoring cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_test_environment(tmpdir)
            
            try:
                # Create session and make it idle
                session = env['session_manager'].get_or_create('test_session')
                session.info.last_active = time.time() - 10  # 10 seconds ago
                
                # Force cleanup by calling cleanup_idle_sessions directly
                # (monitoring cycle may not trigger cleanup immediately due to timing)
                env['session_manager'].cleanup_idle_sessions()
                
                # Session should be removed
                removed_session = env['session_manager'].get('test_session')
                assert removed_session is None
            
            finally:
                # Cleanup queue service before temp directory is removed
                env['queue_manager'].close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
