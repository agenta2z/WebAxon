"""Thread-safe session lifecycle management for webaxon

Extends the generic SessionManager with WebAgent-specific session creation,
directory setup, and cleanup logic.
"""
import time
from typing import Optional, Any

from attr import attrs, attrib
from rich_python_utils.io_utils.json_io import JsonLogger
from rich_python_utils.path_utils.common import sanitize_filename
from rich_python_utils.service_utils.session_management import (
    SessionLogger,
    SessionManager,
)
from webaxon.devsuite.common import DebuggerLogTypes
from webaxon.devsuite.constants import (
    FOLDER_NAME_SERVICE_LOGS,
    FOLDER_NAME_AGENT_LOGS,
    LOG_FILE_EXT,
    SESSION_LOG_FILENAME,
)

from ..core.config import ServiceConfig
from .agent_session import AgentSession
from .agent_session_info import AgentSessionInfo


def _default_parts_file_namer(obj) -> str:
    """Extract log type from log_data dict for human-readable filenames."""
    if not isinstance(obj, dict):
        return None
    log_type = obj.get('type', '')
    return sanitize_filename(str(log_type)) if log_type else None


@attrs(slots=False)
class AgentSessionManager(SessionManager):
    """Manages agent sessions with thread-safe operations.

    Extends the generic SessionManager with WebAgent-specific:
    - Directory structure (agent_logs, service_logs)
    - JsonLogger wiring with parts extraction
    - Agent/thread/interactive runtime field routing
    - DebuggerLogTypes for log type strings
    """
    _config: ServiceConfig = attrib(kw_only=True)
    _queue_service: Any = attrib(kw_only=True)

    _RUNTIME_FIELDS = frozenset({'agent', 'agent_thread', 'interactive'})

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._session_idle_timeout = self._config.session_idle_timeout

    # ------------------------------------------------------------------
    # Log type overrides
    # ------------------------------------------------------------------

    def _get_log_type_session_management(self) -> str:
        return DebuggerLogTypes.SESSION_MANAGEMENT

    def _get_log_type_session_cleanup(self) -> str:
        return DebuggerLogTypes.SESSION_CLEANUP

    # ------------------------------------------------------------------
    # Session creation (abstract method implementation)
    # ------------------------------------------------------------------

    def _create_session(self, session_id: str, session_type: str, **kwargs) -> AgentSession:
        """Create an AgentSession with full logging infrastructure."""
        current_time = time.time()

        # 1. Create session logger (structured output: turns, manifest)
        agent_logs_dir = kwargs.get('base_log_dir') or (self._service_log_dir / FOLDER_NAME_AGENT_LOGS)
        session_logger = SessionLogger(
            base_log_dir=agent_logs_dir,
            session_id=session_id,
            session_type=session_type,
        )

        # Add turn-aware JsonLogger (needs session_dir created above)
        session_logger.add_turn_aware_logger(
            JsonLogger(
                file_path=str(session_logger.session_dir / SESSION_LOG_FILENAME),
                append=True,
                parts_key_path_root='item',
                artifacts_as_parts=True,
            ),
        )

        # 2. Create log directories (same timestamped name as session_logger)
        session_dir_name = session_logger.session_dir.name

        session_service_log_dir = self._service_log_dir / FOLDER_NAME_SERVICE_LOGS / session_dir_name
        session_service_log_dir.mkdir(parents=True, exist_ok=True)

        # 3. Create pure data info
        info = AgentSessionInfo(
            session_id=session_id,
            created_at=current_time,
            last_active=current_time,
            session_type=session_type,
            initialized=False,
            template_version="",
        )

        # 4. Create AgentSession — IS the Debuggable (no standalone Debugger)
        session = AgentSession(
            id=f'agent_session_{session_id}',
            log_name=f'AgentSession_{session_id}',
            logger=[
                print,
                JsonLogger(
                    file_path=str(session_service_log_dir / f'service_{session_id}{LOG_FILE_EXT}'),
                    append=True,
                    space_ext_mode='move',
                    parts_key_path_root='item',
                ),
            ],
            debug_mode=self._config.debug_mode_service,
            log_time=True,
            always_add_logging_based_logger=False,
            info=info,
            session_logger=session_logger,
        )

        return session

    # ------------------------------------------------------------------
    # Cleanup hook
    # ------------------------------------------------------------------

    def _on_before_cleanup(self, session: AgentSession) -> None:
        """WebAgent-specific cleanup: log thread status, clear runtime refs."""
        if session.agent_thread and session.agent_thread.is_alive():
            session.log_info({
                'type': DebuggerLogTypes.SESSION_CLEANUP,
                'message': f'Agent thread still running for session {session.session_id}, marking for cleanup',
            })

        session.interactive = None
        session.agent = None

    # ------------------------------------------------------------------
    # Backward-compat get_or_create signature
    # ------------------------------------------------------------------

    def get_or_create(
        self,
        session_id: str,
        agent_type: Optional[str] = None,
        create_immediately: bool = False,
        **kwargs,
    ) -> AgentSession:
        """Get existing session or create new one (thread-safe).

        Backward-compatible signature: ``agent_type`` maps to ``session_type``.

        Args:
            session_id: Unique identifier for the session.
            agent_type: Type of agent to create (if creating new session).
            create_immediately: If True, create agent immediately (default: False).
            **kwargs: Forwarded to ``_create_session()``.  Supports
                ``base_log_dir`` to redirect agent logs to a custom directory.

        Returns:
            AgentSession for the session.
        """
        session_type = agent_type
        if session_type is None:
            session_type = self._config.default_agent_type

        return super().get_or_create(session_id, session_type=session_type, **kwargs)
