"""Tests for SessionMonitor class.

This module tests the session monitoring functionality including:
- Status change detection
- Lazy agent creation
- Periodic cleanup
- Error resilience
"""
import sys
import resolve_path  # Setup import paths

import time
import threading
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path for imports
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager, AgentSession
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_monitor import AgentSessionMonitor


def test_session_monitor_initialization():
    """Test SessionMonitor initialization."""
    # Create mocks
    session_manager = Mock(spec=SessionManager)
    queue_service = Mock()
    config = ServiceConfig()
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory,
        agent_runner=Mock()
    )

    # Verify initialization
    assert monitor._session_manager == session_manager
    assert monitor._queue_service == queue_service
    assert monitor._config == config
    assert monitor._agent_factory == agent_factory
    assert isinstance(monitor._last_cleanup_time, float)
    
    print("✓ SessionMonitor initialization test passed")


def test_check_status_changes_no_sessions():
    """Test status change detection with no sessions."""
    # Create mocks
    session_manager = Mock(spec=SessionManager)
    session_manager.get_all_sessions.return_value = {}
    queue_service = Mock()
    config = ServiceConfig()
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory,
        agent_runner=Mock()
    )

    # Run check - should not raise error
    monitor.check_status_changes()

    # Verify get_all_sessions was called
    session_manager.get_all_sessions.assert_called_once()
    
    print("✓ Status change detection with no sessions test passed")


def test_check_status_changes_with_agent():
    """Test status change detection with active agent."""
    # Create mocks
    session_manager = Mock(spec=SessionManager)
    queue_service = Mock()
    config = ServiceConfig()
    agent_factory = Mock(spec=AgentFactory)
    
    # Create mock session with agent
    session = Mock()
    session.session_id = 'test_session'
    session.info.initialized = True
    session.agent = Mock()
    session.agent_thread = Mock()
    session.agent_thread.is_alive.return_value = True
    session.info.last_agent_status = None

    session_manager.get_all_sessions.return_value = {
        'test_session': session
    }
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory,
        agent_runner=Mock()
    )

    # Run check
    monitor.check_status_changes()

    # Verify status was checked and updated
    session_manager.update_session.assert_called_once()
    queue_service.put.assert_called_once()
    
    print("✓ Status change detection with agent test passed")


def test_check_lazy_agent_creation_disabled():
    """Test lazy agent creation when disabled."""
    # Create mocks
    session_manager = Mock(spec=SessionManager)
    queue_service = Mock()
    config = ServiceConfig()
    config.new_agent_on_first_submission = False
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory,
        agent_runner=Mock()
    )

    # Run check - should return early
    monitor.check_lazy_agent_creation()
    
    # Verify no sessions were checked
    session_manager.get_all_sessions.assert_not_called()
    
    print("✓ Lazy agent creation disabled test passed")


def test_periodic_cleanup_not_due():
    """Test periodic cleanup when interval hasn't elapsed."""
    # Create mocks
    session_manager = Mock(spec=SessionManager)
    queue_service = Mock()
    config = ServiceConfig()
    config.cleanup_check_interval = 300  # 5 minutes
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory,
        agent_runner=Mock()
    )

    # Set last cleanup time to now
    monitor._last_cleanup_time = time.time()
    
    # Run cleanup - should not execute
    monitor.periodic_cleanup()
    
    # Verify cleanup was not called
    session_manager.cleanup_idle_sessions.assert_not_called()
    
    print("✓ Periodic cleanup not due test passed")


def test_periodic_cleanup_due():
    """Test periodic cleanup when interval has elapsed."""
    # Create mocks
    session_manager = Mock(spec=SessionManager)
    queue_service = Mock()
    config = ServiceConfig()
    config.cleanup_check_interval = 1  # 1 second for testing
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory,
        agent_runner=Mock()
    )

    # Set last cleanup time to past
    monitor._last_cleanup_time = time.time() - 2

    # Run cleanup - should execute
    monitor.periodic_cleanup()

    # Verify cleanup was called
    session_manager.cleanup_idle_sessions.assert_called_once()
    
    # Verify last cleanup time was updated
    assert monitor._last_cleanup_time > time.time() - 1
    
    print("✓ Periodic cleanup due test passed")


def test_run_monitoring_cycle():
    """Test full monitoring cycle."""
    # Create mocks
    session_manager = Mock(spec=SessionManager)
    session_manager.get_all_sessions.return_value = {}
    queue_service = Mock()
    config = ServiceConfig()
    config.new_agent_on_first_submission = False
    config.cleanup_check_interval = 1
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory,
        agent_runner=Mock()
    )

    # Set last cleanup time to past
    monitor._last_cleanup_time = time.time() - 2

    # Run monitoring cycle
    monitor.run_monitoring_cycle()
    
    # Verify all checks were called
    session_manager.get_all_sessions.assert_called()
    session_manager.cleanup_idle_sessions.assert_called_once()
    
    print("✓ Full monitoring cycle test passed")


def test_error_resilience():
    """Test that errors in monitoring don't crash the service."""
    # Create mocks
    session_manager = Mock(spec=SessionManager)
    session_manager.get_all_sessions.side_effect = Exception("Test error")
    queue_service = Mock()
    config = ServiceConfig()
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory,
        agent_runner=Mock()
    )

    # Run check - should not raise error
    try:
        monitor.check_status_changes()
        print("✓ Error resilience test passed")
    except Exception as e:
        print(f"✗ Error resilience test failed: {e}")
        raise


def test_get_agent_status():
    """Test agent status detection."""
    # Create mocks
    session_manager = Mock(spec=SessionManager)
    queue_service = Mock()
    config = ServiceConfig()
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory,
        agent_runner=Mock()
    )

    # Test not created
    session = Mock()
    session.agent = None
    assert monitor._get_agent_status(session) == 'not_created'

    # Test running
    session.agent = Mock()
    session.agent_thread = Mock()
    session.agent_thread.is_alive.return_value = True
    assert monitor._get_agent_status(session) == 'running'

    # Test stopped
    session.agent_thread.is_alive.return_value = False
    assert monitor._get_agent_status(session) == 'stopped'

    # Test ready (no thread)
    session.agent_thread = None
    assert monitor._get_agent_status(session) == 'ready'
    
    print("✓ Agent status detection test passed")


if __name__ == '__main__':
    print("Running SessionMonitor tests...\n")
    
    test_session_monitor_initialization()
    test_check_status_changes_no_sessions()
    test_check_status_changes_with_agent()
    test_check_lazy_agent_creation_disabled()
    test_periodic_cleanup_not_due()
    test_periodic_cleanup_due()
    test_run_monitoring_cycle()
    test_error_resilience()
    test_get_agent_status()
    
    print("\n✅ All SessionMonitor tests passed!")
