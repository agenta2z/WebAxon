"""Session state management for agent debugger.

This module provides thread-safe session management with centralized state tracking.
"""
import threading
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Any

from science_modeling_tools.ui.dash_interactive.utils.log_collector import LogCollector
from rich_python_utils.common_objects.debuggable import Debugger
from rich_python_utils.datetime_utils.common import timestamp
from rich_python_utils.io_utils.json_io import write_json
from rich_python_utils.service_utils.session_management import SessionInfo
from webaxon.devsuite.constants import RUNTIME_DIR, FOLDER_NAME_DEBUGGER_LOGS, AGENT_TYPE_DEFAULT
from webaxon.devsuite import config


@dataclass
class DebuggerSessionInfo(SessionInfo):
    """Information about a debugger session (client-side).

    Extends SessionInfo with debugger-specific fields for UI state and log tracking.
    """
    # Log tracking
    log_file_path: Optional[str] = None
    log_collector: Optional[LogCollector] = None

    # Agent control and status
    agent_control: str = 'continue'
    agent_status: str = 'not_started'
    control_pending: bool = False
    status_messages: list = field(default_factory=list)

    # UI state tracking
    loaded_log_data: Optional[Dict] = None
    initial_load_done: bool = False
    last_displayed_mtime: Optional[float] = None
    logged_waiting_messages: set = field(default_factory=set)

    # Session debugger instance
    debugger: Optional[Debugger] = None
    
    # Action Tester fields
    browser_session: Optional[Any] = None
    active_test_id: Optional[str] = None


class SessionManager:
    """Manages session state with thread-safe operations."""
    
    def __init__(self, base_log_dir: Optional[Path] = None):
        """Initialize the session manager."""
        self._sessions: Dict[str, DebuggerSessionInfo] = {}
        self._lock = threading.RLock()
        self._base_log_dir = base_log_dir or (Path.cwd() / RUNTIME_DIR)
        self._log_groups_cache: Dict[tuple, Any] = {}
    
    def get_or_create(self, session_id: str) -> DebuggerSessionInfo:
        """Get existing session or create new one (thread-safe)."""
        with self._lock:
            if session_id not in self._sessions:
                debugger_log_dir = self._base_log_dir / FOLDER_NAME_DEBUGGER_LOGS / session_id
                debugger_log_dir.mkdir(parents=True, exist_ok=True)

                session_debugger = Debugger(
                    id=f'debugger_{session_id}',
                    log_name=f'AgentDebugger_{session_id}',
                    logger=[
                        print,
                        partial(write_json, file_path=str(debugger_log_dir / FOLDER_NAME_DEBUGGER_LOGS), append=True)
                    ],
                    debug_mode=config.DEBUG_MODE_DEBUGGER,
                    log_time=True,
                    always_add_logging_based_logger=False,
                    # Rate limiting for console output
                    console_display_rate_limit=config.CONSOLE_DISPLAY_RATE_LIMIT,
                    enable_console_update=config.ENABLE_CONSOLE_UPDATE
                )

                self._sessions[session_id] = DebuggerSessionInfo(
                    session_id=session_id,
                    created_at=timestamp(),
                    last_active=timestamp(),
                    session_type=AGENT_TYPE_DEFAULT,
                    debugger=session_debugger
                )
            
            return self._sessions[session_id]
    
    def get(self, session_id: str) -> Optional[DebuggerSessionInfo]:
        """Get session info if it exists (thread-safe)."""
        with self._lock:
            return self._sessions.get(session_id)
    
    def update_session(self, session_id: str, **updates) -> None:
        """Update session fields (thread-safe)."""
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(f"Session {session_id} does not exist")
            
            session = self._sessions[session_id]
            for key, value in updates.items():
                if hasattr(session, key):
                    setattr(session, key, value)
                else:
                    raise AttributeError(f"DebuggerSessionInfo has no attribute '{key}'")
            
            session.last_active = timestamp()
    
    def delete_session(self, session_id: str) -> None:
        """Delete session and cleanup resources (thread-safe)."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                
                if session.log_collector:
                    session.log_collector.clear()
                
                del self._sessions[session_id]
                
                keys_to_delete = [key for key in self._log_groups_cache.keys() if key[0] == session_id]
                for key in keys_to_delete:
                    del self._log_groups_cache[key]
    
    def get_active_ids(self) -> List[str]:
        """Get list of all active session IDs (thread-safe)."""
        with self._lock:
            return list(self._sessions.keys())
    
    def cleanup_inactive(self, active_ids: List[str]) -> None:
        """Remove sessions not in the active list (thread-safe)."""
        with self._lock:
            active_set = set(active_ids)
            sessions_to_remove = [sid for sid in self._sessions.keys() if sid not in active_set]
            
            for session_id in sessions_to_remove:
                self.delete_session(session_id)
    
    def get_log_groups_cache(self) -> Dict[tuple, Any]:
        """Get the log groups cache (for backward compatibility)."""
        with self._lock:
            return self._log_groups_cache
