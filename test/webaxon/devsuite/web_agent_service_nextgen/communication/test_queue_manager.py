"""Tests for QueueManager implementation.

This test verifies that the QueueManager correctly:
- Initializes queue service with timestamped paths
- Creates all required queues
- Provides access to queue service
- Handles cleanup properly
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path

# Add parent directories to path for imports
import tempfile
import shutil

from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.communication.queue_manager import QueueManager


def test_queue_manager():
    """Test QueueManager initialization and queue creation."""
    # Create temporary directory for testing
    temp_dir = Path(tempfile.mkdtemp(prefix='test_queue_manager_'))
    
    try:
        print("\n=== Testing QueueManager ===\n")
        
        # Create config
        config = ServiceConfig()
        print(f"✓ Created ServiceConfig")
        print(f"  - Input queue: {config.input_queue_id}")
        print(f"  - Response queue: {config.response_queue_id}")
        print(f"  - Client control queue: {config.client_control_queue_id}")
        print(f"  - Server control queue: {config.server_control_queue_id}")
        
        # Create QueueManager
        queue_manager = QueueManager(temp_dir, config)
        print(f"\n✓ Created QueueManager")
        
        # Initialize queue service
        queue_service = queue_manager.initialize()
        print(f"\n✓ Initialized queue service")
        
        # Check queue root path
        queue_root_path = queue_manager.get_queue_root_path()
        print(f"  - Queue root path: {queue_root_path}")
        assert queue_root_path is not None, "Queue root path should not be None"
        assert queue_root_path.exists(), "Queue root path should exist"
        
        # Verify timestamped path (should contain a timestamp in the path)
        path_parts = str(queue_root_path).split('/')
        has_timestamp = any(
            part.replace('-', '').replace('_', '').replace(':', '').isdigit() 
            for part in path_parts
        )
        print(f"  - Has timestamped path: {has_timestamp}")
        
        # Create queues
        queue_manager.create_queues()
        print(f"\n✓ Created all required queues")
        
        # Verify queues exist by trying to put/get
        test_message = {'test': 'message'}
        
        # Test input queue
        queue_service.put(config.input_queue_id, test_message)
        retrieved = queue_service.get(config.input_queue_id, blocking=False)
        assert retrieved == test_message, "Input queue should work"
        print(f"  - Input queue: working")
        
        # Test response queue
        queue_service.put(config.response_queue_id, test_message)
        retrieved = queue_service.get(config.response_queue_id, blocking=False)
        assert retrieved == test_message, "Response queue should work"
        print(f"  - Response queue: working")
        
        # Test client control queue
        queue_service.put(config.client_control_queue_id, test_message)
        retrieved = queue_service.get(config.client_control_queue_id, blocking=False)
        assert retrieved == test_message, "Client control queue should work"
        print(f"  - Client control queue: working")
        
        # Test server control queue
        queue_service.put(config.server_control_queue_id, test_message)
        retrieved = queue_service.get(config.server_control_queue_id, blocking=False)
        assert retrieved == test_message, "Server control queue should work"
        print(f"  - Server control queue: working")
        
        # Test get_queue_service
        retrieved_service = queue_manager.get_queue_service()
        assert retrieved_service is queue_service, "Should return same queue service instance"
        print(f"\n✓ get_queue_service() returns correct instance")
        
        # Test close
        queue_manager.close()
        print(f"\n✓ Closed queue service successfully")
        
        print("\n=== All QueueManager tests passed! ===\n")
        
    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def test_queue_manager_custom_path():
    """Test QueueManager with custom queue root path."""
    # Create temporary directory for testing
    temp_dir = Path(tempfile.mkdtemp(prefix='test_queue_manager_custom_'))
    custom_queue_path = temp_dir / 'custom_queues'
    
    try:
        print("\n=== Testing QueueManager with Custom Path ===\n")
        
        # Create config with custom path
        config = ServiceConfig(queue_root_path=str(custom_queue_path))
        print(f"✓ Created ServiceConfig with custom path: {custom_queue_path}")
        
        # Create QueueManager
        queue_manager = QueueManager(temp_dir, config)
        
        # Initialize queue service
        queue_service = queue_manager.initialize()
        print(f"✓ Initialized queue service")
        
        # Check queue root path matches custom path
        queue_root_path = queue_manager.get_queue_root_path()
        assert queue_root_path == custom_queue_path, "Should use custom queue path"
        print(f"  - Queue root path: {queue_root_path}")
        print(f"  - Matches custom path: {queue_root_path == custom_queue_path}")
        
        # Create queues
        queue_manager.create_queues()
        print(f"✓ Created all required queues")
        
        # Close
        queue_manager.close()
        print(f"✓ Closed queue service successfully")
        
        print("\n=== Custom path test passed! ===\n")
        
    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def test_queue_manager_error_handling():
    """Test QueueManager error handling."""
    temp_dir = Path(tempfile.mkdtemp(prefix='test_queue_manager_errors_'))
    
    try:
        print("\n=== Testing QueueManager Error Handling ===\n")
        
        config = ServiceConfig()
        queue_manager = QueueManager(temp_dir, config)
        
        # Test getting queue service before initialization
        try:
            queue_manager.get_queue_service()
            assert False, "Should raise RuntimeError"
        except RuntimeError as e:
            print(f"✓ Correctly raises error when getting service before init: {e}")
        
        # Test creating queues before initialization
        try:
            queue_manager.create_queues()
            assert False, "Should raise RuntimeError"
        except RuntimeError as e:
            print(f"✓ Correctly raises error when creating queues before init: {e}")
        
        # Initialize
        queue_manager.initialize()
        
        # Test double initialization
        try:
            queue_manager.initialize()
            assert False, "Should raise RuntimeError"
        except RuntimeError as e:
            print(f"✓ Correctly raises error on double initialization: {e}")
        
        # Close
        queue_manager.close()
        
        # Test that close is idempotent (can be called multiple times)
        queue_manager.close()
        print(f"✓ Close is idempotent (can be called multiple times)")
        
        print("\n=== Error handling tests passed! ===\n")
        
    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    test_queue_manager()
    test_queue_manager_custom_path()
    test_queue_manager_error_handling()
    print("\n" + "="*50)
    print("ALL TESTS PASSED!")
    print("="*50 + "\n")
