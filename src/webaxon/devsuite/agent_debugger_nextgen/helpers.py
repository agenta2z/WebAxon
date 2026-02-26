"""
Helper Functions Module

Provides integration functions that use the modular components.
These functions maintain backward compatibility with the original interface
while using the new modular architecture.
"""
from pathlib import Path
from typing import List, Optional, Tuple
from science_modeling_tools.ui.dash_interactive.utils.log_collector import LogCollector
from rich_python_utils.console_utils import hprint_message

# Import modular components
from webaxon.devsuite.agent_debugger_nextgen.core import SessionManager
from webaxon.devsuite.agent_debugger_nextgen.communication import QueueClient, MessageHandlers
from webaxon.devsuite.agent_debugger_nextgen.monitoring import LogMonitor

# Import constants from devsuite
try:
    from webaxon.devsuite import (
        INPUT_QUEUE_ID,
        RESPONSE_QUEUE_ID,
        CLIENT_CONTROL_QUEUE_ID,
        SERVER_CONTROL_QUEUE_ID,
        SPECIAL_MESSAGE_WAITING_FOR_RESPONSE,
        get_queue_service
    )
except ImportError:
    # Fallback for different import contexts
    INPUT_QUEUE_ID = "user_input"
    RESPONSE_QUEUE_ID = "agent_response"
    CLIENT_CONTROL_QUEUE_ID = "client_control"
    SERVER_CONTROL_QUEUE_ID = "server_control"
    SPECIAL_MESSAGE_WAITING_FOR_RESPONSE = "⏳ Waiting for response..."
    get_queue_service = None


# Global instances (will be initialized by setup_helpers)
_queue_client: Optional[QueueClient] = None
_message_handlers: Optional[MessageHandlers] = None
_session_manager: Optional[SessionManager] = None
_log_monitor: Optional[LogMonitor] = None


def setup_helpers(testcase_root: Path, session_manager: SessionManager, log_monitor: LogMonitor = None):
    """
    Initialize the helper module with required dependencies.
    
    Args:
        testcase_root: Root directory for queue service discovery
        session_manager: SessionManager instance to use
        log_monitor: Optional LogMonitor instance for background log monitoring
    """
    global _queue_client, _message_handlers, _session_manager, _log_monitor
    
    _session_manager = session_manager
    _log_monitor = log_monitor
    
    # Initialize queue client
    _queue_client = QueueClient(
        testcase_root=testcase_root,
        input_queue_id=INPUT_QUEUE_ID,
        response_queue_id=RESPONSE_QUEUE_ID,
        client_control_queue_id=CLIENT_CONTROL_QUEUE_ID,
        server_control_queue_id=SERVER_CONTROL_QUEUE_ID,
        queue_check_interval=5.0,
        get_queue_service_func=get_queue_service
    )
    
    # Initialize message handlers
    _message_handlers = MessageHandlers(
        session_manager=session_manager,
        get_active_session_ids_func=session_manager.get_active_ids,
        hprint_func=hprint_message
    )


def get_queue_client() -> QueueClient:
    """Get the global queue client instance."""
    if _queue_client is None:
        raise RuntimeError("Helpers not initialized. Call setup_helpers() first.")
    return _queue_client


def get_message_handlers() -> MessageHandlers:
    """Get the global message handlers instance."""
    if _message_handlers is None:
        raise RuntimeError("Helpers not initialized. Call setup_helpers() first.")
    return _message_handlers


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    if _session_manager is None:
        raise RuntimeError("Helpers not initialized. Call setup_helpers() first.")
    return _session_manager


def get_log_monitor() -> Optional[LogMonitor]:
    """Get the global log monitor instance.
    
    Returns:
        LogMonitor instance or None if not initialized
    """
    return _log_monitor


def get_log_monitor_messages() -> List[str]:
    """Get recent monitor messages from LogMonitor (thread-safe).
    
    This helper function retrieves messages from the background LogMonitor
    in a thread-safe manner. The LogMonitor stores timestamped messages
    about log file monitoring activity.
    
    Returns:
        List of recent monitor messages, or empty list if LogMonitor not available
        
    Requirements: 5.4, 5.5
    """
    if _log_monitor is None:
        return []
    return _log_monitor.get_recent_messages()


# ============================================================================
# Backward-Compatible Helper Functions
# ============================================================================
# These functions provide the same interface as the original monolithic file
# but use the new modular components internally.


def initialize_queue_service():
    """
    Initialize or refresh the shared queue service.
    
    Returns:
        Queue service instance
    """
    return get_queue_client().initialize_queue_service()


def sync_active_sessions(active_session_ids: list, debugger=None):
    """
    Sync all active session IDs with the agent service.
    
    Args:
        active_session_ids: List of all currently active session IDs
        debugger: Optional debugger instance for logging
    """
    get_queue_client().sync_active_sessions(active_session_ids, debugger)


def sync_session_agent(session_id: str, agent_type: str, debugger=None):
    """
    Update the agent configuration for a specific session.
    
    Args:
        session_id: Session ID to update
        agent_type: Type of agent to use
        debugger: Optional debugger instance for logging
    """
    get_queue_client().sync_session_agent(session_id, agent_type, debugger)


def sync_session_template_version(session_id: str, template_version: str, debugger=None):
    """
    Update the template version for a specific session.
    
    Args:
        session_id: Session ID to update
        template_version: Template version to use (empty string for default)
        debugger: Optional debugger instance for logging
    """
    get_queue_client().sync_session_template_version(session_id, template_version, debugger)


def send_agent_control(session_id: str, control: str):
    """
    Send an agent workflow control command to the agent service.
    
    Args:
        session_id: Session ID to control
        control: Control command ('stop', 'pause', 'continue', 'step')
    """
    get_queue_client().send_agent_control(session_id, control, hprint_message)
    
    # Mark control as pending for this session
    session_info = get_session_manager().get_or_create(session_id)
    session_info.control_pending = True


def queue_message_handler_internal(
    message: str,
    session_id: str,
    all_session_ids: list = None,
    current_agent_type: str = None,
    debugger=None
) -> str:
    """
    Message handler that sends user input to the agent service via queue.
    
    Args:
        message: User input message
        session_id: Session ID to associate this message with
        all_session_ids: List of all active session IDs
        current_agent_type: Current agent type for this session
        debugger: Optional debugger instance for logging
        
    Returns:
        Special waiting message marker
    """
    get_queue_client().send_user_input(
        session_id=session_id,
        message=message,
        all_session_ids=all_session_ids,
        current_agent_type=current_agent_type,
        debugger=debugger
    )
    
    return SPECIAL_MESSAGE_WAITING_FOR_RESPONSE


def check_for_agent_response() -> Tuple[Optional[str], Optional[str], Optional[LogCollector]]:
    """
    Check if there's a response from the agent service.
    
    Returns:
        Tuple of (session_id, response_text, log_collector) or (None, None, None)
    """
    queue_client = get_queue_client()
    message_handlers = get_message_handlers()
    
    # Check for response (non-blocking)
    response_data = queue_client.receive_message(RESPONSE_QUEUE_ID, blocking=False)
    
    if response_data is None:
        return None, None, None
    
    # Extract session_id and response from response_data
    if isinstance(response_data, dict):
        session_id = response_data.get('session_id')
        response = response_data.get('response', '')
        
        # Handle list responses
        if isinstance(response, list):
            response = '\n\n'.join(str(item) for item in response)
    else:
        # Fallback for old format
        session_id = None
        response = str(response_data)
    
    # Return with latest log collector
    return session_id, response, message_handlers.latest_log_collector


def get_latest_agent_logs(graph_type: str = None) -> LogCollector:
    """
    Get the latest agent execution logs for visualization.
    
    Args:
        graph_type: Graph type selector (ignored)
        
    Returns:
        LogCollector with the latest agent execution logs
    """
    message_handlers = get_message_handlers()
    
    if message_handlers.latest_log_collector:
        return message_handlers.latest_log_collector
    
    # Fallback: return the most recent from history
    recent = message_handlers.recent_log_collectors
    if recent:
        latest_key = sorted(recent.keys())[-1]
        return recent[latest_key]
    
    # No logs available - return empty collector
    return LogCollector()


def handle_agent_status_message(msg: dict, session_id: str, app_instance):
    """
    Handle agent_status message type.
    
    Args:
        msg: Message dict with type "agent_status"
        session_id: Current active session ID
        app_instance: QueueBasedDashApp instance
        
    Returns:
        tuple: (latest_agent, agent_created)
    """
    return get_message_handlers().handle_agent_status_message(msg, session_id, app_instance)


def handle_agent_control_ack_message(msg: dict, session_id: str, debugger=None):
    """
    Handle agent_control_ack message type.
    
    Args:
        msg: Message dict with type "agent_control_ack"
        session_id: Current active session ID
        debugger: Optional debugger instance
    """
    get_message_handlers().handle_agent_control_ack_message(msg, session_id, debugger)


def handle_log_path_message(msg: dict, debugger=None):
    """
    Handle log_path_available message type.
    
    Args:
        msg: Message dict with type "log_path_available"
        debugger: Optional debugger instance
    """
    get_message_handlers().handle_log_path_message(msg, debugger)


def process_client_control_messages(
    messages: list,
    session_id: str,
    app_instance,
    debugger=None
) -> dict:
    """
    Process a batch of client control messages.
    
    Args:
        messages: List of message dicts from CLIENT_CONTROL_QUEUE
        session_id: Current active session ID
        app_instance: QueueBasedDashApp instance
        debugger: Optional debugger instance
        
    Returns:
        dict: Processing results
    """
    return get_message_handlers().process_client_control_messages(
        messages, session_id, app_instance, debugger
    )
