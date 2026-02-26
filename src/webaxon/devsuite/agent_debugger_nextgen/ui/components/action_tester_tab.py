"""
Action Tester Tab UI Component

Provides the split-panel layout for the Action Tester tab.
Left panel (60%): Browser controls, JSON editor, execution results
Right panel (40%): Action reference documentation

Styling is provided by action_tester_styles.css in the ui/assets folder.
"""
from dash import html, dcc
from typing import List, Dict, Any


def create_loading_spinner() -> html.Span:
    """Create a loading spinner element."""
    return html.Span(className='loading-spinner')


def create_action_tester_tab_layout() -> html.Div:
    """
    Create Action Tester tab with split-panel layout.
    
    Returns:
        html.Div containing:
        - Left panel (60%): Browser controls, JSON editor, execution results
        - Right panel (40%): Action reference documentation
        - dcc.Interval for browser status refresh (2 seconds)
    """
    return html.Div(
        # Note: ID is set by TabbedPanel wrapper, not here
        children=[
            # Split panel container
            html.Div(
                children=[
                    # LEFT PANEL (60%) - Editor and Controls
                    html.Div(
                        id='action-tester-left-panel',
                        children=[
                            # Browser Controls Section
                            html.Div(
                                children=[
                                    html.Div(
                                        children='🌐 Browser Controls',
                                        className='section-header',
                                        style={
                                            'fontSize': '14px',
                                            'fontWeight': '600',
                                            'color': '#ECECF1',
                                            'marginBottom': '12px'
                                        }
                                    ),
                                    # Profile selection dropdown with copy checkbox
                                    html.Div(
                                        children=[
                                            html.Label(
                                                'Chrome Profile:',
                                                style={
                                                    'color': '#ECECF1',
                                                    'fontSize': '12px',
                                                    'marginBottom': '4px',
                                                    'display': 'block'
                                                }
                                            ),
                                            html.Div(
                                                children=[
                                                    dcc.Dropdown(
                                                        id='chrome-profile-dropdown',
                                                        options=[],  # Will be populated dynamically
                                                        value='Default',  # Default selection
                                                        placeholder='Select a Chrome profile...',
                                                        style={
                                                            'fontSize': '12px',
                                                            'flex': '1'
                                                        },
                                                        className='action-tester-dropdown'
                                                    ),
                                                    dcc.Checklist(
                                                        id='copy-profile-checkbox',
                                                        options=[{'label': ' Copy profile', 'value': 'copy'}],
                                                        value=['copy'],  # Default to copying
                                                        style={
                                                            'color': '#ECECF1',
                                                            'fontSize': '11px',
                                                            'marginLeft': '8px',
                                                            'display': 'flex',
                                                            'alignItems': 'center'
                                                        }
                                                    )
                                                ],
                                                style={
                                                    'display': 'flex',
                                                    'alignItems': 'center',
                                                    'gap': '4px'
                                                }
                                            )
                                        ],
                                        style={'marginBottom': '12px'}
                                    ),
                                    html.Div(
                                        children=[
                                            html.Button(
                                                '🚀 Launch Browser',
                                                id='action-tester-launch-btn',
                                                n_clicks=0,
                                                style={
                                                    'padding': '8px 16px',
                                                    'backgroundColor': '#19C37D',
                                                    'color': '#FFFFFF',
                                                    'border': 'none',
                                                    'borderRadius': '4px',
                                                    'cursor': 'pointer',
                                                    'fontSize': '12px',
                                                    'fontWeight': '500',
                                                    'marginRight': '8px'
                                                }
                                            ),
                                            html.Button(
                                                '❌ Close Browser',
                                                id='action-tester-close-btn',
                                                n_clicks=0,
                                                style={
                                                    'padding': '8px 16px',
                                                    'backgroundColor': '#FF6B6B',
                                                    'color': '#FFFFFF',
                                                    'border': 'none',
                                                    'borderRadius': '4px',
                                                    'cursor': 'pointer',
                                                    'fontSize': '12px',
                                                    'fontWeight': '500',
                                                    'marginRight': '8px'
                                                }
                                            ),
                                            html.Button(
                                                '🏷️ Assign __id__',
                                                id='action-tester-assign-ids-btn',
                                                n_clicks=0,
                                                style={
                                                    'padding': '8px 16px',
                                                    'backgroundColor': '#4A9EFF',
                                                    'color': '#FFFFFF',
                                                    'border': 'none',
                                                    'borderRadius': '4px',
                                                    'cursor': 'pointer',
                                                    'fontSize': '12px',
                                                    'fontWeight': '500'
                                                }
                                            )
                                        ],
                                        style={'marginBottom': '12px'}
                                    ),
                                    # Browser Status
                                    html.Div(
                                        id='browser-status-indicator',
                                        children='🔴 Not Active',
                                        style={
                                            'fontSize': '12px',
                                            'color': '#8E8EA0',
                                            'fontFamily': 'monospace',
                                            'padding': '8px',
                                            'backgroundColor': 'rgba(0, 0, 0, 0.2)',
                                            'borderRadius': '4px',
                                            'marginBottom': '8px'
                                        }
                                    ),
                                    # Status details
                                    html.Div(
                                        children=[
                                            html.Div(
                                                id='browser-window-count',
                                                children='0 tab(s) open',
                                                style={'fontSize': '11px', 'color': '#8E8EA0', 'marginBottom': '4px'}
                                            ),
                                            html.Div(
                                                id='browser-active-window',
                                                children='None',
                                                style={'fontSize': '11px', 'color': '#8E8EA0', 'marginBottom': '4px'}
                                            ),
                                            html.Div(
                                                id='browser-current-url',
                                                children='—',
                                                style={'fontSize': '11px', 'color': '#8E8EA0', 'wordBreak': 'break-all'}
                                            )
                                        ]
                                    ),
                                    # ID assignment result
                                    html.Div(
                                        id='assign-ids-result',
                                        children='',
                                        style={
                                            'fontSize': '11px',
                                            'color': '#19C37D',
                                            'marginTop': '8px',
                                            'display': 'none'
                                        }
                                    )
                                ],
                                style={
                                    'padding': '16px',
                                    'backgroundColor': '#40414F',
                                    'borderRadius': '6px',
                                    'marginBottom': '16px'
                                }
                            ),
                            
                            # JSON Editor Section
                            html.Div(
                                children=[
                                    html.Div(
                                        children='📝 Action Sequence Editor',
                                        className='section-header',
                                        style={
                                            'fontSize': '14px',
                                            'fontWeight': '600',
                                            'color': '#ECECF1',
                                            'marginBottom': '12px'
                                        }
                                    ),
                                    # Editor buttons
                                    html.Div(
                                        children=[
                                            html.Button(
                                                '▶️ Run Sequence',
                                                id='run-sequence-btn',
                                                n_clicks=0,
                                                style={
                                                    'padding': '8px 16px',
                                                    'backgroundColor': '#19C37D',
                                                    'color': '#FFFFFF',
                                                    'border': 'none',
                                                    'borderRadius': '4px',
                                                    'cursor': 'pointer',
                                                    'fontSize': '12px',
                                                    'fontWeight': '500',
                                                    'marginRight': '8px'
                                                }
                                            ),
                                            html.Button(
                                                '✓ Validate JSON',
                                                id='validate-json-btn',
                                                n_clicks=0,
                                                style={
                                                    'padding': '8px 16px',
                                                    'backgroundColor': '#4A9EFF',
                                                    'color': '#FFFFFF',
                                                    'border': 'none',
                                                    'borderRadius': '4px',
                                                    'cursor': 'pointer',
                                                    'fontSize': '12px',
                                                    'fontWeight': '500',
                                                    'marginRight': '8px'
                                                }
                                            ),
                                            html.Button(
                                                '📄 Load Template',
                                                id='load-template-btn',
                                                n_clicks=0,
                                                style={
                                                    'padding': '8px 16px',
                                                    'backgroundColor': '#8E8EA0',
                                                    'color': '#FFFFFF',
                                                    'border': 'none',
                                                    'borderRadius': '4px',
                                                    'cursor': 'pointer',
                                                    'fontSize': '12px',
                                                    'fontWeight': '500'
                                                }
                                            )
                                        ],
                                        style={'marginBottom': '12px'}
                                    ),
                                    # JSON Editor (Textarea)
                                    dcc.Textarea(
                                        id='action-sequence-editor',
                                        value='',
                                        placeholder='Enter action sequence JSON here...',
                                        style={
                                            'width': '100%',
                                            'height': '400px',
                                            'padding': '12px',
                                            'backgroundColor': '#2C2D3A',
                                            'color': '#ECECF1',
                                            'border': '1px solid #565869',
                                            'borderRadius': '4px',
                                            'fontSize': '12px',
                                            'fontFamily': 'monospace',
                                            'resize': 'vertical'
                                        }
                                    )
                                ],
                                style={
                                    'padding': '16px',
                                    'backgroundColor': '#40414F',
                                    'borderRadius': '6px',
                                    'marginBottom': '16px'
                                }
                            ),
                            
                            # Execution Results Section
                            html.Div(
                                children=[
                                    html.Div(
                                        children='📊 Execution Results',
                                        className='section-header',
                                        style={
                                            'fontSize': '14px',
                                            'fontWeight': '600',
                                            'color': '#ECECF1',
                                            'marginBottom': '12px'
                                        }
                                    ),
                                    html.Div(
                                        id='sequence-execution-results',
                                        children='No sequence executed yet',
                                        style={
                                            'padding': '12px',
                                            'backgroundColor': '#2C2D3A',
                                            'borderRadius': '4px',
                                            'fontSize': '12px',
                                            'fontFamily': 'monospace',
                                            'color': '#8E8EA0',
                                            'minHeight': '100px',
                                            'maxHeight': '300px',
                                            'overflowY': 'auto',
                                            'whiteSpace': 'pre-wrap',
                                            'wordBreak': 'break-word'
                                        }
                                    )
                                ],
                                style={
                                    'padding': '16px',
                                    'backgroundColor': '#40414F',
                                    'borderRadius': '6px'
                                }
                            )
                        ],
                        style={
                            'width': '60%',
                            'paddingRight': '10px',
                            'overflowY': 'auto',
                            'height': '100%'
                        }
                    ),
                    
                    # RIGHT PANEL (40%) - Action Reference
                    html.Div(
                        id='action-tester-right-panel',
                        children=[
                            html.Div(
                                children=[
                                    html.Div(
                                        children='📚 Action Reference',
                                        className='section-header',
                                        style={
                                            'fontSize': '14px',
                                            'fontWeight': '600',
                                            'color': '#ECECF1',
                                            'marginBottom': '12px'
                                        }
                                    ),
                                    html.Div(
                                        id='action-reference-content',
                                        children='Loading action reference...',
                                        style={
                                            'fontSize': '12px',
                                            'color': '#ECECF1'
                                        }
                                    )
                                ],
                                style={
                                    'padding': '16px',
                                    'backgroundColor': '#40414F',
                                    'borderRadius': '6px',
                                    'height': '100%',
                                    'overflowY': 'auto'
                                }
                            )
                        ],
                        style={
                            'width': '40%',
                            'paddingLeft': '10px',
                            'overflowY': 'auto',
                            'height': '100%'
                        }
                    )
                ],
                style={
                    'display': 'flex',
                    'height': 'calc(100vh - 100px)',
                    'gap': '0px'
                }
            ),

            # Note: browser-status-interval is now at root level in app.py
            # so it runs even when this tab is hidden

            # Hidden stores for state management
            dcc.Store(id='action-tester-active-test-id', data=None),
            
            # Test list container (rendered in sidebar area)
            html.Div(
                id='action-tester-test-list',
                children=create_test_list_panel([], None),
                style={
                    'position': 'fixed',
                    'left': '0',
                    'top': '50px',
                    'width': '260px',
                    'height': 'calc(100vh - 50px)',
                    'backgroundColor': '#202123',
                    'borderRight': '1px solid #565869',
                    'padding': '12px',
                    'overflowY': 'auto',
                    'zIndex': '100'
                }
            )
        ],
        style={
            # Note: visibility is controlled by TabbedPanel wrapper
            'height': '100%',
            'padding': '20px',
            'overflow': 'hidden'
        }
    )



def create_test_list_panel(tests: List[Dict], active_test_id: str) -> html.Div:
    """
    Create test list panel for sidebar.
    
    Args:
        tests: List of test dicts with test_id, test_name
        active_test_id: ID of currently active test
        
    Returns:
        html.Div containing:
        - "New Test" button
        - List of test items (clickable, with close button)
        - Active test highlighted
        - Empty state message if no tests
    """
    children = []
    
    # New Test button
    children.append(
        html.Button(
            '+ New Test',
            id='action-tester-new-test-btn',
            n_clicks=0,
            style={
                'width': '100%',
                'padding': '10px',
                'backgroundColor': '#19C37D',
                'color': '#FFFFFF',
                'border': 'none',
                'borderRadius': '4px',
                'cursor': 'pointer',
                'fontSize': '13px',
                'fontWeight': '600',
                'marginBottom': '12px'
            }
        )
    )
    
    # Test list or empty state
    if not tests:
        children.append(
            html.Div(
                'No tests yet. Click "New Test" to create one.',
                style={
                    'fontSize': '12px',
                    'color': '#8E8EA0',
                    'textAlign': 'center',
                    'padding': '20px',
                    'fontStyle': 'italic'
                }
            )
        )
    else:
        # Test items
        test_items = []
        for test in tests:
            is_active = test['test_id'] == active_test_id
            
            test_items.append(
                html.Div(
                    children=[
                        html.Div(
                            test['test_name'],
                            id={'type': 'test-item', 'index': test['test_id']},
                            n_clicks=0,
                            style={
                                'flex': '1',
                                'cursor': 'pointer',
                                'padding': '10px',
                                'fontSize': '13px',
                                'color': '#ECECF1' if is_active else '#8E8EA0',
                                'fontWeight': '600' if is_active else '400'
                            }
                        ),
                        html.Button(
                            '×',
                            id={'type': 'test-close-btn', 'index': test['test_id']},
                            n_clicks=0,
                            style={
                                'padding': '4px 8px',
                                'backgroundColor': 'transparent',
                                'color': '#FF6B6B',
                                'border': 'none',
                                'cursor': 'pointer',
                                'fontSize': '18px',
                                'fontWeight': '600'
                            }
                        )
                    ],
                    className='active-test-indicator' if is_active else '',
                    style={
                        'display': 'flex',
                        'alignItems': 'center',
                        'marginBottom': '4px',
                        'backgroundColor': '#19C37D' if is_active else '#40414F',
                        'borderRadius': '4px',
                        'border': f'2px solid {"#19C37D" if is_active else "transparent"}'
                    }
                )
            )
        
        children.append(
            html.Div(
                test_items,
                className='test-list-container',
                style={'overflowY': 'auto', 'maxHeight': '400px'}
            )
        )
    
    return html.Div(
        children=children,
        style={
            'padding': '16px',
            'backgroundColor': '#2C2D3A',
            'borderRadius': '6px',
            'height': '100%'
        }
    )


def create_action_reference_panel(actions: List[Dict]) -> html.Div:
    """
    Create action reference panel for right sidebar.
    
    Args:
        actions: List of action metadata dicts with name, description, target_required, supported_args
        
    Returns:
        html.Div containing:
        - Searchable list of available actions
        - Action details with description, parameters, examples
        - Collapsible sections for each action
    """
    children = []
    
    # Header
    children.append(
        html.Div(
            '📚 Available Actions',
            style={
                'fontSize': '16px',
                'fontWeight': '600',
                'color': '#ECECF1',
                'marginBottom': '16px',
                'textAlign': 'center'
            }
        )
    )
    
    # Action list or empty state
    if not actions:
        children.append(
            html.Div(
                'No actions available. Check action metadata configuration.',
                style={
                    'fontSize': '12px',
                    'color': '#8E8EA0',
                    'textAlign': 'center',
                    'padding': '20px',
                    'fontStyle': 'italic'
                }
            )
        )
    else:
        # Action items
        action_items = []
        for action in actions:
            # Action header (collapsible)
            action_items.append(
                html.Details(
                    children=[
                        html.Summary(
                            action['name'],
                            style={
                                'fontSize': '14px',
                                'fontWeight': '600',
                                'color': '#19C37D',
                                'cursor': 'pointer',
                                'padding': '8px 0',
                                'borderBottom': '1px solid #565869'
                            }
                        ),
                        html.Div(
                            children=[
                                # Description
                                html.Div(
                                    action.get('description', 'No description available'),
                                    style={
                                        'fontSize': '12px',
                                        'color': '#ECECF1',
                                        'marginBottom': '12px',
                                        'lineHeight': '1.4'
                                    }
                                ),
                                # Target requirement
                                html.Div(
                                    children=[
                                        html.Span(
                                            'Target Required: ',
                                            style={'fontWeight': '600', 'color': '#8E8EA0'}
                                        ),
                                        html.Span(
                                            'Yes' if action.get('target_required', False) else 'No',
                                            style={
                                                'color': '#19C37D' if action.get('target_required', False) else '#FF6B6B'
                                            }
                                        )
                                    ],
                                    style={
                                        'fontSize': '11px',
                                        'marginBottom': '8px'
                                    }
                                ),
                                # Supported arguments
                                html.Div(
                                    children=[
                                        html.Div(
                                            'Arguments:',
                                            style={
                                                'fontWeight': '600',
                                                'color': '#8E8EA0',
                                                'fontSize': '11px',
                                                'marginBottom': '4px'
                                            }
                                        ),
                                        html.Div(
                                            ', '.join(action.get('supported_args', [])) if action.get('supported_args') else 'None',
                                            style={
                                                'fontSize': '11px',
                                                'color': '#ECECF1',
                                                'fontFamily': 'monospace',
                                                'backgroundColor': '#2C2D3A',
                                                'padding': '4px 8px',
                                                'borderRadius': '3px'
                                            }
                                        )
                                    ],
                                    style={'marginBottom': '12px'}
                                ),
                                # Example usage
                                html.Div(
                                    children=[
                                        html.Div(
                                            'Example:',
                                            style={
                                                'fontWeight': '600',
                                                'color': '#8E8EA0',
                                                'fontSize': '11px',
                                                'marginBottom': '4px'
                                            }
                                        ),
                                        html.Pre(
                                            _generate_action_example(action),
                                            style={
                                                'fontSize': '10px',
                                                'color': '#ECECF1',
                                                'backgroundColor': '#1A1B26',
                                                'padding': '8px',
                                                'borderRadius': '3px',
                                                'border': '1px solid #565869',
                                                'overflowX': 'auto',
                                                'whiteSpace': 'pre-wrap',
                                                'margin': '0'
                                            }
                                        )
                                    ]
                                )
                            ],
                            style={
                                'padding': '12px 0',
                                'borderLeft': '3px solid #19C37D',
                                'paddingLeft': '12px',
                                'marginLeft': '8px'
                            }
                        )
                    ],
                    style={
                        'marginBottom': '8px',
                        'backgroundColor': '#40414F',
                        'borderRadius': '4px',
                        'padding': '8px'
                    }
                )
            )
        
        children.append(
            html.Div(
                children=action_items,
                style={
                    'overflowY': 'auto',
                    'maxHeight': '600px'
                }
            )
        )
    
    return html.Div(
        children=children,
        style={
            'padding': '16px',
            'backgroundColor': '#2C2D3A',
            'borderRadius': '6px',
            'height': '100%'
        }
    )


def _generate_action_example(action: Dict) -> str:
    """
    Generate example JSON for an action.
    
    Args:
        action: Action metadata dict
        
    Returns:
        JSON string example
    """
    import json
    
    example = {
        "id": "action_1",
        "type": action['name']
    }
    
    # Add target if required
    if action.get('target_required', False):
        example["target"] = {
            "strategy": "css",
            "value": "#example-element"
        }
    
    # Add common args based on action type
    args = {}
    action_name = action['name']
    
    if action_name == 'input_text':
        args['text'] = 'Hello World'
    elif action_name == 'visit_url':
        args['url'] = 'https://example.com'
    elif action_name == 'scroll':
        args['direction'] = 'down'
        args['distance'] = 'medium'
    elif action_name == 'wait':
        args['seconds'] = 2
    elif action_name == 'screenshot':
        args['filename'] = 'screenshot.png'
    
    if args:
        example['args'] = args
    
    # Add description
    example['description'] = f"Example {action_name} action"
    
    return json.dumps(example, indent=2)
