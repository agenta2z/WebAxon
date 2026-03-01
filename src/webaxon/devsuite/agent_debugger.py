"""
Agent Debugger - Dash UI for Queue-Based Agent Interaction

This provides a web UI for interacting with the agent service through
shared on-storage queues. It displays chat messages and visualizes
execution logs from the agent.

Architecture:
- Uses StorageBasedQueueService to communicate with agent service
- Sends user input to 'user_input' queue
- Receives responses from 'agent_response' queue
- Receives log paths from 'agent_logs' queue
- Loads and visualizes execution logs

Queue Communication:
- Input Queue: 'user_input' - sends user messages to agent
- Response Queue: 'agent_response' - receives agent responses
- Log Queue: 'agent_logs' - receives log file paths

Usage:
    1. Start the agent service: python web_agent_service.py
    2. Start the debugger UI: python agent_debugger.py
    3. Navigate to http://localhost:8050
    4. Type messages in the chat - they go to the agent service
    5. View responses and execution logs in the UI

Run this script and navigate to http://localhost:8050 to see the UI.
"""
import sys
from functools import partial
from pathlib import Path
import time
import threading

# Add source to path if needed
project_root = Path(__file__).parent.parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Also add SciencePythonUtils and ScienceModelingTools src paths
rich_python_utils_src = project_root / "SciencePythonUtils" / "src"
agent_foundation_src = project_root / "ScienceModelingTools" / "src"
for path_item in [rich_python_utils_src, agent_foundation_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

from agent_foundation.ui.dash_interactive.queue_based_dash_interactive_app import QueueBasedDashInteractiveApp
from agent_foundation.ui.dash_interactive.utils.log_collector import LogCollector
from rich_python_utils.common_objects.debuggable import Debugger
from rich_python_utils.datetime_utils.common import timestamp
from rich_python_utils.console_utils import hprint_message
from rich_python_utils.io_utils.json_io import write_json
from dash.dependencies import Input, Output, State
from dash import html, dcc
import dash

# Import web agent framework utilities from devsuite
from webaxon.devsuite import (
    INPUT_QUEUE_ID,
    RESPONSE_QUEUE_ID,
    CLIENT_CONTROL_QUEUE_ID,
    SERVER_CONTROL_QUEUE_ID,
    SPECIAL_MESSAGE_WAITING_FOR_RESPONSE,
    AGENT_TYPE_DEFAULT,
    AGENT_TYPE_MOCK_CLARIFICATION,
    get_queue_service,
    config
)
from rich_python_utils.service_utils.session_management import SessionInfo
from webaxon.devsuite.common import DebuggerLogTypes
from webaxon.devsuite.constants import RUNTIME_DIR, FOLDER_NAME_DEBUGGER_LOGS
from dataclasses import dataclass, field


@dataclass
class DebuggerSessionInfo(SessionInfo):
    """Information about a debugger session (client-side).

    Extends SessionInfo with debugger-specific fields for UI state and log tracking.
    This tracks the client-side view of a session, including log visualization state
    and agent control/status polling.
    """
    # Log tracking
    log_file_path: str = None  # Path to session logs on disk
    log_collector: LogCollector = None  # LogCollector instance for this session

    # Agent control and status (polled from service)
    agent_control: str = 'continue'  # Current control signal ("stop"/"pause"/"continue"/"step")
    agent_status: str = 'not_started'  # Current execution status ("running"/"paused"/"stopped"/"not_started")
    control_pending: bool = False  # Waiting for control acknowledgment
    status_messages: list = field(default_factory=list)  # Status updates from service

    # UI state tracking
    loaded_log_data: dict = None  # Cached log data: {nodes, edges, mtime, timestamp, graph_structure}
    initial_load_done: bool = False  # True once auto-load is completed
    last_displayed_mtime: float = None  # Last displayed modification time (for change detection)
    logged_waiting_messages: set = field(default_factory=set)  # Message types already logged (avoid spam)

    # Session debugger instance
    debugger: Debugger = None  # Debugger instance for this session


# Global state
_queue_service = None
_latest_log_collector = None
_latest_log_file_path = None
_recent_log_collectors = {}  # timestamp_key -> LogCollector (for backward compatibility)
_last_queue_check_time = 0
_queue_check_interval = 5.0  # Check for new queue every 5 seconds
_pending_message_id = None  # Store ID of the placeholder message waiting for response

# Thread lock for CLIENT_CONTROL_QUEUE polling
# Prevents race conditions when multiple callbacks compete for messages
_client_control_poll_lock = threading.Lock()

# Unified session tracking (replaces 8+ separate dictionaries)
_session_info = {}  # session_id -> DebuggerSessionInfo

# Background log monitoring state
_log_monitor_thread = None
_log_monitor_running = False
_log_data_lock = None  # Will be initialized with threading.Lock()
_monitor_messages = []  # List of recent monitor messages (max 10)
_monitor_messages_lock = None  # Will be initialized with threading.Lock()

# Log data processing cache (preprocessing done in background, rendering in main thread)
_log_groups_cache = {}  # (session_id, log_group_id, mtime) -> processed log list (ready for rendering)

# Global debugger for module-level events (will be initialized in main())
_global_debugger = None


def _get_or_create_global_debugger():
    """Get or create the global debugger for non-session events."""
    global _global_debugger
    if _global_debugger is None:
        # Use project root to create global debugger log directory
        testcase_root = Path(__file__).parent
        debugger_log_dir = testcase_root / RUNTIME_DIR / FOLDER_NAME_DEBUGGER_LOGS / 'global'
        debugger_log_dir.mkdir(parents=True, exist_ok=True)

        _global_debugger = Debugger(
            id='agent_debugger_global',
            log_name='AgentDebugger',
            logger=[
                print,  # Console output
                partial(write_json, file_path=str(debugger_log_dir / FOLDER_NAME_DEBUGGER_LOGS), append=True)
            ],
            debug_mode=config.DEBUG_MODE_DEBUGGER,
            log_time=True,
            always_add_logging_based_logger=False
        )
    return _global_debugger


def get_session_info(session_id: str) -> DebuggerSessionInfo:
    """
    Get or create session info for the given session_id.

    This is the unified way to access session information. If the session doesn't
    exist yet, it creates a new DebuggerSessionInfo with default values.

    Args:
        session_id: Session identifier

    Returns:
        DebuggerSessionInfo object for this session
    """
    global _session_info
    if session_id not in _session_info:
        # Create session-specific debugger log directory
        testcase_root = Path(__file__).parent
        debugger_log_dir = testcase_root / RUNTIME_DIR / FOLDER_NAME_DEBUGGER_LOGS / session_id
        debugger_log_dir.mkdir(parents=True, exist_ok=True)

        # Create session-specific debugger
        session_debugger = Debugger(
            id=f'debugger_{session_id}',
            log_name=f'AgentDebugger_{session_id}',
            logger=[
                print,  # Console output
                partial(write_json, file_path=str(debugger_log_dir / FOLDER_NAME_DEBUGGER_LOGS), append=True)
            ],
            debug_mode=config.DEBUG_MODE_DEBUGGER,
            log_time=True,
            always_add_logging_based_logger=False
        )

        _session_info[session_id] = DebuggerSessionInfo(
            session_id=session_id,
            created_at=timestamp(),
            last_active=timestamp(),
            session_type=AGENT_TYPE_DEFAULT,
            debugger=session_debugger  # Store debugger
        )
    return _session_info[session_id]


def get_debugger(session_id: str = None) -> Debugger:
    """
    Get session debugger or fall back to global debugger.

    Args:
        session_id: Optional session ID to get debugger for

    Returns:
        Debugger instance (session-specific if session_id provided, global otherwise)
    """
    if session_id:
        session_info = get_session_info(session_id)
        return session_info.debugger
    return _get_or_create_global_debugger()


def get_active_session_ids() -> list:
    """
    Get list of all currently tracked session IDs.

    Returns:
        List of session ID strings
    """
    return list(_session_info.keys())


def cleanup_inactive_sessions(active_session_ids: list):
    """
    Remove session info for sessions not in the active list.

    This performs comprehensive cleanup of all session-related data to prevent
    memory leaks from orphaned sessions.

    Args:
        active_session_ids: List of session IDs that should be kept
    """
    global _session_info, _log_groups_cache

    active_set = set(active_session_ids)

    # Clean up session info dict
    for session_id in list(_session_info.keys()):
        if session_id not in active_set:
            del _session_info[session_id]

    # Clean up log groups cache (composite keys with session_id as first element)
    for key in list(_log_groups_cache.keys()):
        if key[0] not in active_set:
            del _log_groups_cache[key]


def add_monitor_message(message: str):
    """Add a message to the monitor message queue (thread-safe)."""
    global _monitor_messages, _monitor_messages_lock

    if _monitor_messages_lock is None:
        _monitor_messages_lock = threading.Lock()

    with _monitor_messages_lock:
        timestamp = time.strftime('%H:%M:%S')
        _monitor_messages.append(f"[{timestamp}] {message}")
        # Keep only last 10 messages
        if len(_monitor_messages) > 10:
            _monitor_messages.pop(0)


def get_monitor_messages() -> list:
    """Get recent monitor messages (thread-safe)."""
    global _monitor_messages, _monitor_messages_lock

    if _monitor_messages_lock is None:
        return []

    with _monitor_messages_lock:
        return list(_monitor_messages)  # Return a copy


def initialize_queue_service():
    """
    Initialize or refresh the shared queue service by finding the latest queue path.

    This is called periodically and will automatically detect when the agent service
    restarts with a new timestamp folder.
    """
    global _queue_service, _last_queue_check_time

    current_time = time.time()

    # Check if we should refresh the queue service
    should_check = (
            _queue_service is None or
            (current_time - _last_queue_check_time) >= _queue_check_interval
    )

    if should_check:
        testcase_root = Path(__file__).parent

        # get_queue_service handles all the logic: path comparison, logging, and cleanup
        _queue_service = get_queue_service(
            testcase_root,
            existing_service=_queue_service,
            log_on_change=True
        )

        _last_queue_check_time = current_time

    return _queue_service


def sync_active_sessions(active_session_ids: list):
    """
    Sync all active session IDs with the agent service.

    This sends a complete list of active sessions to the service, allowing it to:
    - Create agents for new sessions (with default DefaultAgent configuration)
    - Close agents for sessions that are no longer active

    Args:
        active_session_ids: List of all currently active session IDs
    """
    queue_service = initialize_queue_service()

    debugger = _get_or_create_global_debugger()
    debugger.log_info({'active_sessions': active_session_ids}, DebuggerLogTypes.QUEUE_OPERATION)

    # Send session sync message with generic format
    control_message = {
        "type": "sync_active_sessions",
        "message": {
            "active_sessions": active_session_ids
        },
        "timestamp": timestamp()
    }

    queue_service.put(SERVER_CONTROL_QUEUE_ID, control_message)
    debugger.log_info(f"Active sessions sync message sent to {SERVER_CONTROL_QUEUE_ID}", DebuggerLogTypes.QUEUE_OPERATION)


def sync_session_agent(session_id: str, agent_type: str):
    """
    Update the agent configuration for a specific session.

    Args:
        session_id: Session ID to update
        agent_type: Type of agent to use (e.g., 'DefaultAgent', 'MockClarificationAgent')
    """
    queue_service = initialize_queue_service()

    debugger = get_debugger(session_id)
    debugger.log_info({'session_id': session_id, 'agent_type': agent_type}, DebuggerLogTypes.QUEUE_OPERATION)

    # Send per-session agent update with generic format
    control_message = {
        "type": "sync_session_agent",
        "message": {
            "session_id": session_id,
            "agent_type": agent_type
        },
        "timestamp": timestamp()
    }

    queue_service.put(SERVER_CONTROL_QUEUE_ID, control_message)
    debugger.log_info(f"Session agent update sent to {SERVER_CONTROL_QUEUE_ID}", DebuggerLogTypes.QUEUE_OPERATION)


def send_agent_control(session_id: str, control: str):
    """
    Send an agent workflow control command to the agent service.

    Args:
        session_id: Session ID to control
        control: Control command ('stop', 'pause', 'continue', 'step')
    """
    queue_service = initialize_queue_service()

    # Send agent control message
    control_message = {
        "type": "agent_control",
        "message": {
            "session_id": session_id,
            "control": control
        },
        "timestamp": timestamp()
    }

    hprint_message(
        control_message,
        title=f"[CONTROL SENT] {control.upper()} → {SERVER_CONTROL_QUEUE_ID}"
    )

    queue_service.put(SERVER_CONTROL_QUEUE_ID, control_message)

    # Mark control as pending for this session
    get_session_info(session_id).control_pending = True


def queue_message_handler_internal(message: str, session_id: str, all_session_ids: list = None, current_agent_type: str = None) -> str:
    """
    Message handler that sends user input to the agent service via queue.

    This function immediately returns after sending the message.
    The response will be polled asynchronously by the UI.

    Args:
        message: User input message
        session_id: Session ID to associate this message with
        all_session_ids: List of all active session IDs (for session reconciliation)
        current_agent_type: Current agent type for this session (if changed)

    Returns:
        Immediate acknowledgment message
    """
    queue_service = initialize_queue_service()

    debugger = get_debugger(session_id)
    debugger.log_info('Sending message to agent service...', DebuggerLogTypes.QUEUE_OPERATION)
    debugger.log_debug({
        'message_type': type(message).__name__,
        'message_value': message,
        'session_id_type': type(session_id).__name__,
        'session_id': session_id,
        'all_session_ids': all_session_ids,
        'current_agent_type': current_agent_type
    }, DebuggerLogTypes.DEBUG)

    # Sync active sessions (this allows service to reconcile and close inactive sessions)
    sync_active_sessions(all_session_ids or [session_id])

    # If agent type is specified for this session, sync it
    if current_agent_type:
        sync_session_agent(session_id, current_agent_type)

    # Put user input on the session-specific queue
    # Format: {"session_id": session_id, "user_input": message}
    # Using "user_input" key matches Agent's task_input_field_user_input
    queue_data = {
        "session_id": session_id,
        "user_input": message
    }
    debugger.log_debug({'queue_data': queue_data}, DebuggerLogTypes.DEBUG)

    # Send to session-specific input queue (e.g., 'user_input_session_1_20251110103004')
    # The agent thread will pick it up from there
    session_input_queue_id = f"{INPUT_QUEUE_ID}_{session_id}"
    queue_service.put(session_input_queue_id, queue_data)
    debugger.log_info(f"Message sent to session-specific queue: {session_input_queue_id}", DebuggerLogTypes.QUEUE_OPERATION)

    # Return special marker that will be rendered with animation
    return SPECIAL_MESSAGE_WAITING_FOR_RESPONSE


# NOTE: check_for_log_paths() function has been removed
# Its logic has been extracted to _handle_log_path_message() and is now called
# by the unified poll_client_controls callback


def background_log_monitor():
    """
    Background thread that monitors log file paths and loads log data.

    This runs independently and continuously:
    1. Checks for new log paths in CLIENT_CONTROL_QUEUE
    2. Loads log data from disk (this can be slow)
    3. Stores loaded data with node/edge counts
    4. UI can check if new data is ready and prompt user to refresh
    """
    global _log_monitor_running, _log_data_lock

    debugger = _get_or_create_global_debugger()
    debugger.log_info("Background log monitor started", DebuggerLogTypes.LOG_MONITOR)
    add_monitor_message("Monitor started")

    while _log_monitor_running:
        try:
            # Check for each session's log path
            session_items = [(sid, info.log_file_path) for sid, info in _session_info.items() if info.log_file_path]
            if session_items:
                add_monitor_message(f"Checking {len(session_items)} session(s)")

            for session_id, log_file_path in session_items:
                # Check if we need to reload this session's logs
                with _log_data_lock:
                    session_info = get_session_info(session_id)
                    existing_data = session_info.loaded_log_data

                # Get file modification time
                try:
                    log_path = Path(log_file_path)
                    if not log_path.exists():
                        add_monitor_message(f"{session_id[:20]}: path not found")
                        continue

                    # Check newest file in the log directory
                    # Look for all files recursively (log files may not have .json extension)
                    all_files = [f for f in log_path.rglob('*') if f.is_file()]
                    if not all_files:
                        add_monitor_message(f"{session_id[:20]}: no log files")
                        continue

                    newest_mtime = max(f.stat().st_mtime for f in all_files)
                    existing_mtime = existing_data.get('mtime', 0) if existing_data else 0

                    # Skip if we already loaded this data recently
                    if existing_data and existing_mtime >= newest_mtime:
                        continue

                    debugger.log_info({'session_id': session_id, 'log_file_path': log_file_path}, DebuggerLogTypes.LOG_MONITOR)
                    add_monitor_message(f"{session_id[:20]}: loading... (mtime changed)")

                    # Load log data (this is the slow part)
                    log_collector = LogCollector.from_json_logs(log_file_path, json_file_pattern='*')
                    graph_structure = log_collector.get_graph_structure()

                    num_nodes = len(graph_structure['nodes'])
                    num_edges = len(graph_structure['edges'])

                    # Store the loaded data with lock
                    with _log_data_lock:
                        session_info.loaded_log_data = {
                            'log_collector': log_collector,
                            'graph_structure': graph_structure,
                            'nodes': num_nodes,
                            'edges': num_edges,
                            'mtime': newest_mtime,
                            'timestamp': time.time(),
                            'log_file_path': log_file_path
                        }

                    debugger.log_info({
                        'session_id': session_id,
                        'num_nodes': num_nodes,
                        'num_edges': num_edges
                    }, DebuggerLogTypes.LOG_MONITOR)
                    add_monitor_message(f"{session_id[:20]}: loaded {num_nodes}N {num_edges}E")

                except Exception as e:
                    debugger.log_error({'session_id': session_id, 'error': str(e)}, DebuggerLogTypes.LOG_MONITOR)
                    add_monitor_message(f"{session_id[:20]}: ERROR - {str(e)[:30]}")

        except Exception as e:
            debugger.log_error({'error': str(e)}, DebuggerLogTypes.LOG_MONITOR)

        # Sleep before next check
        time.sleep(2.0)  # Check every 2 seconds

    debugger.log_info("Background log monitor stopped", DebuggerLogTypes.LOG_MONITOR)


def start_log_monitor():
    """Start the background log monitoring thread."""
    global _log_monitor_thread, _log_monitor_running, _log_data_lock

    if _log_data_lock is None:
        _log_data_lock = threading.Lock()

    if _log_monitor_thread is None or not _log_monitor_thread.is_alive():
        _log_monitor_running = True
        _log_monitor_thread = threading.Thread(target=background_log_monitor, daemon=True)
        _log_monitor_thread.start()
        debugger = _get_or_create_global_debugger()
        debugger.log_info("Started background log monitoring thread", DebuggerLogTypes.LOG_MONITOR)


def stop_log_monitor():
    """Stop the background log monitoring thread."""
    global _log_monitor_running
    _log_monitor_running = False
    debugger = _get_or_create_global_debugger()
    debugger.log_info("Stopping background log monitor...", DebuggerLogTypes.LOG_MONITOR)


def check_for_agent_response():
    """
    Check if there's a response from the agent service.

    This is called periodically by the UI to poll for responses.

    Returns:
        Tuple of (session_id, response_text, log_collector) or (None, None, None) if no response
    """
    global _latest_log_collector, _latest_log_file_path, _recent_log_collectors

    queue_service = initialize_queue_service()

    # If queue service isn't initialized, can't check for responses
    if queue_service is None:
        return None, None, None

    # Check for response (non-blocking)
    response_data = queue_service.get(RESPONSE_QUEUE_ID, blocking=False)

    if response_data is None:
        return None, None, None

    debugger = _get_or_create_global_debugger()
    debugger.log_debug({
        'type': type(response_data).__name__,
        'keys': list(response_data.keys()) if isinstance(response_data, dict) else 'N/A',
        'value_preview': str(response_data)[:200]
    }, DebuggerLogTypes.DEBUG)

    # Extract session_id and response from response_data
    # Expected format: {"session_id": session_id, "response": response_text_or_list}
    if isinstance(response_data, dict):
        session_id = response_data.get('session_id')
        response = response_data.get('response', '')
        debugger.log_debug({
            'response_type': 'dict',
            'session_id': session_id,
            'session_id_type': type(session_id).__name__
        }, DebuggerLogTypes.DEBUG)

        # Handle list responses (e.g., clarification with context)
        if isinstance(response, list):
            debugger.log_debug({'response_list_length': len(response)}, DebuggerLogTypes.DEBUG)
            response = '\n\n'.join(str(item) for item in response)

        debugger.log_debug({
            'response_length': len(response) if isinstance(response, str) else 'N/A'
        }, DebuggerLogTypes.DEBUG)
    else:
        # Fallback for old format (plain string) - no session routing
        debugger.log_warning({
            'message': 'Response in old format (not dict), cannot route to session',
            'response_type': type(response_data).__name__,
            'value': response_data
        }, DebuggerLogTypes.WARNING)
        session_id = None
        response = str(response_data)

    debugger.log_info({
        'session_id': session_id,
        'response_preview': response[:100] if len(response) > 100 else response
    }, DebuggerLogTypes.QUEUE_OPERATION)

    # Note: Log paths are now checked separately in check_for_log_paths()
    # which is called periodically by the polling callback

    return session_id, response, _latest_log_collector


def get_latest_agent_logs(graph_type: str = None):
    """
    Get the latest agent execution logs for visualization.

    Args:
        graph_type: Graph type selector (ignored - always returns latest)

    Returns:
        LogCollector with the latest agent execution logs
    """
    global _latest_log_collector

    if _latest_log_collector:
        return _latest_log_collector

    # Fallback: return the most recent from history
    if _recent_log_collectors:
        latest_key = sorted(_recent_log_collectors.keys())[-1]
        return _recent_log_collectors[latest_key]

    # No logs available - return empty collector
    return LogCollector()


# ============================================================================
# Client Control Message Handlers
# ============================================================================
# These handlers process different message types from CLIENT_CONTROL_QUEUE
# They are called by the unified poll_client_controls callback

def _handle_agent_status_message(msg, session_id, app_instance):
    """
    Handle agent_status message type.

    Updates session status tracking and agent creation flags.

    Args:
        msg: Message dict with type "agent_status"
        session_id: Current active session ID
        app_instance: QueueBasedDashApp instance for accessing state

    Returns:
        tuple: (latest_agent, agent_created) - latest agent type and creation flag
    """
    payload = msg.get('message', {})
    msg_session_id = payload.get('session_id')

    latest_agent = None
    agent_created = False

    if msg_session_id == session_id:
        # Store message for this session (store the whole message with timestamp)
        if session_id not in app_instance.agent_status_messages:
            app_instance.agent_status_messages[session_id] = []
        app_instance.agent_status_messages[session_id].append(msg)

        # Track latest agent from status messages
        status = payload.get('status')
        if status in ('created', 'agent_updated'):
            latest_agent = payload.get('agent_type')
            agent_created = True  # Agent is now created and locked
        elif status == 'agent_locked':
            # Agent type change rejected because agent already created
            agent_created = True

    return latest_agent, agent_created


def _handle_agent_control_ack_message(msg, session_id):
    """
    Handle agent_control_ack message type.

    Updates agent control and status for ALL active sessions (not just current).

    Args:
        msg: Message dict with type "agent_control_ack"
        session_id: Current active session ID (used for debug logging)
    """
    payload = msg.get('message', {})
    msg_session_id = payload.get('session_id')

    # Process message for any session (not just current one)
    # Check if this is a known/active session
    active_sessions = get_active_session_ids()
    if msg_session_id and (msg_session_id in active_sessions or msg_session_id == session_id):
        # Update agent control and status for the message's session
        agent_control = payload.get('control', 'continue')
        agent_status = payload.get('agent_status', 'unknown')
        operation_status = payload.get('operation_status', 'success')

        session_info = get_session_info(msg_session_id)
        session_info.agent_control = agent_control
        session_info.agent_status = agent_status
        session_info.control_pending = False

        # Highlight received ack message
        hprint_message(
            {
                'session_id': msg_session_id,
                'control': agent_control,
                'status': agent_status,
                'operation': operation_status
            },
            title=f"[ACK RECEIVED] Session {msg_session_id}: {operation_status}"
        )
    else:
        debugger = _get_or_create_global_debugger()
        debugger.log_debug({
            'message': f"Skipping ack for session {msg_session_id}",
            'reason': 'not in active sessions',
            'current_session': session_id
        }, DebuggerLogTypes.CONTROL_ACK)


def _handle_log_path_message(msg):
    """
    Handle log_path_available message type.

    Loads log files and stores them in session info and global state.

    Args:
        msg: Message dict with type "log_path_available"
    """
    import datetime
    global _latest_log_collector, _latest_log_file_path, _recent_log_collectors

    debugger = _get_or_create_global_debugger()

    # Extract log path from message payload
    log_file_path = msg.get('message', {}).get('log_path')
    if not log_file_path:
        debugger.log_warning({
            'message': 'log_path_available message missing log_path',
            'msg': msg
        }, DebuggerLogTypes.WARNING)
        return

    debugger.log_debug({'log_file_path': log_file_path}, DebuggerLogTypes.DEBUG)

    try:
        # Load logs from the directory
        log_collector = LogCollector.from_json_logs(log_file_path, json_file_pattern='*')

        # Store as the latest for UI access
        _latest_log_collector = log_collector
        _latest_log_file_path = log_file_path

        # Extract session_id from log path (e.g., ".../session_1_20251111062506")
        session_id = Path(log_file_path).name

        debugger.log_debug({'session_id': session_id}, DebuggerLogTypes.DEBUG)

        if session_id:
            session_info = get_session_info(session_id)
            session_info.log_collector = log_collector
            session_info.log_file_path = log_file_path
            debugger.log_debug({
                'session_id': session_id,
                'active_sessions': get_active_session_ids()
            }, DebuggerLogTypes.DEBUG)
        else:
            debugger.log_debug('Could not extract session_id from log path', DebuggerLogTypes.DEBUG)

        # Also store with a timestamp key for history
        timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        session_key = f"agent_{timestamp_str}"
        _recent_log_collectors[session_key] = log_collector

        # Keep only last 10 executions
        if len(_recent_log_collectors) > 10:
            oldest_key = sorted(_recent_log_collectors.keys())[0]
            del _recent_log_collectors[oldest_key]

    except Exception as e:
        import traceback
        debugger.log_warning({
            'message': f'Could not load logs from {log_file_path}',
            'error': str(e),
            'traceback': traceback.format_exc()
        }, DebuggerLogTypes.WARNING)


def main():
    """Run the agent debugger UI."""
    # Initialize queue service
    initialize_queue_service()

    # Create a custom subclass to override the polling behavior
    class QueueBasedDashApp(QueueBasedDashInteractiveApp):
        """Custom Dash app that polls from shared queue service instead of session queues."""

        def __init__(self, queue_service=None, **kwargs):
            """Initialize app with custom Settings tab.

            Args:
                queue_service: Queue service for agent communication (used by Settings callbacks)
                **kwargs: Additional arguments to pass to parent class (title, port, debug, etc.)
            """
            # Store queue service (needed by Settings tab callbacks for polling agent status)
            self.queue_service = queue_service

            # Initialize session-specific tracking dictionaries
            self.session_agents = {}  # Maps session_id -> agent_type
            self.agent_status_messages = {}  # Maps session_id -> list of status messages
            self.sessions_agent_created = {}  # Maps session_id -> bool (True if agent created/locked)

            # Create Settings tab content
            from dash import html, dcc

            settings_content = self._create_settings_tab_content()

            # Create custom monitor tabs list to pass to parent
            custom_monitor_tabs = [
                {
                    'id': 'settings',
                    'label': 'Settings',
                    'content': settings_content
                }
            ]

            # Call parent init with custom tabs
            # Pass response_checker, special_waiting_message, and custom_monitor_tabs
            # Note: queue_service is NOT passed to parent - it only needs the response_checker callback
            super().__init__(
                response_checker=check_for_agent_response,
                special_waiting_message=SPECIAL_MESSAGE_WAITING_FOR_RESPONSE,
                custom_monitor_tabs=custom_monitor_tabs,
                **kwargs
            )

            # Register Settings tab callbacks after app is created
            self._register_settings_callbacks()

        def _create_layout(self) -> html.Div:
            """Override to add custom control stores at root level.

            This ensures control stores are accessible from all tabs,
            not just the Settings tab where they were previously located.
            """
            # Get parent layout
            parent_layout = super()._create_layout()

            # Create control stores that need to be accessible globally
            control_stores = [
                # Hidden store for agent control button clicks
                dcc.Store(id='agent-control-click-store', data=None),
                # Hidden store for agent control status (updated by server)
                dcc.Store(id='agent-control-status-store', data={'state': 'not_started'}),
            ]

            # Insert stores after existing stores but before intervals
            # Parent layout structure: [stores..., intervals..., main_ui_div]
            existing_children = list(parent_layout.children)

            # Find position of first dcc.Interval component
            insert_position = len(existing_children)
            for i, child in enumerate(existing_children):
                if isinstance(child, dcc.Interval):
                    insert_position = i
                    break

            # Insert control stores at the correct position
            new_children = (
                existing_children[:insert_position] +
                control_stores +
                existing_children[insert_position:]
            )

            parent_layout.children = new_children
            return parent_layout

        def _create_settings_tab_content(self):
            """Create the Settings tab content."""
            from dash import html, dcc

            return [
                html.Div(
                    children='⚙️ Session Settings',
                    style={
                        'fontSize': '11px',
                        'color': '#ECECF1',
                        'marginBottom': '10px',
                        'fontWeight': '600'
                    }
                ),
                html.Div(
                    children=[
                        html.Label(
                            'Agent Configuration:',
                            style={
                                'fontSize': '10px',
                                'color': '#8E8EA0',
                                'marginBottom': '4px',
                                'display': 'block',
                                'fontWeight': '500'
                            }
                        ),
                        dcc.Dropdown(
                            id='main-panel-log-graph-agent-dropdown',
                            options=[
                                {'label': 'Default Agent (Full Planning + Web Actions)', 'value': AGENT_TYPE_DEFAULT},
                                {'label': 'Mock Clarification Agent (Simple Testing)', 'value': AGENT_TYPE_MOCK_CLARIFICATION},
                            ],
                            value=AGENT_TYPE_DEFAULT,  # Default
                            placeholder='Select agent configuration...',
                            style={
                                'fontSize': '10px',
                                'marginBottom': '8px'
                            },
                            className='agent-dropdown'
                        )
                    ]
                ),
                html.Button(
                    'Apply Changes',
                    id='main-panel-log-graph-apply-settings-btn',
                    n_clicks=0,
                    style={
                        'width': '100%',
                        'padding': '6px 12px',
                        'backgroundColor': '#19C37D',
                        'color': '#FFFFFF',
                        'border': 'none',
                        'borderRadius': '4px',
                        'cursor': 'pointer',
                        'fontSize': '10px',
                        'fontWeight': '500',
                        'marginBottom': '10px',
                        'transition': 'all 0.2s'
                    }
                ),
                html.Div(
                    children=[
                        html.Div(
                            children='Current Agent:',
                            style={
                                'fontSize': '9px',
                                'color': '#8E8EA0',
                                'marginBottom': '2px',
                                'fontWeight': '500'
                            }
                        ),
                        html.Div(
                            id='main-panel-log-graph-current-agent',
                            children=AGENT_TYPE_DEFAULT,
                            style={
                                'fontSize': '9px',
                                'color': '#19C37D',
                                'fontFamily': 'monospace',
                                'backgroundColor': 'rgba(0, 0, 0, 0.2)',
                                'padding': '4px 6px',
                                'borderRadius': '3px',
                                'marginBottom': '10px'
                            }
                        )
                    ]
                ),
                html.Div(
                    children=[
                        html.Div(
                            children='Agent Status:',
                            style={
                                'fontSize': '9px',
                                'color': '#8E8EA0',
                                'marginBottom': '2px',
                                'fontWeight': '500'
                            }
                        ),
                        html.Div(
                            id='main-panel-log-graph-agent-status',
                            children='No status updates',
                            style={
                                'fontSize': '8px',
                                'color': '#ECECF1',
                                'backgroundColor': 'rgba(0, 0, 0, 0.2)',
                                'padding': '4px 6px',
                                'borderRadius': '3px',
                                'marginBottom': '10px',
                                'maxHeight': '60px',
                                'overflowY': 'auto'
                            }
                        )
                    ]
                ),
                html.Div(
                    children='ℹ️ Settings are session-specific',
                    style={
                        'fontSize': '8px',
                        'color': '#6E6E80',
                        'fontStyle': 'italic',
                        'textAlign': 'center'
                    }
                ),
                # Hidden store for log path polling callback
                dcc.Store(id='log-path-poll-dummy', data=None),
                # Interval component to poll for agent status updates
                dcc.Interval(
                    id='agent-status-poll-interval',
                    interval=1000,  # Poll every 1 second
                    n_intervals=0
                )
            ]

        def _register_settings_callbacks(self):
            """Register callbacks for Settings tab functionality."""
            from dash.dependencies import Input, Output, State
            from dash.exceptions import PreventUpdate

            # Callback to populate agent dropdown based on current session
            @self.app.callback(
                [
                    Output('main-panel-log-graph-agent-dropdown', 'value'),
                    Output('main-panel-log-graph-current-agent', 'children'),
                    Output('main-panel-log-graph-agent-dropdown', 'disabled')
                ],
                [
                    Input('current-session-store', 'data')
                ],
                prevent_initial_call=False
            )
            def populate_agent_settings(session_id):
                """Update dropdown to show current session's agent and disable if agent created."""
                # Check if agent has been created for this session
                is_agent_created = self.sessions_agent_created.get(session_id, False) if session_id else False

                if session_id and session_id in self.session_agents:
                    current_agent = self.session_agents[session_id]
                    return current_agent, current_agent, is_agent_created
                else:
                    # Default
                    return AGENT_TYPE_DEFAULT, AGENT_TYPE_DEFAULT, is_agent_created

            # Callback to apply agent settings
            @self.app.callback(
                [
                    Output('main-panel-log-graph-apply-settings-btn', 'children'),
                    Output('main-panel-log-graph-current-agent', 'children', allow_duplicate=True)
                ],
                [
                    Input('main-panel-log-graph-apply-settings-btn', 'n_clicks')
                ],
                [
                    State('main-panel-log-graph-agent-dropdown', 'value'),
                    State('current-session-store', 'data')
                ],
                prevent_initial_call=True
            )
            def apply_agent_settings(n_clicks, selected_agent, session_id):
                """Apply agent settings when button is clicked."""
                if not n_clicks or not selected_agent or not session_id:
                    raise PreventUpdate

                # Store the selected agent for this session
                self.session_agents[session_id] = selected_agent

                # Send control message to agent service immediately
                sync_session_agent(session_id, selected_agent)

                # Show "Pending..." while waiting for acknowledgment from service
                return '✓ Applied', 'Pending Service Change...'

            # Unified callback to poll for ALL client control messages
            # This replaces three separate callbacks that were competing for messages
            @self.app.callback(
                [
                    Output('main-panel-log-graph-agent-status', 'children'),
                    Output('main-panel-log-graph-current-agent', 'children', allow_duplicate=True),
                    Output('main-panel-log-graph-agent-dropdown', 'disabled', allow_duplicate=True),
                    Output('agent-control-status-store', 'data')
                ],
                [
                    Input('agent-status-poll-interval', 'n_intervals')
                ],
                [
                    State('current-session-store', 'data')
                ],
                prevent_initial_call=True
            )
            def poll_client_controls(_n_intervals, session_id):
                """
                Unified polling function for ALL CLIENT_CONTROL_QUEUE message types.

                This replaces three separate callbacks (poll_agent_status, poll_agent_control_ack,
                poll_log_paths) that were competing for messages, causing race conditions and
                message loss.

                Handles three message types:
                - agent_status: Agent creation/update/locking status
                - agent_control_ack: Control command acknowledgments
                - log_path_available: Log file path notifications

                Uses a non-blocking lock to prevent concurrent queue access while keeping UI responsive.
                """
                from dash import html
                import dash

                # Try to initialize queue service if not available yet
                # This handles the case where debugger starts before the service
                if not self.queue_service:
                    self.queue_service = initialize_queue_service()
                    if not self.queue_service:
                        # Service still not available - return early
                        return (
                            'No status updates (waiting for service)',
                            dash.no_update,
                            False,
                            {'control': 'continue', 'status': 'not_started', 'pending': False}
                        )
                    else:
                        debugger = _get_or_create_global_debugger()
                        debugger.log_info('Connected to queue service successfully', DebuggerLogTypes.QUEUE_OPERATION)

                # Try to acquire lock - skip this poll if already running
                if not _client_control_poll_lock.acquire(blocking=False):
                    # Another callback is already processing - skip to keep UI responsive
                    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

                try:
                    # Atomically read ALL messages from queue
                    messages = []
                    max_messages = 100  # Prevent runaway processing

                    while len(messages) < max_messages:
                        msg = self.queue_service.get(CLIENT_CONTROL_QUEUE_ID, blocking=False, timeout=0)
                        if msg is None:
                            break
                        messages.append(msg)

                    # Track state changes for agent_status messages
                    latest_agent = None
                    agent_created = False

                    # Dispatch messages by type
                    for msg in messages:
                        if not isinstance(msg, dict):
                            debugger = _get_or_create_global_debugger()
                            debugger.log_warning({'message': 'Non-dict message in CLIENT_CONTROL_QUEUE', 'value': msg}, DebuggerLogTypes.WARNING)
                            continue

                        msg_type = msg.get('type')

                        if msg_type == 'agent_status':
                            agent, created = _handle_agent_status_message(msg, session_id, self)
                            if agent:
                                latest_agent = agent
                            if created:
                                agent_created = True

                        elif msg_type == 'agent_control_ack':
                            _handle_agent_control_ack_message(msg, session_id)

                        elif msg_type == 'log_path_available':
                            _handle_log_path_message(msg)

                        else:
                            debugger = _get_or_create_global_debugger()
                            debugger.log_warning({'message': 'Unknown message type', 'msg_type': msg_type}, DebuggerLogTypes.WARNING)

                    # If no active session, just return defaults but still process messages
                    if not session_id:
                        return (
                            'No status updates (no active session)',
                            dash.no_update,
                            False,
                            {'control': 'continue', 'status': 'not_started', 'pending': False}
                        )

                    # Update the sessions_agent_created flag if agent was created/locked
                    if agent_created:
                        self.sessions_agent_created[session_id] = True

                    # Build agent status display from accumulated messages
                    status_display = 'No status updates'
                    if session_id in self.agent_status_messages:
                        recent_messages = self.agent_status_messages[session_id][-5:]

                        # Format messages for display
                        status_divs = []
                        for msg in reversed(recent_messages):  # Show newest first
                            payload = msg.get('message', {})
                            status = payload.get('status', 'unknown')
                            agent_type = payload.get('agent_type', 'N/A')
                            msg_timestamp = msg.get('timestamp', 'N/A')
                            error = payload.get('error')

                            if status == 'created':
                                text = f"[{msg_timestamp}] ✓ Agent created with {agent_type}"
                                color = '#19C37D'
                            elif status == 'agent_updated':
                                text = f"[{msg_timestamp}] ✓ Agent updated to {agent_type}"
                                color = '#19C37D'
                            elif status == 'agent_locked':
                                text = f"[{msg_timestamp}] 🔒 Agent locked (cannot change after first message)"
                                color = '#FF9800'
                            elif status == 'agent_type_updated':
                                text = f"[{msg_timestamp}] ✓ Agent type updated to {agent_type} (not created yet)"
                                color = '#19C37D'
                            elif status == 'error':
                                text = f"[{msg_timestamp}] ✗ Error: {error}"
                                color = '#FF6B6B'
                            else:
                                text = f"[{msg_timestamp}] Status: {status}"
                                color = '#8E8EA0'

                            status_divs.append(html.Div(text, style={'color': color, 'marginBottom': '2px'}))

                        status_display = status_divs if status_divs else 'No status updates'

                    # Update Current Agent if we got a new agent from service
                    current_agent_display = latest_agent if latest_agent else dash.no_update

                    # Update disabled state based on whether agent has been created
                    dropdown_disabled = self.sessions_agent_created.get(session_id, False)

                    # Get agent control status for this session
                    session_info = get_session_info(session_id)
                    control_status = {
                        'control': session_info.agent_control,
                        'status': session_info.agent_status,
                        'pending': session_info.control_pending
                    }

                    return status_display, current_agent_display, dropdown_disabled, control_status

                except Exception as e:
                    import traceback
                    debugger = _get_or_create_global_debugger()
                    debugger.log_error({
                        'error': str(e),
                        'traceback': traceback.format_exc()
                    }, DebuggerLogTypes.ERROR)
                    return (
                        f'Error polling: {str(e)}',
                        dash.no_update,
                        dash.no_update,
                        {'control': 'continue', 'status': 'error', 'pending': False}
                    )
                finally:
                    _client_control_poll_lock.release()

        # NOTE: _register_log_path_polling_callback has been removed
        # Log path messages are now handled by the unified poll_client_controls callback

    # Create the app using our custom subclass
    app = QueueBasedDashApp(
        title="Web Agent Debugger",
        port=8050,
        debug=False,
        queue_service=initialize_queue_service()  # Enable queue-based inferencer selection
    )

    # Create a closure that has access to app.session_agents
    def queue_message_handler_with_app(message: str, session_id: str, all_session_ids: list = None) -> str:
        """Message handler that has access to app's session_agents."""
        # Get the current agent type for this session (default to AGENT_TYPE_DEFAULT to match server)
        current_agent_type = AGENT_TYPE_DEFAULT  # Default matches server default
        if hasattr(app, 'session_agents') and session_id in app.session_agents:
            current_agent_type = app.session_agents[session_id]

        # Call the internal handler with current agent type for this session only
        return queue_message_handler_internal(message, session_id, all_session_ids, current_agent_type)

    # Set custom message handler
    app.set_message_handler(queue_message_handler_with_app)

    # Add clientside callback to make log monitor panel draggable
    app.app.clientside_callback(
        """
        function() {
            // Make the log monitor panel draggable
            const panel = document.getElementById('main-panel-log-graph-log-monitor-panel');
            const dragHandle = document.getElementById('main-panel-log-graph-monitor-drag-handle');

            if (panel && dragHandle && !panel.dataset.draggableInitialized) {
                let isDragging = false;
                let currentX;
                let currentY;
                let initialX;
                let initialY;
                let xOffset = 0;
                let yOffset = 0;

                dragHandle.addEventListener('mousedown', dragStart);
                document.addEventListener('mousemove', drag);
                document.addEventListener('mouseup', dragEnd);

                function dragStart(e) {
                    initialX = e.clientX - xOffset;
                    initialY = e.clientY - yOffset;

                    if (e.target === dragHandle || dragHandle.contains(e.target)) {
                        isDragging = true;
                    }
                }

                function drag(e) {
                    if (isDragging) {
                        e.preventDefault();

                        currentX = e.clientX - initialX;
                        currentY = e.clientY - initialY;

                        xOffset = currentX;
                        yOffset = currentY;

                        setTranslate(currentX, currentY, panel);
                    }
                }

                function dragEnd(e) {
                    initialX = currentX;
                    initialY = currentY;
                    isDragging = false;
                }

                function setTranslate(xPos, yPos, el) {
                    el.style.transform = 'translate3d(' + xPos + 'px, ' + yPos + 'px, 0)';
                }

                panel.dataset.draggableInitialized = 'true';
                console.log('[Log Monitor] Drag functionality initialized');
            }

            return window.dash_clientside.no_update;
        }
        """,
        Output('main-panel-log-graph-log-monitor-panel', 'data-drag-initialized'),
        Input('main-panel-log-graph-log-monitor-panel', 'id'),
        prevent_initial_call=False
    )

    # Add clientside callback for monitor tab switching
    app.app.clientside_callback(
        """
        function(logs_clicks, responses_clicks, settings_clicks) {
            // Determine which button was clicked
            const ctx = window.dash_clientside.callback_context;
            if (!ctx.triggered.length) {
                return window.dash_clientside.no_update;
            }

            const triggerId = ctx.triggered[0].prop_id.split('.')[0];

            // Define tabs
            const tabs = ['logs', 'responses', 'settings'];
            let activeTab = 'logs';  // default

            if (triggerId.includes('logs')) {
                activeTab = 'logs';
            } else if (triggerId.includes('responses')) {
                activeTab = 'responses';
            } else if (triggerId.includes('settings')) {
                activeTab = 'settings';
            }

            // Update tab visibility and button styles
            tabs.forEach(tab => {
                const tabContent = document.getElementById(`main-panel-log-graph-monitor-${tab}-tab`);
                const tabBtn = document.getElementById(`main-panel-log-graph-monitor-tab-${tab}-btn`);

                if (tab === activeTab) {
                    if (tabContent) tabContent.style.display = 'block';
                    if (tabBtn) {
                        tabBtn.style.backgroundColor = '#19C37D';
                        tabBtn.style.color = '#FFFFFF';
                    }
                } else {
                    if (tabContent) tabContent.style.display = 'none';
                    if (tabBtn) {
                        tabBtn.style.backgroundColor = '#4A4A5A';
                        tabBtn.style.color = '#8E8EA0';
                    }
                }
            });

            return window.dash_clientside.no_update;
        }
        """,
        Output('main-panel-log-graph-monitor-panel', 'data-tab-switch'),
        [
            Input('main-panel-log-graph-monitor-tab-logs-btn', 'n_clicks'),
            Input('main-panel-log-graph-monitor-tab-responses-btn', 'n_clicks'),
            Input('main-panel-log-graph-monitor-tab-settings-btn', 'n_clicks')
        ],
        prevent_initial_call=False
    )

    # Add clientside callback to inject agent control buttons into Logs tab
    app.app.clientside_callback(
        """
        function(n_intervals) {
            // Check if control buttons already injected
            if (document.getElementById('agent-control-buttons-container')) {
                return window.dash_clientside.no_update;
            }

            // Find the Logs tab content
            const logsTab = document.getElementById('main-panel-log-graph-monitor-logs-tab');
            const statsDiv = document.getElementById('main-panel-log-graph-monitor-stats');

            if (!logsTab || !statsDiv) {
                return window.dash_clientside.no_update;
            }

            // Create control buttons container
            const controlContainer = document.createElement('div');
            controlContainer.id = 'agent-control-buttons-container';
            controlContainer.style.cssText = 'margin-bottom: 6px; padding: 0; backgroundColor: transparent; borderRadius: 4px;';

            // Create buttons container
            const buttonsDiv = document.createElement('div');
            buttonsDiv.style.cssText = 'display: flex; gap: 2px; justifyContent: space-around;';

            // Create control buttons
            const buttons = [
                {id: 'agent-control-stop-btn', label: '■', title: 'Stop', color: '#FF6B6B'},
                {id: 'agent-control-pause-btn', label: '‖', title: 'Pause', color: '#FF9800'},
                {id: 'agent-control-continue-btn', label: '▶', title: 'Continue', color: '#19C37D'},
                {id: 'agent-control-step-btn', label: '⏭', title: 'Step', color: '#4A9EFF'}
            ];

            buttons.forEach(btnInfo => {
                const btn = document.createElement('button');
                btn.id = btnInfo.id;
                btn.innerHTML = btnInfo.label;
                btn.title = btnInfo.title;
                btn.style.cssText = `flex: 1; display: flex; align-items: center; justify-content: center; padding: 0; background: none; background-color: transparent; color: ${btnInfo.color}; border: 1px solid ${btnInfo.color}; border-radius: 3px; cursor: pointer; font-size: 14px; height: 24px; text-align: center; transition: all 0.2s;`;
                btn.onmouseover = () => { btn.style.backgroundColor = 'rgba(255, 255, 255, 0.1)'; };
                btn.onmouseout = () => { btn.style.backgroundColor = 'transparent'; };
                buttonsDiv.appendChild(btn);
            });

            controlContainer.appendChild(buttonsDiv);

            // Insert after stats div
            statsDiv.parentNode.insertBefore(controlContainer, statsDiv.nextSibling);

            console.log('[Agent Controls] Injected control buttons into Logs tab');
            return window.dash_clientside.no_update;
        }
        """,
        Output('main-panel-log-graph-monitor-panel', 'data-controls-initialized'),
        Input('response-poll-interval', 'n_intervals'),
        prevent_initial_call=False
    )

    # Add clientside callback to set up button click handlers
    app.app.clientside_callback(
        """
        function(n_intervals, current_store_data) {
            // Check if buttons exist
            const stopBtn = document.getElementById('agent-control-stop-btn');
            const pauseBtn = document.getElementById('agent-control-pause-btn');
            const continueBtn = document.getElementById('agent-control-continue-btn');
            const stepBtn = document.getElementById('agent-control-step-btn');

            if (!stopBtn || stopBtn.dataset.clickHandlerAttached) {
                return window.dash_clientside.no_update;
            }

            // Attach click handlers
            const buttons = [
                {btn: stopBtn, control: 'stop'},
                {btn: pauseBtn, control: 'pause'},
                {btn: continueBtn, control: 'continue'},
                {btn: stepBtn, control: 'step'}
            ];

            buttons.forEach(({btn, control}) => {
                btn.addEventListener('click', () => {
                    // Find the store element and update its data
                    const storeEl = document.getElementById('agent-control-click-store');
                    if (storeEl && storeEl._dash_props_callback) {
                        // Trigger Dash callback by setting props
                        const newData = {
                            control: control,
                            timestamp: Date.now()
                        };
                        storeEl._dash_props_callback({data: newData});
                        console.log(`[Agent Controls] ${control} button clicked, store updated`);
                    } else {
                        console.warn('[Agent Controls] Store not found or not initialized');
                    }
                });
                btn.dataset.clickHandlerAttached = 'true';
            });

            console.log('[Agent Controls] Click handlers attached');
            return window.dash_clientside.no_update;
        }
        """,
        Output('main-panel-log-graph-monitor-panel', 'data-click-handlers'),
        [
            Input('response-poll-interval', 'n_intervals'),
            Input('agent-control-click-store', 'data')
        ],
        prevent_initial_call=False
    )

    # Add callback to sync sessions on page load/refresh
    @app.app.callback(
        Output('sessions-store', 'data', allow_duplicate=True),
        Input('sessions-store', 'data'),
        prevent_initial_call='initial_duplicate'  # Run on initial load with allow_duplicate
    )
    def sync_sessions_on_load(sessions):
        """
        Sync sessions with the service when page loads/refreshes.

        This ensures that when the page is refreshed and sessions are lost,
        the service is notified to clean up any orphaned agent sessions.
        """
        # Extract active session IDs from sessions store (SOURCE OF TRUTH from Dash)
        active_session_ids = [s['id'] for s in sessions] if sessions else []

        # Comprehensive cleanup of all session-related data
        cleanup_inactive_sessions(active_session_ids)
        debugger = _get_or_create_global_debugger()
        debugger.log_info({'active_sessions': active_session_ids}, DebuggerLogTypes.SESSION_SWITCH)

        # Sync active sessions with service (this will close any sessions not in the list)
        sync_active_sessions(active_session_ids)

        # Sync agent for each session that has one set
        if hasattr(app, 'session_agents'):
            for session_id in active_session_ids:
                if session_id in app.session_agents:
                    sync_session_agent(session_id, app.session_agents[session_id])

        debugger.log_info({'action': 'synced_sessions_on_page_load', 'active_sessions': active_session_ids}, DebuggerLogTypes.SESSION_SWITCH)

        # Return sessions unchanged
        return sessions if sessions else dash.no_update

    # Add callback to handle agent control button clicks
    @app.app.callback(
        Output('agent-control-click-store', 'data', allow_duplicate=True),
        [Input('agent-control-click-store', 'data')],
        [State('current-session-store', 'data')],
        prevent_initial_call=True
    )
    def handle_agent_control_click(control_data, session_id):
        """
        Handle agent control button clicks and send control messages to agent service.

        Args:
            control_data: Dict with 'control' and 'timestamp' keys
            session_id: Current session ID
        """
        import dash

        if not control_data or not session_id:
            return dash.no_update

        control = control_data.get('control')
        if not control:
            return dash.no_update

        debugger = get_debugger(session_id)
        debugger.log_info({'control': control, 'session_id': session_id}, DebuggerLogTypes.AGENT_CONTROL)

        # Send control message to agent service
        send_agent_control(session_id, control)

        # Clear store to allow same button to be clicked again
        return None

    # NOTE: poll_agent_control_ack callback has been removed and unified into poll_client_controls
    # The unified callback in QueueBasedDashApp now handles agent_control_ack messages

    # Add callback for initial auto-load when switching to Log Debugging tab
    @app.app.callback(
        [
            Output('log-data-store', 'data', allow_duplicate=True),
            Output('main-panel-log-graph-plotly-loading-overlay', 'style', allow_duplicate=True),
            Output('main-panel-log-graph-cytoscape-loading-overlay', 'style', allow_duplicate=True)
        ],
        [Input('main-panel-log-btn', 'n_clicks')],
        [
            State('log-data-store', 'data'),
            State('current-session-store', 'data'),
            State('main-panel-log-graph-rendering-mode', 'value')
        ],
        prevent_initial_call=True
    )
    def auto_load_on_first_tab_switch(log_btn_clicks, current_data, session_id, rendering_mode):
        """Auto-load logs on first switch to Log Debugging tab."""
        global _log_data_lock
        import dash

        # Define styles for showing/hiding overlay
        overlay_visible = {
            'position': 'absolute', 'top': '0', 'left': '0', 'right': '0', 'bottom': '0',
            'backgroundColor': 'rgba(44, 44, 44, 0.95)', 'display': 'flex',
            'alignItems': 'center', 'justifyContent': 'center', 'zIndex': '2000'
        }
        overlay_hidden = {
            'position': 'absolute', 'top': '0', 'left': '0', 'right': '0', 'bottom': '0',
            'backgroundColor': 'rgba(44, 44, 44, 0.95)', 'display': 'none',
            'alignItems': 'center', 'justifyContent': 'center', 'zIndex': '2000'
        }

        if not log_btn_clicks or not session_id:
            return dash.no_update, dash.no_update, dash.no_update

        # Get session info
        session_info = get_session_info(session_id)

        # Check if we've already done initial load for this session
        if session_info.initial_load_done:
            return dash.no_update, dash.no_update, dash.no_update

        debugger = get_debugger(session_id)
        debugger.log_info({'action': 'first_time_viewing_log_debugging', 'session_id': session_id}, DebuggerLogTypes.AUTO_LOAD)

        # Get the pre-loaded log data from background thread
        with _log_data_lock:
            loaded_data = session_info.loaded_log_data

        # If background thread hasn't loaded it yet, try loading it directly
        if not loaded_data:
            log_file_path = session_info.log_file_path

            if log_file_path:
                debugger.log_info({'action': 'loading_directly', 'log_file_path': log_file_path}, DebuggerLogTypes.AUTO_LOAD)
                try:
                    # Load logs directly (this is synchronous, but only happens once)
                    log_collector = LogCollector.from_json_logs(log_file_path, json_file_pattern='*')
                    graph_structure = log_collector.get_graph_structure()

                    num_nodes = len(graph_structure['nodes'])
                    num_edges = len(graph_structure['edges'])

                    # Get mtime for tracking
                    log_path = Path(log_file_path)
                    # Look for all files recursively (log files may not have .json extension)
                    all_files = [f for f in log_path.rglob('*') if f.is_file()]
                    newest_mtime = max(f.stat().st_mtime for f in all_files) if all_files else 0

                    # Mark as loaded
                    session_info.initial_load_done = True
                    session_info.last_displayed_mtime = newest_mtime

                    debugger.log_info({'action': 'loaded_directly', 'num_nodes': num_nodes, 'num_edges': num_edges}, DebuggerLogTypes.AUTO_LOAD)

                    # Return graph structure
                    result = {
                        'graph_data': {
                            'nodes': graph_structure['nodes'],
                            'edges': graph_structure['edges'],
                            'agent': graph_structure['agent'],
                            'log_file': Path(log_file_path).name if log_file_path else f'session_{session_id}'
                        },
                        'log_groups': {k: v for k, v in log_collector.log_groups.items()}
                    }

                    debugger.log_info({'action': 'initial_load_complete', 'num_log_groups': len(result['log_groups'])}, DebuggerLogTypes.AUTO_LOAD)
                    # Hide loading overlay after loading completes
                    plotly_overlay = overlay_hidden if rendering_mode == 'plotly' else dash.no_update
                    cytoscape_overlay = overlay_hidden if rendering_mode == 'cytoscape' else dash.no_update
                    return result, plotly_overlay, cytoscape_overlay

                except Exception as e:
                    debugger.log_error({'error': str(e)}, DebuggerLogTypes.ERROR)
                    # Mark as done even on error so monitor can show status
                    session_info.initial_load_done = True
                    return dash.no_update, overlay_hidden, overlay_hidden
            else:
                debugger.log_warning({
                    'message': 'No log path available for session',
                    'session_id': session_id,
                    'available_sessions': get_active_session_ids()
                }, DebuggerLogTypes.WARNING)
                # IMPORTANT: Mark as done even without data so monitor panel shows proper status
                # The background monitor will load data and the monitor panel will show "new data available"
                session_info.initial_load_done = True
                debugger.log_info({'action': 'marked_as_initially_loaded', 'session_id': session_id}, DebuggerLogTypes.AUTO_LOAD)
                return dash.no_update, dash.no_update, dash.no_update

        # Use pre-loaded data from background thread
        session_info.initial_load_done = True
        session_info.last_displayed_mtime = loaded_data['mtime']

        log_collector = loaded_data['log_collector']
        graph_structure = loaded_data['graph_structure']
        log_file_path = loaded_data['log_file_path']

        num_nodes = loaded_data['nodes']
        num_edges = loaded_data['edges']

        debugger.log_info({'action': 'using_preloaded_data', 'num_nodes': num_nodes, 'num_edges': num_edges}, DebuggerLogTypes.AUTO_LOAD)

        # Return graph structure
        result = {
            'graph_data': {
                'nodes': graph_structure['nodes'],
                'edges': graph_structure['edges'],
                'agent': graph_structure['agent'],
                'log_file': Path(log_file_path).name if log_file_path else f'session_{session_id}'
            },
            'log_groups': {k: v for k, v in log_collector.log_groups.items()}
        }

        debugger.log_info({'action': 'initial_load_complete', 'num_log_groups': len(result['log_groups'])}, DebuggerLogTypes.AUTO_LOAD)
        # Hide loading overlay after loading completes
        plotly_overlay = overlay_hidden if rendering_mode == 'plotly' else dash.no_update
        cytoscape_overlay = overlay_hidden if rendering_mode == 'cytoscape' else dash.no_update
        return result, plotly_overlay, cytoscape_overlay

    # Add callback to handle session switches while on Log Debugging tab
    @app.app.callback(
        Output('log-data-store', 'data', allow_duplicate=True),
        [Input('current-session-store', 'data')],
        [State('log-data-store', 'data')],
        prevent_initial_call=True
    )
    def handle_session_switch(session_id, current_log_data):
        """Load appropriate log graph when switching sessions while on Log Debugging tab."""
        global _log_data_lock
        import dash

        if not session_id:
            return dash.no_update

        session_info = get_session_info(session_id)

        # Check if this session has been loaded before
        if not session_info.initial_load_done:
            # Never loaded this session - don't auto-load on session switch
            # Let the tab switch callback handle first-time load
            return dash.no_update

        debugger = get_debugger(session_id)
        debugger.log_info({'action': 'switching_to_session', 'session_id': session_id}, DebuggerLogTypes.SESSION_SWITCH)

        # Try to get pre-loaded data from background thread
        with _log_data_lock:
            loaded_data = session_info.loaded_log_data

        # Check if we have the last displayed data for this session
        last_mtime = session_info.last_displayed_mtime or 0

        # If we have newer data than what was last displayed, use the old mtime data
        # Otherwise load from file path if available
        if loaded_data and loaded_data['mtime'] == last_mtime:
            # Use the exact data that was last displayed
            log_collector = loaded_data['log_collector']
            graph_structure = loaded_data['graph_structure']
            log_file_path = loaded_data['log_file_path']

            debugger.log_info({'action': 'using_cached_data', 'session_id': session_id}, DebuggerLogTypes.SESSION_SWITCH)
        else:
            # Need to load the last displayed version
            log_file_path = session_info.log_file_path
            if not log_file_path:
                debugger.log_warning({'message': 'No log path for session', 'session_id': session_id}, DebuggerLogTypes.WARNING)
                return dash.no_update

            try:
                debugger.log_info({'action': 'loading_last_displayed_data', 'log_file_path': log_file_path}, DebuggerLogTypes.SESSION_SWITCH)
                log_collector = LogCollector.from_json_logs(log_file_path, json_file_pattern='*')
                graph_structure = log_collector.get_graph_structure()
            except Exception as e:
                debugger.log_error({'error': str(e)}, DebuggerLogTypes.ERROR)
                return dash.no_update

        # Return the graph structure
        result = {
            'graph_data': {
                'nodes': graph_structure['nodes'],
                'edges': graph_structure['edges'],
                'agent': graph_structure['agent'],
                'log_file': Path(log_file_path).name if log_file_path else f'session_{session_id}'
            },
            'log_groups': {k: v for k, v in log_collector.log_groups.items()}
        }

        debugger.log_info({'action': 'loaded_graph', 'num_log_groups': len(result['log_groups'])}, DebuggerLogTypes.SESSION_SWITCH)
        return result

    # Add callback to toggle monitor messages visibility
    @app.app.callback(
        [
            Output('main-panel-log-graph-monitor-messages', 'style'),
            Output('main-panel-log-graph-monitor-messages-toggle', 'children')
        ],
        [Input('main-panel-log-graph-monitor-messages-toggle', 'n_clicks')],
        prevent_initial_call=False
    )
    def toggle_monitor_messages(n_clicks):
        """Toggle visibility of monitor messages."""
        is_hidden = n_clicks % 2 == 1  # Odd clicks = hidden

        if is_hidden:
            return {'display': 'none'}, 'show'
        else:
            return {
                'fontSize': '9px', 'color': '#6E6E80', 'fontFamily': 'monospace',
                'maxHeight': '100px', 'overflowY': 'auto',
                'backgroundColor': 'rgba(0, 0, 0, 0.2)', 'padding': '6px',
                'borderRadius': '3px', 'marginBottom': '10px', 'lineHeight': '1.3'
            }, 'hide'

    # Add callback to update floating log monitor panel
    @app.app.callback(
        [
            Output('main-panel-log-graph-refresh-btn', 'style'),
            Output('main-panel-log-graph-monitor-status', 'children'),
            Output('main-panel-log-graph-monitor-stats', 'children'),
            Output('main-panel-log-graph-monitor-messages', 'children')
        ],
        [Input('response-poll-interval', 'n_intervals')],
        [State('current-session-store', 'data')],
        prevent_initial_call=False
    )
    def update_log_monitor_panel(n_intervals, session_id):
        """Update floating log monitor panel with real-time status."""
        global _log_data_lock
        import dash
        import datetime
        from dash import html

        # Helper function to get agent control and status prefix
        def get_agent_state_prefix(session_id):
            """Get agent control and status prefix for display."""
            if not session_id:
                return "[CTL:---] [Status:---]"

            session_info = get_session_info(session_id)
            control = session_info.agent_control
            status = session_info.agent_status

            # Map control values to display names
            control_map = {
                'stop': 'Stop',
                'pause': 'Pause',
                'continue': 'Continue',
                'step': 'Step',
                'stepbystep': 'Step'
            }
            control_display = control_map.get(control, 'Continue')

            # Map status values to display names
            status_map = {
                'running': 'Running',
                'paused': 'Paused',
                'stopped': 'Stopped',
                'not_started': 'NotStarted',
                'unknown': 'Unknown'
            }
            status_display = status_map.get(status, 'Unknown')

            return f"[CTL:{control_display}] [Status:{status_display}]"

        # Debug logging for first few calls
        debugger = _get_or_create_global_debugger()
        if n_intervals is not None and n_intervals < 5:
            debugger.log_debug({'call_number': n_intervals, 'session_id': session_id}, DebuggerLogTypes.MONITOR_PANEL)

        # Get monitor messages
        monitor_messages = get_monitor_messages()
        if monitor_messages:
            messages_div = html.Div([html.Div(msg, style={'marginBottom': '2px'}) for msg in monitor_messages[-10:]])
        else:
            messages_div = "No messages yet..."

        if not session_id:
            gray_button = {
                'width': '100%', 'padding': '8px 12px',
                'backgroundColor': '#4A4A5A', 'color': '#8E8EA0',
                'border': 'none', 'borderRadius': '4px',
                'cursor': 'not-allowed', 'fontSize': '12px',
                'fontWeight': '500', 'transition': 'all 0.2s'
            }
            # Only log once to avoid console flooding (use debug level to avoid spam)
            debugger.log_debug('No session_id, returning default state', DebuggerLogTypes.MONITOR_PANEL)
            return gray_button, f"{get_agent_state_prefix(None)} ⏸️ No active session", "Switch to a session tab", messages_div

        session_info = get_session_info(session_id)

        # Check if initial load has been done
        if not session_info.initial_load_done:
            gray_button = {
                'width': '100%', 'padding': '8px 12px',
                'backgroundColor': '#4A4A5A', 'color': '#8E8EA0',
                'border': 'none', 'borderRadius': '4px',
                'cursor': 'not-allowed', 'fontSize': '12px',
                'fontWeight': '500', 'transition': 'all 0.2s'
            }
            # Only log once per session to avoid console flooding
            if 'waiting_first_load' not in session_info.logged_waiting_messages:
                session_debugger = get_debugger(session_id)
                session_debugger.log_debug({'session_id': session_id, 'status': 'waiting_for_first_load'}, DebuggerLogTypes.MONITOR_PANEL)
                session_info.logged_waiting_messages.add('waiting_first_load')
            return gray_button, f"{get_agent_state_prefix(session_id)} ⏳ Waiting for first load...", f"Session: {session_id[:20]}...", messages_div

        # Get log file path for this session
        log_file_path = session_info.log_file_path
        if not log_file_path:
            gray_button = {
                'width': '100%', 'padding': '8px 12px',
                'backgroundColor': '#4A4A5A', 'color': '#8E8EA0',
                'border': 'none', 'borderRadius': '4px',
                'cursor': 'not-allowed', 'fontSize': '12px',
                'fontWeight': '500', 'transition': 'all 0.2s'
            }
            # Only log once per session to avoid console flooding
            if 'no_log_path' not in session_info.logged_waiting_messages:
                session_debugger = get_debugger(session_id)
                session_debugger.log_debug({
                    'session_id': session_id,
                    'status': 'no_log_path_yet',
                    'available_sessions': get_active_session_ids()
                }, DebuggerLogTypes.MONITOR_PANEL)
                session_info.logged_waiting_messages.add('no_log_path')
            return gray_button, f"{get_agent_state_prefix(session_id)} ❌ No log path", f"Session: {session_id[:20]}...", messages_div

        # Check if we have NEW loaded log data for this session
        with _log_data_lock:
            loaded_data = session_info.loaded_log_data

        if loaded_data:
            # Check if this data is newer than what's currently displayed
            current_mtime = loaded_data.get('mtime', 0)
            last_displayed = session_info.last_displayed_mtime or 0

            num_nodes = loaded_data.get('nodes', 0)
            num_edges = loaded_data.get('edges', 0)
            load_timestamp = loaded_data.get('timestamp', 0)

            # Format timestamps
            current_time_str = datetime.datetime.fromtimestamp(current_mtime).strftime('%H:%M:%S') if current_mtime else 'N/A'
            last_displayed_str = datetime.datetime.fromtimestamp(last_displayed).strftime('%H:%M:%S') if last_displayed else 'N/A'
            age_seconds = time.time() - load_timestamp if load_timestamp else 0

            # Build stats text
            stats_lines = [
                f"Nodes: {num_nodes} | Edges: {num_edges}",
                f"File: {current_time_str}",
                f"Displayed: {last_displayed_str}",
                f"Age: {age_seconds:.0f}s"
            ]
            stats_text = html.Div([html.Div(line, style={'marginBottom': '2px'}) for line in stats_lines])

            # Debug output (only log when there's a difference or on first few calls)
            session_debugger = get_debugger(session_id)
            if current_mtime != last_displayed or (n_intervals is not None and n_intervals < 3):
                session_debugger.log_debug({
                    'session_id': session_id,
                    'current_mtime': current_mtime,
                    'last_displayed': last_displayed,
                    'newer': current_mtime > last_displayed,
                    'num_nodes': num_nodes,
                    'num_edges': num_edges,
                    'age_seconds': int(age_seconds)
                }, DebuggerLogTypes.MONITOR_PANEL)

            if current_mtime > last_displayed:
                # New data available!
                session_debugger.log_info({
                    'status': 'new_data_available',
                    'session_id': session_id,
                    'num_nodes': num_nodes,
                    'num_edges': num_edges
                }, DebuggerLogTypes.MONITOR_PANEL)

                # Enable button with green style
                button_style = {
                    'width': '100%',
                    'padding': '8px 12px',
                    'backgroundColor': '#19C37D',
                    'color': '#ECECF1',
                    'border': 'none',
                    'borderRadius': '4px',
                    'cursor': 'pointer',
                    'fontSize': '12px',
                    'fontWeight': '500',
                    'transition': 'all 0.2s',
                    'boxShadow': '0 0 10px rgba(25, 195, 125, 0.3)'
                }
                status_text = f"{get_agent_state_prefix(session_id)} ✅ New data available!"
                return button_style, status_text, stats_text, messages_div
            else:
                # Up to date - gray button
                button_style = {
                    'width': '100%',
                    'padding': '8px 12px',
                    'backgroundColor': '#4A4A5A',
                    'color': '#8E8EA0',
                    'border': 'none',
                    'borderRadius': '4px',
                    'cursor': 'not-allowed',
                    'fontSize': '12px',
                    'fontWeight': '500',
                    'transition': 'all 0.2s'
                }
                status_text = f"{get_agent_state_prefix(session_id)} Up to date"
                return button_style, status_text, stats_text, messages_div

        # No loaded data yet - monitor is working but hasn't loaded this session
        # Only log once per session to avoid console flooding
        if 'no_loaded_data' not in session_info.logged_waiting_messages:
            session_debugger = get_debugger(session_id)
            session_debugger.log_debug({
                'session_id': session_id,
                'status': 'no_loaded_data_yet'
            }, DebuggerLogTypes.MONITOR_PANEL)
            session_info.logged_waiting_messages.add('no_loaded_data')
        return (
            {
                'width': '100%', 'padding': '8px 12px',
                'backgroundColor': '#4A4A5A', 'color': '#8E8EA0',
                'border': 'none', 'borderRadius': '4px',
                'cursor': 'not-allowed', 'fontSize': '12px',
                'fontWeight': '500', 'transition': 'all 0.2s'
            },
            f"{get_agent_state_prefix(session_id)} ⏳ Monitor loading...",
            f"Path: {log_file_path[:30]}...",
            messages_div
        )

    # Add callback to refresh log graph when button clicked
    @app.app.callback(
        [
            Output('log-data-store', 'data', allow_duplicate=True),
            Output('main-panel-log-graph-plotly-loading-overlay', 'style', allow_duplicate=True),
            Output('main-panel-log-graph-cytoscape-loading-overlay', 'style', allow_duplicate=True)
        ],
        [Input('main-panel-log-graph-refresh-btn', 'n_clicks')],
        [
            State('log-data-store', 'data'),
            State('current-session-store', 'data'),
            State('main-panel-log-graph-rendering-mode', 'value')
        ],
        prevent_initial_call=True
    )
    def refresh_log_graph_on_button_click(refresh_clicks, current_data, session_id, rendering_mode):
        """Refresh log graph when user clicks the refresh button."""
        global _log_data_lock
        import dash

        # Define styles for hiding overlay
        overlay_hidden = {
            'position': 'absolute', 'top': '0', 'left': '0', 'right': '0', 'bottom': '0',
            'backgroundColor': 'rgba(44, 44, 44, 0.95)', 'display': 'none',
            'alignItems': 'center', 'justifyContent': 'center', 'zIndex': '2000'
        }

        if not refresh_clicks:
            return dash.no_update, dash.no_update, dash.no_update

        if not session_id:
            return dash.no_update, dash.no_update, dash.no_update

        debugger = get_debugger(session_id)
        debugger.log_info({'action': 'refresh_button_clicked', 'session_id': session_id}, DebuggerLogTypes.REFRESH)
        session_info = get_session_info(session_id)

        # Get the pre-loaded log data from background thread
        with _log_data_lock:
            loaded_data = session_info.loaded_log_data

        if not loaded_data:
            debugger.log_warning({'message': 'No loaded data available', 'session_id': session_id}, DebuggerLogTypes.WARNING)
            return (current_data if current_data else dash.no_update), dash.no_update, dash.no_update

        # Track the mtime of this data so we know it's been displayed
        session_info.last_displayed_mtime = loaded_data['mtime']

        # Use the pre-loaded data (already has graph_structure computed)
        log_collector = loaded_data['log_collector']
        graph_structure = loaded_data['graph_structure']
        log_file_path = loaded_data['log_file_path']

        num_nodes = loaded_data['nodes']
        num_edges = loaded_data['edges']

        debugger.log_info({'action': 'using_preloaded_data', 'num_nodes': num_nodes, 'num_edges': num_edges}, DebuggerLogTypes.REFRESH)

        # Return graph structure
        result = {
            'graph_data': {
                'nodes': graph_structure['nodes'],
                'edges': graph_structure['edges'],
                'agent': graph_structure['agent'],
                'log_file': Path(log_file_path).name if log_file_path else f'session_{session_id}'
            },
            'log_groups': {k: v for k, v in log_collector.log_groups.items()}
        }

        debugger.log_info({'action': 'refreshed_graph', 'num_log_groups': len(result['log_groups'])}, DebuggerLogTypes.REFRESH)
        # Hide loading overlay after refresh completes
        plotly_overlay = overlay_hidden if rendering_mode == 'plotly' else dash.no_update
        cytoscape_overlay = overlay_hidden if rendering_mode == 'cytoscape' else dash.no_update
        return result, plotly_overlay, cytoscape_overlay

    # Run the app
    debugger = _get_or_create_global_debugger()
    startup_info = {
        'title': 'WEB AGENT DEBUGGER - Queue-Based UI',
        'architecture': {
            'queue_based_communication': 'Uses StorageBasedQueueService',
            'decoupled_design': 'UI and agent run in separate processes',
            'persistent_queues': 'File-based queues survive restarts',
            'real_agent': 'Full grocery planning agent with web automation',
            'log_visualization': 'Execution graph from JSON logs'
        },
        'queue_configuration': {
            'queue_base_path': '_runtime/queue_storage/',
            'auto_detect': 'Latest timestamp folder',
            'input_queue': INPUT_QUEUE_ID,
            'response_queue': RESPONSE_QUEUE_ID,
            'client_control_queue': CLIENT_CONTROL_QUEUE_ID
        },
        'setup': [
            'Start the agent service: python web_agent_service.py',
            'Start this debugger UI: python agent_debugger.py',
            'Navigate to http://localhost:8050'
        ],
        'features': [
            'Asynchronous communication through queues',
            'Real web agent with browser automation',
            'Execution graph visualization',
            'Detailed log inspection',
            'Multi-process architecture'
        ]
    }
    debugger.log_info(startup_info, DebuggerLogTypes.DEBUGGER_STARTUP)

    # Start background log monitoring thread
    start_log_monitor()

    # Disable Flask/Werkzeug request logging to reduce console spam
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)

    app.run()


if __name__ == '__main__':
    main()
