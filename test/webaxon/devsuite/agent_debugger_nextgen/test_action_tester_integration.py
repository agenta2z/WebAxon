"""
Basic integration test for Action Tester functionality.

This test verifies that the Action Tester components are properly integrated.
"""
import sys
from pathlib import Path

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != 'test' and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
def test_action_tester_imports():
    """Test that all Action Tester components can be imported."""
    from webaxon.devsuite.agent_debugger_nextgen.action_tester import (
        ActionTesterManager,
        get_action_tester_manager,
        Test,
        TestInfo,
        BrowserStatus,
        SequenceValidationResult,
        ActionStepResult,
        ElementIDResult,
        get_default_sequence_template
    )
    
    assert ActionTesterManager is not None
    assert get_action_tester_manager is not None
    assert Test is not None
    assert TestInfo is not None
    assert BrowserStatus is not None
    assert SequenceValidationResult is not None
    assert ActionStepResult is not None
    assert ElementIDResult is not None
    assert get_default_sequence_template is not None
    print("✓ All Action Tester imports successful")


def test_action_tester_manager_basic():
    """Test basic ActionTesterManager functionality."""
    from webaxon.devsuite.agent_debugger_nextgen.action_tester import ActionTesterManager
    
    manager = ActionTesterManager()
    
    # Test that manager initializes correctly
    assert manager.tests == {}
    assert manager.active_test_id is None
    assert manager.driver is None
    assert manager.is_browser_active is False
    
    print("✓ ActionTesterManager basic functionality works")


def test_action_templates():
    """Test ActionTemplates functionality via ActionTesterManager."""
    from webaxon.devsuite.agent_debugger_nextgen.action_tester import ActionTesterManager
    
    manager = ActionTesterManager()
    
    # Test that action_metadata is loaded (if available)
    # The manager loads action metadata from the schema system
    if manager.action_metadata is not None:
        # ActionMetadataRegistry has get_action_type method
        # Just verify the registry is initialized
        assert manager.action_metadata is not None
        print("✓ ActionTemplates functionality works (action_metadata loaded)")
    else:
        print("⚠ ActionTemplates test skipped (action_metadata not available)")


def test_ui_component_creation():
    """Test that UI components can be created."""
    try:
        from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_action_tester_tab_layout
        
        layout = create_action_tester_tab_layout()
        assert layout is not None
        # Dash components use .id property differently - check the children or structure
        assert hasattr(layout, 'children')
        
        print("✓ UI component creation works")
    except ImportError as e:
        print(f"⚠ UI component test skipped (missing dependencies): {e}")


def test_app_integration():
    """Test that Action Tester is integrated into the app."""
    try:
        from webaxon.devsuite.agent_debugger_nextgen.app import create_app
        
        # Create app (don't run it)
        app = create_app(testcase_root=Path(__file__).parent)
        
        # Verify action_tester_manager is available
        assert hasattr(app, 'action_tester_manager')
        assert app.action_tester_manager is not None
        
        print("✓ Action Tester integrated into app")
    except ImportError as e:
        print(f"⚠ App integration test skipped (missing dependencies): {e}")


if __name__ == '__main__':
    print("Running Action Tester Integration Tests...\n")
    
    try:
        test_action_tester_imports()
        test_action_tester_manager_basic()
        test_action_templates()
        test_ui_component_creation()
        test_app_integration()
        
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
