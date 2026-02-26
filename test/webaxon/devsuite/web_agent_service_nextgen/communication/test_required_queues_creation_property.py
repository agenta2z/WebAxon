"""Property-based tests for required queues creation.

This module contains property-based tests using hypothesis to verify
that all required queues are created during queue service initialization.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
import tempfile
import shutil

# Add parent directory to path
from hypothesis import given, strategies as st, settings
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.communication import QueueManager


# Windows reserved names that cannot be used as filenames
WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}


def is_valid_queue_id(queue_id: str) -> bool:
    """Check if a queue ID is valid (not a Windows reserved name)."""
    if not queue_id or not queue_id.strip():
        return False
    # Check if it's a Windows reserved name (case-insensitive)
    if queue_id.upper() in WINDOWS_RESERVED_NAMES:
        return False
    # Check if it starts or ends with underscore
    if queue_id.startswith('_') or queue_id.endswith('_'):
        return False
    return True


# Feature: web-agent-service-modularization, Property 14: Required Queues Creation
# Validates: Requirements 5.3
@settings(max_examples=100, deadline=None)
@given(
    input_queue_id=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')),
        min_size=1,
        max_size=30
    ).filter(is_valid_queue_id),
    response_queue_id=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')),
        min_size=1,
        max_size=30
    ).filter(is_valid_queue_id),
    client_control_queue_id=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')),
        min_size=1,
        max_size=30
    ).filter(is_valid_queue_id),
    server_control_queue_id=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')),
        min_size=1,
        max_size=30
    ).filter(is_valid_queue_id),
)
def test_required_queues_creation(
    input_queue_id,
    response_queue_id,
    client_control_queue_id,
    server_control_queue_id
):
    """Property: For any queue service initialization, all required queues should be created.
    
    This test verifies that QueueManager.create_queues() creates all four required queues:
    - input queue (for receiving user messages)
    - response queue (for sending agent responses)
    - client_control queue (for receiving control messages from debugger)
    - server_control queue (for sending control messages to debugger)
    
    As specified in Requirement 5.3, these queues are essential for service operation.
    """
    # Create temporary directory for testing
    temp_dir = Path(tempfile.mkdtemp(prefix='test_required_queues_'))
    
    try:
        # Create config with custom queue IDs
        config = ServiceConfig(
            input_queue_id=input_queue_id,
            response_queue_id=response_queue_id,
            client_control_queue_id=client_control_queue_id,
            server_control_queue_id=server_control_queue_id,
        )
        
        # Create QueueManager
        queue_manager = QueueManager(temp_dir, config)
        
        # Initialize queue service
        queue_service = queue_manager.initialize()
        
        # Create all required queues
        queue_manager.create_queues()
        
        # Verify all required queues exist using the queue service's exists() method
        assert queue_service.exists(input_queue_id), (
            f"Input queue '{input_queue_id}' should exist after create_queues()"
        )
        
        assert queue_service.exists(response_queue_id), (
            f"Response queue '{response_queue_id}' should exist after create_queues()"
        )
        
        assert queue_service.exists(client_control_queue_id), (
            f"Client control queue '{client_control_queue_id}' should exist after create_queues()"
        )
        
        assert queue_service.exists(server_control_queue_id), (
            f"Server control queue '{server_control_queue_id}' should exist after create_queues()"
        )
        
        # Verify we can interact with each queue (put and get operations)
        # This ensures the queues are not just directories but functional queues
        test_message = {'type': 'test', 'data': 'verification'}
        
        # Test input queue
        queue_service.put(input_queue_id, test_message)
        retrieved = queue_service.get(input_queue_id, blocking=False)
        assert retrieved == test_message, (
            f"Input queue should be functional. "
            f"Expected: {test_message}, Got: {retrieved}"
        )
        
        # Test response queue
        queue_service.put(response_queue_id, test_message)
        retrieved = queue_service.get(response_queue_id, blocking=False)
        assert retrieved == test_message, (
            f"Response queue should be functional. "
            f"Expected: {test_message}, Got: {retrieved}"
        )
        
        # Test client control queue
        queue_service.put(client_control_queue_id, test_message)
        retrieved = queue_service.get(client_control_queue_id, blocking=False)
        assert retrieved == test_message, (
            f"Client control queue should be functional. "
            f"Expected: {test_message}, Got: {retrieved}"
        )
        
        # Test server control queue
        queue_service.put(server_control_queue_id, test_message)
        retrieved = queue_service.get(server_control_queue_id, blocking=False)
        assert retrieved == test_message, (
            f"Server control queue should be functional. "
            f"Expected: {test_message}, Got: {retrieved}"
        )
        
        # Cleanup
        queue_manager.close()
        
    finally:
        # Cleanup temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


# Feature: web-agent-service-modularization, Property 14: Required Queues Creation
# Validates: Requirements 5.3
@settings(max_examples=100)
@given(
    session_idle_timeout=st.integers(min_value=60, max_value=3600),
    cleanup_check_interval=st.integers(min_value=30, max_value=600),
)
def test_default_queue_ids_creation(session_idle_timeout, cleanup_check_interval):
    """Property: For any configuration, default queue IDs should create all required queues.
    
    This test verifies that when using default queue IDs from ServiceConfig,
    all four required queues are created correctly.
    """
    # Create temporary directory for testing
    temp_dir = Path(tempfile.mkdtemp(prefix='test_default_queues_'))
    
    try:
        # Create config with default queue IDs
        config = ServiceConfig(
            session_idle_timeout=session_idle_timeout,
            cleanup_check_interval=cleanup_check_interval,
        )
        
        # Create QueueManager
        queue_manager = QueueManager(temp_dir, config)
        
        # Initialize queue service
        queue_service = queue_manager.initialize()
        
        # Create all required queues
        queue_manager.create_queues()
        
        # Default queue IDs from ServiceConfig
        default_queues = [
            'user_input',
            'agent_response',
            'client_control',
            'server_control'
        ]
        
        # Verify all default queues exist using the queue service's exists() method
        for queue_id in default_queues:
            assert queue_service.exists(queue_id), (
                f"Default queue '{queue_id}' should exist after create_queues()"
            )
            
            # Verify queue is functional
            test_message = {'queue': queue_id, 'test': True}
            queue_service.put(queue_id, test_message)
            retrieved = queue_service.get(queue_id, blocking=False)
            assert retrieved == test_message, (
                f"Default queue '{queue_id}' should be functional. "
                f"Expected: {test_message}, Got: {retrieved}"
            )
        
        # Cleanup
        queue_manager.close()
        
    finally:
        # Cleanup temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


# Feature: web-agent-service-modularization, Property 14: Required Queues Creation
# Validates: Requirements 5.3
def test_create_queues_before_initialize_fails():
    """Property: Calling create_queues() before initialize() should raise RuntimeError.
    
    This test verifies that the QueueManager enforces proper initialization order.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix='test_init_order_'))
    
    try:
        config = ServiceConfig()
        queue_manager = QueueManager(temp_dir, config)
        
        # Try to create queues before initializing
        try:
            queue_manager.create_queues()
            assert False, "create_queues() should raise RuntimeError when called before initialize()"
        except RuntimeError as e:
            # Expected behavior
            assert "not initialized" in str(e).lower(), (
                f"RuntimeError should mention initialization. Got: {e}"
            )
        
    finally:
        # Cleanup temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    print("Running property-based tests for required queues creation...")
    print()
    
    print("Test 1: Required queues creation with custom queue IDs")
    print("Testing with 100 random queue ID configurations...")
    try:
        test_required_queues_creation()
        print("✓ Property test passed: All required queues created with custom IDs")
        print("  Verified: input, response, client_control, server_control queues")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("Test 2: Required queues creation with default queue IDs")
    print("Testing with 100 random configurations...")
    try:
        test_default_queue_ids_creation()
        print("✓ Property test passed: All default queues created correctly")
        print("  Verified: user_input, agent_response, client_control, server_control")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("Test 3: Initialization order enforcement")
    print("Testing that create_queues() requires initialize() first...")
    try:
        test_create_queues_before_initialize_fails()
        print("✓ Property test passed: Initialization order enforced")
        print("  create_queues() correctly raises RuntimeError before initialize()")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("All property-based tests passed! ✓")
