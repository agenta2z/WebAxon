"""
Constants for the Web Agent framework.

This module contains shared constants used across web agent services and debuggers.
"""

# Queue configuration
INPUT_QUEUE_ID = 'user_input'
RESPONSE_QUEUE_ID = 'agent_response'
CLIENT_CONTROL_QUEUE_ID = 'client_control'  # Server → Client: control signals (log paths, status, etc.)
SERVER_CONTROL_QUEUE_ID = 'server_control'  # Client → Server: control signals (session sync, settings, etc.)

# Runtime directory names
RUNTIME_DIR = '_runtime'
QUEUE_STORAGE_DIR = 'queue_storage'
LOGS_DIR = 'agent_logs'

# Folder names for different log types
FOLDER_NAME_SERVICE_LOGS = 'service_logs'
FOLDER_NAME_DEBUGGER_LOGS = 'debugger_logs'
FOLDER_NAME_AGENT_LOGS = 'agent_logs'
FOLDER_NAME_QUEUE_STORAGE = 'queue_storage'

# Polling intervals (milliseconds)
QUEUE_POLL_INTERVAL_MS = 500
LOG_REFRESH_INTERVAL_MS = 1000

# Special message markers
SPECIAL_MESSAGE_WAITING_FOR_RESPONSE = "__WAITING_FOR_RESPONSE__"

# Agent types
AGENT_TYPE_DEFAULT = 'DefaultAgent'
AGENT_TYPE_MOCK_CLARIFICATION = 'MockClarificationAgent'

# Log file naming
LOG_FILE_EXT = '.jsonl'
MANIFEST_FILENAME = 'manifest.json'
SESSION_LOG_FILENAME = 'session.jsonl'
ARTIFACTS_DIR = 'artifacts'
OVERFLOW_DIR = 'overflow'

