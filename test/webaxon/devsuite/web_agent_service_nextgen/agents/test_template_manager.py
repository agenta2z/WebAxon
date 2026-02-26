"""Tests for TemplateManagerWrapper.

This module tests the template manager wrapper functionality including:
- Initialization
- Version switching
- Version tracking
- Access to underlying TemplateManager
"""
import sys
import resolve_path  # Setup import paths

import tempfile
from pathlib import Path

# Add parent directory to path for imports
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from webaxon.devsuite.web_agent_service_nextgen.agents.template_manager import TemplateManagerWrapper


def test_initialization():
    """Test TemplateManagerWrapper initialization."""
    print("Testing TemplateManagerWrapper initialization...")
    
    # Create a temporary directory for templates
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)

        # Create proper subdirectory structure for TemplateManager
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')

        # Create wrapper
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)
        
        # Verify initial state
        assert wrapper.get_current_version() == "", "Initial version should be empty string"
        assert wrapper.get_template_manager() is not None, "Should have underlying TemplateManager"
        
        print("✓ Initialization test passed")


def test_version_switching():
    """Test template version switching."""
    print("\nTesting version switching...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)

        # Test switching to a version
        wrapper.switch_version('v2.1')
        assert wrapper.get_current_version() == 'v2.1', "Version should be updated to v2.1"
        
        # Test switching to another version
        wrapper.switch_version('experimental')
        assert wrapper.get_current_version() == 'experimental', "Version should be updated to experimental"
        
        # Test switching to empty string (default)
        wrapper.switch_version('')
        assert wrapper.get_current_version() == '', "Version should be reset to empty string"
        
        print("✓ Version switching test passed")


def test_version_tracking():
    """Test that version tracking persists across operations."""
    print("\nTesting version tracking...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)

        # Set a version
        wrapper.switch_version('v1.0')
        
        # Perform other operations
        tm = wrapper.get_template_manager()
        assert tm is not None
        
        # Version should still be tracked
        assert wrapper.get_current_version() == 'v1.0', "Version should persist after getting template manager"
        
        print("✓ Version tracking test passed")


def test_underlying_manager_access():
    """Test access to underlying TemplateManager."""
    print("\nTesting underlying manager access...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)

        # Get underlying manager
        tm = wrapper.get_template_manager()
        
        # Verify it's a TemplateManager
        from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
        assert isinstance(tm, TemplateManager), "Should return TemplateManager instance"
        
        print("✓ Underlying manager access test passed")


def test_switch_delegation():
    """Test that switch() method delegates to underlying TemplateManager."""
    print("\nTesting switch delegation...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)

        # Test that switch() returns TemplateManager
        result = wrapper.switch(active_template_root_space='test_space')
        
        from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
        assert isinstance(result, TemplateManager), "switch() should return TemplateManager"
        
        print("✓ Switch delegation test passed")


def test_version_switching_returns_manager():
    """Test that switch_version returns TemplateManager for chaining."""
    print("\nTesting switch_version return value...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)

        # Test that switch_version returns TemplateManager
        result = wrapper.switch_version('v2.0')
        
        from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
        assert isinstance(result, TemplateManager), "switch_version() should return TemplateManager"
        
        print("✓ Switch version return value test passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing TemplateManagerWrapper")
    print("=" * 60)
    
    test_initialization()
    test_version_switching()
    test_version_tracking()
    test_underlying_manager_access()
    test_switch_delegation()
    test_version_switching_returns_manager()
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)


if __name__ == '__main__':
    main()
