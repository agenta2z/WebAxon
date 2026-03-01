"""
Message Handlers Module

Processes different message types from the CLIENT_CONTROL_QUEUE.
Handles agent status updates, control acknowledgments, and log path notifications.
"""
import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from agent_foundation.ui.dash_interactive.utils.log_collector import LogCollector


class MessageHandlers:
    """
    Centralized message handling for client control queue messages.
    
    Processes different message types:
    - agent_status: Agent creation and configuration updates
    - agent_control_ack: Control command acknowledgments
    - log_path_available: New execution log notifications
    """
    
    def __init__(
        self,
        session_manager,
        get_active_session_ids_func,
        hprint_func=None
    ):
        """
        Initialize message handlers.
        
        Args:
            session_manager: SessionManager instance for session state
            get_active_session_ids_func: Function to get list of active session IDs
            hprint_func: Optional function for highlighted console printing
        """
        self.session_manager = session_manager
        self.get_active_session_ids = get_active_session_ids_func
        self.hprint_func = hprint_func
        
        # Global state for log collectors
        self._latest_log_collector = None
        self._latest_log_file_path = None
        self._recent_log_collectors = {}  # timestamp_key -> LogCollector
    
    @property
    def latest_log_collector(self):
        """Get the most recently loaded log collector."""
        return self._latest_log_collector
    
    @property
    def latest_log_file_path(self):
        """Get the path to the most recently loaded log file."""
        return self._latest_log_file_path
    
    @property
    def recent_log_collectors(self):
        """Get dictionary of recent log collectors by timestamp."""
        return self._recent_log_collectors
    
    def handle_agent_status_message(
        self,
        msg: dict,
        session_id: str,
        app_instance
    ) -> Tuple[Optional[str], bool]:
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
    
    def handle_agent_control_ack_message(
        self,
        msg: dict,
        session_id: str,
        debugger=None
    ):
        """
        Handle agent_control_ack message type.
        
        Updates agent control and status for ALL active sessions (not just current).
        
        Args:
            msg: Message dict with type "agent_control_ack"
            session_id: Current active session ID (used for debug logging)
            debugger: Optional debugger instance for logging
        """
        payload = msg.get('message', {})
        msg_session_id = payload.get('session_id')
        
        # Process message for any session (not just current one)
        # Check if this is a known/active session
        active_sessions = self.get_active_session_ids()
        if msg_session_id and (msg_session_id in active_sessions or msg_session_id == session_id):
            # Update agent control and status for the message's session
            agent_control = payload.get('control', 'continue')
            agent_status = payload.get('agent_status', 'unknown')
            operation_status = payload.get('operation_status', 'success')
            
            session_info = self.session_manager.get_or_create(msg_session_id)
            session_info.agent_control = agent_control
            session_info.agent_status = agent_status
            session_info.control_pending = False
            
            # Highlight received ack message
            if self.hprint_func:
                self.hprint_func(
                    {
                        'session_id': msg_session_id,
                        'control': agent_control,
                        'status': agent_status,
                        'operation': operation_status
                    },
                    title=f"[ACK RECEIVED] Session {msg_session_id}: {operation_status}"
                )
        else:
            if debugger:
                debugger.log_debug({
                    'message': f"Skipping ack for session {msg_session_id}",
                    'reason': 'not in active sessions',
                    'current_session': session_id
                }, 'CONTROL_ACK')
    
    def handle_log_path_message(self, msg: dict, debugger=None):
        """
        Handle log_path_available message type.
        
        Loads log files and stores them in session info and global state.
        
        Args:
            msg: Message dict with type "log_path_available"
            debugger: Optional debugger instance for logging
        """
        # Extract log path from message payload
        log_file_path = msg.get('message', {}).get('log_path')
        if not log_file_path:
            if debugger:
                debugger.log_warning({
                    'message': 'log_path_available message missing log_path',
                    'msg': msg
                }, 'WARNING')
            return
        
        if debugger:
            debugger.log_debug({'log_file_path': log_file_path}, 'DEBUG')
        
        try:
            # Load logs from the directory
            log_collector = LogCollector.from_json_logs(log_file_path, json_file_pattern='*.jsonl')
            
            # Store as the latest for UI access
            self._latest_log_collector = log_collector
            self._latest_log_file_path = log_file_path
            
            # Extract session_id from log path (e.g., ".../session_1_20251111062506")
            session_id = Path(log_file_path).name
            
            if debugger:
                debugger.log_debug({'session_id': session_id}, 'DEBUG')
            
            if session_id:
                session_info = self.session_manager.get_or_create(session_id)
                session_info.log_collector = log_collector
                session_info.log_file_path = log_file_path
                
                if debugger:
                    debugger.log_debug({
                        'session_id': session_id,
                        'active_sessions': self.get_active_session_ids()
                    }, 'DEBUG')
            else:
                if debugger:
                    debugger.log_debug('Could not extract session_id from log path', 'DEBUG')
            
            # Also store with a timestamp key for history
            timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            session_key = f"agent_{timestamp_str}"
            self._recent_log_collectors[session_key] = log_collector
            
            # Keep only last 10 executions
            if len(self._recent_log_collectors) > 10:
                oldest_key = sorted(self._recent_log_collectors.keys())[0]
                del self._recent_log_collectors[oldest_key]
        
        except Exception as e:
            import traceback
            if debugger:
                debugger.log_warning({
                    'message': f'Could not load logs from {log_file_path}',
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }, 'WARNING')
    
    def process_client_control_messages(
        self,
        messages: list,
        session_id: str,
        app_instance,
        debugger=None
    ) -> Dict[str, Any]:
        """
        Process a batch of client control messages.
        
        Routes messages to appropriate handlers based on message type.
        
        Args:
            messages: List of message dicts from CLIENT_CONTROL_QUEUE
            session_id: Current active session ID
            app_instance: QueueBasedDashApp instance for accessing state
            debugger: Optional debugger instance for logging
            
        Returns:
            dict: Processing results with keys:
                - latest_agent: Latest agent type (or None)
                - agent_created: Whether agent was created/locked
                - messages_processed: Number of messages processed
        """
        latest_agent = None
        agent_created = False
        messages_processed = 0
        
        for msg in messages:
            if not isinstance(msg, dict):
                if debugger:
                    debugger.log_warning({
                        'message': 'Non-dict message in CLIENT_CONTROL_QUEUE',
                        'value': msg
                    }, 'WARNING')
                continue
            
            msg_type = msg.get('type')
            
            if msg_type == 'agent_status':
                agent, created = self.handle_agent_status_message(msg, session_id, app_instance)
                if agent:
                    latest_agent = agent
                if created:
                    agent_created = True
                messages_processed += 1
            
            elif msg_type == 'agent_control_ack':
                self.handle_agent_control_ack_message(msg, session_id, debugger)
                messages_processed += 1
            
            elif msg_type == 'log_path_available':
                self.handle_log_path_message(msg, debugger)
                messages_processed += 1
            
            else:
                if debugger:
                    debugger.log_debug({
                        'message': f'Unknown message type: {msg_type}',
                        'msg': msg
                    }, 'DEBUG')
        
        return {
            'latest_agent': latest_agent,
            'agent_created': agent_created,
            'messages_processed': messages_processed
        }
