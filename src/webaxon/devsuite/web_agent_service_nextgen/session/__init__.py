"""Session lifecycle components for web agent service.

This module handles session monitoring, structured logging, artifact management,
health checks, and automatic cleanup of idle sessions.

Components:
    AgentSessionMonitor:
        Session health monitoring and idle cleanup.
        Runs periodic checks to monitor agent status changes, create agents
        lazily, and clean up idle sessions.
        
        Key responsibilities:
            1. Status Change Detection:
               - Monitors agent status changes
               - Sends acknowledgment messages to control queue
               - Enables UI updates when agent status changes
            
            2. Lazy Agent Creation:
               - Checks for messages waiting in input queue
               - Creates agents on-demand when messages arrive
               - Reduces resource usage by not creating agents upfront
            
            3. Periodic Cleanup:
               - Removes sessions idle beyond timeout
               - Prevents resource leaks from abandoned sessions
               - Configurable cleanup interval
            
            4. Error Resilience:
               - Continues monitoring even if individual checks fail
               - Logs errors without crashing service
               - Ensures service reliability
        
        Monitoring cycle:
            The monitor runs a cycle of checks on each iteration:
            1. check_status_changes() - Detect and acknowledge status changes
            2. check_lazy_agent_creation() - Create agents for waiting messages
            3. periodic_cleanup() - Clean up idle sessions (if interval elapsed)
        
        Example:
            >>> monitor = AgentSessionMonitor(
            ...     session_manager,
            ...     queue_service,
            ...     config,
            ...     agent_factory
            ... )
            >>> # In main service loop:
            >>> while not shutdown_requested:
            ...     monitor.run_monitoring_cycle()
            ...     time.sleep(0.1)

Configuration:
    The monitor behavior is controlled by ServiceConfig:
    
    - session_idle_timeout: Seconds before idle session cleanup (default: 1800)
    - cleanup_check_interval: Seconds between cleanup checks (default: 300)
    - new_agent_on_first_submission: Enable lazy agent creation (default: True)
    
    Example:
        >>> config = ServiceConfig(
        ...     session_idle_timeout=3600,  # 1 hour
        ...     cleanup_check_interval=600,  # 10 minutes
        ...     new_agent_on_first_submission=True
        ... )

Design Principles:
    - Separation of Concerns: Monitoring separate from main service logic
    - Configurable Intervals: Prevent excessive checking
    - Error Resilience: Individual check failures don't crash service
    - Resource Efficiency: Lazy creation reduces memory usage

Status Change Detection:
    The monitor tracks agent status changes to enable UI updates:
    
    1. On each cycle, check all sessions for status changes
    2. Compare current status with last_agent_status
    3. If changed, send acknowledgment to control queue
    4. Update last_agent_status to prevent duplicate notifications
    
    This enables the debugger UI to show real-time agent status.

Lazy Agent Creation:
    When enabled, agents are created only when needed:
    
    1. Check input queue for waiting messages
    2. For each message, check if session has agent
    3. If no agent exists, create one using AgentFactory
    4. Agent then processes the waiting message
    
    Benefits:
        - Reduced memory usage (no idle agents)
        - Faster service startup
        - Agents created with correct configuration

Idle Session Cleanup:
    Prevents resource leaks from abandoned sessions:
    
    1. On each cleanup interval, check all sessions
    2. Calculate idle time (current_time - last_active)
    3. If idle_time > session_idle_timeout, cleanup session
    4. Cleanup includes stopping threads, closing resources
    
    This ensures the service doesn't accumulate abandoned sessions.

For detailed documentation, see the individual module files:
    - agent_session_monitor.py: Monitoring implementation
"""

__all__ = [
    'AgentSessionInfo',
    'AgentSession',
    'SessionLogger',
    'SessionManager',
    'SessionMonitor',
]


def __getattr__(name):
    """Lazy imports to avoid circular dependencies."""
    if name == 'SessionMonitor':
        from .agent_session_monitor import AgentSessionMonitor
        return AgentSessionMonitor
    if name == 'AgentSessionInfo':
        from .agent_session_info import AgentSessionInfo
        return AgentSessionInfo
    if name == 'AgentSession':
        from .agent_session import AgentSession
        return AgentSession
    if name == 'SessionLogger':
        from rich_python_utils.service_utils.session_management import SessionLogger
        return SessionLogger
    if name == 'SessionManager':
        from .agent_session_manager import AgentSessionManager
        return AgentSessionManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
