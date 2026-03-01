"""Settings panel component for agent debugger.

This module provides a reusable settings panel component that extends
BaseComponent from dash_interactive.
"""
from typing import Dict, Any, List
from dash import html, dcc
from dash.dependencies import Input, Output

from agent_foundation.ui.dash_interactive.components.base import BaseComponent
from webaxon.devsuite.constants import AGENT_TYPE_DEFAULT, AGENT_TYPE_MOCK_CLARIFICATION


class SettingsPanel(BaseComponent):
    """Settings panel for agent configuration.
    
    This component provides UI for configuring agent type and viewing
    agent status. It extends BaseComponent from dash_interactive.
    """
    
    def __init__(self, component_id: str = "settings-panel"):
        """Initialize the settings panel.
        
        Args:
            component_id: Unique identifier for this component
        """
        super().__init__(component_id)
    
    def _get_default_style(self) -> Dict[str, Any]:
        """Get default styling for the settings panel."""
        return {
            'backgroundColor': '#2C2C2C',
            'padding': '10px',
            'borderRadius': '4px'
        }
    
    def layout(self) -> html.Div:
        """Generate the settings panel layout."""
        return html.Div([
            html.Div(
                children='⚙️ Session Settings',
                style={
                    'fontSize': '11px',
                    'color': '#ECECF1',
                    'marginBottom': '10px',
                    'fontWeight': '600'
                }
            ),
            html.Div([
                html.Label(
                    'Agent Configuration:',
                    style={
                        'fontSize': '10px',
                        'color': '#8E8EA0',
                        'marginBottom': '4px',
                        'display': 'block',
                        'fontWeight': '500'
                    }
                ),
                dcc.Dropdown(
                    id=self.get_id('agent-dropdown'),
                    options=[
                        {'label': 'Default Agent (Full Planning + Web Actions)', 'value': AGENT_TYPE_DEFAULT},
                        {'label': 'Mock Clarification Agent (Simple Testing)', 'value': AGENT_TYPE_MOCK_CLARIFICATION},
                    ],
                    value=AGENT_TYPE_DEFAULT,
                    placeholder='Select agent configuration...',
                    style={
                        'fontSize': '10px',
                        'marginBottom': '8px'
                    },
                    className='agent-dropdown'
                )
            ]),
            html.Button(
                'Apply Changes',
                id=self.get_id('apply-btn'),
                n_clicks=0,
                style={
                    'width': '100%',
                    'padding': '6px 12px',
                    'backgroundColor': '#19C37D',
                    'color': '#FFFFFF',
                    'border': 'none',
                    'borderRadius': '4px',
                    'cursor': 'pointer',
                    'fontSize': '10px',
                    'fontWeight': '500',
                    'marginBottom': '10px',
                    'transition': 'all 0.2s'
                }
            ),
            html.Div([
                html.Div(
                    children='Current Agent:',
                    style={
                        'fontSize': '9px',
                        'color': '#8E8EA0',
                        'marginBottom': '2px',
                        'fontWeight': '500'
                    }
                ),
                html.Div(
                    id=self.get_id('current-agent'),
                    children=AGENT_TYPE_DEFAULT,
                    style={
                        'fontSize': '9px',
                        'color': '#19C37D',
                        'fontFamily': 'monospace',
                        'backgroundColor': 'rgba(0, 0, 0, 0.2)',
                        'padding': '4px 6px',
                        'borderRadius': '3px',
                        'marginBottom': '10px'
                    }
                )
            ]),
            html.Div([
                html.Div(
                    children='Agent Status:',
                    style={
                        'fontSize': '9px',
                        'color': '#8E8EA0',
                        'marginBottom': '2px',
                        'fontWeight': '500'
                    }
                ),
                html.Div(
                    id=self.get_id('agent-status'),
                    children='No status updates',
                    style={
                        'fontSize': '8px',
                        'color': '#ECECF1',
                        'backgroundColor': 'rgba(0, 0, 0, 0.2)',
                        'padding': '4px 6px',
                        'borderRadius': '3px',
                        'marginBottom': '10px',
                        'maxHeight': '60px',
                        'overflowY': 'auto'
                    }
                )
            ]),
            html.Div(
                children='ℹ️ Settings are session-specific',
                style={
                    'fontSize': '8px',
                    'color': '#6E6E80',
                    'fontStyle': 'italic',
                    'textAlign': 'center'
                }
            ),
            # Interval for polling agent status
            dcc.Interval(
                id=self.get_id('status-poll-interval'),
                interval=1000,
                n_intervals=0
            )
        ], style=self.style)
    
    def get_callback_inputs(self) -> List[Input]:
        """Get list of callback inputs."""
        return [
            Input(self.get_id('apply-btn'), 'n_clicks'),
            Input(self.get_id('status-poll-interval'), 'n_intervals')
        ]
    
    def get_callback_outputs(self) -> List[Output]:
        """Get list of callback outputs."""
        return [
            Output(self.get_id('current-agent'), 'children'),
            Output(self.get_id('agent-status'), 'children'),
            Output(self.get_id('agent-dropdown'), 'disabled')
        ]
    
    def register_callbacks(self, app, queue_client, session_manager):
        """Register callbacks for this component.
        
        Args:
            app: Dash app instance
            queue_client: QueueClient for sending messages
            session_manager: SessionManager for session state
        """
        from dash.dependencies import State
        from dash.exceptions import PreventUpdate
        
        @app.callback(
            [
                Output(self.get_id('current-agent'), 'children'),
                Output(self.get_id('apply-btn'), 'children')
            ],
            [Input(self.get_id('apply-btn'), 'n_clicks')],
            [
                State(self.get_id('agent-dropdown'), 'value'),
                State('current-session-store', 'data')
            ],
            prevent_initial_call=True
        )
        def apply_settings(n_clicks, selected_agent, session_id):
            """Apply agent settings when button is clicked."""
            if not n_clicks or not selected_agent or not session_id:
                raise PreventUpdate
            
            # Get session debugger for logging
            session = session_manager.get(session_id)
            debugger = session.debugger if session else None
            
            # Send control message to agent service
            queue_client.sync_session_agent(session_id, selected_agent, debugger)
            
            return selected_agent, '✓ Applied'
