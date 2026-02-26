"""Test script for ServiceConfig validation."""
import sys
import resolve_path  # Setup import paths

from pathlib import Path

# Add parent directory to path
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig


def test_default_config():
    """Test default configuration."""
    config = ServiceConfig()
    config.validate()
    print("✓ Default config validation passed")
    assert config.session_idle_timeout == 1800
    assert config.cleanup_check_interval == 300
    assert config.default_agent_type == 'DefaultAgent'
    print("✓ Default values correct")


def test_invalid_timeout():
    """Test invalid timeout validation."""
    config = ServiceConfig(session_idle_timeout=-100)
    try:
        config.validate()
        print("✗ Should have raised ValueError for negative timeout")
        return False
    except ValueError as e:
        print(f"✓ Validation correctly caught error: {e}")
        return True


def test_invalid_queue_id():
    """Test invalid queue ID validation."""
    config = ServiceConfig(input_queue_id="")
    try:
        config.validate()
        print("✗ Should have raised ValueError for empty queue ID")
        return False
    except ValueError as e:
        print(f"✓ Validation correctly caught error: {e}")
        return True


def test_invalid_agent_type():
    """Test invalid agent type validation."""
    config = ServiceConfig(default_agent_type="")
    try:
        config.validate()
        print("✗ Should have raised ValueError for empty agent type")
        return False
    except ValueError as e:
        print(f"✓ Validation correctly caught error: {e}")
        return True


def test_all_queue_ids():
    """Test all queue IDs are present."""
    config = ServiceConfig()
    assert config.input_queue_id == 'user_input'
    assert config.response_queue_id == 'agent_response'
    assert config.client_control_queue_id == 'client_control'
    assert config.server_control_queue_id == 'server_control'
    print("✓ All queue IDs present and correct")


if __name__ == '__main__':
    print("Testing ServiceConfig...")
    print()
    
    test_default_config()
    test_invalid_timeout()
    test_invalid_queue_id()
    test_invalid_agent_type()
    test_all_queue_ids()
    
    print()
    print("All tests passed! ✓")
