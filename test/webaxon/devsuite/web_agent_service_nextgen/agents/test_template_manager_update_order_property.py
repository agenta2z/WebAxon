"""Property-based test for template manager update order.

This module contains property-based tests using hypothesis to verify
that template manager updates occur before agent creation.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import tempfile

# Add parent directory to path
from hypothesis import given, strategies as st, settings
from webaxon.devsuite.web_agent_service_nextgen.core import AgentFactory, ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.agents import TemplateManagerWrapper
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format


# Feature: web-agent-service-modularization, Property 41: Template Manager Update Order
# Validates: Requirements 10.5
@settings(max_examples=100, deadline=None)
@given(
    agent_type=st.sampled_from(['DefaultAgent', 'MockClarificationAgent']),
    template_version=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
    session_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
)
def test_template_manager_updated_before_agent_creation(agent_type, template_version, session_id):
    """Property: For any template version switch, the template manager should be 
    updated before the agent is created.
    
    This test verifies that template manager updates occur in the correct order
    as specified in Requirement 10.5. The test ensures that:
    
    1. When a template version is provided, the template manager is updated
    2. The template manager update happens BEFORE any agent creation logic
    3. The order of operations is: update template manager -> create agent
    4. This ordering is maintained for all agent types
    
    The test uses mocking to verify the order of method calls and ensure that
    template manager updates always precede agent instantiation.
    """
    # Create a temporary directory for templates
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir) / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal template files for testing
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            template_file = template_dir / subdir / 'default.hbs'
            template_file.write_text('{{input}}')
        
        # Create template manager wrapper
        template_manager = TemplateManagerWrapper(
            template_dir=template_dir,
            template_formatter=handlebars_template_format
        )
        
        # Create service config
        config = ServiceConfig()

        # Create agent factory
        factory = AgentFactory(template_manager.get_template_manager(), config, testcase_root=Path(temp_dir))

        # Create mock interactive and logger
        mock_interactive = Mock()
        mock_interactive.session_metadata = {'session_id': session_id}
        mock_logger = Mock()

        # Track the order of operations using a list
        operation_order = []

        # Mock the template manager's switch method to track when it's called
        original_switch = template_manager.get_template_manager().switch
        def tracked_switch(**kwargs):
            operation_order.append(('template_manager_switch', kwargs))
            return original_switch(**kwargs)
        
        # Mock the internal agent creation methods to track when they're called
        def tracked_create_default(interactive, logger):
            operation_order.append(('create_default_agent', None))
            return Mock()
        
        def tracked_create_mock(interactive, logger):
            operation_order.append(('create_mock_agent', None))
            return Mock()
        
        # Apply the mocks
        with patch.object(template_manager.get_template_manager(), 'switch', side_effect=tracked_switch):
            with patch.object(factory, '_create_default_agent', side_effect=tracked_create_default):
                with patch.object(factory, '_create_mock_agent', side_effect=tracked_create_mock):
                    # Call the factory's create_agent method with a template version
                    agent = factory.create_agent(
                        interactive=mock_interactive,
                        logger=mock_logger,
                        agent_type=agent_type,
                        template_version=template_version
                    )
                    
                    # Verify that the agent was created
                    assert agent is not None, \
                        "AgentFactory.create_agent should return an agent instance"
                    
                    # Verify that operations occurred
                    assert len(operation_order) >= 2, \
                        f"At least two operations should have occurred (template switch + agent creation), got {len(operation_order)}"
                    
                    # Find the template manager switch operation
                    template_switch_index = None
                    for i, (op_type, op_data) in enumerate(operation_order):
                        if op_type == 'template_manager_switch' and op_data.get('template_version') == template_version:
                            template_switch_index = i
                            break
                    
                    # Verify that template manager switching occurred
                    assert template_switch_index is not None, \
                        f"Template manager should be switched to version '{template_version}' when provided. " \
                        f"Operations: {operation_order}"
                    
                    # Find the agent creation operation
                    agent_creation_index = None
                    for i, (op_type, op_data) in enumerate(operation_order):
                        if op_type in ('create_default_agent', 'create_mock_agent'):
                            agent_creation_index = i
                            break
                    
                    # Verify that agent creation occurred
                    assert agent_creation_index is not None, \
                        f"Agent creation method should have been called. Operations: {operation_order}"
                    
                    # CRITICAL: Verify that template manager update happened BEFORE agent creation
                    assert template_switch_index < agent_creation_index, \
                        f"Template manager update (index {template_switch_index}) must occur BEFORE " \
                        f"agent creation (index {agent_creation_index}). " \
                        f"This ensures agents are created with the correct template version. " \
                        f"Order of operations: {operation_order}"
                    
                    # Verify the correct agent creation method was called
                    agent_creation_op = operation_order[agent_creation_index][0]
                    if agent_type == 'DefaultAgent':
                        assert agent_creation_op == 'create_default_agent', \
                            f"DefaultAgent should use _create_default_agent, got {agent_creation_op}"
                    elif agent_type == 'MockClarificationAgent':
                        assert agent_creation_op == 'create_mock_agent', \
                            f"MockClarificationAgent should use _create_mock_agent, got {agent_creation_op}"


@settings(max_examples=100, deadline=None)
@given(
    agent_type=st.sampled_from(['DefaultAgent', 'MockClarificationAgent']),
    session_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
)
def test_no_template_update_when_version_empty(agent_type, session_id):
    """Property: For any agent creation with an empty template version,
    the template manager should NOT be updated (uses current/default version).
    
    This test verifies that when no template version is specified (empty string),
    the factory does not attempt to update the template manager, allowing the
    current or default template version to be used.
    """
    # Create a temporary directory for templates
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir) / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal template files for testing
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            template_file = template_dir / subdir / 'default.hbs'
            template_file.write_text('{{input}}')
        
        # Create template manager wrapper
        template_manager = TemplateManagerWrapper(
            template_dir=template_dir,
            template_formatter=handlebars_template_format
        )
        
        # Create service config
        config = ServiceConfig()

        # Create agent factory
        factory = AgentFactory(template_manager.get_template_manager(), config, testcase_root=Path(temp_dir))

        # Create mock interactive and logger
        mock_interactive = Mock()
        mock_interactive.session_metadata = {'session_id': session_id}
        mock_logger = Mock()

        # Track template switch calls
        template_switch_calls = []
        original_switch = template_manager.get_template_manager().switch
        def tracked_switch(**kwargs):
            template_switch_calls.append(kwargs)
            return original_switch(**kwargs)
        
        # Apply the mock
        with patch.object(template_manager.get_template_manager(), 'switch', side_effect=tracked_switch):
            with patch.object(factory, '_create_default_agent', return_value=Mock()):
                with patch.object(factory, '_create_mock_agent', return_value=Mock()):
                    # Call the factory's create_agent method with empty template version
                    agent = factory.create_agent(
                        interactive=mock_interactive,
                        logger=mock_logger,
                        agent_type=agent_type,
                        template_version=""  # Empty template version
                    )
                    
                    # Verify that the agent was created
                    assert agent is not None, \
                        "AgentFactory.create_agent should return an agent instance"
                    
                    # Verify that template switching was NOT called with template_version parameter
                    # (The factory should skip the switch when template_version is empty)
                    template_version_switches = [
                        call for call in template_switch_calls 
                        if 'template_version' in call
                    ]
                    
                    assert len(template_version_switches) == 0, \
                        f"Template manager should NOT be updated when template_version is empty. " \
                        f"Found {len(template_version_switches)} template_version switches: {template_version_switches}"


@settings(max_examples=100, deadline=None)
@given(
    template_version1=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
    template_version2=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
    session_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
)
def test_template_manager_updated_for_each_agent_creation(template_version1, template_version2, session_id):
    """Property: For any sequence of agent creations with different template versions,
    the template manager should be updated before each agent creation.
    
    This test verifies that when creating multiple agents with different template
    versions, the template manager is correctly updated before each agent creation,
    ensuring each agent uses the correct template version.
    """
    # Skip if template versions are the same (we want to test different versions)
    from hypothesis import assume
    assume(template_version1 != template_version2)
    # Create a temporary directory for templates
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir) / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal template files for testing
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            template_file = template_dir / subdir / 'default.hbs'
            template_file.write_text('{{input}}')
        
        # Create template manager wrapper
        template_manager = TemplateManagerWrapper(
            template_dir=template_dir,
            template_formatter=handlebars_template_format
        )
        
        # Create service config
        config = ServiceConfig()

        # Create agent factory
        factory = AgentFactory(template_manager.get_template_manager(), config, testcase_root=Path(temp_dir))

        # Create mock interactive and logger
        mock_interactive = Mock()
        mock_interactive.session_metadata = {'session_id': session_id}
        mock_logger = Mock()

        # Track the order of operations using a list
        operation_order = []

        # Mock the template manager's switch method to track when it's called
        original_switch = template_manager.get_template_manager().switch
        def tracked_switch(**kwargs):
            operation_order.append(('template_manager_switch', kwargs.copy()))
            return original_switch(**kwargs)
        
        # Mock the internal agent creation methods to track when they're called
        def tracked_create_default(interactive, logger):
            operation_order.append(('create_default_agent', None))
            return Mock()
        
        # Apply the mocks
        with patch.object(template_manager.get_template_manager(), 'switch', side_effect=tracked_switch):
            with patch.object(factory, '_create_default_agent', side_effect=tracked_create_default):
                # Create first agent with template_version1
                agent1 = factory.create_agent(
                    interactive=mock_interactive,
                    logger=mock_logger,
                    agent_type='DefaultAgent',
                    template_version=template_version1
                )
                
                # Create second agent with template_version2
                agent2 = factory.create_agent(
                    interactive=mock_interactive,
                    logger=mock_logger,
                    agent_type='DefaultAgent',
                    template_version=template_version2
                )
                
                # Verify both agents were created
                assert agent1 is not None, "First agent should be created"
                assert agent2 is not None, "Second agent should be created"
                
                # Find all template switches and agent creations
                template_switches = [
                    (i, op_data) for i, (op_type, op_data) in enumerate(operation_order)
                    if op_type == 'template_manager_switch' and 'template_version' in op_data
                ]
                agent_creations = [
                    i for i, (op_type, op_data) in enumerate(operation_order)
                    if op_type == 'create_default_agent'
                ]
                
                # Verify we have at least 2 template switches and 2 agent creations
                assert len(template_switches) >= 2, \
                    f"Should have at least 2 template switches, got {len(template_switches)}"
                assert len(agent_creations) >= 2, \
                    f"Should have at least 2 agent creations, got {len(agent_creations)}"
                
                # Verify first template switch happens before first agent creation
                first_switch_idx = template_switches[0][0]
                first_creation_idx = agent_creations[0]
                assert first_switch_idx < first_creation_idx, \
                    f"First template switch (index {first_switch_idx}) must occur before " \
                    f"first agent creation (index {first_creation_idx})"
                
                # Verify second template switch happens before second agent creation
                second_switch_idx = template_switches[1][0]
                second_creation_idx = agent_creations[1]
                assert second_switch_idx < second_creation_idx, \
                    f"Second template switch (index {second_switch_idx}) must occur before " \
                    f"second agent creation (index {second_creation_idx})"
                
                # Verify the template versions were correct
                assert template_switches[0][1]['template_version'] == template_version1, \
                    f"First switch should use template_version1: {template_version1}"
                assert template_switches[1][1]['template_version'] == template_version2, \
                    f"Second switch should use template_version2: {template_version2}"


if __name__ == '__main__':
    print("Running property-based test for template manager update order...")
    print("Testing that template manager is updated BEFORE agent creation...")
    print("Testing with 100 random combinations of agent types and template versions...")
    print()
    
    try:
        # Test 1: Template manager updated before agent creation
        print("Test 1: Template manager updated before agent creation")
        test_template_manager_updated_before_agent_creation()
        print("✓ Property test passed: Template manager is updated before agent creation")
        print("  Template manager is switched when template version is provided")
        print("  Switching always happens BEFORE agent instantiation")
        print("  Order of operations is verified: update template -> create agent")
        print()
        
        # Test 2: No template update when version is empty
        print("Test 2: No template update when version is empty")
        test_no_template_update_when_version_empty()
        print("✓ Property test passed: Empty template version uses current version")
        print("  Template manager is NOT updated when version is empty")
        print("  Current/default template version is used without explicit update")
        print()
        
        # Test 3: Template manager updated for each agent creation
        print("Test 3: Template manager updated for each agent creation")
        test_template_manager_updated_for_each_agent_creation()
        print("✓ Property test passed: Template manager updated for each agent")
        print("  Multiple agents with different versions each trigger updates")
        print("  Each update happens before its corresponding agent creation")
        print("  Template versions are correctly applied in sequence")
        print()
        
        print("All property-based tests passed! ✓")
        
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
