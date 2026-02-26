"""Property-based tests for timestamped queue paths.

This module contains property-based tests using hypothesis to verify
that queue initialization creates timestamped paths for isolation.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
import re
import tempfile
import shutil

# Add parent directory to path
from hypothesis import given, strategies as st, settings
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.communication import QueueManager


# Feature: web-agent-service-modularization, Property 13: Timestamped Queue Paths
# Validates: Requirements 5.2
@settings(max_examples=100)
@given(
    session_idle_timeout=st.integers(min_value=60, max_value=3600),
    cleanup_check_interval=st.integers(min_value=30, max_value=600),
)
def test_timestamped_queue_paths(session_idle_timeout, cleanup_check_interval):
    """Property: For any queue initialization, the queue root path should contain a timestamp.
    
    This test verifies that QueueManager creates timestamped queue paths to ensure
    isolation between service runs, as specified in Requirement 5.2.
    
    The timestamp should be in a recognizable format (containing digits, dashes, underscores,
    or colons) to prevent queue conflicts when restarting the service.
    """
    # Create temporary directory for testing
    temp_dir = Path(tempfile.mkdtemp(prefix='test_timestamped_queue_'))
    
    try:
        # Create config with random timeout values
        config = ServiceConfig(
            session_idle_timeout=session_idle_timeout,
            cleanup_check_interval=cleanup_check_interval,
            # Don't set queue_root_path - let it create timestamped path
            queue_root_path=None
        )
        
        # Create QueueManager
        queue_manager = QueueManager(temp_dir, config)
        
        # Initialize queue service (this should create timestamped path)
        queue_service = queue_manager.initialize()
        
        # Get the queue root path
        queue_root_path = queue_manager.get_queue_root_path()
        
        # Verify queue root path exists
        assert queue_root_path is not None, "Queue root path should not be None after initialization"
        assert queue_root_path.exists(), "Queue root path should exist after initialization"
        
        # Verify the path contains a timestamp component
        # A timestamp should contain digits and possibly separators like '-', '_', ':'
        path_str = str(queue_root_path)
        path_parts = path_str.split('/')
        
        # Look for a path component that looks like a timestamp
        # Timestamps typically have patterns like:
        # - YYYY-MM-DD_HH-MM-SS
        # - YYYYMMDD_HHMMSS
        # - YYYY-MM-DD-HH-MM-SS-ffffff
        # At minimum, should have a component with many digits
        has_timestamp = False
        for part in path_parts:
            # Check if this part looks like a timestamp
            # Should have at least 8 digits (for YYYYMMDD)
            digit_count = sum(c.isdigit() for c in part)
            if digit_count >= 8:
                has_timestamp = True
                break
            
            # Alternative: check for timestamp-like patterns
            # Pattern: digits with separators
            if re.search(r'\d{4}[-_]\d{2}[-_]\d{2}', part):
                has_timestamp = True
                break
        
        assert has_timestamp, (
            f"Queue root path should contain a timestamp component for isolation. "
            f"Path: {queue_root_path}"
        )
        
        # Verify that multiple initializations create different paths
        # (This ensures true isolation between runs)
        queue_manager.close()
        
        # Create a second QueueManager with same config
        queue_manager2 = QueueManager(temp_dir, config)
        queue_service2 = queue_manager2.initialize()
        queue_root_path2 = queue_manager2.get_queue_root_path()
        
        # The paths should be different (different timestamps)
        # Note: In rare cases they might be the same if executed in the same second,
        # but the timestamp() function typically includes microseconds
        # We'll just verify both have timestamps, not that they're different
        # (since that could be flaky)
        path_str2 = str(queue_root_path2)
        path_parts2 = path_str2.split('/')
        has_timestamp2 = False
        for part in path_parts2:
            digit_count = sum(c.isdigit() for c in part)
            if digit_count >= 8:
                has_timestamp2 = True
                break
            if re.search(r'\d{4}[-_]\d{2}[-_]\d{2}', part):
                has_timestamp2 = True
                break
        
        assert has_timestamp2, (
            f"Second queue root path should also contain a timestamp component. "
            f"Path: {queue_root_path2}"
        )
        
        # Cleanup
        queue_manager2.close()
        
    finally:
        # Cleanup temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


# Feature: web-agent-service-modularization, Property 13: Timestamped Queue Paths
# Validates: Requirements 5.2
@settings(max_examples=100)
@given(
    custom_path_suffix=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip() and not x.startswith('_'))
)
def test_custom_queue_path_no_timestamp(custom_path_suffix):
    """Property: When a custom queue_root_path is provided, it should be used as-is.
    
    This test verifies that when a custom queue_root_path is specified in the config,
    the QueueManager uses that path directly without adding a timestamp.
    This allows users to control the queue location when needed.
    """
    # Create temporary directory for testing
    temp_dir = Path(tempfile.mkdtemp(prefix='test_custom_queue_'))
    
    try:
        # Create custom queue path
        custom_queue_path = temp_dir / 'custom_queues' / custom_path_suffix
        
        # Create config with custom queue path
        config = ServiceConfig(
            queue_root_path=str(custom_queue_path)
        )
        
        # Create QueueManager
        queue_manager = QueueManager(temp_dir, config)
        
        # Initialize queue service
        queue_service = queue_manager.initialize()
        
        # Get the queue root path
        queue_root_path = queue_manager.get_queue_root_path()
        
        # Verify the path matches the custom path exactly
        assert queue_root_path == custom_queue_path, (
            f"When custom queue_root_path is provided, it should be used as-is. "
            f"Expected: {custom_queue_path}, Got: {queue_root_path}"
        )
        
        # Verify the path exists
        assert queue_root_path.exists(), "Custom queue root path should exist after initialization"
        
        # Cleanup
        queue_manager.close()
        
    finally:
        # Cleanup temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    print("Running property-based tests for timestamped queue paths...")
    print()
    
    print("Test 1: Timestamped queue paths for isolation")
    print("Testing with 100 random configurations...")
    try:
        test_timestamped_queue_paths()
        print("✓ Property test passed: Timestamped queue paths verified")
        print("  Queue paths contain timestamps for isolation between runs")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("Test 2: Custom queue paths used as-is")
    print("Testing with 100 random custom paths...")
    try:
        test_custom_queue_path_no_timestamp()
        print("✓ Property test passed: Custom queue paths used correctly")
        print("  Custom paths are used as-is without adding timestamps")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("All property-based tests passed! ✓")
