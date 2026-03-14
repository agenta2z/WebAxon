"""Agent management components for web agent service.

This module handles agent execution and template management, providing
flexible execution modes and template versioning support.

Components:
    AgentRunner:
        Thread management for agent execution.
        Provides both asynchronous (threaded) and synchronous execution modes,
        enabling production deployment and step-through debugging.
        
        Execution modes:
            - Asynchronous (default): Agent runs in separate daemon thread
            - Synchronous (debug): Agent runs in main process for debugging
        
        Key features:
            - Thread lifecycle management
            - Error handling and recovery
            - Status updates on completion/failure
            - Thread reference tracking
        
        Example:
            >>> runner = AgentRunner(config)
            >>> thread = runner.start_agent_thread(session_info, queue_service)
            >>> # Agent now running in background thread
            >>> # Or for debugging:
            >>> config.synchronous_agent = True
            >>> runner.start_agent_thread(session_info, queue_service)
            >>> # Agent runs synchronously (blocks)
    
    TemplateManagerWrapper:
        Template versioning wrapper.
        Wraps the existing TemplateManager to add version tracking and
        switching capabilities, enabling per-session template versions.
        
        Key features:
            - Version tracking
            - Version switching
            - Delegation to underlying TemplateManager
            - Clean interface for version management
        
        Benefits:
            - Different sessions can use different template versions
            - Easy A/B testing of template changes
            - Gradual rollout of template updates
            - Debugging with specific template versions
        
        Example:
            >>> wrapper = TemplateManagerWrapper(
            ...     template_dir=Path('templates'),
            ...     template_formatter=handlebars_format
            ... )
            >>> wrapper.switch_version('v2.1')
            >>> current = wrapper.get_current_version()  # 'v2.1'
            >>> template_manager = wrapper.get_template_manager()

Design Principles:
    - Flexible Execution: Support both production and debugging modes
    - Wrapper Pattern: Extend functionality without modifying existing code
    - Version Control: Enable per-session template versioning
    - Error Resilience: Handle execution errors gracefully

Thread Safety:
    AgentRunner creates daemon threads that don't block service shutdown.
    Each agent runs in its own thread with isolated state.
    
    Thread lifecycle:
        1. start_agent_thread() creates and starts thread
        2. Thread runs agent() in background
        3. On completion/error, status updated in session
        4. Thread exits naturally or on service shutdown

Template Versioning:
    Template versions enable:
        - Testing new templates without affecting all sessions
        - Rolling back to previous templates if issues arise
        - Debugging with specific template versions
        - A/B testing of template effectiveness
    
    Version format:
        Versions are strings (e.g., 'v2.1', 'experimental', 'stable')
        Empty string means default/latest version

For detailed documentation, see the individual module files:
    - agent_runner.py: Thread management and execution
    - template_manager.py: Template versioning wrapper
"""

from .agent_runner import AgentRunner
from .meta_agent_adapter import MetaAgentAdapter, MetaAgentRunResult
from .regular_agent_adapter import RegularAgentAdapter, RegularAgentRunResult
from .template_manager import TemplateManagerWrapper

__all__ = [
    'AgentRunner',
    'MetaAgentAdapter',
    'MetaAgentRunResult',
    'RegularAgentAdapter',
    'RegularAgentRunResult',
    'TemplateManagerWrapper',
]
