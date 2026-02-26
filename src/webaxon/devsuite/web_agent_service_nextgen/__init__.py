"""Web Agent Service - Modularized Architecture.

This package provides a modular, maintainable implementation of the web agent service
with clear separation of concerns and improved testability.

The service follows a clean architecture pattern with dependency injection,
making it easy to test, maintain, and extend. It handles agent lifecycle management,
queue-based communication, session monitoring, and template versioning.

Main Components:
    - core: Configuration, session management, and agent factory
    - communication: Queue management and message handling
    - agents: Agent execution and template management
    - session: Session monitoring, logging, and cleanup

Architecture:
    The service is organized into focused modules with clear responsibilities:
    
    1. Core Module (core/):
       - ServiceConfig: Centralized configuration with environment support
       - AgentSessionInfo: Session state tracking
       - SessionManager: Thread-safe session lifecycle management
       - AgentFactory: Agent creation and configuration
    
    2. Communication Module (communication/):
       - QueueManager: Queue service initialization and lifecycle
       - MessageHandlers: Control message processing and dispatch
    
    3. Agents Module (agents/):
       - AgentRunner: Thread management for agent execution
       - TemplateManagerWrapper: Template versioning wrapper
    
    4. Session Module (session/):
       - SessionMonitor: Session health monitoring and cleanup
       - SessionLogger: Structured session logging and artifacts

Usage:
    Basic usage with default configuration:
    
    >>> from pathlib import Path
    >>> from web_agent_service_nextgen import WebAgentService
    >>> 
    >>> testcase_root = Path('/path/to/testcase')
    >>> service = WebAgentService(testcase_root)
    >>> service.run()  # Blocks until shutdown signal
    
    Advanced usage with custom configuration:
    
    >>> from web_agent_service_nextgen import WebAgentService
    >>> from web_agent_service_nextgen.core import ServiceConfig
    >>> 
    >>> config = ServiceConfig(
    ...     session_idle_timeout=1800,  # 30 minutes
    ...     debug_mode_service=True,
    ...     synchronous_agent=False
    ... )
    >>> service = WebAgentService(testcase_root, config)
    >>> service.run()
    
    Loading configuration from environment:
    
    >>> from web_agent_service_nextgen.core import ServiceConfig
    >>> config = ServiceConfig.from_env()
    >>> service = WebAgentService(testcase_root, config)
    >>> service.run()

Entry Point:
    The service can be launched using the provided entry point script:
    
    $ python launch_service.py /path/to/testcase

For more information, see README.md in this directory.
"""

__version__ = '1.0.0'
__author__ = 'Web Agent Service Team'
__license__ = 'MIT'

# Main service class
from .service import WebAgentService

# Re-export commonly used classes for convenience
from .core import ServiceConfig, AgentSessionInfo, AgentSession, AgentSessionManager, AgentFactory
from .communication import QueueManager, MessageHandlers
from .agents import AgentRunner, TemplateManagerWrapper
from .session import SessionMonitor

__all__ = [
    # Version and metadata
    '__version__',
    '__author__',
    '__license__',
    
    # Main service
    'WebAgentService',
    
    # Core components
    'ServiceConfig',
    'AgentSessionInfo',
    'AgentSession',
    'AgentSessionManager',
    'AgentFactory',
    
    # Communication components
    'QueueManager',
    'MessageHandlers',
    
    # Agent management
    'AgentRunner',
    'TemplateManagerWrapper',
    
    # Session
    'SessionMonitor',
]
