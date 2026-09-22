"""
Web Agent Framework - Common utilities and constants.

This package provides shared functionality for web agent services and debuggers,
including queue management, path utilities, and constants.
"""

from . import config
from .common import (
    find_latest_queue_path,
    get_log_dir_path,
    get_queue_base_path,
    get_queue_service,
)
from .config import OPTION_NEW_AGENT_ON_FIRST_SUBMISSION
from .constants import (
    AGENT_TYPE_DEFAULT,
    AGENT_TYPE_MOCK_CLARIFICATION,
    CLIENT_CONTROL_QUEUE_ID,
    INPUT_QUEUE_ID,
    LOG_REFRESH_INTERVAL_MS,
    LOGS_DIR,
    QUEUE_POLL_INTERVAL_MS,
    QUEUE_STORAGE_DIR,
    RESPONSE_QUEUE_ID,
    RUNTIME_DIR,
    SERVER_CONTROL_QUEUE_ID,
    SPECIAL_MESSAGE_WAITING_FOR_RESPONSE,
)

__all__ = [
    # Constants
    "INPUT_QUEUE_ID",
    "RESPONSE_QUEUE_ID",
    "CLIENT_CONTROL_QUEUE_ID",
    "SERVER_CONTROL_QUEUE_ID",
    "RUNTIME_DIR",
    "QUEUE_STORAGE_DIR",
    "LOGS_DIR",
    "QUEUE_POLL_INTERVAL_MS",
    "LOG_REFRESH_INTERVAL_MS",
    "SPECIAL_MESSAGE_WAITING_FOR_RESPONSE",
    "AGENT_TYPE_DEFAULT",
    "AGENT_TYPE_MOCK_CLARIFICATION",
    # Configuration
    "config",
    "OPTION_NEW_AGENT_ON_FIRST_SUBMISSION",
    # Functions
    "get_queue_base_path",
    "find_latest_queue_path",
    "get_queue_service",
    "get_log_dir_path",
]
