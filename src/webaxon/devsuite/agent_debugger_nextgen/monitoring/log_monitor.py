"""Background log file monitoring for agent debugger.

This module provides a background service that monitors log files
and loads log data asynchronously.
"""
import threading
import time
from pathlib import Path
from typing import List, Optional

from agent_foundation.ui.dash_interactive.utils.log_collector import LogCollector


class LogMonitor:
    """Background service for monitoring log files.
    
    This service runs in a background thread and monitors log file
    changes, loading log data when files are updated.
    """
    
    def __init__(self, session_manager, debugger, check_interval: float = 2.0, max_messages: int = 10):
        """Initialize the log monitor.

        Args:
            session_manager: SessionManager instance
            debugger: Debugger instance for rate-limited console output
            check_interval: Seconds between log file checks
            max_messages: Maximum number of monitor messages to keep
        """
        self._session_manager = session_manager
        self._debugger = debugger
        self._check_interval = check_interval
        self._max_messages = max_messages
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._messages: List[str] = []
        self._data_lock = threading.Lock()
    
    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._thread is None or not self._thread.is_alive():
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
            self._add_message("Monitor started")
    
    def stop(self) -> None:
        """Stop the background monitoring thread."""
        self._running = False
        self._add_message("Monitor stopping...")
    
    def get_recent_messages(self) -> List[str]:
        """Get recent monitor messages (thread-safe).
        
        Returns:
            List of recent monitor messages
        """
        with self._lock:
            return list(self._messages)
    
    def _add_message(self, message: str) -> None:
        """Add a monitor message (thread-safe).
        
        Args:
            message: Message to add
        """
        with self._lock:
            timestamp = time.strftime('%H:%M:%S')
            self._messages.append(f"[{timestamp}] {message}")
            if len(self._messages) > self._max_messages:
                self._messages.pop(0)
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop (runs in background thread)."""
        while self._running:
            try:
                # Get all sessions with log paths
                session_ids = self._session_manager.get_active_ids()
                sessions_with_logs = []
                
                for session_id in session_ids:
                    session = self._session_manager.get(session_id)
                    if session and session.log_file_path:
                        sessions_with_logs.append((session_id, session.log_file_path))
                
                if sessions_with_logs:
                    msg = f"Checking {len(sessions_with_logs)} session(s)"
                    self._debugger.log_info(msg, log_type='MonitorStatus')
                    self._add_message(msg)
                
                for session_id, log_file_path in sessions_with_logs:
                    self._check_session_logs(session_id, log_file_path)
                
            except Exception as e:
                self._add_message(f"ERROR: {str(e)[:30]}")
            
            time.sleep(self._check_interval)
    
    def _check_session_logs(self, session_id: str, log_file_path: str) -> None:
        """Check and load logs for a specific session.
        
        Args:
            session_id: Session identifier
            log_file_path: Path to log files
        """
        try:
            log_path = Path(log_file_path)
            if not log_path.exists():
                return
            
            # Find newest file modification time
            all_files = [f for f in log_path.rglob('*') if f.is_file()]
            if not all_files:
                return
            
            newest_mtime = max(f.stat().st_mtime for f in all_files)
            
            # Check if we need to reload
            session = self._session_manager.get(session_id)
            if not session:
                return
            
            existing_data = session.loaded_log_data
            existing_mtime = existing_data.get('mtime', 0) if existing_data else 0
            
            if existing_mtime >= newest_mtime:
                return
            
            # Load log data
            self._add_message(f"{session_id[:20]}: loading...")
            log_collector = LogCollector.from_json_logs(log_file_path, json_file_pattern='*')
            graph_structure = log_collector.get_graph_structure()
            
            num_nodes = len(graph_structure['nodes'])
            num_edges = len(graph_structure['edges'])
            
            # Store loaded data
            with self._data_lock:
                self._session_manager.update_session(
                    session_id,
                    loaded_log_data={
                        'log_collector': log_collector,
                        'graph_structure': graph_structure,
                        'nodes': num_nodes,
                        'edges': num_edges,
                        'mtime': newest_mtime,
                        'timestamp': time.time(),
                        'log_file_path': log_file_path
                    }
                )
            
            self._add_message(f"{session_id[:20]}: loaded {num_nodes}N {num_edges}E")
            
        except Exception as e:
            self._add_message(f"{session_id[:20]}: ERROR - {str(e)[:30]}")
