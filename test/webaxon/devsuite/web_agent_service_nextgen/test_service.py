"""Tests for WebAgentService main orchestration.

This module tests the main service class including:
- Component initialization
- Signal handling
- Logging setup
- Service lifecycle
"""
import sys
import resolve_path  # Setup import paths

import tempfile
import threading
import time
from pathlib import Path

import pytest

from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.service import WebAgentService


def setup_test_templates(testcase_root: Path):
    """Helper function to create dummy template files for testing."""
    template_dir = testcase_root / 'prompt_templates'
    template_dir.mkdir(parents=True, exist_ok=True)
    # Create proper subdirectory structure for TemplateManager
    for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
        (template_dir / subdir).mkdir(parents=True, exist_ok=True)
        (template_dir / subdir / 'default.hbs').write_text('{{input}}')
    return template_dir


class TestWebAgentService:
    """Test suite for WebAgentService."""
    
    def test_service_initialization(self):
        """Test that service initializes all components correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            testcase_root = Path(tmpdir)
            setup_test_templates(testcase_root)
            
            # Create config
            config = ServiceConfig(
                debug_mode_service=True,
                synchronous_agent=False,
                new_agent_on_first_submission=True
            )
            
            # Create service
            service = WebAgentService(testcase_root, config)
            
            # Verify components are initialized
            assert service._testcase_root == testcase_root
            assert service._config == config
            assert service._queue_manager is not None
            assert service._template_manager is not None
            assert service._agent_factory is not None
            
            # Components initialized in run() should be None
            assert service._session_manager is None
            assert service._message_handlers is None
            assert service._agent_runner is None
            assert service._session_monitor is None
            assert service._global_debugger is None
            assert service._shutdown_requested is False
    
    def test_service_with_default_config(self):
        """Test that service works with default configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            testcase_root = Path(tmpdir)
            setup_test_templates(testcase_root)
            
            # Create service with default config
            service = WebAgentService(testcase_root)
            
            # Verify default config is used
            assert service._config is not None
            assert service._config.session_idle_timeout == 30 * 60
            assert service._config.cleanup_check_interval == 5 * 60
            assert service._config.debug_mode_service is True
    
    def test_service_config_validation(self):
        """Test that service validates configuration on initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            testcase_root = Path(tmpdir)
            setup_test_templates(testcase_root)
            
            # Create invalid config (negative timeout)
            config = ServiceConfig(session_idle_timeout=-1)
            
            # Should raise ValueError during initialization
            with pytest.raises(ValueError, match="session_idle_timeout must be positive"):
                service = WebAgentService(testcase_root, config)
    
    def test_template_manager_creation(self):
        """Test that template manager is created correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            testcase_root = Path(tmpdir)
            setup_test_templates(testcase_root)
            
            # Create service
            service = WebAgentService(testcase_root)
            
            # Verify template manager is created
            assert service._template_manager is not None
            
            # Verify it's a wrapper
            from webaxon.devsuite.web_agent_service_nextgen.agents.template_manager import TemplateManagerWrapper
            assert isinstance(service._template_manager, TemplateManagerWrapper)
            
            # Verify underlying template manager exists
            tm = service._template_manager.get_template_manager()
            assert tm is not None
    
    def test_agent_factory_creation(self):
        """Test that agent factory is created with template manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            testcase_root = Path(tmpdir)
            setup_test_templates(testcase_root)
            
            # Create service
            service = WebAgentService(testcase_root)
            
            # Verify agent factory is created
            assert service._agent_factory is not None
            
            # Verify it has access to template manager
            from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
            assert isinstance(service._agent_factory, AgentFactory)
    
    def test_shutdown_flag(self):
        """Test that shutdown flag is initially False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            testcase_root = Path(tmpdir)
            setup_test_templates(testcase_root)
            
            # Create service
            service = WebAgentService(testcase_root)
            
            # Verify shutdown flag is False
            assert service._shutdown_requested is False


class TestServiceLifecycle:
    """Test suite for service lifecycle operations."""
    
    def test_logging_initialization(self):
        """Test that logging is initialized correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            testcase_root = Path(tmpdir)
            setup_test_templates(testcase_root)
            
            # Create service
            service = WebAgentService(testcase_root)
            
            # Initialize logging
            service._initialize_logging()
            
            # Verify global debugger is created
            assert service._global_debugger is not None
            
            # Verify log directory is created
            log_dir = testcase_root / '_runtime' / 'service_logs' / 'global'
            assert log_dir.exists()
    
    def test_signal_handler_setup(self):
        """Test that signal handlers are set up correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            testcase_root = Path(tmpdir)
            setup_test_templates(testcase_root)
            
            # Create service
            service = WebAgentService(testcase_root)
            
            # Initialize logging (required for signal handler)
            service._initialize_logging()
            
            # Setup signal handlers
            service._setup_signal_handlers()
            
            # Verify shutdown flag is still False
            assert service._shutdown_requested is False
            
            # Note: We can't easily test signal handling without actually
            # sending signals, which could interfere with the test runner


class TestServiceIntegration:
    """Integration tests for service components working together."""
    
    def test_service_components_integration(self):
        """Test that all service components can be initialized together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            testcase_root = Path(tmpdir)
            setup_test_templates(testcase_root)
            
            # Create service
            config = ServiceConfig(
                debug_mode_service=False,  # Reduce log noise
                synchronous_agent=True,  # Easier to test
                new_agent_on_first_submission=True
            )
            service = WebAgentService(testcase_root, config)
            
            # Initialize logging
            service._initialize_logging()
            
            # Initialize queue service
            queue_service = service._queue_manager.initialize()
            service._queue_manager.create_queues()
            
            # Initialize remaining components
            service_log_dir = testcase_root / config.log_root_path
            
            from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager
            from webaxon.devsuite.web_agent_service_nextgen.communication.message_handlers import MessageHandlers
            from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import AgentRunner
            from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_monitor import AgentSessionMonitor
            
            service._session_manager = SessionManager(
                id='test', log_name='Test', logger=[print],
                always_add_logging_based_logger=False,
                config=config,
                queue_service=queue_service,
                service_log_dir=service_log_dir,
            )
            
            service._message_handlers = MessageHandlers(
                service._session_manager,
                service._agent_factory,
                queue_service,
                config
            )
            
            service._agent_runner = AgentRunner(config)
            
            service._session_monitor = AgentSessionMonitor(
                service._session_manager,
                queue_service,
                config,
                service._agent_factory,
                service._agent_runner
            )
            
            # Verify all components are initialized
            assert service._session_manager is not None
            assert service._message_handlers is not None
            assert service._agent_runner is not None
            assert service._session_monitor is not None
            
            # Cleanup
            service._queue_manager.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
