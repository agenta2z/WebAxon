"""Main service orchestration for web agent service.

This module provides the WebAgentService class that coordinates all components
and runs the main service loop.
"""
import signal
import time
import traceback
from pathlib import Path
from typing import Optional

from rich_python_utils.common_objects.debuggable import Debugger
from rich_python_utils.datetime_utils.common import timestamp
from rich_python_utils.io_utils.json_io import JsonLogger
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from webaxon.devsuite.common import DebuggerLogTypes
from webaxon.devsuite.constants import FOLDER_NAME_SERVICE_LOGS, LOG_FILE_EXT

from .agents.agent_runner import AgentRunner
from .agents.template_manager import TemplateManagerWrapper
from .communication.message_handlers import MessageHandlers
from .communication.queue_manager import QueueManager
from .core.agent_factory import AgentFactory
from .core.config import ServiceConfig
from .session.agent_session_manager import AgentSessionManager
from .session.agent_session_monitor import AgentSessionMonitor


class WebAgentService:
    """Main web agent service.
    
    This class coordinates all service components and runs the main service loop.
    It handles:
    - Component initialization
    - Signal handling for graceful shutdown
    - Global logging setup
    - Main service loop (message processing and monitoring)
    - Cleanup on shutdown
    
    The service follows a clean architecture with dependency injection,
    making it easy to test and maintain.
    
    Example:
        >>> config = ServiceConfig()
        >>> service = WebAgentService(Path('/path/to/testcase'), config)
        >>> service.run()  # Blocks until shutdown signal
    """
    
    def __init__(self, testcase_root: Path, config: Optional[ServiceConfig] = None):
        """Initialize the web agent service.
        
        This constructor initializes all components but does not start the
        service loop. Call run() to start the service.
        
        Args:
            testcase_root: Root directory for the testcase
            config: Service configuration (uses defaults if not provided)
        """
        self._testcase_root = testcase_root
        self._config = config or ServiceConfig()
        self._config.validate()
        
        # Initialize components that don't require queue service
        self._queue_manager = QueueManager(testcase_root, self._config)
        self._template_manager = self._create_template_manager()
        self._agent_factory = AgentFactory(
            self._template_manager.get_template_manager(),
            self._config,
            testcase_root=self._testcase_root
        )
        
        # Components initialized in run()
        self._session_manager: Optional[AgentSessionManager] = None
        self._message_handlers: Optional[MessageHandlers] = None
        self._agent_runner: Optional[AgentRunner] = None
        self._session_monitor: Optional[AgentSessionMonitor] = None
        self._global_debugger: Optional[Debugger] = None
        self._shutdown_requested = False
    
    def _create_template_manager(self) -> TemplateManagerWrapper:
        """Create template manager with default configuration.
        
        Returns:
            TemplateManagerWrapper instance configured with template directory
        """
        # Template directory is relative to testcase root (configurable via config.template_dir)
        template_dir = self._testcase_root / self._config.template_dir
        
        return TemplateManagerWrapper(
            template_dir=template_dir,
            template_formatter=handlebars_template_format
        )
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown.
        
        This method registers handlers for SIGINT (Ctrl+C) and SIGTERM
        to enable graceful shutdown of the service.
        
        Note: Signal handlers can only be registered in the main thread.
        If running in a non-main thread (e.g., during testing), this
        method will skip signal handler registration.
        """
        import threading
        
        # Check if we're in the main thread
        if threading.current_thread() is not threading.main_thread():
            if self._global_debugger:
                self._global_debugger.log_warning({
                    'type': DebuggerLogTypes.SERVICE_STARTUP,
                    'message': 'Skipping signal handler setup (not in main thread)'
                })
            return
        
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'
            
            if self._global_debugger:
                self._global_debugger.log_warning({
                    'type': DebuggerLogTypes.SERVICE_SHUTDOWN,
                    'message': f'Shutdown signal received: {signal_name}',
                    'signal': signal_name
                })
            else:
                print(f"[{timestamp()}] Shutdown signal received: {signal_name}")
            
            self._shutdown_requested = True
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _initialize_logging(self) -> None:
        """Initialize global service logging.
        
        This method creates the global service log directory and initializes
        the global debugger for service-level logging.
        """
        # Create global service log directory
        service_log_dir = (
            self._testcase_root / 
            self._config.log_root_path / 
            FOLDER_NAME_SERVICE_LOGS / 
            'global'
        )
        service_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create global debugger
        self._global_debugger = Debugger(
            id='web_agent_service_global',
            log_name='WebAgentService',
            logger=[
                print,
                JsonLogger(
                    file_path=str(service_log_dir / f'global_service{LOG_FILE_EXT}'),
                    append=True
                )
            ],
            debug_mode=self._config.debug_mode_service,
            log_time=True,
            always_add_logging_based_logger=False
        )
    
    def run(self) -> None:
        """Run the service loop.
        
        This method:
        1. Initializes logging
        2. Sets up signal handlers
        3. Initializes queue service and remaining components
        4. Runs the main service loop
        5. Performs cleanup on shutdown
        
        The main loop processes control messages and runs monitoring cycles
        until a shutdown signal is received.
        
        This method blocks until shutdown is requested.
        """
        # Initialize logging
        self._initialize_logging()
        self._global_debugger.log_info({
            'type': DebuggerLogTypes.SERVICE_STARTUP,
            'message': 'Web Agent Service Starting',
            'testcase_root': str(self._testcase_root),
            'config': {
                'session_idle_timeout': self._config.session_idle_timeout,
                'cleanup_check_interval': self._config.cleanup_check_interval,
                'debug_mode_service': self._config.debug_mode_service,
                'synchronous_agent': self._config.synchronous_agent,
                'new_agent_on_first_submission': self._config.new_agent_on_first_submission,
                'default_agent_type': self._config.default_agent_type
            }
        })
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        try:
            # Initialize queue service
            self._global_debugger.log_info({
                'type': DebuggerLogTypes.SERVICE_STARTUP,
                'message': 'Initializing queue service'
            })
            
            queue_service = self._queue_manager.initialize()
            self._queue_manager.create_queues()
            
            queue_root_path = self._queue_manager.get_queue_root_path()
            self._global_debugger.log_info({
                'type': DebuggerLogTypes.SERVICE_STARTUP,
                'message': 'Queue service initialized',
                'queue_root_path': str(queue_root_path),
                'input_queue_id': self._config.input_queue_id,
                'response_queue_id': self._config.response_queue_id,
                'client_control_queue_id': self._config.client_control_queue_id,
                'server_control_queue_id': self._config.server_control_queue_id
            })
            
            # Initialize remaining components
            service_log_dir = self._testcase_root / self._config.log_root_path
            
            session_mgr_log_dir = service_log_dir / FOLDER_NAME_SERVICE_LOGS / 'session_manager'
            session_mgr_log_dir.mkdir(parents=True, exist_ok=True)

            self._session_manager = AgentSessionManager(
                id='session_manager',
                log_name='SessionManager',
                logger=[
                    print,
                    JsonLogger(
                        file_path=str(session_mgr_log_dir / f'session_manager{LOG_FILE_EXT}'),
                        append=True
                    )
                ],
                debug_mode=self._config.debug_mode_service,
                log_time=True,
                always_add_logging_based_logger=False,
                config=self._config,
                queue_service=queue_service,
                service_log_dir=service_log_dir,
            )
            
            self._message_handlers = MessageHandlers(
                self._session_manager,
                self._agent_factory,
                queue_service,
                self._config,
                debugger=self._global_debugger
            )
            
            self._agent_runner = AgentRunner(self._config)

            self._session_monitor = AgentSessionMonitor(
                self._session_manager,
                queue_service,
                self._config,
                self._agent_factory,
                self._agent_runner,
                debugger=self._global_debugger
            )
            
            self._global_debugger.log_info({
                'type': DebuggerLogTypes.SERVICE_STARTUP,
                'message': 'All components initialized',
                'components': [
                    'QueueManager',
                    'SessionManager',
                    'AgentFactory',
                    'MessageHandlers',
                    'AgentRunner',
                    'SessionMonitor'
                ]
            })
            
            self._global_debugger.log_info({
                'type': DebuggerLogTypes.SERVICE_STARTUP,
                'message': 'Service initialized, entering main loop'
            })
            
            # Main service loop
            while not self._shutdown_requested:
                try:
                    # Check for control messages (from client/debugger to server)
                    control_msg = queue_service.get(
                        self._config.server_control_queue_id,
                        blocking=False
                    )
                    
                    if control_msg:
                        self._global_debugger.log_info({
                            'type': DebuggerLogTypes.CONTROL_MESSAGE,
                            'message': 'Control message received',
                            'message_type': control_msg.get('type'),
                            'message_data': control_msg
                        })
                        
                        # Dispatch to appropriate handler
                        self._message_handlers.dispatch(control_msg)
                    
                    # Run monitoring cycle
                    self._session_monitor.run_monitoring_cycle()
                    
                    # Small sleep to prevent tight loop
                    time.sleep(0.1)
                    
                except Exception as e:
                    # Capture full traceback for structured logging
                    tb_str = traceback.format_exc()
                    
                    # Log structured error with exception details
                    self._global_debugger.log_error({
                        'type': DebuggerLogTypes.ERROR,
                        'message': f'Error in main loop: {str(e)}',
                        'error': str(e),
                        'exception_type': type(e).__name__,
                        'exception_message': str(e),
                        'traceback': tb_str
                    }, log_type='Error')
                    
                    # Sleep to avoid tight loop on persistent errors
                    time.sleep(1)
            
            # Shutdown requested
            self._global_debugger.log_info({
                'type': DebuggerLogTypes.SERVICE_SHUTDOWN,
                'message': 'Shutting down service'
            })
            
        except Exception as e:
            # Fatal error during initialization or main loop
            tb_str = traceback.format_exc()
            if self._global_debugger:
                self._global_debugger.log_error({
                    'type': DebuggerLogTypes.ERROR,
                    'message': f'Fatal error in service: {str(e)}',
                    'error': str(e),
                    'exception_type': type(e).__name__,
                    'exception_message': str(e),
                    'traceback': tb_str
                }, log_type='Error')
            else:
                print(f"[{timestamp()}] Fatal error in service: {str(e)}")
            
            raise
        
        finally:
            # Always cleanup, even if error occurred
            self._cleanup()
    
    def _cleanup(self) -> None:
        """Cleanup all resources.
        
        This method:
        1. Stops all agent threads
        2. Cleans up all sessions
        3. Closes the agent factory (knowledge provider cleanup)
        4. Closes the queue service
        5. Logs shutdown completion
        
        This method is called during shutdown and handles errors gracefully
        to ensure cleanup proceeds even if individual operations fail.
        """
        if self._global_debugger:
            self._global_debugger.log_info({
                'type': DebuggerLogTypes.SERVICE_SHUTDOWN,
                'message': 'Starting cleanup'
            })
        
        # Stop all agent threads and cleanup sessions
        if self._session_manager:
            try:
                sessions = self._session_manager.get_all_sessions()
                
                if self._global_debugger:
                    self._global_debugger.log_info({
                        'type': DebuggerLogTypes.SERVICE_SHUTDOWN,
                        'message': f'Cleaning up {len(sessions)} active sessions',
                        'session_ids': list(sessions.keys())
                    })
                
                for session_id in list(sessions.keys()):
                    try:
                        self._session_manager.cleanup_session(session_id)
                    except Exception as e:
                        if self._global_debugger:
                            self._global_debugger.log_error({
                                'type': DebuggerLogTypes.ERROR,
                                'message': f'Error cleaning up session {session_id}: {str(e)}',
                                'session_id': session_id,
                                'error': str(e)
                            })
            
            except Exception as e:
                if self._global_debugger:
                    self._global_debugger.log_error({
                        'type': DebuggerLogTypes.ERROR,
                        'message': f'Error during session cleanup: {str(e)}',
                        'error': str(e)
                    })
        
        # Close agent factory (knowledge provider cleanup)
        if self._agent_factory:
            try:
                self._agent_factory.close()
                if self._global_debugger:
                    self._global_debugger.log_info({
                        'type': DebuggerLogTypes.SERVICE_SHUTDOWN,
                        'message': 'Agent factory closed'
                    })
            except Exception as e:
                if self._global_debugger:
                    self._global_debugger.log_error({
                        'type': DebuggerLogTypes.ERROR,
                        'message': f'Error closing agent factory: {str(e)}',
                        'error': str(e)
                    })
        
        # Close queue service
        try:
            self._queue_manager.close()
            
            if self._global_debugger:
                self._global_debugger.log_info({
                    'type': DebuggerLogTypes.SERVICE_SHUTDOWN,
                    'message': 'Queue service closed'
                })
        
        except Exception as e:
            if self._global_debugger:
                self._global_debugger.log_error({
                    'type': DebuggerLogTypes.ERROR,
                    'message': f'Error closing queue service: {str(e)}',
                    'error': str(e)
                })
        
        # Final shutdown message
        if self._global_debugger:
            self._global_debugger.log_info({
                'type': DebuggerLogTypes.SERVICE_SHUTDOWN,
                'message': 'Service stopped'
            })
        else:
            print(f"[{timestamp()}] Service stopped")
