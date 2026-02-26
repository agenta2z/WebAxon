"""
Common utilities for the Web Agent framework.

This module provides shared functionality for web agent services and debuggers,
including queue service initialization and path management.
"""
from enum import Enum
from pathlib import Path
from typing import Optional

from rich_python_utils.service_utils.queue_service.storage_based_queue_service import StorageBasedQueueService

from .constants import (
    INPUT_QUEUE_ID,
    RESPONSE_QUEUE_ID,
    CLIENT_CONTROL_QUEUE_ID,
    RUNTIME_DIR,
    QUEUE_STORAGE_DIR
)


# =============================================================================
# Log Type Enums
# =============================================================================

class ServiceLogTypes(str, Enum):
    """
    Log types for the Web Agent Service.

    These categorize different types of log messages emitted by the service,
    making it easier to filter and analyze service behavior.
    """
    # Service lifecycle
    SERVICE_STARTUP = 'ServiceStartup'
    SERVICE_STATUS = 'ServiceStatus'
    SERVICE_SHUTDOWN = 'ServiceShutdown'

    # Request processing
    INPUT_RECEIVED = 'InputReceived'
    AGENT_PROCESSING = 'AgentProcessing'
    AGENT_COMPLETED = 'AgentCompleted'

    # Error handling
    AGENT_EXECUTION_ERROR = 'AgentExecutionError'
    UNEXPECTED_ERROR = 'UnexpectedError'

    # System events
    SIGNAL_HANDLER = 'SignalHandler'
    KEYBOARD_INTERRUPT = 'KeyboardInterrupt'


class DebuggerLogTypes(str, Enum):
    """
    Log types for the Agent Debugger UI and Web Agent Service.

    These categorize different types of log messages emitted by the debugger and service,
    making it easier to filter and analyze behavior.
    """
    # Queue and communication
    QUEUE_OPERATION = 'QueueOperation'
    CONTROL_MESSAGE = 'ControlMessage'

    # Debugging information
    DEBUG = 'Debug'

    # Log monitoring (background thread)
    LOG_MONITOR = 'LogMonitor'

    # UI operations (debugger)
    AUTO_LOAD = 'AutoLoad'
    SESSION_SWITCH = 'SessionSwitch'
    MONITOR_PANEL = 'MonitorPanel'
    REFRESH = 'Refresh'

    # Session management (service and debugger)
    SESSION_MANAGEMENT = 'SessionManagement'
    SESSION_SYNC = 'SessionSync'
    SESSION_CLEANUP = 'SessionCleanup'

    # Agent lifecycle (service)
    AGENT_LIFECYCLE = 'AgentLifecycle'

    # Agent control
    AGENT_CONTROL = 'AgentControl'
    CONTROL_ACK = 'ControlAck'

    # Service lifecycle (service)
    SERVICE_STARTUP = 'ServiceStartup'
    SERVICE_SHUTDOWN = 'ServiceShutdown'

    # System events
    WARNING = 'Warning'
    ERROR = 'Error'
    DEBUGGER_STARTUP = 'DebuggerStartup'



def get_queue_base_path(testcase_root: Path) -> Path:
    """
    Get the base path for queue storage.

    Args:
        testcase_root: Root directory of the test case

    Returns:
        Path to the queue storage base directory
    """
    return testcase_root / RUNTIME_DIR / QUEUE_STORAGE_DIR


def find_latest_queue_path(queue_base_path: Path) -> Optional[Path]:
    """
    Find the queue path with the maximum timestamp under queue_storage.

    Args:
        queue_base_path: Base path for queue storage

    Returns:
        Path to the latest queue storage directory, or None if not found
    """
    if not queue_base_path.exists():
        return None

    # Get all timestamp directories
    timestamp_dirs = [d for d in queue_base_path.iterdir() if d.is_dir()]

    if not timestamp_dirs:
        return None

    # Return the directory with the maximum (latest) timestamp
    return max(timestamp_dirs, key=lambda d: d.name)


def get_queue_service(
    testcase_root: Path,
    existing_service: Optional[StorageBasedQueueService] = None,
    log_on_change: bool = False
) -> Optional[StorageBasedQueueService]:
    """
    Get the queue service, either by returning the existing one or creating a new one.

    This function intelligently handles queue service lifecycle:
    - If no existing service, creates a new one
    - If existing service path matches latest path, returns existing service
    - If path changed (agent restart), closes old service and creates new one

    Args:
        testcase_root: Root directory of the test case
        existing_service: Optional existing queue service to check against
        log_on_change: If True, log when queue path changes or is first initialized

    Returns:
        StorageBasedQueueService instance, or None if no queue storage found
    """
    from rich_python_utils.datetime_utils.common import timestamp
    from rich_python_utils.console_utils import hprint_message

    queue_base_path = get_queue_base_path(testcase_root)

    # Find the latest queue path
    queue_root_path = find_latest_queue_path(queue_base_path)

    if queue_root_path is None:
        # No queue found
        if existing_service is None and log_on_change:
            # Use message tracking to prevent console flooding
            # In terminals with cursor control support, message updates in place
            # In terminals without support (like PyCharm), message prints normally
            hprint_message(
                "Queue Status",
                f"No queue storage found under {queue_base_path}",
                message_id="queue_wait",
                update_previous=True
            )
            hprint_message(
                "Action Required",
                "Please start the web_agent_service.py first!",
                message_id="queue_wait_action",
                update_previous=True
            )
        return None

    # Check if we can reuse existing service
    if existing_service is not None:
        existing_path = existing_service.root_path
        new_path = str(queue_root_path)

        if existing_path == new_path:
            # Same path - return existing service
            return existing_service
        else:
            # Path changed - close old service and create new one
            if log_on_change:
                print(f"\n[{timestamp()}] Queue path changed - agent service restarted!")
                print(f"  Old path: {existing_path}")
                print(f"  New path: {new_path}")

            try:
                existing_service.close()
            except:
                pass

    # Create new queue service
    queue_service = StorageBasedQueueService(root_path=str(queue_root_path))

    # Create or ensure queues exist
    queue_service.create_queue(INPUT_QUEUE_ID)
    queue_service.create_queue(RESPONSE_QUEUE_ID)
    queue_service.create_queue(CLIENT_CONTROL_QUEUE_ID)

    # Log initialization if requested and this is first time
    if log_on_change and existing_service is None:
        print(f"[{timestamp()}] Connected to queue: {queue_service.root_path}")
    elif log_on_change and existing_service is not None:
        print(f"[{timestamp()}] Connected to new queue")

    return queue_service


def get_log_dir_path(testcase_root: Path, log_name: str) -> Path:
    """
    Get the path for a log directory.

    Args:
        testcase_root: Root directory of the test case
        log_name: Name of the log directory (e.g., 'web_agent_20251106_143052.json')

    Returns:
        Full path to the log directory
    """
    from .constants import LOGS_DIR
    return testcase_root / RUNTIME_DIR / LOGS_DIR / log_name
