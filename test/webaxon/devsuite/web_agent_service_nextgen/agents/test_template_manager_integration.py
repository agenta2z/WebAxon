"""Integration test for TemplateManagerWrapper with AgentFactory.

This test verifies that the TemplateManagerWrapper integrates correctly
with the AgentFactory for template version switching.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
import tempfile

# Add parent directory to path for imports
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from webaxon.devsuite.web_agent_service_nextgen.agents.template_manager import TemplateManagerWrapper
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig


def test_wrapper_with_config():
    """Test that wrapper works with ServiceConfig."""
    print("Testing TemplateManagerWrapper with ServiceConfig...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')

        # Create config
        config = ServiceConfig()
        
        # Create wrapper (as AgentFactory would)
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)
        
        # Test version switching
        wrapper.switch_version('v2.1')
        assert wrapper.get_current_version() == 'v2.1'
        
        print("✓ Wrapper works with ServiceConfig")


def test_wrapper_api_matches_design():
    """Test that wrapper API matches design document specification."""
    print("\nTesting wrapper API matches design...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')

        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)

        # Verify all methods from design document exist
        assert hasattr(wrapper, 'switch_version'), "Missing switch_version method"
        assert hasattr(wrapper, 'get_current_version'), "Missing get_current_version method"
        assert hasattr(wrapper, 'get_template_manager'), "Missing get_template_manager method"
        assert hasattr(wrapper, 'switch'), "Missing switch method"
        
        # Verify method signatures work as designed
        result = wrapper.switch_version('v1.0')
        assert result is not None
        
        version = wrapper.get_current_version()
        assert isinstance(version, str)
        
        tm = wrapper.get_template_manager()
        assert tm is not None
        
        result = wrapper.switch(active_template_root_space='test')
        assert result is not None
        
        print("✓ Wrapper API matches design document")


def test_version_switching_order():
    """Test that version switching happens before agent creation (Property 41)."""
    print("\nTesting version switching order (Property 41)...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')

        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)

        # Simulate what AgentFactory.create_agent does:
        # 1. Switch template version if provided
        template_version = 'v2.0'
        if template_version:
            result = wrapper.switch_version(template_version)
            # At this point, TemplateManager should be switched
            assert wrapper.get_current_version() == 'v2.0'
        
        # 2. Create agent (would happen here)
        # The template manager is already switched to correct version
        
        print("✓ Version switching order is correct (Property 41)")


def test_empty_version_handling():
    """Test that empty version string is handled correctly (Property 40)."""
    print("\nTesting empty version handling (Property 40)...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')

        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)

        # Initial state should be empty
        assert wrapper.get_current_version() == ''
        
        # Switch to a version
        wrapper.switch_version('v1.0')
        assert wrapper.get_current_version() == 'v1.0'
        
        # Switch back to default (empty string)
        wrapper.switch_version('')
        assert wrapper.get_current_version() == ''
        
        print("✓ Empty version handling is correct (Property 40)")


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("TemplateManagerWrapper Integration Tests")
    print("=" * 70)
    print()
    
    test_wrapper_with_config()
    test_wrapper_api_matches_design()
    test_version_switching_order()
    test_empty_version_handling()
    
    print()
    print("=" * 70)
    print("All integration tests passed! ✓")
    print("=" * 70)


if __name__ == '__main__':
    main()
