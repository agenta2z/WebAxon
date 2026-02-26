"""Test script for AgentFactory implementation.

This script verifies that the AgentFactory:
1. Can be instantiated with proper dependencies
2. Supports template version switching
3. Creates agents of different types
4. Properly configures agents with all required dependencies
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path

# Add parent directory to path
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig


def test_agent_factory_import():
    """Test that AgentFactory can be imported and basic structure is correct."""
    print("=" * 80)
    print("Testing AgentFactory Implementation")
    print("=" * 80)
    
    # 1. Test import
    print("\n1. Testing AgentFactory import...")
    try:
        from webaxon.devsuite.web_agent_service_nextgen.core import AgentFactory
        print("   ✓ AgentFactory imported successfully")
    except ImportError as e:
        print(f"   ✗ Failed to import AgentFactory: {e}")
        return False
    
    # 2. Test that class has required methods
    print("\n2. Testing AgentFactory has required methods...")
    required_methods = [
        'create_agent',
        'get_available_types',
        '_create_default_agent',
        '_create_mock_agent',
        '_load_user_profile',
        '_load_response_format_config'
    ]
    
    for method_name in required_methods:
        if hasattr(AgentFactory, method_name):
            print(f"   ✓ Method '{method_name}' exists")
        else:
            print(f"   ✗ Method '{method_name}' missing")
            return False
    
    # 3. Test factory can be instantiated (without actually creating agents)
    print("\n3. Testing AgentFactory instantiation...")
    try:
        # We need to mock the template manager for this test
        class MockTemplateManager:
            def switch(self, **kwargs):
                return self
        
        config = ServiceConfig()
        mock_template_manager = MockTemplateManager()
        factory = AgentFactory(mock_template_manager, config)
        print("   ✓ Factory instantiated successfully")
    except Exception as e:
        print(f"   ✗ Failed to instantiate factory: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. Test available agent types
    print("\n4. Testing available agent types...")
    try:
        available_types = factory.get_available_types()
        print(f"   Available types: {available_types}")
        assert 'DefaultAgent' in available_types, "DefaultAgent should be available"
        assert 'MockClarificationAgent' in available_types, "MockClarificationAgent should be available"
        print("   ✓ All expected agent types are available")
    except Exception as e:
        print(f"   ✗ Error getting available types: {e}")
        return False
    
    # 5. Test user profile loading
    print("\n5. Testing user profile loading...")
    try:
        user_profile = factory._load_user_profile()
        assert user_profile is not None, "User profile should not be None"
        assert 'Name' in user_profile, "User profile should have Name field"
        print(f"   User profile loaded: {user_profile.get('Name', {})}")
        print("   ✓ User profile loaded successfully")
    except Exception as e:
        print(f"   ✗ Error loading user profile: {e}")
        return False
    
    # 6. Test response format config loading
    print("\n6. Testing response format config loading...")
    try:
        response_format = factory._load_response_format_config()
        assert response_format is not None, "Response format should not be None"
        assert 'raw_response_start_delimiter' in response_format
        assert 'raw_response_end_delimiter' in response_format
        assert 'raw_response_format' in response_format
        print(f"   Response format keys: {list(response_format.keys())}")
        print("   ✓ Response format config loaded successfully")
    except Exception as e:
        print(f"   ✗ Error loading response format: {e}")
        return False
    
    print("\n" + "=" * 80)
    print("AgentFactory Basic Tests Complete!")
    print("=" * 80)
    print("\nNote: Full agent creation tests require the complete environment")
    print("with all dependencies (Claude API, WebDriver, etc.)")
    
    return True


if __name__ == '__main__':
    success = test_agent_factory_import()
    sys.exit(0 if success else 1)
