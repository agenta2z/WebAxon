"""
Test that Action Tester is correctly located in the main tabs.

Verifies that Action Tester has been moved from the Monitor panel to the main horizontal tabs.
"""
import sys
from pathlib import Path

# Add paths for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "SciencePythonUtils" / "src"))
sys.path.insert(0, str(project_root / "ScienceModelingTools" / "src"))

import pytest
from unittest.mock import Mock, MagicMock, patch


class TestMainTabLocation:
    """Test Action Tester main tab location."""
    
    def test_tabbed_panel_supports_custom_main_tabs(self):
        """Test that TabbedPanel now supports custom_main_tabs parameter."""
        from science_modeling_tools.ui.dash_interactive.components.tabbed_panel import TabbedPanel
        
        # Test that TabbedPanel accepts custom_main_tabs parameter
        custom_main_tabs = [
            {
                'id': 'test-tab',
                'label': '🧪 Test Tab',
                'content': []
            }
        ]
        
        # Should not raise an error
        panel = TabbedPanel(
            component_id="test-panel",
            custom_main_tabs=custom_main_tabs
        )
        
        assert panel.custom_main_tabs == custom_main_tabs
        assert hasattr(panel, 'custom_main_tabs')
    
    def test_tabbed_panel_creates_custom_main_tab_buttons(self):
        """Test that TabbedPanel creates buttons for custom main tabs."""
        from science_modeling_tools.ui.dash_interactive.components.tabbed_panel import TabbedPanel
        
        custom_main_tabs = [
            {
                'id': 'action-tester',
                'label': '🧪 Action Tester',
                'content': []
            }
        ]
        
        panel = TabbedPanel(
            component_id="main-panel",
            custom_main_tabs=custom_main_tabs
        )
        
        # Create the tab buttons
        tab_buttons = panel._create_tab_buttons()
        
        # Convert to string to search for the Action Tester button
        buttons_str = str(tab_buttons)
        
        # Should contain the Action Tester button
        assert '🧪 Action Tester' in buttons_str
        assert 'main-panel-action-tester-btn' in buttons_str
    
    def test_tabbed_panel_creates_custom_main_tab_content(self):
        """Test that TabbedPanel creates content divs for custom main tabs."""
        from science_modeling_tools.ui.dash_interactive.components.tabbed_panel import TabbedPanel
        from dash import html
        
        test_content = html.Div("Test Action Tester Content")
        
        custom_main_tabs = [
            {
                'id': 'action-tester',
                'label': '🧪 Action Tester',
                'content': test_content
            }
        ]
        
        panel = TabbedPanel(
            component_id="main-panel",
            custom_main_tabs=custom_main_tabs
        )
        
        # Create the layout
        layout = panel.layout()
        
        # Search for the Action Tester tab content div
        found_action_tester_tab = False
        
        def search_component(component, target_id):
            nonlocal found_action_tester_tab
            if hasattr(component, 'id') and component.id == target_id:
                found_action_tester_tab = True
                return
            if hasattr(component, 'children'):
                children = component.children
                if isinstance(children, list):
                    for child in children:
                        search_component(child, target_id)
                elif children is not None:
                    search_component(children, target_id)
        
        search_component(layout, 'main-panel-action-tester-tab')
        
        assert found_action_tester_tab, "Layout should contain main-panel-action-tester-tab div"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
