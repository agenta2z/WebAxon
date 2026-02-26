"""Property-based tests for ServiceConfig.

This module contains property-based tests using hypothesis to verify
configuration field completeness and correctness.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path

# Add parent directory to path
from hypothesis import given, strategies as st, settings
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig


# Feature: web-agent-service-modularization, Property 3: Configuration Field Completeness
# Validates: Requirements 2.2, 2.3, 2.4, 2.5
@settings(max_examples=100)
@given(
    session_idle_timeout=st.integers(min_value=1, max_value=86400),
    cleanup_check_interval=st.integers(min_value=1, max_value=3600),
    debug_mode_service=st.booleans(),
    synchronous_agent=st.booleans(),
    new_agent_on_first_submission=st.booleans(),
    default_agent_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    input_queue_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    response_queue_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    client_control_queue_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    server_control_queue_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    log_root_path=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
)
def test_config_field_completeness(
    session_idle_timeout,
    cleanup_check_interval,
    debug_mode_service,
    synchronous_agent,
    new_agent_on_first_submission,
    default_agent_type,
    input_queue_id,
    response_queue_id,
    client_control_queue_id,
    server_control_queue_id,
    log_root_path,
):
    """Property: For any ServiceConfig instance, it should have all required fields.
    
    This test verifies that ServiceConfig has all required fields as specified in
    Requirements 2.2, 2.3, 2.4, 2.5:
    - Timeout values (session_idle_timeout, cleanup_check_interval)
    - Debug settings (debug_mode_service, synchronous_agent)
    - Agent settings (new_agent_on_first_submission, default_agent_type)
    - Queue IDs (input_queue_id, response_queue_id, client_control_queue_id, server_control_queue_id)
    - Paths (log_root_path)
    """
    # Create config with generated values
    config = ServiceConfig(
        session_idle_timeout=session_idle_timeout,
        cleanup_check_interval=cleanup_check_interval,
        debug_mode_service=debug_mode_service,
        synchronous_agent=synchronous_agent,
        new_agent_on_first_submission=new_agent_on_first_submission,
        default_agent_type=default_agent_type,
        input_queue_id=input_queue_id,
        response_queue_id=response_queue_id,
        client_control_queue_id=client_control_queue_id,
        server_control_queue_id=server_control_queue_id,
        log_root_path=log_root_path,
    )
    
    # Verify all required fields are present and have the correct values
    # Requirement 2.2: Timeout values
    assert hasattr(config, 'session_idle_timeout'), "Missing session_idle_timeout field"
    assert config.session_idle_timeout == session_idle_timeout
    assert hasattr(config, 'cleanup_check_interval'), "Missing cleanup_check_interval field"
    assert config.cleanup_check_interval == cleanup_check_interval
    
    # Requirement 2.3: Debug settings
    assert hasattr(config, 'debug_mode_service'), "Missing debug_mode_service field"
    assert config.debug_mode_service == debug_mode_service
    assert hasattr(config, 'synchronous_agent'), "Missing synchronous_agent field"
    assert config.synchronous_agent == synchronous_agent
    
    # Requirement 2.4: Queue identifiers
    assert hasattr(config, 'input_queue_id'), "Missing input_queue_id field"
    assert config.input_queue_id == input_queue_id
    assert hasattr(config, 'response_queue_id'), "Missing response_queue_id field"
    assert config.response_queue_id == response_queue_id
    assert hasattr(config, 'client_control_queue_id'), "Missing client_control_queue_id field"
    assert config.client_control_queue_id == client_control_queue_id
    assert hasattr(config, 'server_control_queue_id'), "Missing server_control_queue_id field"
    assert config.server_control_queue_id == server_control_queue_id
    
    # Requirement 2.5: Agent settings
    assert hasattr(config, 'new_agent_on_first_submission'), "Missing new_agent_on_first_submission field"
    assert config.new_agent_on_first_submission == new_agent_on_first_submission
    assert hasattr(config, 'default_agent_type'), "Missing default_agent_type field"
    assert config.default_agent_type == default_agent_type
    
    # Additional fields
    assert hasattr(config, 'log_root_path'), "Missing log_root_path field"
    assert config.log_root_path == log_root_path
    assert hasattr(config, 'queue_root_path'), "Missing queue_root_path field"
    
    # Verify validation passes for valid configurations
    config.validate()


if __name__ == '__main__':
    print("Running property-based tests for ServiceConfig...")
    print("Testing configuration field completeness with 100 random examples...")
    print()
    
    try:
        test_config_field_completeness()
        print("✓ Property test passed: Configuration field completeness verified")
        print("  All required fields present across 100 random configurations")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("All property-based tests passed! ✓")
