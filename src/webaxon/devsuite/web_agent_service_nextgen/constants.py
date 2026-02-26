"""Constants for web_agent_service_nextgen."""
from pathlib import Path

# Default workspace directory name, relative to the web_agent_service_nextgen package.
# Both the service and CLI use this as the default testcase_root.
DEFAULT_WORKSPACE_DIR = '_workspace'

# Knowledge store directory name, relative to the workspace (testcase_root).
# Static data — should NOT live under _runtime.
KNOWLEDGE_STORE_DIR = '_knowledge_store'

# Resolved default workspace path (absolute)
_PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_WORKSPACE_PATH = _PACKAGE_DIR / DEFAULT_WORKSPACE_DIR
