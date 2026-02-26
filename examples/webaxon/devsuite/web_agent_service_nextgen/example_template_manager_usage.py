"""Example usage of TemplateManagerWrapper in the web agent service.

This demonstrates how the TemplateManagerWrapper integrates with other
components in the modularized service architecture.
"""
import resolve_path  # Sets up Python path for webaxon imports
from pathlib import Path
import tempfile

from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from webaxon.devsuite.web_agent_service_nextgen.agents.template_manager import TemplateManagerWrapper
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig


def example_basic_usage():
    """Example: Basic template manager wrapper usage."""
    print("Example 1: Basic Usage")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        (template_dir / 'test.txt').write_text('test')
        
        # Create wrapper
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)
        
        # Check initial version (default)
        print(f"Initial version: '{wrapper.get_current_version()}'")
        
        # Switch to a specific version
        wrapper.switch_version('v2.1')
        print(f"After switch: '{wrapper.get_current_version()}'")
        
        # Get underlying manager for advanced operations
        tm = wrapper.get_template_manager()
        print(f"Underlying manager: {type(tm).__name__}")
    
    print()


def example_agent_factory_integration():
    """Example: How AgentFactory would use the wrapper."""
    print("Example 2: AgentFactory Integration")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        (template_dir / 'test.txt').write_text('test')
        
        # Simulate AgentFactory initialization
        config = ServiceConfig()
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)
        
        print("AgentFactory initialized with TemplateManagerWrapper")
        
        # Simulate agent creation with template version
        def create_agent_with_version(template_version: str):
            """Simulate AgentFactory.create_agent()."""
            print(f"\nCreating agent with template version: '{template_version}'")
            
            # Switch template version if provided
            if template_version:
                wrapper.switch_version(template_version)
                print(f"  → Template manager switched to: '{wrapper.get_current_version()}'")
            else:
                print(f"  → Using default template version")
            
            # Agent would be created here with the switched template manager
            print(f"  → Agent created successfully")
        
        # Create agents with different versions
        create_agent_with_version('v2.0')
        create_agent_with_version('experimental')
        create_agent_with_version('')  # Default version
    
    print()


def example_session_template_versioning():
    """Example: Per-session template versioning."""
    print("Example 3: Per-Session Template Versioning")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        (template_dir / 'test.txt').write_text('test')
        
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)
        
        # Simulate multiple sessions with different template versions
        sessions = {
            'session1': 'v2.0',
            'session2': 'v2.1',
            'session3': '',  # default
        }
        
        print("Creating agents for multiple sessions:")
        for session_id, template_version in sessions.items():
            print(f"\n  Session: {session_id}")
            print(f"    Template version: '{template_version or 'default'}'")
            
            # Switch to session's template version
            wrapper.switch_version(template_version)
            print(f"    Current version: '{wrapper.get_current_version()}'")
            
            # Agent would be created here
            print(f"    Agent created for {session_id}")
    
    print()


def example_template_operations():
    """Example: Using template manager operations through wrapper."""
    print("Example 4: Template Manager Operations")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        (template_dir / 'test.txt').write_text('test')
        
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)
        
        # Version switching
        print("1. Version switching:")
        wrapper.switch_version('v2.0')
        print(f"   Current version: {wrapper.get_current_version()}")
        
        # Direct template manager operations via delegation
        print("\n2. Template space switching (via delegation):")
        tm = wrapper.switch(active_template_root_space='response_agent')
        print(f"   Switched to response_agent space")
        print(f"   Still tracking version: {wrapper.get_current_version()}")
        
        # Get underlying manager for complex operations
        print("\n3. Direct access to underlying manager:")
        tm = wrapper.get_template_manager()
        print(f"   Got TemplateManager: {type(tm).__name__}")
        print(f"   Version still tracked: {wrapper.get_current_version()}")
    
    print()


def example_version_tracking_benefits():
    """Example: Benefits of version tracking."""
    print("Example 5: Version Tracking Benefits")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        template_dir = Path(temp_dir)
        (template_dir / 'test.txt').write_text('test')
        
        wrapper = TemplateManagerWrapper(template_dir, handlebars_template_format)
        
        # Simulate logging/debugging scenario
        def log_agent_creation(session_id: str, template_version: str):
            """Simulate logging during agent creation."""
            wrapper.switch_version(template_version)
            
            # With version tracking, we can log which version is being used
            current_version = wrapper.get_current_version()
            print(f"[LOG] Creating agent for {session_id}")
            print(f"      Template version: '{current_version or 'default'}'")
            print(f"      Timestamp: 2024-01-15 10:30:00")
        
        print("Logging agent creation with version tracking:\n")
        log_agent_creation('session_abc', 'v2.1')
        print()
        log_agent_creation('session_xyz', '')
        
        print("\nBenefit: Easy to debug which template version each agent uses!")
    
    print()


def main():
    """Run all examples."""
    print("=" * 70)
    print("TemplateManagerWrapper Usage Examples")
    print("=" * 70)
    print()
    
    example_basic_usage()
    example_agent_factory_integration()
    example_session_template_versioning()
    example_template_operations()
    example_version_tracking_benefits()
    
    print("=" * 70)
    print("Examples complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
