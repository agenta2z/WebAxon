"""Queue service lifecycle and initialization management.

This module provides centralized queue service management including:
- Queue service initialization with timestamped paths
- Creation of all required queues
- Clean shutdown and resource cleanup
- Error handling for queue operations
"""
from pathlib import Path
from typing import Optional

from rich_python_utils.datetime_utils.common import timestamp
from rich_python_utils.service_utils.queue_service.storage_based_queue_service import StorageBasedQueueService

from ..core.config import ServiceConfig


class QueueManager:
    """Manages queue service lifecycle.
    
    This class handles the initialization, configuration, and cleanup of the
    queue service. It creates timestamped queue directories to prevent conflicts
    between service runs and ensures all required queues are created.
    
    Attributes:
        _testcase_root: Root directory for the testcase
        _config: Service configuration
        _queue_service: StorageBasedQueueService instance (initialized on demand)
        _queue_root_path: Path to the queue storage directory
    """
    
    def __init__(self, testcase_root: Path, config: ServiceConfig):
        """Initialize the queue manager.
        
        Args:
            testcase_root: Root directory for the testcase
            config: Service configuration
        """
        self._testcase_root = testcase_root
        self._config = config
        self._queue_service: Optional[StorageBasedQueueService] = None
        self._queue_root_path: Optional[Path] = None
    
    def initialize(self) -> StorageBasedQueueService:
        """Initialize queue service with timestamped path.
        
        Creates a timestamped queue directory to ensure isolation between
        service runs. This prevents queue conflicts when restarting the service.
        
        Returns:
            Initialized StorageBasedQueueService instance
            
        Raises:
            RuntimeError: If queue service is already initialized
        """
        if self._queue_service is not None:
            raise RuntimeError("Queue service already initialized")
        
        # Use custom queue root path if provided, otherwise create timestamped path
        if self._config.queue_root_path:
            self._queue_root_path = Path(self._config.queue_root_path)
        else:
            # Create timestamped queue directory for isolation
            queue_base_path = self._testcase_root / '_runtime' / 'queues'
            self._queue_root_path = queue_base_path / timestamp()
        
        # Create directory
        self._queue_root_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize StorageBasedQueueService with archiving enabled for debugging
        self._queue_service = StorageBasedQueueService(
            root_path=str(self._queue_root_path),
            archive_popped_items=True,
            archive_dir_name='_archive'
        )
        
        return self._queue_service
    
    def create_queues(self) -> None:
        """Create all required queues.
        
        Creates the following queues:
        - Input queue: for receiving user messages
        - Response queue: for sending agent responses
        - Client control queue: for receiving control messages from debugger
        - Server control queue: for sending control messages to debugger
        
        Raises:
            RuntimeError: If queue service is not initialized
        """
        if self._queue_service is None:
            raise RuntimeError("Queue service not initialized. Call initialize() first.")
        
        # Create all required queues
        self._queue_service.create_queue(self._config.input_queue_id)
        self._queue_service.create_queue(self._config.response_queue_id)
        self._queue_service.create_queue(self._config.client_control_queue_id)
        self._queue_service.create_queue(self._config.server_control_queue_id)
    
    def get_queue_service(self) -> StorageBasedQueueService:
        """Get the queue service instance.
        
        Returns:
            StorageBasedQueueService instance
            
        Raises:
            RuntimeError: If queue service is not initialized
        """
        if self._queue_service is None:
            raise RuntimeError("Queue service not initialized. Call initialize() first.")
        return self._queue_service
    
    def get_queue_root_path(self) -> Optional[Path]:
        """Get the queue root path.
        
        Returns:
            Path to queue root directory, or None if not initialized
        """
        return self._queue_root_path
    
    def close(self) -> None:
        """Close queue service and cleanup resources.
        
        Properly closes the queue service and releases all resources.
        This should be called during service shutdown.
        """
        if self._queue_service:
            try:
                self._queue_service.close()
            finally:
                self._queue_service = None
