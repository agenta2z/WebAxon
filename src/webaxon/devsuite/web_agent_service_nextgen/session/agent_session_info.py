"""Pure data container for agent session information.

This module provides the AgentSessionInfo dataclass that holds only data fields
for an agent session. Runtime objects (agent, thread, interactive) and logging
(debugger, session_logger) live on AgentSession instead.
"""
from dataclasses import dataclass
from typing import Optional

from rich_python_utils.service_utils.session_management import SessionInfo


@dataclass
class AgentSessionInfo(SessionInfo):
    """Pure data for an agent session. No runtime objects or logging.

    Extends SessionInfo with service-specific data fields.
    Runtime state (agent, thread, interactive) and logging (debugger,
    session_logger) are managed by AgentSession.

    Inherited from SessionInfo:
        session_id: Unique identifier for the session
        created_at: Timestamp when session was created
        last_active: Timestamp of last activity
        session_type: Type of session (e.g., 'DefaultAgent')
        initialized: True once agent is created and locked

    Attributes:
        last_agent_status: Last known agent status for change detection
        template_version: Template version for this session
    """
    # Status tracking
    last_agent_status: Optional[str] = None

    # Template versioning
    template_version: str = ""
