"""Property-based tests for AgentSessionInfo.

This module contains property-based tests using hypothesis to verify
session info field completeness and correctness.
"""
import sys
import resolve_path  # Setup import paths

# Add parent directory to path
from hypothesis import given, strategies as st, settings
from webaxon.devsuite.web_agent_service_nextgen.session import AgentSessionInfo


# Feature: web-agent-service-modularization, Property 5: Session Info Field Completeness
# Validates: Requirements 3.2
@settings(max_examples=100)
@given(
    session_id=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
    created_at=st.floats(min_value=0, max_value=2000000000),
    last_active=st.floats(min_value=0, max_value=2000000000),
    agent_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    agent_created=st.booleans(),
    template_version=st.text(min_size=0, max_size=50),
)
def test_session_info_field_completeness(
    session_id,
    created_at,
    last_active,
    agent_type,
    agent_created,
    template_version,
):
    """Property: For any AgentSessionInfo instance, it should have all required fields.

    This test verifies that AgentSessionInfo (now a pure data class) has all required
    fields as specified in Requirement 3.2:
    - last_agent_status: Last known agent status for change detection
    - template_version: Template version for this session

    Additionally verifies inherited fields from SessionInfo:
    - session_id: Unique identifier for the session
    - created_at: Timestamp when session was created
    - last_active: Timestamp of last activity
    - session_type: Type of session (e.g., 'DefaultAgent')
    - initialized: True once agent is created and locked
    """
    # Create session info with generated values
    session_info = AgentSessionInfo(
        session_id=session_id,
        created_at=created_at,
        last_active=last_active,
        session_type=agent_type,
        initialized=agent_created,
        template_version=template_version,
    )
    
    # Verify all required fields from SessionInfo are present
    assert hasattr(session_info, 'session_id'), "Missing session_id field"
    assert session_info.session_id == session_id
    assert hasattr(session_info, 'created_at'), "Missing created_at field"
    assert session_info.created_at == created_at
    assert hasattr(session_info, 'last_active'), "Missing last_active field"
    assert session_info.last_active == last_active
    assert hasattr(session_info, 'session_type'), "Missing session_type field"
    assert session_info.session_type == agent_type
    assert hasattr(session_info, 'initialized'), "Missing initialized field"
    assert session_info.initialized == agent_created
    
    # Verify all service-specific fields are present (Requirement 3.2)
    # Status tracking fields
    assert hasattr(session_info, 'last_agent_status'), "Missing last_agent_status field"

    # Template versioning fields
    assert hasattr(session_info, 'template_version'), "Missing template_version field"
    assert session_info.template_version == template_version

    # Verify that optional fields can be None (proper initialization)
    assert session_info.last_agent_status is None or isinstance(session_info.last_agent_status, str), \
        "last_agent_status should be None or str"


if __name__ == '__main__':
    print("Running property-based tests for AgentSessionInfo...")
    print("Testing session info field completeness with 100 random examples...")
    print()
    
    try:
        test_session_info_field_completeness()
        print("✓ Property test passed: Session info field completeness verified")
        print("  All required fields present across 100 random session configurations")
        print()
        print("  Verified fields:")
        print("    - Base fields: session_id, created_at, last_active, session_type, initialized")
        print("    - Status tracking: last_agent_status")
        print("    - Template versioning: template_version")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("All property-based tests passed! ✓")
