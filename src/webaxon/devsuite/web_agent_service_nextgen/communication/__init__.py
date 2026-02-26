"""Communication components for web agent service.

This module handles queue-based communication between the service and external
components (debugger UI, clients, etc.).

Components:
    QueueManager:
        Queue service lifecycle management.
        Handles initialization, queue creation, and cleanup of the
        StorageBasedQueueService used for inter-process communication.
        
        Key features:
            - Timestamped queue paths for isolation
            - Automatic creation of all required queues
            - Clean shutdown and resource management
            - Error handling for queue operations
        
        Required queues:
            - input_queue: User input messages to agents
            - response_queue: Agent responses to users
            - client_control_queue: Control messages from clients
            - server_control_queue: Control messages from service
        
        Example:
            >>> manager = QueueManager(testcase_root, config)
            >>> queue_service = manager.initialize()
            >>> manager.create_queues()
            >>> # ... use queue_service ...
            >>> manager.close()
    
    MessageHandlers:
        Control message processing and dispatch.
        Handles different types of control messages sent to the service,
        coordinating with SessionManager and AgentFactory as needed.
        
        Supported message types:
            - sync_active_sessions: Get list of active session IDs
            - sync_session_agent: Get agent status for a session
            - sync_session_template_version: Get template version for a session
            - agent_control: Execute control action (stop/pause/continue/step)
        
        Message format:
            All messages are dictionaries with a 'type' field and optional
            additional fields depending on the message type.
            
            Example:
                {
                    'type': 'sync_active_sessions',
                    'timestamp': '2024-01-15T10:30:00'
                }
        
        Example:
            >>> handlers = MessageHandlers(
            ...     session_manager,
            ...     agent_factory,
            ...     queue_service,
            ...     config
            ... )
            >>> message = {'type': 'sync_active_sessions'}
            >>> handlers.dispatch(message)

Design Principles:
    - Message Dispatch Pattern: Easy to add new message types
    - Separation of Concerns: Each handler focuses on one message type
    - Dependency Injection: Handlers coordinate through injected dependencies
    - Error Handling: Graceful handling of malformed messages

Message Protocol:
    The service uses a queue-based message protocol for communication:
    
    1. Control messages arrive on client_control_queue
    2. MessageHandlers dispatches to appropriate handler
    3. Handler processes message and coordinates with other components
    4. Response sent to server_control_queue
    
    This protocol enables:
    - Asynchronous communication
    - Decoupling of service and UI
    - Multiple concurrent clients
    - Reliable message delivery

For detailed documentation, see the individual module files:
    - queue_manager.py: Queue service management
    - message_handlers.py: Message processing and dispatch
"""

from .queue_manager import QueueManager
from .message_handlers import MessageHandlers

__all__ = [
    'QueueManager',
    'MessageHandlers',
]
