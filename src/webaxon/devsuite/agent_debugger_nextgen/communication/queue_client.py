"""
Queue Client Module

Provides a centralized interface for all queue operations in the agent debugger.
Handles queue initialization, message sending, and session synchronization.
"""
import time
from pathlib import Path
from typing import Optional, List
from rich_python_utils.datetime_utils.common import timestamp


class QueueClient:
    """
    Centralized client for queue operations.
    
    Handles:
    - Queue service initialization and refresh
    - Sending messages to various queues
    - Session synchronization with agent service
    - Agent control commands
    """
    
    def __init__(
        self,
        testcase_root: Path,
        input_queue_id: str,
        response_queue_id: str,
        client_control_queue_id: str,
        server_control_queue_id: str,
        queue_check_interval: float = 5.0,
        get_queue_service_func=None
    ):
        """
        Initialize the queue client.
        
        Args:
            testcase_root: Root directory for queue service discovery
            input_queue_id: ID for user input queue
            response_queue_id: ID for agent response queue
            client_control_queue_id: ID for client control messages
            server_control_queue_id: ID for server control messages
            queue_check_interval: Seconds between queue service refresh checks
            get_queue_service_func: Function to get/create queue service
        """
        self.testcase_root = testcase_root
        self.input_queue_id = input_queue_id
        self.response_queue_id = response_queue_id
        self.client_control_queue_id = client_control_queue_id
        self.server_control_queue_id = server_control_queue_id
        self.queue_check_interval = queue_check_interval
        self.get_queue_service_func = get_queue_service_func
        
        self._queue_service = None
        self._last_queue_check_time = 0.0
    
    def initialize_queue_service(self):
        """
        Initialize or refresh the shared queue service by finding the latest queue path.
        
        This is called periodically and will automatically detect when the agent service
        restarts with a new timestamp folder.
        
        Returns:
            Queue service instance
        """
        current_time = time.time()
        
        # Check if we should refresh the queue service
        should_check = (
            self._queue_service is None or
            (current_time - self._last_queue_check_time) >= self.queue_check_interval
        )
        
        if should_check:
            # get_queue_service handles all the logic: path comparison, logging, and cleanup
            self._queue_service = self.get_queue_service_func(
                self.testcase_root,
                existing_service=self._queue_service,
                log_on_change=True
            )
            
            self._last_queue_check_time = current_time
        
        return self._queue_service
    
    @property
    def queue_service(self):
        """Get the current queue service, initializing if needed."""
        return self.initialize_queue_service()
    
    def send_message(self, queue_id: str, message: dict):
        """
        Send a message to a specific queue.
        
        Args:
            queue_id: Target queue identifier
            message: Message data to send
        """
        self.queue_service.put(queue_id, message)
    
    def receive_message(self, queue_id: str, blocking: bool = False, timeout: float = 0) -> Optional[dict]:
        """
        Receive a message from a specific queue.
        
        Args:
            queue_id: Source queue identifier
            blocking: Whether to block waiting for a message
            timeout: Timeout in seconds (0 for non-blocking)
            
        Returns:
            Message data or None if no message available
        """
        return self.queue_service.get(queue_id, blocking=blocking, timeout=timeout)
    
    def sync_active_sessions(self, active_session_ids: List[str], debugger=None):
        """
        Sync all active session IDs with the agent service.
        
        This sends a complete list of active sessions to the service, allowing it to:
        - Create agents for new sessions (with default DefaultAgent configuration)
        - Close agents for sessions that are no longer active
        
        Args:
            active_session_ids: List of all currently active session IDs
            debugger: Optional debugger instance for logging
        """
        if debugger:
            debugger.log_info({'active_sessions': active_session_ids}, 'QUEUE_OPERATION')
        
        # Send session sync message with generic format
        control_message = {
            "type": "sync_active_sessions",
            "message": {
                "active_sessions": active_session_ids
            },
            "timestamp": timestamp()
        }
        
        self.send_message(self.server_control_queue_id, control_message)
        
        if debugger:
            debugger.log_info(
                f"Active sessions sync message sent to {self.server_control_queue_id}",
                'QUEUE_OPERATION'
            )
    
    def sync_session_agent(self, session_id: str, agent_type: str, debugger=None):
        """
        Update the agent configuration for a specific session.
        
        Args:
            session_id: Session ID to update
            agent_type: Type of agent to use (e.g., 'DefaultAgent', 'MockClarificationAgent')
            debugger: Optional debugger instance for logging
        """
        if debugger:
            debugger.log_info(
                {'session_id': session_id, 'agent_type': agent_type},
                'QUEUE_OPERATION'
            )
        
        # Send per-session agent update with generic format
        control_message = {
            "type": "sync_session_agent",
            "message": {
                "session_id": session_id,
                "agent_type": agent_type
            },
            "timestamp": timestamp()
        }
        
        self.send_message(self.server_control_queue_id, control_message)
        
        if debugger:
            debugger.log_info(
                f"Session agent update sent to {self.server_control_queue_id}",
                'QUEUE_OPERATION'
            )
    
    def sync_session_template_version(self, session_id: str, template_version: str, debugger=None):
        """
        Update the template version for a specific session.
        
        Args:
            session_id: Session ID to update
            template_version: Template version to use (empty string for default/no version)
            debugger: Optional debugger instance for logging
        """
        if debugger:
            debugger.log_info(
                {'session_id': session_id, 'template_version': template_version},
                'QUEUE_OPERATION'
            )
        
        # Send per-session template version update
        control_message = {
            "type": "sync_session_template_version",
            "message": {
                "session_id": session_id,
                "template_version": template_version
            },
            "timestamp": timestamp()
        }
        
        self.send_message(self.server_control_queue_id, control_message)
        
        if debugger:
            debugger.log_info(
                f"Session template version update sent to {self.server_control_queue_id}",
                'QUEUE_OPERATION'
            )
    
    def send_agent_control(self, session_id: str, control: str, hprint_func=None):
        """
        Send an agent workflow control command to the agent service.
        
        Args:
            session_id: Session ID to control
            control: Control command ('stop', 'pause', 'continue', 'step')
            hprint_func: Optional function for highlighted printing
        """
        # Send agent control message
        control_message = {
            "type": "agent_control",
            "message": {
                "session_id": session_id,
                "control": control
            },
            "timestamp": timestamp()
        }
        
        if hprint_func:
            hprint_func(
                control_message,
                title=f"[CONTROL SENT] {control.upper()} → {self.server_control_queue_id}"
            )
        
        self.send_message(self.server_control_queue_id, control_message)
    
    def send_user_input(
        self,
        session_id: str,
        message: str,
        all_session_ids: Optional[List[str]] = None,
        current_agent_type: Optional[str] = None,
        debugger=None
    ) -> str:
        """
        Send user input message to the agent service.
        
        Args:
            session_id: Session ID to associate this message with
            message: User input message
            all_session_ids: List of all active session IDs (for session reconciliation)
            current_agent_type: Current agent type for this session (if changed)
            debugger: Optional debugger instance for logging
            
        Returns:
            Session-specific input queue ID where message was sent
        """
        if debugger:
            debugger.log_info('Sending message to agent service...', 'QUEUE_OPERATION')
            debugger.log_debug({
                'message_type': type(message).__name__,
                'message_value': message,
                'session_id_type': type(session_id).__name__,
                'session_id': session_id,
                'all_session_ids': all_session_ids,
                'current_agent_type': current_agent_type
            }, 'DEBUG')
        
        # Sync active sessions (this allows service to reconcile and close inactive sessions)
        self.sync_active_sessions(all_session_ids or [session_id], debugger)
        
        # If agent type is specified for this session, sync it
        if current_agent_type:
            self.sync_session_agent(session_id, current_agent_type, debugger)
        
        # Put user input on the session-specific queue
        # Format: {"session_id": session_id, "user_input": message}
        # Using "user_input" key matches Agent's task_input_field_user_input
        queue_data = {
            "session_id": session_id,
            "user_input": message
        }
        
        if debugger:
            debugger.log_debug({'queue_data': queue_data}, 'DEBUG')
        
        # Send to session-specific input queue (e.g., 'user_input_session_1_20251110103004')
        # The agent thread will pick it up from there
        session_input_queue_id = f"{self.input_queue_id}_{session_id}"
        self.send_message(session_input_queue_id, queue_data)
        
        if debugger:
            debugger.log_info(
                f"Message sent to session-specific queue: {session_input_queue_id}",
                'QUEUE_OPERATION'
            )
        
        return session_input_queue_id
