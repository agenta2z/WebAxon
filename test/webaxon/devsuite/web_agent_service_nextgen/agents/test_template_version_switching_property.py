"""Property-based test for template version switching.

This module contains property-based tests using hypothesis to verify
that template version switching occurs before agent creation.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import tempfile

# Add parent directory to path
from hypothesis import given, strategies as st, settings, assume
from webaxon.devsuite.web_agent_service_nextgen.core import AgentFactory, ServiceConfig
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format


# Feature: web-agent-service-modularization, Property 10: Template Version Switching
# Validates: Requirements 4.2
@settings(max_examples=100)
@given(
    agent_type=st.sampled_from(['DefaultAgent', 'MockClarificationAgent']),
    template_version=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
    session_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
)
def test_template_version_switching_before_agent_creation(agent_type, template_version, session_id):
    """Property: For any agent creation with a non-empty template version, 
    the template manager should be switched to that version before the agent is created.
    
    This test verifies that template version switching occurs in the correct order
    as specified in Requirement 4.2. The test ensures that:
    
    1. When a non-empty template version is provided, the template manager is switched
    2. The template switching happens BEFORE the agent creation methods are called
    3. The order of operations is: switch template -> create agent
    4. Empty template versions do not trigger switching
    
    The test uses mocking to verify the order of method calls and ensure that
    template switching always precedes agent instantiation.
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
        
        # Create template manager
        template_manager = TemplateManager(
            templates=str(template_dir),
            template_formatter=handlebars_template_format
        )
        
        # Create service config
        config = ServiceConfig()
        
        # Create agent factory
        factory = AgentFactory(template_manager, config, testcase_root=Path(temp_dir))
        
        # Create mock interactive and logger
        mock_interactive = Mock()
        mock_interactive.session_metadata = {'session_id': session_id}
        mock_logger = Mock()
        
        # Track the order of operations using a list
        operation_order = []
        
        # Mock the template manager's switch method to track when it's called
        original_switch = template_manager.switch
        def tracked_switch(**kwargs):
            operation_order.append(('template_switch', kwargs))
            return original_switch(**kwargs)
        
        # Mock the internal agent creation methods to track when they're called
        def tracked_create_default(interactive, logger):
            operation_order.append(('create_default_agent', None))
            return Mock()
        
        def tracked_create_mock(interactive, logger):
            operation_order.append(('create_mock_agent', None))
            return Mock()
        
        # Apply the mocks
        with patch.object(template_manager, 'switch', side_effect=tracked_switch):
            with patch.object(factory, '_create_default_agent', side_effect=tracked_create_default):
                with patch.object(factory, '_create_mock_agent', side_effect=tracked_create_mock):
                    # Call the factory's create_agent method with a non-empty template version
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
                    assert len(operation_order) > 0, \
                        "At least one operation should have occurred"
                    
                    # Find the template switch operation
                    template_switch_index = None
                    for i, (op_type, op_data) in enumerate(operation_order):
                        if op_type == 'template_switch' and op_data.get('template_version') == template_version:
                            template_switch_index = i
                            break
                    
                    # Verify that template switching occurred
                    assert template_switch_index is not None, \
                        f"Template manager should be switched to version '{template_version}' when provided"
                    
                    # Find the agent creation operation
                    agent_creation_index = None
                    for i, (op_type, op_data) in enumerate(operation_order):
                        if op_type in ('create_default_agent', 'create_mock_agent'):
                            agent_creation_index = i
                            break
                    
                    # Verify that agent creation occurred
                    assert agent_creation_index is not None, \
                        "Agent creation method should have been called"
                    
                    # CRITICAL: Verify that template switching happened BEFORE agent creation
                    assert template_switch_index < agent_creation_index, \
                        f"Template switching (index {template_switch_index}) must occur BEFORE " \
                        f"agent creation (index {agent_creation_index}). " \
                        f"Order of operations: {operation_order}"
                    
                    # Verify the correct agent creation method was called
                    agent_creation_op = operation_order[agent_creation_index][0]
                    if agent_type == 'DefaultAgent':
                        assert agent_creation_op == 'create_default_agent', \
                            f"DefaultAgent should use _create_default_agent, got {agent_creation_op}"
                    elif agent_type == 'MockClarificationAgent':
                        assert agent_creation_op == 'create_mock_agent', \
                            f"MockClarificationAgent should use _create_mock_agent, got {agent_creation_op}"


@settings(max_examples=100)
@given(
    agent_type=st.sampled_from(['DefaultAgent', 'MockClarificationAgent']),
    session_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
)
def test_empty_template_version_no_switching(agent_type, session_id):
    """Property: For any agent creation with an empty template version,
    the template manager should NOT be switched (uses default).
    
    This test verifies that when no template version is specified (empty string),
    the factory does not attempt to switch templates, allowing the default
    template version to be used.
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
        
        # Create template manager
        template_manager = TemplateManager(
            templates=str(template_dir),
            template_formatter=handlebars_template_format
        )
        
        # Create service config
        config = ServiceConfig()
        
        # Create agent factory
        factory = AgentFactory(template_manager, config, testcase_root=Path(temp_dir))
        
        # Create mock interactive and logger
        mock_interactive = Mock()
        mock_interactive.session_metadata = {'session_id': session_id}
        mock_logger = Mock()
        
        # Track template switch calls
        template_switch_calls = []
        original_switch = template_manager.switch
        def tracked_switch(**kwargs):
            template_switch_calls.append(kwargs)
            return original_switch(**kwargs)
        
        # Apply the mock
        with patch.object(template_manager, 'switch', side_effect=tracked_switch):
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
                        f"Template manager should NOT be switched when template_version is empty. " \
                        f"Found {len(template_version_switches)} template_version switches: {template_version_switches}"


if __name__ == '__main__':
    print("Running property-based test for template version switching...")
    print("Testing that template switching occurs BEFORE agent creation...")
    print("Testing with 100 random combinations of agent types and template versions...")
    print()
    
    try:
        # Test 1: Non-empty template versions should trigger switching before creation
        print("Test 1: Template version switching before agent creation")
        test_template_version_switching_before_agent_creation()
        print("✓ Property test passed: Template switching occurs before agent creation")
        print("  Template manager is switched when non-empty version is provided")
        print("  Switching always happens BEFORE agent instantiation")
        print("  Order of operations is verified: switch -> create")
        print()
        
        # Test 2: Empty template versions should not trigger switching
        print("Test 2: Empty template version does not trigger switching")
        test_empty_template_version_no_switching()
        print("✓ Property test passed: Empty template version uses default")
        print("  Template manager is NOT switched when version is empty")
        print("  Default template version is used without explicit switching")
        print()
        
        print("All property-based tests passed! ✓")
        
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
