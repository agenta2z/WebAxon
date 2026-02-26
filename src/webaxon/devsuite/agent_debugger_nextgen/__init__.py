"""Agent Debugger - Modular Dash UI for Queue-Based Agent Interaction.

This package provides a modular web UI for interacting with agent services
through shared on-storage queues.
"""

__version__ = '2.0.0'

# Export core components
from webaxon.devsuite.agent_debugger_nextgen.core import DebuggerConfig, DebuggerSessionInfo, SessionManager
from webaxon.devsuite.agent_debugger_nextgen.communication import QueueClient, MessageHandlers

# Export helper functions for backward compatibility
from webaxon.devsuite.agent_debugger_nextgen.helpers import (
    setup_helpers,
    get_queue_client,
    get_message_handlers,
    get_session_manager,
    get_log_monitor,
    get_log_monitor_messages,
    initialize_queue_service,
    sync_active_sessions,
    sync_session_agent,
    sync_session_template_version,
    send_agent_control,
    queue_message_handler_internal,
    check_for_agent_response,
    get_latest_agent_logs,
    handle_agent_status_message,
    handle_agent_control_ack_message,
    handle_log_path_message,
    process_client_control_messages
)

__all__ = [
    # Core
    'DebuggerConfig',
    'DebuggerSessionInfo',
    'SessionManager',
    # Communication
    'QueueClient',
    'MessageHandlers',
    # Helpers
    'setup_helpers',
    'get_queue_client',
    'get_message_handlers',
    'get_session_manager',
    'get_log_monitor',
    'get_log_monitor_messages',
    'initialize_queue_service',
    'sync_active_sessions',
    'sync_session_agent',
    'sync_session_template_version',
    'send_agent_control',
    'queue_message_handler_internal',
    'check_for_agent_response',
    'get_latest_agent_logs',
    'handle_agent_status_message',
    'handle_agent_control_ack_message',
    'handle_log_path_message',
    'process_client_control_messages',
]
