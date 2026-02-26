"""Tests for AgentRunner class.

This module tests the agent thread management functionality.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
import threading
import time
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path for imports
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session.agent_session import AgentSession
from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import AgentRunner


def test_agent_runner_initialization():
    """Test AgentRunner initialization."""
    config = ServiceConfig()
    runner = AgentRunner(config)

    assert runner._config == config
    print("✓ AgentRunner initialization works")


def test_start_agent_thread_async_mode():
    """Test starting agent in async mode (separate thread)."""
    config = ServiceConfig(synchronous_agent=False)
    runner = AgentRunner(config)

    # Create mock session
    session = Mock()
    session.session_id = 'test_session'
    session.info.session_type = 'DefaultAgent'
    session.info.last_agent_status = None

    # Create mock agent that runs for a short time
    def slow_agent():
        time.sleep(0.2)
        return 'completed'
    session.agent = Mock(side_effect=slow_agent)
    session.interactive = Mock()

    # Create mock queue service
    queue_service = Mock()

    # Start agent thread
    thread = runner.start_agent_thread(session, queue_service)

    # Verify thread was created
    assert thread is not None
    assert isinstance(thread, threading.Thread)

    # Give thread a moment to start
    time.sleep(0.05)
    assert thread.is_alive()
    assert thread.daemon is True
    assert 'AgentThread-test_session' in thread.name

    # Wait for thread to complete
    thread.join(timeout=2.0)

    # Verify status was updated
    assert session.info.last_agent_status == 'completed'

    print("✓ Agent thread creation in async mode works")


def test_start_agent_thread_synchronous_mode():
    """Test starting agent in synchronous mode (main process)."""
    config = ServiceConfig(synchronous_agent=True)
    runner = AgentRunner(config)

    # Create mock session
    session = Mock()
    session.session_id = 'test_session'
    session.info.session_type = 'DefaultAgent'
    session.info.last_agent_status = None

    # Create mock agent that completes quickly
    session.agent = Mock(return_value='completed')
    session.interactive = Mock()

    # Create mock queue service
    queue_service = Mock()

    # Start agent (should run synchronously)
    thread = runner.start_agent_thread(session, queue_service)

    # Verify no thread was created (synchronous mode)
    assert thread is None

    # Verify agent was called
    session.agent.assert_called_once()

    # Verify status was updated
    assert session.info.last_agent_status == 'completed'

    print("✓ Agent synchronous execution works")


def test_run_agent_in_thread_success():
    """Test successful agent execution in thread."""
    config = ServiceConfig()
    runner = AgentRunner(config)

    # Create mock session
    session = Mock()
    session.session_id = 'test_session'
    session.info.session_type = 'DefaultAgent'
    session.info.last_agent_status = None

    # Create mock agent
    session.agent = Mock(return_value='success')

    # Create mock queue service
    queue_service = Mock()

    # Run agent
    runner.run_agent_in_thread(session, queue_service)

    # Verify agent was called
    session.agent.assert_called_once()

    # Verify status was updated to completed
    assert session.info.last_agent_status == 'completed'

    print("✓ Agent execution in thread with success works")


def test_run_agent_in_thread_error():
    """Test agent execution error handling in thread."""
    config = ServiceConfig()
    runner = AgentRunner(config)

    # Create mock session
    session = Mock()
    session.session_id = 'test_session'
    session.info.session_type = 'DefaultAgent'
    session.info.last_agent_status = None
    session.interactive = Mock()

    # Create mock agent that raises an error
    session.agent = Mock(side_effect=RuntimeError('Test error'))

    # Create mock queue service
    queue_service = Mock()

    # Run agent (should handle error)
    runner.run_agent_in_thread(session, queue_service)

    # Verify agent was called
    session.agent.assert_called_once()

    # Verify status was updated to error
    assert session.info.last_agent_status == 'error'

    # Verify error was logged
    session.log_error.assert_called()

    # Verify error response was sent
    session.interactive.send_response.assert_called_once()
    call_args = session.interactive.send_response.call_args
    response = call_args[0][0]
    assert 'error' in response
    assert 'Test error' in response['error']

    print("✓ Agent execution error handling works")


def test_run_agent_synchronously_success():
    """Test successful synchronous agent execution."""
    config = ServiceConfig()
    runner = AgentRunner(config)

    # Create mock session
    session = Mock()
    session.session_id = 'test_session'
    session.info.session_type = 'DefaultAgent'
    session.info.last_agent_status = None

    # Create mock agent
    session.agent = Mock(return_value='success')

    # Create mock queue service
    queue_service = Mock()

    # Run agent synchronously
    runner.run_agent_synchronously(session, queue_service)

    # Verify agent was called
    session.agent.assert_called_once()

    # Verify status was updated to completed
    assert session.info.last_agent_status == 'completed'

    print("✓ Synchronous agent execution with success works")


def test_run_agent_synchronously_error():
    """Test synchronous agent execution error handling."""
    config = ServiceConfig()
    runner = AgentRunner(config)

    # Create mock session
    session = Mock()
    session.session_id = 'test_session'
    session.info.session_type = 'DefaultAgent'
    session.info.last_agent_status = None
    session.interactive = Mock()

    # Create mock agent that raises an error
    session.agent = Mock(side_effect=ValueError('Sync test error'))

    # Create mock queue service
    queue_service = Mock()

    # Run agent synchronously (should handle error)
    runner.run_agent_synchronously(session, queue_service)

    # Verify agent was called
    session.agent.assert_called_once()

    # Verify status was updated to error
    assert session.info.last_agent_status == 'error'

    # Verify error was logged
    session.log_error.assert_called()

    # Verify error response was sent
    session.interactive.send_response.assert_called_once()
    call_args = session.interactive.send_response.call_args
    response = call_args[0][0]
    assert 'error' in response
    assert 'Sync test error' in response['error']

    print("✓ Synchronous agent execution error handling works")


def test_thread_reference_tracking():
    """Test that thread reference is properly tracked."""
    config = ServiceConfig(synchronous_agent=False)
    runner = AgentRunner(config)

    # Create mock session
    session = Mock()
    session.session_id = 'test_session'
    session.info.session_type = 'DefaultAgent'

    # Create mock agent that runs for a short time
    def slow_agent():
        time.sleep(0.1)
        return 'completed'
    session.agent = Mock(side_effect=slow_agent)
    session.interactive = Mock()

    # Create mock queue service
    queue_service = Mock()

    # Start agent thread
    thread = runner.start_agent_thread(session, queue_service)

    # Verify thread reference is returned
    assert thread is not None
    assert isinstance(thread, threading.Thread)

    # Verify thread is running
    assert thread.is_alive()

    # Wait for completion
    thread.join(timeout=2.0)

    # Verify thread completed
    assert not thread.is_alive()

    print("✓ Thread reference tracking works")


def test_status_update_on_completion():
    """Test that session status is updated on agent completion."""
    config = ServiceConfig()
    runner = AgentRunner(config)

    # Create mock session
    session = Mock()
    session.session_id = 'test_session'
    session.info.session_type = 'DefaultAgent'
    session.info.last_agent_status = 'running'

    # Create mock agent
    session.agent = Mock(return_value='done')

    # Create mock queue service
    queue_service = Mock()

    # Run agent
    runner.run_agent_in_thread(session, queue_service)

    # Verify status was updated
    assert session.info.last_agent_status == 'completed'

    print("✓ Status update on completion works")


def test_status_update_on_failure():
    """Test that session status is updated on agent failure."""
    config = ServiceConfig()
    runner = AgentRunner(config)

    # Create mock session
    session = Mock()
    session.session_id = 'test_session'
    session.info.session_type = 'DefaultAgent'
    session.info.last_agent_status = 'running'
    session.interactive = Mock()

    # Create mock agent that fails
    session.agent = Mock(side_effect=Exception('Failure'))

    # Create mock queue service
    queue_service = Mock()

    # Run agent
    runner.run_agent_in_thread(session, queue_service)

    # Verify status was updated to error
    assert session.info.last_agent_status == 'error'

    print("✓ Status update on failure works")


if __name__ == '__main__':
    print("\n=== Testing AgentRunner ===\n")

    test_agent_runner_initialization()
    test_start_agent_thread_async_mode()
    test_start_agent_thread_synchronous_mode()
    test_run_agent_in_thread_success()
    test_run_agent_in_thread_error()
    test_run_agent_synchronously_success()
    test_run_agent_synchronously_error()
    test_thread_reference_tracking()
    test_status_update_on_completion()
    test_status_update_on_failure()

    print("\n=== All AgentRunner tests passed! ===\n")
