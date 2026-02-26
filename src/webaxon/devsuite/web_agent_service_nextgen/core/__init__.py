"""Core components for web agent service.

This module contains the fundamental building blocks of the service:

Components:
    ServiceConfig:
        Centralized configuration management with environment variable support.
        Provides validation and type-safe access to all service configuration.
        
        Example:
            >>> config = ServiceConfig()
            >>> config.session_idle_timeout  # 1800 (30 minutes)
            >>> config = ServiceConfig.from_env()  # Load from environment
    
    AgentSessionInfo:
        Pure data container for session state. Extends SessionInfo
        with last_agent_status and template_version.

    AgentSession:
        Live session with Debuggable logging and agent runtime state.
        Contains AgentSessionInfo via composition (session.info).
        The session IS the Debuggable — no standalone Debugger needed.

    AgentSessionManager:
        Thread-safe session lifecycle management (Debuggable).
        Provides centralized control over session creation, updates,
        and cleanup with proper resource management.

        Key methods:
            - get_or_create(): Get or create session (lazy initialization)
            - get(): Retrieve existing session
            - update_session(): Update session fields
            - cleanup_session(): Clean up session resources
            - cleanup_idle_sessions(): Remove idle sessions
            - get_all_sessions(): Get all active sessions
    
    AgentFactory:
        Agent creation and configuration.
        Centralizes agent creation logic with support for different agent types
        and template versioning.
        
        Supported agent types:
            - DefaultAgent: Full-featured planning agent
            - MockClarificationAgent: Mock agent for testing
        
        Example:
            >>> factory = AgentFactory(template_manager, config)
            >>> agent = factory.create_agent(
            ...     interactive=queue_interactive,
            ...     logger=session_logger,
            ...     agent_type='DefaultAgent',
            ...     template_version='v2.1'
            ... )

Design Principles:
    - Dependency Injection: Components receive dependencies through constructors
    - Thread Safety: All operations are thread-safe using RLock
    - Lazy Initialization: Resources created only when needed
    - Configuration Over Code: Behavior controlled through ServiceConfig
    - Clean Interfaces: Well-defined public APIs for each component

For detailed documentation, see the individual module files:
    - config.py: Configuration management
    - ../session/: Session state, lifecycle, and monitoring
    - agent_factory.py: Agent creation logic
"""

from .config import ServiceConfig
from ..session.agent_session_info import AgentSessionInfo
from ..session.agent_session import AgentSession
from ..session.agent_session_manager import AgentSessionManager
from .agent_factory import AgentFactory

__all__ = [
    'ServiceConfig',
    'AgentSessionInfo',
    'AgentSession',
    'AgentSessionManager',
    'AgentFactory',
]
