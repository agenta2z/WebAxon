"""
Main Application Module

Creates and configures the Agent Debugger Dash application using modular components.
"""
import sys
import atexit
import threading
from pathlib import Path
from functools import partial

# Add source paths if needed
project_root = Path(__file__).parent.parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

rich_python_utils_src = project_root / "SciencePythonUtils" / "src"
agent_foundation_src = project_root / "ScienceModelingTools" / "src"
for path_item in [rich_python_utils_src, agent_foundation_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

from agent_foundation.ui.dash_interactive.queue_based_dash_interactive_app import QueueBasedDashInteractiveApp
from rich_python_utils.common_objects.debuggable import Debugger
from rich_python_utils.io_utils.json_io import write_json
from dash import html, dcc
import dash

# Import modular components
from webaxon.devsuite.agent_debugger_nextgen.core import SessionManager
from webaxon.devsuite.agent_debugger_nextgen.communication import QueueClient, MessageHandlers
from webaxon.devsuite.agent_debugger_nextgen.monitoring import LogMonitor
from webaxon.devsuite.agent_debugger_nextgen import helpers
from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import get_action_tester_manager
from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_action_tester_tab_layout

# Import constants from devsuite
from webaxon.devsuite import (
    INPUT_QUEUE_ID,
    RESPONSE_QUEUE_ID,
    CLIENT_CONTROL_QUEUE_ID,
    SERVER_CONTROL_QUEUE_ID,
    SPECIAL_MESSAGE_WAITING_FOR_RESPONSE,
    AGENT_TYPE_DEFAULT,
    AGENT_TYPE_MOCK_CLARIFICATION,
    get_queue_service,
    config
)
from webaxon.devsuite.common import DebuggerLogTypes
from webaxon.devsuite.constants import RUNTIME_DIR, FOLDER_NAME_DEBUGGER_LOGS


class AgentDebuggerApp(QueueBasedDashInteractiveApp):
    """
    Custom Dash app for agent debugging with modular architecture.
    
    Uses the modular components:
    - SessionManager for session state
    - QueueClient for queue operations
    - MessageHandlers for message processing
    """
    
    def __init__(self, testcase_root: Path, **kwargs):
        """
        Initialize the agent debugger app.

        Args:
            testcase_root: Root directory for queue service discovery
            **kwargs: Additional arguments (title, port, debug, etc.)
        """
        self.testcase_root = testcase_root

        # Create global debugger for app-level logging
        debugger_log_dir = testcase_root / RUNTIME_DIR / FOLDER_NAME_DEBUGGER_LOGS / 'global'
        debugger_log_dir.mkdir(parents=True, exist_ok=True)
        self._global_debugger = Debugger(
            id='agent_debugger_app',
            log_name='AgentDebuggerApp',
            logger=[
                print,
                partial(write_json, file_path=str(debugger_log_dir / FOLDER_NAME_DEBUGGER_LOGS), append=True)
            ],
            debug_mode=config.DEBUG_MODE_DEBUGGER,
            log_time=True,
            always_add_logging_based_logger=False,
            console_display_rate_limit=config.CONSOLE_DISPLAY_RATE_LIMIT,
            enable_console_update=config.ENABLE_CONSOLE_UPDATE
        )

        # Initialize session manager
        self.session_manager = SessionManager()

        # Initialize and start log monitor
        self._log_monitor = LogMonitor(
            session_manager=self.session_manager,
            debugger=self._global_debugger,
            check_interval=2.0,
            max_messages=10
        )
        self._log_monitor.start()

        # Setup helpers module with dependencies (including log_monitor for thread-safe message access)
        helpers.setup_helpers(testcase_root, self.session_manager, self._log_monitor)
        
        # Initialize tracking dictionaries for Settings tab
        self.session_agents = {}
        self.agent_status_messages = {}
        self.sessions_agent_created = {}
        self.session_template_versions = {}  # Track template version per session
        
        # Threading lock for CLIENT_CONTROL_QUEUE polling to prevent race conditions
        self._client_control_poll_lock = threading.Lock()
        
        # Store reference to action tester manager (global singleton)
        self.action_tester_manager = get_action_tester_manager()
        
        # Register cleanup handler
        atexit.register(self._cleanup_on_exit)
        
        # Create Settings tab content
        settings_content = self._create_settings_tab_content()
        
        # Create Action Tester tab content
        action_tester_content = create_action_tester_tab_layout()
        
        # Create custom main tabs (Action Tester goes in main panel)
        custom_main_tabs = [
            {
                'id': 'action-tester',
                'label': '🧪 Action Tester',
                'content': action_tester_content
            }
        ]
        
        # Create custom monitor tabs (Settings stays in monitor panel)
        custom_monitor_tabs = [
            {
                'id': 'settings',
                'label': '⚙️ Settings',
                'content': settings_content
            }
        ]
        
        # Call parent init
        super().__init__(
            response_checker=helpers.check_for_agent_response,
            special_waiting_message=SPECIAL_MESSAGE_WAITING_FOR_RESPONSE,
            custom_monitor_tabs=custom_monitor_tabs,
            custom_main_tabs=custom_main_tabs,
            **kwargs
        )
        
        # Register Settings tab callbacks
        self._register_settings_callbacks()

        # Register Action Tester callbacks
        self._register_action_tester_callbacks()

        # Register sidebar test list callbacks
        self._register_sidebar_test_list_callbacks()

        # Register main tab switching callback (override parent's 2-tab callback)
        self._register_main_tab_switching_callback()

        # Register New Chat browser launch callback
        self._register_new_chat_browser_callback()
        
        # Register agent control callback
        self._register_agent_control_callback()
        
        # Register clientside callbacks for agent control buttons
        self._register_agent_control_buttons_clientside()
        
        # Register log auto-load and refresh callbacks
        self._register_log_callbacks()
        
        # Register log monitor panel callback
        self._register_log_monitor_callback()
        
        # Register toggle monitor messages callback
        self._register_toggle_messages_callback()
        
        # Register clientside callbacks for draggable panel and tab switching
        self._register_draggable_panel_clientside()
        self._register_monitor_tab_switching_clientside()
    
    def _create_layout(self) -> html.Div:
        """Override to add custom control stores at root level."""
        parent_layout = super()._create_layout()

        # Create control stores and intervals at root level
        # Note: browser-status-interval is at root level so it fires even when Action Tester tab is hidden
        control_stores = [
            dcc.Store(id='agent-control-click-store', data=None),
            dcc.Store(id='agent-control-status-store', data={'state': 'not_started'}),
            dcc.Interval(
                id='browser-status-interval',
                interval=2000,  # 2 seconds
                n_intervals=0
            ),
        ]
        
        # Insert stores before intervals
        existing_children = list(parent_layout.children)
        insert_position = len(existing_children)
        for i, child in enumerate(existing_children):
            if isinstance(child, dcc.Interval):
                insert_position = i
                break
        
        new_children = (
            existing_children[:insert_position] +
            control_stores +
            existing_children[insert_position:]
        )
        
        parent_layout.children = new_children
        return parent_layout
    
    def _create_settings_tab_content(self):
        """Create the Settings tab content."""
        return [
            html.Div(
                children='⚙️ Session Settings',
                style={
                    'fontSize': '11px',
                    'color': '#ECECF1',
                    'marginBottom': '10px',
                    'fontWeight': '600'
                }
            ),
            html.Div(
                children=[
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
                        id='main-panel-log-graph-agent-dropdown',
                        options=[
                            {'label': 'Default Agent (Full Planning + Web Actions)', 'value': AGENT_TYPE_DEFAULT},
                            {'label': 'Mock Clarification Agent (Simple Testing)', 'value': AGENT_TYPE_MOCK_CLARIFICATION},
                        ],
                        value=AGENT_TYPE_DEFAULT,
                        placeholder='Select agent configuration...',
                        style={'fontSize': '10px', 'marginBottom': '8px'},
                        className='agent-dropdown'
                    )
                ]
            ),
            html.Div(
                children=[
                    html.Label(
                        'Template Version:',
                        style={
                            'fontSize': '10px',
                            'color': '#8E8EA0',
                            'marginBottom': '4px',
                            'marginTop': '8px',
                            'display': 'block',
                            'fontWeight': '500'
                        }
                    ),
                    dcc.Dropdown(
                        id='main-panel-log-graph-template-version-dropdown',
                        options=[
                            {'label': 'Default (No Version)', 'value': ''},
                            {'label': 'End Customers', 'value': 'end_customers'},
                            {'label': 'Internal Users', 'value': 'internal_users'},
                            {'label': 'Beta Testing', 'value': 'beta'},
                            {'label': 'Production', 'value': 'production'},
                        ],
                        value='',
                        placeholder='Select template version...',
                        style={'fontSize': '10px', 'marginBottom': '8px'},
                        className='template-version-dropdown'
                    )
                ]
            ),
            html.Button(
                'Apply Changes',
                id='main-panel-log-graph-apply-settings-btn',
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
                    'marginBottom': '10px'
                }
            ),
            html.Div(
                children=[
                    html.Div('Current Agent:', style={'fontSize': '9px', 'color': '#8E8EA0', 'marginBottom': '2px'}),
                    html.Div(
                        id='main-panel-log-graph-current-agent',
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
                ]
            ),
            html.Div(
                children=[
                    html.Div('Current Template Version:', style={'fontSize': '9px', 'color': '#8E8EA0', 'marginBottom': '2px'}),
                    html.Div(
                        id='main-panel-log-graph-current-template-version',
                        children='Default (No Version)',
                        style={
                            'fontSize': '9px',
                            'color': '#4A9EFF',
                            'fontFamily': 'monospace',
                            'backgroundColor': 'rgba(0, 0, 0, 0.2)',
                            'padding': '4px 6px',
                            'borderRadius': '3px',
                            'marginBottom': '10px'
                        }
                    )
                ]
            ),
            html.Div(
                children=[
                    html.Div('Agent Status:', style={'fontSize': '9px', 'color': '#8E8EA0', 'marginBottom': '2px'}),
                    html.Div(
                        id='main-panel-log-graph-agent-status',
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
                ]
            ),
            html.Div(
                children='ℹ️ Settings are session-specific',
                style={'fontSize': '8px', 'color': '#6E6E80', 'fontStyle': 'italic', 'textAlign': 'center'}
            ),
            dcc.Store(id='log-path-poll-dummy', data=None),
        ]
    
    def _register_settings_callbacks(self):
        """Register callbacks for the Settings tab."""
        from dash.dependencies import Input, Output, State
        
        # Apply settings callback
        @self.app.callback(
            [
                Output('main-panel-log-graph-current-agent', 'children'),
                Output('main-panel-log-graph-current-template-version', 'children'),
            ],
            Input('main-panel-log-graph-apply-settings-btn', 'n_clicks'),
            [
                State('main-panel-log-graph-agent-dropdown', 'value'),
                State('main-panel-log-graph-template-version-dropdown', 'value'),
                State('current-session-store', 'data'),
            ],
            prevent_initial_call=True
        )
        def apply_settings(_n_clicks, agent_type, template_version, session_id):
            if not session_id:
                return dash.no_update, dash.no_update
            
            # Store the agent type for this session
            if agent_type:
                self.session_agents[session_id] = agent_type
                # Sync with agent service
                helpers.sync_session_agent(session_id, agent_type)
            
            # Store the template version for this session
            self.session_template_versions[session_id] = template_version if template_version else ''
            
            # Sync template version with agent service
            helpers.sync_session_template_version(session_id, template_version if template_version else '')
            
            # Format display text
            agent_display = agent_type if agent_type else dash.no_update
            template_display = template_version if template_version else 'Default (No Version)'
            
            return agent_display, template_display
        
        # Poll CLIENT_CONTROL_QUEUE for agent status, control acks, and log paths
        @self.app.callback(
            [
                Output('main-panel-log-graph-agent-status', 'children'),
                Output('main-panel-log-graph-current-agent', 'children', allow_duplicate=True),
                Output('main-panel-log-graph-agent-dropdown', 'disabled', allow_duplicate=True),
                Output('agent-control-status-store', 'data', allow_duplicate=True),
            ],
            Input('response-poll-interval', 'n_intervals'),
            State('current-session-store', 'data'),
            prevent_initial_call=True
        )
        def poll_client_controls(_n_intervals, session_id):
            """Poll CLIENT_CONTROL_QUEUE and process all pending messages."""
            if not session_id:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update
            
            # Use lock to prevent race conditions with other callbacks
            if not self._client_control_poll_lock.acquire(blocking=False):
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update
            
            try:
                # Check if queue service is available
                try:
                    queue_client = helpers.get_queue_client()
                except RuntimeError:
                    # Queue service not yet initialized
                    return dash.no_update, dash.no_update, dash.no_update, dash.no_update
                
                # Collect all messages from CLIENT_CONTROL_QUEUE (up to 100 per poll)
                messages = []
                for _ in range(100):
                    msg = queue_client.receive_message(CLIENT_CONTROL_QUEUE_ID, blocking=False)
                    if msg is None:
                        break
                    messages.append(msg)
                
                if not messages:
                    # No new messages, but still return current state
                    messages_list = self.agent_status_messages.get(session_id, [])
                    if messages_list:
                        latest = messages_list[-1]
                        payload = latest.get('message', {})
                        status_text = f"{payload.get('status', 'unknown')}: {payload.get('agent_type', 'N/A')}"
                    else:
                        status_text = 'No status updates'
                    
                    current_agent = self.session_agents.get(session_id, AGENT_TYPE_DEFAULT)
                    agent_created = self.sessions_agent_created.get(session_id, False)
                    session_info = self.session_manager.get_or_create(session_id)
                    control_status = {
                        'state': session_info.agent_status or 'not_started',
                        'control': session_info.agent_control or 'continue',
                        'pending': session_info.control_pending
                    }
                    
                    return status_text, current_agent, agent_created, control_status
                
                # Process all collected messages
                result = helpers.process_client_control_messages(
                    messages=messages,
                    session_id=session_id,
                    app_instance=self,
                    debugger=self._global_debugger
                )
                
                # Update agent_created tracking
                if result.get('agent_created'):
                    self.sessions_agent_created[session_id] = True
                
                # Update current agent if changed
                if result.get('latest_agent'):
                    self.session_agents[session_id] = result['latest_agent']
                
                # Format status text from latest messages
                messages_list = self.agent_status_messages.get(session_id, [])
                if messages_list:
                    latest = messages_list[-1]
                    payload = latest.get('message', {})
                    status_text = f"{payload.get('status', 'unknown')}: {payload.get('agent_type', 'N/A')}"
                else:
                    status_text = 'No status updates'
                
                # Get current values
                current_agent = self.session_agents.get(session_id, AGENT_TYPE_DEFAULT)
                agent_created = self.sessions_agent_created.get(session_id, False)
                session_info = self.session_manager.get_or_create(session_id)
                control_status = {
                    'state': session_info.agent_status or 'not_started',
                    'control': session_info.agent_control or 'continue',
                    'pending': session_info.control_pending
                }
                
                return status_text, current_agent, agent_created, control_status
                
            except Exception as e:
                # Log error but don't crash
                self._global_debugger.log_warning({
                    'message': f'Error polling CLIENT_CONTROL_QUEUE: {str(e)}',
                    'session_id': session_id
                }, 'WARNING')
                return f'Error: {str(e)[:50]}', dash.no_update, dash.no_update, dash.no_update
            finally:
                self._client_control_poll_lock.release()
    
    def _register_action_tester_callbacks(self):
        """Register callbacks for the Action Tester tab using multi-test architecture."""
        from dash.dependencies import Input, Output, State
        from webaxon.devsuite.agent_debugger_nextgen.action_tester.models import get_default_sequence_template
        
        # Populate Chrome profile dropdown on page load and interval refresh
        @self.app.callback(
            Output('chrome-profile-dropdown', 'options'),
            Input('browser-status-interval', 'n_intervals'),
            State('chrome-profile-dropdown', 'options'),
            prevent_initial_call=False
        )
        def populate_profile_dropdown(n_intervals, current_options):
            # Only populate if not already populated (empty or None)
            if current_options:
                return dash.no_update
            from webaxon.browser_utils import get_chrome_profile_options_for_dropdown
            return get_chrome_profile_options_for_dropdown()
        
        # Launch Browser callback
        @self.app.callback(
            Output('browser-status-indicator', 'children'),
            Input('action-tester-launch-btn', 'n_clicks'),
            State('chrome-profile-dropdown', 'value'),
            State('copy-profile-checkbox', 'value'),
            prevent_initial_call=True
        )
        def launch_browser(n_clicks, profile_directory, copy_profile_value):
            if n_clicks == 0:
                return dash.no_update

            # Use empty string if None
            if profile_directory is None:
                profile_directory = 'Default'

            # Check if copy profile is enabled (checkbox returns list of selected values)
            copy_profile = 'copy' in (copy_profile_value or [])

            # Launch global browser with selected profile
            result = self.action_tester_manager.launch_browser(
                profile_directory=profile_directory,
                copy_profile=copy_profile
            )
            
            if result['success']:
                # Auto-create first test
                try:
                    self.action_tester_manager.create_test("Test 1")
                except Exception as e:
                    print(f"Error creating first test: {e}")
                return '🟢 Active'
            else:
                return f'🔴 Error: {result["message"][:50]}'
        
        # Close Browser callback
        @self.app.callback(
            [
                Output('browser-status-indicator', 'children', allow_duplicate=True),
                Output('browser-window-count', 'children'),
                Output('browser-active-window', 'children'),
                Output('browser-current-url', 'children'),
            ],
            Input('action-tester-close-btn', 'n_clicks'),
            prevent_initial_call=True
        )
        def close_browser(n_clicks):
            if n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update
            
            # Close global browser
            self.action_tester_manager.close_browser()
            
            return '🔴 Not Active', '0 tab(s) open', 'None', '—'
        
        # Browser status refresh interval - also detects externally closed browser
        @self.app.callback(
            [
                Output('browser-status-indicator', 'children', allow_duplicate=True),
                Output('browser-window-count', 'children', allow_duplicate=True),
                Output('browser-active-window', 'children', allow_duplicate=True),
                Output('browser-current-url', 'children', allow_duplicate=True),
            ],
            Input('browser-status-interval', 'n_intervals'),
            prevent_initial_call='initial_duplicate'  # Allow initial call while supporting duplicate outputs
        )
        def refresh_browser_status(n_intervals):
            status = self.action_tester_manager.get_browser_status()
            return (
                status['status_indicator'],
                status['window_count_text'],
                status['active_window'],
                status['current_url']
            )
        
        # Assign IDs callback
        @self.app.callback(
            [
                Output('assign-ids-result', 'children'),
                Output('assign-ids-result', 'style'),
            ],
            Input('action-tester-assign-ids-btn', 'n_clicks'),
            prevent_initial_call=True
        )
        def assign_element_ids(n_clicks):
            if n_clicks == 0:
                return dash.no_update, dash.no_update
            
            result = self.action_tester_manager.add_element_ids()
            
            if result['success']:
                return (
                    f"✓ Tagged {result['elements_tagged']} elements",
                    {'fontSize': '11px', 'color': '#19C37D', 'marginTop': '8px', 'display': 'block'}
                )
            else:
                return (
                    f"✗ Error: {result['error']}",
                    {'fontSize': '11px', 'color': '#FF6B6B', 'marginTop': '8px', 'display': 'block'}
                )
        
        # Load template callback
        @self.app.callback(
            Output('action-sequence-editor', 'value'),
            Input('load-template-btn', 'n_clicks'),
            prevent_initial_call=True
        )
        def load_template(n_clicks):
            if n_clicks == 0:
                return dash.no_update
            return get_default_sequence_template()
        
        # Validate JSON callback
        @self.app.callback(
            Output('sequence-execution-results', 'children'),
            Input('validate-json-btn', 'n_clicks'),
            State('action-sequence-editor', 'value'),
            prevent_initial_call=True
        )
        def validate_json(n_clicks, json_content):
            if n_clicks == 0 or not json_content:
                return dash.no_update
            
            result = self.action_tester_manager.validate_sequence_json(json_content)
            
            if result['valid']:
                return f"✓ Valid JSON\nSequence ID: {result['sequence_id']}\nActions: {result['action_count']}"
            else:
                return f"✗ Invalid JSON\nError: {result['error']}"
        
        # Run sequence callback
        @self.app.callback(
            Output('sequence-execution-results', 'children', allow_duplicate=True),
            Input('run-sequence-btn', 'n_clicks'),
            [
                State('action-sequence-editor', 'value'),
                State('action-tester-active-test-id', 'data'),
            ],
            prevent_initial_call=True
        )
        def run_sequence(n_clicks, json_content, active_test_id):
            if n_clicks == 0 or not json_content:
                return dash.no_update
            
            # Get active test or use first test
            if not active_test_id:
                tests = self.action_tester_manager.get_test_list()
                if not tests:
                    return "✗ No active test. Please launch browser first."
                active_test_id = tests[0]['test_id']
            
            # Execute sequence
            results = self.action_tester_manager.execute_sequence(active_test_id, json_content)
            
            # Format results
            result_lines = []
            for r in results:
                if r['success']:
                    result_lines.append(f"✓ {r['action_id']} ({r['action_type']})")
                else:
                    result_lines.append(f"✗ {r['action_id']} ({r['action_type']}): {r['error']}")
            
            return '\n'.join(result_lines) if result_lines else "No results"
        
        # Initialize editor with template on load
        @self.app.callback(
            Output('action-sequence-editor', 'value', allow_duplicate=True),
            Input('main-panel-action-tester-tab', 'style'),
            prevent_initial_call='initial_duplicate'
        )
        def initialize_editor(style):
            # Load template when tab becomes visible
            if style and style.get('display') != 'none':
                return get_default_sequence_template()
            return dash.no_update
        
        # New Test callback
        @self.app.callback(
            Output('action-tester-active-test-id', 'data'),
            Input('action-tester-new-test-btn', 'n_clicks'),
            State('action-tester-active-test-id', 'data'),
            prevent_initial_call=True
        )
        def create_new_test(n_clicks, current_test_id):
            if n_clicks == 0:
                return dash.no_update
            
            try:
                # Generate unique test name
                test_count = len(self.action_tester_manager.get_test_list()) + 1
                test_name = f"Test {test_count}"
                
                # Create test
                test_id = self.action_tester_manager.create_test(test_name)
                return test_id
            except Exception as e:
                print(f"Error creating test: {e}")
                return dash.no_update
        
        # Update editor content when switching tests
        @self.app.callback(
            Output('action-sequence-editor', 'value', allow_duplicate=True),
            Input('action-tester-active-test-id', 'data'),
            prevent_initial_call=True
        )
        def load_test_content(test_id):
            if not test_id:
                return dash.no_update
            
            content = self.action_tester_manager.get_test_content(test_id)
            return content if content else get_default_sequence_template()
        
        # Save editor content when it changes
        @self.app.callback(
            Output('action-tester-active-test-id', 'data', allow_duplicate=True),
            Input('action-sequence-editor', 'value'),
            State('action-tester-active-test-id', 'data'),
            prevent_initial_call=True
        )
        def save_test_content(json_content, test_id):
            if test_id and json_content:
                self.action_tester_manager.update_test_content(test_id, json_content)
            return dash.no_update
        
        # Load action reference panel
        @self.app.callback(
            Output('action-reference-content', 'children'),
            Input('main-panel-action-tester-tab', 'style'),
            prevent_initial_call=False
        )
        def load_action_reference(style):
            # Load action reference when tab becomes visible
            if style and style.get('display') != 'none':
                from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_action_reference_panel
                
                # Get available actions from manager
                actions = self.action_tester_manager.get_available_actions()
                
                return create_action_reference_panel(actions)
            return dash.no_update
    
    def _register_sidebar_test_list_callbacks(self):
        """Register callbacks for sidebar test list functionality."""
        from dash import ALL
        from dash.dependencies import Input, Output, State
        
        # Callback to handle test item clicks (switch active test)
        @self.app.callback(
            Output('action-tester-active-test-id', 'data', allow_duplicate=True),
            Input({'type': 'test-item', 'index': ALL}, 'n_clicks'),
            State({'type': 'test-item', 'index': ALL}, 'id'),
            prevent_initial_call=True
        )
        def switch_active_test(n_clicks, ids):
            """Switch active test when test item is clicked."""
            ctx = dash.callback_context
            if not ctx.triggered or not any(n_clicks):
                return dash.no_update
            
            # Find which test was clicked
            triggered_prop = ctx.triggered[0]['prop_id']
            # Extract test_id from pattern-matching ID
            import json
            triggered_id = json.loads(triggered_prop.split('.')[0])
            test_id = triggered_id['index']
            
            # Switch to the test
            try:
                self.action_tester_manager.switch_to_test(test_id)
            except Exception as e:
                print(f"Error switching to test: {e}")
            
            return test_id
        
        # Callback to handle close button clicks
        @self.app.callback(
            [
                Output('action-tester-active-test-id', 'data', allow_duplicate=True),
                Output('action-tester-test-list', 'children', allow_duplicate=True)
            ],
            Input({'type': 'test-close-btn', 'index': ALL}, 'n_clicks'),
            [
                State({'type': 'test-close-btn', 'index': ALL}, 'id'),
                State('action-tester-active-test-id', 'data')
            ],
            prevent_initial_call=True
        )
        def close_test(n_clicks, ids, active_test_id):
            """Close test when close button is clicked."""
            ctx = dash.callback_context
            if not ctx.triggered or not any(n_clicks):
                return dash.no_update, dash.no_update
            
            # Find which close button was clicked
            triggered_prop = ctx.triggered[0]['prop_id']
            import json
            triggered_id = json.loads(triggered_prop.split('.')[0])
            test_id_to_close = triggered_id['index']
            
            # Close the test
            self.action_tester_manager.close_test(test_id_to_close)
            
            # If we closed the active test, switch to another test or None
            new_active_test_id = active_test_id
            if active_test_id == test_id_to_close:
                remaining_tests = self.action_tester_manager.get_test_list()
                new_active_test_id = remaining_tests[0]['test_id'] if remaining_tests else None
            
            # Refresh test list
            from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_test_list_panel
            updated_tests = self.action_tester_manager.get_test_list()
            new_test_list = create_test_list_panel(updated_tests, new_active_test_id)
            
            return new_active_test_id, new_test_list
        
        # Callback to refresh test list when tests change
        @self.app.callback(
            Output('action-tester-test-list', 'children'),
            [
                Input('action-tester-active-test-id', 'data'),
                Input('action-tester-new-test-btn', 'n_clicks')
            ],
            prevent_initial_call=True
        )
        def refresh_test_list(active_test_id, new_test_clicks):
            """Refresh test list when active test changes or new test is created."""
            from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_test_list_panel
            tests = self.action_tester_manager.get_test_list()
            return create_test_list_panel(tests, active_test_id)
    
    def _register_main_tab_switching_callback(self):
        """Register callback for main tab switching (Chat, Log Debugging, Action Tester)."""
        from dash.dependencies import Input, Output
        
        # Define styles
        active_btn_style = {
            'padding': '12px 24px', 'backgroundColor': '#19C37D',
            'color': '#ECECF1', 'border': 'none',
            'borderBottom': '2px solid #19C37D', 'cursor': 'pointer',
            'fontSize': '14px', 'fontWeight': '500', 'flex': '1'
        }
        inactive_btn_style = {
            'padding': '12px 24px', 'backgroundColor': '#40414F',
            'color': '#8E8EA0', 'border': 'none',
            'borderBottom': '2px solid transparent', 'cursor': 'pointer',
            'fontSize': '14px', 'fontWeight': '500', 'flex': '1'
        }
        visible_tab_style = {'display': 'block', 'height': '100%'}
        hidden_tab_style = {'display': 'none', 'height': '100%'}
        
        @self.app.callback(
            [
                Output('main-panel-chat-tab', 'style', allow_duplicate=True),
                Output('main-panel-log-debug-tab', 'style', allow_duplicate=True),
                Output('main-panel-action-tester-tab', 'style'),
                Output('main-panel-chat-btn', 'style', allow_duplicate=True),
                Output('main-panel-log-btn', 'style', allow_duplicate=True),
                Output('main-panel-action-tester-btn', 'style'),
            ],
            [
                Input('main-panel-chat-btn', 'n_clicks'),
                Input('main-panel-log-btn', 'n_clicks'),
                Input('main-panel-action-tester-btn', 'n_clicks'),
            ],
            prevent_initial_call=True
        )
        def switch_main_tabs(chat_clicks, log_clicks, action_tester_clicks):
            """Switch between main panel tabs including Action Tester."""
            ctx = dash.callback_context
            
            # Default to chat tab
            if not ctx.triggered:
                return (
                    visible_tab_style, hidden_tab_style, hidden_tab_style,
                    active_btn_style, inactive_btn_style, inactive_btn_style
                )
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if button_id == 'main-panel-log-btn':
                return (
                    hidden_tab_style, visible_tab_style, hidden_tab_style,
                    inactive_btn_style, active_btn_style, inactive_btn_style
                )
            elif button_id == 'main-panel-action-tester-btn':
                return (
                    hidden_tab_style, hidden_tab_style, visible_tab_style,
                    inactive_btn_style, inactive_btn_style, active_btn_style
                )
            else:
                # Default: show chat tab
                return (
                    visible_tab_style, hidden_tab_style, hidden_tab_style,
                    active_btn_style, inactive_btn_style, inactive_btn_style
                )

    def _register_new_chat_browser_callback(self):
        """
        Register callback to sync sessions with the agent service when sessions change.

        This mirrors the legacy agent_debugger.py sync_sessions_on_load callback.
        When sessions-store changes (new chat created, session deleted, page refresh),
        we sync with the web_agent_service.py which manages agents/browsers.

        The service creates agents based on OPTION_NEW_AGENT_ON_FIRST_SUBMISSION:
        - False: Create agent/browser immediately when session is synced
        - True: Create agent/browser lazily on first message submission
        """
        from dash.dependencies import Input, Output

        @self.app.callback(
            Output('sessions-store', 'data', allow_duplicate=True),
            Input('sessions-store', 'data'),
            prevent_initial_call='initial_duplicate'
        )
        def sync_sessions_on_change(sessions):
            """
            Sync sessions with the agent service when sessions change.

            Called when:
            - Page loads/refreshes
            - New Chat button is clicked (base class adds to sessions-store)
            - Session is deleted
            """
            # Extract active session IDs from sessions store
            active_session_ids = [s['id'] for s in sessions] if sessions else []

            # Cleanup inactive sessions from local session manager
            self.session_manager.cleanup_inactive(active_session_ids)

            self._global_debugger.log_info(
                {'active_sessions': active_session_ids},
                DebuggerLogTypes.SESSION_SWITCH
            )

            # Sync active sessions with the agent service
            # The service will create/close agents based on this list
            helpers.sync_active_sessions(active_session_ids, self._global_debugger)

            # Sync agent type for each session that has one configured
            for session_id in active_session_ids:
                if session_id in self.session_agents:
                    helpers.sync_session_agent(
                        session_id,
                        self.session_agents[session_id],
                        self._global_debugger
                    )

            self._global_debugger.log_info(
                {'action': 'synced_sessions', 'active_sessions': active_session_ids},
                DebuggerLogTypes.SESSION_SWITCH
            )

            # Return sessions unchanged
            return sessions if sessions else dash.no_update

    def _register_agent_control_callback(self):
        """
        Register callback for agent control commands (stop, pause, continue, step).
        
        This callback handles the agent-control-click-store data changes and sends
        control commands to the agent service via the queue.
        """
        from dash.dependencies import Input, Output, State
        
        @self.app.callback(
            Output('agent-control-click-store', 'data', allow_duplicate=True),
            Input('agent-control-click-store', 'data'),
            State('current-session-store', 'data'),
            prevent_initial_call=True
        )
        def handle_agent_control_click(control_data, session_id):
            """Handle agent control button clicks."""
            if not control_data or not session_id:
                return dash.no_update
            
            # Extract control command from store data
            control = control_data.get('control')
            if not control:
                return dash.no_update
            
            # Valid control commands
            valid_controls = ['stop', 'pause', 'continue', 'step']
            if control not in valid_controls:
                self._global_debugger.log_warning({
                    'message': f'Invalid control command: {control}',
                    'valid_controls': valid_controls
                }, 'WARNING')
                return None  # Clear store
            
            # Send control command to agent service
            try:
                helpers.send_agent_control(session_id, control)
                
                self._global_debugger.log_info({
                    'action': 'agent_control_sent',
                    'session_id': session_id,
                    'control': control
                }, 'AGENT_CONTROL')
            except Exception as e:
                self._global_debugger.log_warning({
                    'message': f'Error sending agent control: {str(e)}',
                    'session_id': session_id,
                    'control': control
                }, 'WARNING')
            
            # Clear store to allow repeated clicks
            return None

    def _register_agent_control_buttons_clientside(self):
        """
        Register clientside callbacks to inject agent control buttons into the Log Debug tab.
        
        This uses JavaScript to dynamically inject Stop, Pause, Continue, Step buttons
        and attach click handlers that update the agent-control-click-store.
        """
        from dash.dependencies import Input, Output
        
        # Clientside callback to inject control buttons into Log Debug tab
        self.app.clientside_callback(
            """
            function(n_intervals) {
                // Check if control buttons already injected
                if (document.getElementById('agent-control-buttons-container')) {
                    return window.dash_clientside.no_update;
                }

                // Find the Log Debug tab content
                const logDebugTab = document.getElementById('main-panel-log-debug-tab');
                if (!logDebugTab) {
                    return window.dash_clientside.no_update;
                }

                // Create control buttons container
                const controlContainer = document.createElement('div');
                controlContainer.id = 'agent-control-buttons-container';
                controlContainer.style.cssText = 'margin-bottom: 8px; padding: 6px; background-color: rgba(0, 0, 0, 0.2); border-radius: 4px;';

                // Create label
                const label = document.createElement('div');
                label.textContent = 'Agent Control:';
                label.style.cssText = 'font-size: 10px; color: #8E8EA0; margin-bottom: 4px;';
                controlContainer.appendChild(label);

                // Create buttons container
                const buttonsDiv = document.createElement('div');
                buttonsDiv.style.cssText = 'display: flex; gap: 4px;';

                // Create control buttons
                const buttons = [
                    {id: 'agent-control-stop-btn', label: '■ Stop', title: 'Stop', color: '#FF6B6B'},
                    {id: 'agent-control-pause-btn', label: '‖ Pause', title: 'Pause', color: '#FF9800'},
                    {id: 'agent-control-continue-btn', label: '▶ Continue', title: 'Continue', color: '#19C37D'},
                    {id: 'agent-control-step-btn', label: '⏭ Step', title: 'Step', color: '#4A9EFF'}
                ];

                buttons.forEach(btnInfo => {
                    const btn = document.createElement('button');
                    btn.id = btnInfo.id;
                    btn.innerHTML = btnInfo.label;
                    btn.title = btnInfo.title;
                    btn.style.cssText = `flex: 1; padding: 4px 8px; background-color: transparent; color: ${btnInfo.color}; border: 1px solid ${btnInfo.color}; border-radius: 3px; cursor: pointer; font-size: 10px; transition: all 0.2s;`;
                    btn.onmouseover = () => { btn.style.backgroundColor = 'rgba(255, 255, 255, 0.1)'; };
                    btn.onmouseout = () => { btn.style.backgroundColor = 'transparent'; };
                    buttonsDiv.appendChild(btn);
                });

                controlContainer.appendChild(buttonsDiv);

                // Insert at the beginning of Log Debug tab
                logDebugTab.insertBefore(controlContainer, logDebugTab.firstChild);

                console.log('[Agent Controls] Injected control buttons into Log Debug tab');
                return window.dash_clientside.no_update;
            }
            """,
            Output('agent-control-status-store', 'data'),
            Input('response-poll-interval', 'n_intervals'),
            prevent_initial_call=False
        )
        
        # Clientside callback to attach click handlers to control buttons
        self.app.clientside_callback(
            """
            function(n_intervals) {
                // Check if buttons exist
                const stopBtn = document.getElementById('agent-control-stop-btn');
                const pauseBtn = document.getElementById('agent-control-pause-btn');
                const continueBtn = document.getElementById('agent-control-continue-btn');
                const stepBtn = document.getElementById('agent-control-step-btn');

                if (!stopBtn || stopBtn.dataset.clickHandlerAttached) {
                    return window.dash_clientside.no_update;
                }

                // Attach click handlers
                const buttons = [
                    {btn: stopBtn, control: 'stop'},
                    {btn: pauseBtn, control: 'pause'},
                    {btn: continueBtn, control: 'continue'},
                    {btn: stepBtn, control: 'step'}
                ];

                buttons.forEach(({btn, control}) => {
                    btn.addEventListener('click', () => {
                        // Update the store by dispatching a custom event
                        const storeEl = document.getElementById('agent-control-click-store');
                        if (storeEl) {
                            // Use setProps if available (Dash internal)
                            if (window.dash_clientside && window.dash_clientside.set_props) {
                                window.dash_clientside.set_props('agent-control-click-store', {
                                    data: {control: control, timestamp: Date.now()}
                                });
                            } else {
                                // Fallback: trigger via hidden input
                                const event = new CustomEvent('dash-update', {
                                    detail: {control: control, timestamp: Date.now()}
                                });
                                storeEl.dispatchEvent(event);
                            }
                            console.log(`[Agent Controls] ${control} button clicked`);
                        }
                    });
                    btn.dataset.clickHandlerAttached = 'true';
                });

                console.log('[Agent Controls] Click handlers attached');
                return window.dash_clientside.no_update;
            }
            """,
            Output('agent-control-click-store', 'data'),
            Input('response-poll-interval', 'n_intervals'),
            prevent_initial_call=False
        )

    def _register_log_callbacks(self):
        """
        Register callbacks for log auto-load and refresh functionality.
        
        This implements:
        - auto_load_on_first_tab_switch: Auto-load logs when switching to Log Debugging tab
        - handle_session_switch: Load appropriate logs when switching sessions
        - refresh_log_graph_on_button_click: Refresh log graph when user clicks refresh button
        
        Requirements: 4.1, 4.2, 4.3, 4.4, 5.3
        """
        from dash.dependencies import Input, Output, State
        from pathlib import Path
        
        # Define styles for showing/hiding overlay
        overlay_visible = {
            'position': 'absolute', 'top': '0', 'left': '0', 'right': '0', 'bottom': '0',
            'backgroundColor': 'rgba(44, 44, 44, 0.95)', 'display': 'flex',
            'alignItems': 'center', 'justifyContent': 'center', 'zIndex': '2000'
        }
        overlay_hidden = {
            'position': 'absolute', 'top': '0', 'left': '0', 'right': '0', 'bottom': '0',
            'backgroundColor': 'rgba(44, 44, 44, 0.95)', 'display': 'none',
            'alignItems': 'center', 'justifyContent': 'center', 'zIndex': '2000'
        }
        
        # Auto-load on first tab switch callback
        @self.app.callback(
            [
                Output('log-data-store', 'data', allow_duplicate=True),
                Output('main-panel-log-graph-plotly-loading-overlay', 'style', allow_duplicate=True),
                Output('main-panel-log-graph-cytoscape-loading-overlay', 'style', allow_duplicate=True)
            ],
            [Input('main-panel-log-btn', 'n_clicks')],
            [
                State('log-data-store', 'data'),
                State('current-session-store', 'data'),
                State('main-panel-log-graph-rendering-mode', 'value')
            ],
            prevent_initial_call=True
        )
        def auto_load_on_first_tab_switch(log_btn_clicks, current_data, session_id, rendering_mode):
            """Auto-load logs on first switch to Log Debugging tab.
            
            Requirements: 4.1, 4.3, 4.4
            """
            if not log_btn_clicks or not session_id:
                return dash.no_update, dash.no_update, dash.no_update
            
            # Get session info
            session_info = self.session_manager.get_or_create(session_id)
            
            # Check if we've already done initial load for this session
            if session_info.initial_load_done:
                return dash.no_update, dash.no_update, dash.no_update
            
            self._global_debugger.log_info({
                'action': 'first_time_viewing_log_debugging',
                'session_id': session_id
            }, 'AUTO_LOAD')
            
            # Get the pre-loaded log data from background thread
            loaded_data = session_info.loaded_log_data
            
            # If background thread hasn't loaded it yet, try loading it directly
            if not loaded_data:
                log_file_path = session_info.log_file_path
                
                if log_file_path:
                    self._global_debugger.log_info({
                        'action': 'loading_directly',
                        'log_file_path': log_file_path
                    }, 'AUTO_LOAD')
                    try:
                        # Load logs directly (this is synchronous, but only happens once)
                        from agent_foundation.ui.dash_interactive.utils.log_collector import LogCollector
                        log_collector = LogCollector.from_json_logs(log_file_path, json_file_pattern='*')
                        graph_structure = log_collector.get_graph_structure()
                        
                        num_nodes = len(graph_structure['nodes'])
                        num_edges = len(graph_structure['edges'])
                        
                        # Get mtime for tracking
                        log_path = Path(log_file_path)
                        all_files = [f for f in log_path.rglob('*') if f.is_file()]
                        newest_mtime = max(f.stat().st_mtime for f in all_files) if all_files else 0
                        
                        # Mark as loaded
                        session_info.initial_load_done = True
                        session_info.last_displayed_mtime = newest_mtime
                        
                        self._global_debugger.log_info({
                            'action': 'loaded_directly',
                            'num_nodes': num_nodes,
                            'num_edges': num_edges
                        }, 'AUTO_LOAD')
                        
                        # Return graph structure
                        result = {
                            'graph_data': {
                                'nodes': graph_structure['nodes'],
                                'edges': graph_structure['edges'],
                                'agent': graph_structure['agent'],
                                'log_file': Path(log_file_path).name if log_file_path else f'session_{session_id}'
                            },
                            'log_groups': {k: v for k, v in log_collector.log_groups.items()}
                        }
                        
                        self._global_debugger.log_info({
                            'action': 'initial_load_complete',
                            'num_log_groups': len(result['log_groups'])
                        }, 'AUTO_LOAD')
                        
                        # Hide loading overlay after loading completes
                        plotly_overlay = overlay_hidden if rendering_mode == 'plotly' else dash.no_update
                        cytoscape_overlay = overlay_hidden if rendering_mode == 'cytoscape' else dash.no_update
                        return result, plotly_overlay, cytoscape_overlay
                        
                    except Exception as e:
                        self._global_debugger.log_warning({
                            'error': str(e)
                        }, 'ERROR')
                        # Mark as done even on error so monitor can show status
                        session_info.initial_load_done = True
                        return dash.no_update, overlay_hidden, overlay_hidden
                else:
                    self._global_debugger.log_warning({
                        'message': 'No log path available for session',
                        'session_id': session_id,
                        'available_sessions': self.session_manager.get_active_ids()
                    }, 'WARNING')
                    # Mark as done even without data so monitor panel shows proper status
                    session_info.initial_load_done = True
                    self._global_debugger.log_info({
                        'action': 'marked_as_initially_loaded',
                        'session_id': session_id
                    }, 'AUTO_LOAD')
                    return dash.no_update, dash.no_update, dash.no_update
            
            # Use pre-loaded data from background thread
            session_info.initial_load_done = True
            session_info.last_displayed_mtime = loaded_data['mtime']
            
            log_collector = loaded_data['log_collector']
            graph_structure = loaded_data['graph_structure']
            log_file_path = loaded_data['log_file_path']
            
            num_nodes = loaded_data['nodes']
            num_edges = loaded_data['edges']
            
            self._global_debugger.log_info({
                'action': 'using_preloaded_data',
                'num_nodes': num_nodes,
                'num_edges': num_edges
            }, 'AUTO_LOAD')
            
            # Return graph structure
            result = {
                'graph_data': {
                    'nodes': graph_structure['nodes'],
                    'edges': graph_structure['edges'],
                    'agent': graph_structure['agent'],
                    'log_file': Path(log_file_path).name if log_file_path else f'session_{session_id}'
                },
                'log_groups': {k: v for k, v in log_collector.log_groups.items()}
            }
            
            self._global_debugger.log_info({
                'action': 'initial_load_complete',
                'num_log_groups': len(result['log_groups'])
            }, 'AUTO_LOAD')
            
            # Hide loading overlay after loading completes
            plotly_overlay = overlay_hidden if rendering_mode == 'plotly' else dash.no_update
            cytoscape_overlay = overlay_hidden if rendering_mode == 'cytoscape' else dash.no_update
            return result, plotly_overlay, cytoscape_overlay
        
        # Handle session switch callback
        @self.app.callback(
            Output('log-data-store', 'data', allow_duplicate=True),
            [Input('current-session-store', 'data')],
            [State('log-data-store', 'data')],
            prevent_initial_call=True
        )
        def handle_session_switch(session_id, current_log_data):
            """Load appropriate log graph when switching sessions while on Log Debugging tab.
            
            Requirements: 4.2
            """
            if not session_id:
                return dash.no_update
            
            session_info = self.session_manager.get_or_create(session_id)
            
            # Check if this session has been loaded before
            if not session_info.initial_load_done:
                # Never loaded this session - don't auto-load on session switch
                # Let the tab switch callback handle first-time load
                return dash.no_update
            
            self._global_debugger.log_info({
                'action': 'switching_to_session',
                'session_id': session_id
            }, 'SESSION_SWITCH')
            
            # Try to get pre-loaded data from background thread
            loaded_data = session_info.loaded_log_data
            
            # Check if we have the last displayed data for this session
            last_mtime = session_info.last_displayed_mtime or 0
            
            # If we have newer data than what was last displayed, use the old mtime data
            # Otherwise load from file path if available
            if loaded_data and loaded_data['mtime'] == last_mtime:
                # Use the exact data that was last displayed
                log_collector = loaded_data['log_collector']
                graph_structure = loaded_data['graph_structure']
                log_file_path = loaded_data['log_file_path']
                
                self._global_debugger.log_info({
                    'action': 'using_cached_data',
                    'session_id': session_id
                }, 'SESSION_SWITCH')
            else:
                # Need to load the last displayed version
                log_file_path = session_info.log_file_path
                if not log_file_path:
                    self._global_debugger.log_warning({
                        'message': 'No log path for session',
                        'session_id': session_id
                    }, 'WARNING')
                    return dash.no_update
                
                try:
                    self._global_debugger.log_info({
                        'action': 'loading_last_displayed_data',
                        'log_file_path': log_file_path
                    }, 'SESSION_SWITCH')
                    from agent_foundation.ui.dash_interactive.utils.log_collector import LogCollector
                    log_collector = LogCollector.from_json_logs(log_file_path, json_file_pattern='*')
                    graph_structure = log_collector.get_graph_structure()
                except Exception as e:
                    self._global_debugger.log_warning({
                        'error': str(e)
                    }, 'ERROR')
                    return dash.no_update
            
            # Return the graph structure
            result = {
                'graph_data': {
                    'nodes': graph_structure['nodes'],
                    'edges': graph_structure['edges'],
                    'agent': graph_structure['agent'],
                    'log_file': Path(log_file_path).name if log_file_path else f'session_{session_id}'
                },
                'log_groups': {k: v for k, v in log_collector.log_groups.items()}
            }
            
            self._global_debugger.log_info({
                'action': 'loaded_graph',
                'num_log_groups': len(result['log_groups'])
            }, 'SESSION_SWITCH')
            return result
        
        # Refresh log graph on button click callback
        @self.app.callback(
            [
                Output('log-data-store', 'data', allow_duplicate=True),
                Output('main-panel-log-graph-plotly-loading-overlay', 'style', allow_duplicate=True),
                Output('main-panel-log-graph-cytoscape-loading-overlay', 'style', allow_duplicate=True)
            ],
            [Input('main-panel-log-graph-refresh-btn', 'n_clicks')],
            [
                State('log-data-store', 'data'),
                State('current-session-store', 'data'),
                State('main-panel-log-graph-rendering-mode', 'value')
            ],
            prevent_initial_call=True
        )
        def refresh_log_graph_on_button_click(refresh_clicks, current_data, session_id, rendering_mode):
            """Refresh log graph when user clicks the refresh button.
            
            Requirements: 5.3
            """
            if not refresh_clicks:
                return dash.no_update, dash.no_update, dash.no_update
            
            if not session_id:
                return dash.no_update, dash.no_update, dash.no_update
            
            self._global_debugger.log_info({
                'action': 'refresh_button_clicked',
                'session_id': session_id
            }, 'REFRESH')
            
            session_info = self.session_manager.get_or_create(session_id)
            
            # Get the pre-loaded log data from background thread
            loaded_data = session_info.loaded_log_data
            
            if not loaded_data:
                self._global_debugger.log_warning({
                    'message': 'No loaded data available',
                    'session_id': session_id
                }, 'WARNING')
                return (current_data if current_data else dash.no_update), dash.no_update, dash.no_update
            
            # Track the mtime of this data so we know it's been displayed
            session_info.last_displayed_mtime = loaded_data['mtime']
            
            # Use the pre-loaded data (already has graph_structure computed)
            log_collector = loaded_data['log_collector']
            graph_structure = loaded_data['graph_structure']
            log_file_path = loaded_data['log_file_path']
            
            num_nodes = loaded_data['nodes']
            num_edges = loaded_data['edges']
            
            self._global_debugger.log_info({
                'action': 'using_preloaded_data',
                'num_nodes': num_nodes,
                'num_edges': num_edges
            }, 'REFRESH')
            
            # Return graph structure
            result = {
                'graph_data': {
                    'nodes': graph_structure['nodes'],
                    'edges': graph_structure['edges'],
                    'agent': graph_structure['agent'],
                    'log_file': Path(log_file_path).name if log_file_path else f'session_{session_id}'
                },
                'log_groups': {k: v for k, v in log_collector.log_groups.items()}
            }
            
            self._global_debugger.log_info({
                'action': 'refreshed_graph',
                'num_log_groups': len(result['log_groups'])
            }, 'REFRESH')
            
            # Hide loading overlay after refresh completes
            plotly_overlay = overlay_hidden if rendering_mode == 'plotly' else dash.no_update
            cytoscape_overlay = overlay_hidden if rendering_mode == 'cytoscape' else dash.no_update
            return result, plotly_overlay, cytoscape_overlay

    def _register_log_monitor_callback(self):
        """
        Register callback for log monitor panel updates.
        
        This implements the update_log_monitor_panel callback that:
        - Triggered by response-poll-interval
        - Gets session info and loaded_log_data
        - Compares loaded_log_data.mtime with session.last_displayed_mtime
        - If newer: green button style, "New data available" status
        - If same: gray button style, "Up to date" status
        - Formats agent control state prefix: [CTL:Continue] [Status:Running]
        - Formats stats: Nodes, Edges, File timestamp, Displayed timestamp, Age
        - Gets monitor messages from LogMonitor
        
        Requirements: 5.1, 5.2, 5.4, 5.5
        """
        from dash.dependencies import Input, Output, State
        from dash import html
        import datetime
        import time
        
        @self.app.callback(
            [
                Output('main-panel-log-graph-refresh-btn', 'style'),
                Output('main-panel-log-graph-monitor-status', 'children'),
                Output('main-panel-log-graph-monitor-stats', 'children'),
                Output('main-panel-log-graph-monitor-messages', 'children')
            ],
            [Input('response-poll-interval', 'n_intervals')],
            [State('current-session-store', 'data')],
            prevent_initial_call=False
        )
        def update_log_monitor_panel(n_intervals, session_id):
            """Update floating log monitor panel with real-time status.
            
            Requirements: 5.1, 5.2, 5.4, 5.5
            """
            # Helper function to get agent control and status prefix
            def get_agent_state_prefix(sid):
                """Get agent control and status prefix for display."""
                if not sid:
                    return "[CTL:---] [Status:---]"
                
                session_info = self.session_manager.get_or_create(sid)
                control = session_info.agent_control
                status = session_info.agent_status
                
                # Map control values to display names
                control_map = {
                    'stop': 'Stop',
                    'pause': 'Pause',
                    'continue': 'Continue',
                    'step': 'Step',
                    'stepbystep': 'Step'
                }
                control_display = control_map.get(control, 'Continue')
                
                # Map status values to display names
                status_map = {
                    'running': 'Running',
                    'paused': 'Paused',
                    'stopped': 'Stopped',
                    'not_started': 'NotStarted',
                    'unknown': 'Unknown'
                }
                status_display = status_map.get(status, 'Unknown')
                
                return f"[CTL:{control_display}] [Status:{status_display}]"
            
            # Define button styles
            gray_button = {
                'width': '100%', 'padding': '8px 12px',
                'backgroundColor': '#4A4A5A', 'color': '#8E8EA0',
                'border': 'none', 'borderRadius': '4px',
                'cursor': 'not-allowed', 'fontSize': '12px',
                'fontWeight': '500', 'transition': 'all 0.2s'
            }
            
            green_button = {
                'width': '100%', 'padding': '8px 12px',
                'backgroundColor': '#19C37D', 'color': '#ECECF1',
                'border': 'none', 'borderRadius': '4px',
                'cursor': 'pointer', 'fontSize': '12px',
                'fontWeight': '500', 'transition': 'all 0.2s',
                'boxShadow': '0 0 10px rgba(25, 195, 125, 0.3)'
            }
            
            # Get monitor messages from LogMonitor via helper (thread-safe)
            # Requirements: 5.4, 5.5
            monitor_messages = helpers.get_log_monitor_messages()
            if monitor_messages:
                messages_div = html.Div([
                    html.Div(msg, style={'marginBottom': '2px'}) 
                    for msg in monitor_messages[-10:]
                ])
            else:
                messages_div = "No messages yet..."
            
            # Handle no session case
            if not session_id:
                return (
                    gray_button,
                    f"{get_agent_state_prefix(None)} ⏸️ No active session",
                    "Switch to a session tab",
                    messages_div
                )
            
            session_info = self.session_manager.get_or_create(session_id)
            
            # Check if initial load has been done
            if not session_info.initial_load_done:
                return (
                    gray_button,
                    f"{get_agent_state_prefix(session_id)} ⏳ Waiting for first load...",
                    f"Session: {session_id[:20]}...",
                    messages_div
                )
            
            # Get log file path for this session
            log_file_path = session_info.log_file_path
            if not log_file_path:
                return (
                    gray_button,
                    f"{get_agent_state_prefix(session_id)} ❌ No log path",
                    f"Session: {session_id[:20]}...",
                    messages_div
                )
            
            # Check if we have loaded log data for this session
            loaded_data = session_info.loaded_log_data
            
            if loaded_data:
                # Check if this data is newer than what's currently displayed
                current_mtime = loaded_data.get('mtime', 0)
                last_displayed = session_info.last_displayed_mtime or 0
                
                num_nodes = loaded_data.get('nodes', 0)
                num_edges = loaded_data.get('edges', 0)
                load_timestamp = loaded_data.get('timestamp', 0)
                
                # Format timestamps
                current_time_str = datetime.datetime.fromtimestamp(current_mtime).strftime('%H:%M:%S') if current_mtime else 'N/A'
                last_displayed_str = datetime.datetime.fromtimestamp(last_displayed).strftime('%H:%M:%S') if last_displayed else 'N/A'
                age_seconds = time.time() - load_timestamp if load_timestamp else 0
                
                # Build stats text
                stats_lines = [
                    f"Nodes: {num_nodes} | Edges: {num_edges}",
                    f"File: {current_time_str}",
                    f"Displayed: {last_displayed_str}",
                    f"Age: {age_seconds:.0f}s"
                ]
                stats_text = html.Div([
                    html.Div(line, style={'marginBottom': '2px'}) 
                    for line in stats_lines
                ])
                
                if current_mtime > last_displayed:
                    # New data available! - green button
                    # Requirements 5.1: green refresh button with "New data available" status
                    return (
                        green_button,
                        f"{get_agent_state_prefix(session_id)} ✅ New data available!",
                        stats_text,
                        messages_div
                    )
                else:
                    # Up to date - gray button
                    # Requirements 5.2: gray disabled refresh button
                    return (
                        gray_button,
                        f"{get_agent_state_prefix(session_id)} Up to date",
                        stats_text,
                        messages_div
                    )
            
            # No loaded data yet - monitor is working but hasn't loaded this session
            return (
                gray_button,
                f"{get_agent_state_prefix(session_id)} ⏳ Monitor loading...",
                f"Path: {log_file_path[:30]}...",
                messages_div
            )

    def _register_toggle_messages_callback(self):
        """
        Register callback for toggling monitor messages visibility.
        
        This implements the toggle functionality that:
        - Toggles visibility style between display:none and visible style
        - Toggles button text between "show" and "hide"
        - Uses n_clicks % 2 to determine state
        
        Requirements: 7.1, 7.2, 7.3, 7.4
        """
        from dash.dependencies import Input, Output
        
        @self.app.callback(
            [
                Output('main-panel-log-graph-monitor-messages', 'style'),
                Output('main-panel-log-graph-monitor-messages-toggle', 'children')
            ],
            [Input('main-panel-log-graph-monitor-messages-toggle', 'n_clicks')],
            prevent_initial_call=False
        )
        def toggle_monitor_messages(n_clicks):
            """Toggle visibility of monitor messages.
            
            Requirements: 7.1, 7.2, 7.3, 7.4
            - 7.1: WHEN a user clicks the toggle button THEN the monitor messages section SHALL hide if visible
            - 7.2: WHEN a user clicks the toggle button again THEN the monitor messages section SHALL show if hidden
            - 7.3: WHEN messages are hidden THEN the toggle button SHALL display "show"
            - 7.4: WHEN messages are visible THEN the toggle button SHALL display "hide"
            """
            # Use n_clicks % 2 to determine state
            # Odd clicks = hidden, Even clicks (including 0) = visible
            is_hidden = n_clicks % 2 == 1
            
            if is_hidden:
                # Messages are hidden - show "show" button text
                # Requirements 7.1, 7.3
                return {'display': 'none'}, 'show'
            else:
                # Messages are visible - show "hide" button text
                # Requirements 7.2, 7.4
                return {
                    'fontSize': '9px',
                    'color': '#6E6E80',
                    'fontFamily': 'monospace',
                    'maxHeight': '100px',
                    'overflowY': 'auto',
                    'backgroundColor': 'rgba(0, 0, 0, 0.2)',
                    'padding': '6px',
                    'borderRadius': '3px',
                    'marginBottom': '10px',
                    'lineHeight': '1.3'
                }, 'hide'

    def _register_draggable_panel_clientside(self):
        """
        Register clientside callback to make the log monitor panel draggable.
        
        This implements drag start, drag, drag end handlers using mousedown/mousemove/mouseup.
        Uses transform translate3d for smooth positioning.
        Marks panel as initialized with dataset.draggableInitialized to prevent duplicate handlers.
        
        Requirements: 6.1, 6.2, 6.3
        """
        from dash.dependencies import Input, Output
        
        self.app.clientside_callback(
            """
            function() {
                // Make the log monitor panel draggable
                const panel = document.getElementById('main-panel-log-graph-monitor-panel');
                const dragHandle = document.getElementById('main-panel-log-graph-monitor-drag-handle');

                if (panel && dragHandle && !panel.dataset.draggableInitialized) {
                    let isDragging = false;
                    let currentX;
                    let currentY;
                    let initialX;
                    let initialY;
                    let xOffset = 0;
                    let yOffset = 0;

                    dragHandle.addEventListener('mousedown', dragStart);
                    document.addEventListener('mousemove', drag);
                    document.addEventListener('mouseup', dragEnd);

                    function dragStart(e) {
                        initialX = e.clientX - xOffset;
                        initialY = e.clientY - yOffset;

                        if (e.target === dragHandle || dragHandle.contains(e.target)) {
                            isDragging = true;
                        }
                    }

                    function drag(e) {
                        if (isDragging) {
                            e.preventDefault();

                            currentX = e.clientX - initialX;
                            currentY = e.clientY - initialY;

                            xOffset = currentX;
                            yOffset = currentY;

                            setTranslate(currentX, currentY, panel);
                        }
                    }

                    function dragEnd(e) {
                        initialX = currentX;
                        initialY = currentY;
                        isDragging = false;
                    }

                    function setTranslate(xPos, yPos, el) {
                        el.style.transform = 'translate3d(' + xPos + 'px, ' + yPos + 'px, 0)';
                    }

                    panel.dataset.draggableInitialized = 'true';
                    console.log('[Log Monitor] Drag functionality initialized');
                }

                return window.dash_clientside.no_update;
            }
            """,
            Output('main-panel-log-graph-monitor-panel', 'data-drag-initialized'),
            Input('main-panel-log-graph-monitor-panel', 'id'),
            prevent_initial_call=False
        )

    def _register_monitor_tab_switching_clientside(self):
        """
        Register clientside callback for monitor tab switching.
        
        Handles clicks on logs, responses, settings tab buttons.
        Updates tab content visibility (display: block/none).
        Updates button styles (active: #19C37D, inactive: #4A4A5A).
        
        Requirements: 2.1
        """
        from dash.dependencies import Input, Output
        
        self.app.clientside_callback(
            """
            function(logs_clicks, responses_clicks, settings_clicks) {
                // Determine which button was clicked
                const ctx = window.dash_clientside.callback_context;
                if (!ctx.triggered.length) {
                    return window.dash_clientside.no_update;
                }

                const triggerId = ctx.triggered[0].prop_id.split('.')[0];

                // Define tabs
                const tabs = ['logs', 'responses', 'settings'];
                let activeTab = 'logs';  // default

                if (triggerId.includes('logs')) {
                    activeTab = 'logs';
                } else if (triggerId.includes('responses')) {
                    activeTab = 'responses';
                } else if (triggerId.includes('settings')) {
                    activeTab = 'settings';
                }

                // Update tab visibility and button styles
                tabs.forEach(tab => {
                    const tabContent = document.getElementById(`main-panel-log-graph-monitor-${tab}-tab`);
                    const tabBtn = document.getElementById(`main-panel-log-graph-monitor-tab-${tab}-btn`);

                    if (tab === activeTab) {
                        if (tabContent) tabContent.style.display = 'block';
                        if (tabBtn) {
                            tabBtn.style.backgroundColor = '#19C37D';
                            tabBtn.style.color = '#FFFFFF';
                        }
                    } else {
                        if (tabContent) tabContent.style.display = 'none';
                        if (tabBtn) {
                            tabBtn.style.backgroundColor = '#4A4A5A';
                            tabBtn.style.color = '#8E8EA0';
                        }
                    }
                });

                return window.dash_clientside.no_update;
            }
            """,
            Output('main-panel-log-graph-monitor-panel', 'data-tab-switch'),
            [
                Input('main-panel-log-graph-monitor-tab-logs-btn', 'n_clicks'),
                Input('main-panel-log-graph-monitor-tab-responses-btn', 'n_clicks'),
                Input('main-panel-log-graph-monitor-tab-settings-btn', 'n_clicks')
            ],
            prevent_initial_call=False
        )

    def _cleanup_on_exit(self):
        """Cleanup handler called on application exit."""
        try:
            # Stop log monitor
            if hasattr(self, '_log_monitor'):
                self._log_monitor.stop()
            # Cleanup action tester (close browser)
            self.action_tester_manager.close_browser()
        except Exception:
            pass


def create_app(testcase_root: Path = None, **kwargs) -> AgentDebuggerApp:
    """
    Factory function to create the agent debugger app.
    
    Args:
        testcase_root: Root directory for queue service discovery
        **kwargs: Additional arguments (title, port, debug, etc.)
        
    Returns:
        Configured AgentDebuggerApp instance
    """
    if testcase_root is None:
        testcase_root = Path(__file__).parent.parent  # Go up to webaxon/devsuite/

    # Set default kwargs
    kwargs.setdefault('title', 'Web Agent Debugger')
    kwargs.setdefault('port', 8050)
    kwargs.setdefault('debug', True)
    
    # Create the app
    app = AgentDebuggerApp(testcase_root=testcase_root, **kwargs)
    
    # Create a closure that has access to app.session_agents
    # This wires user chat input to actually send messages via queue_message_handler_internal
    def queue_message_handler_with_app(message: str, session_id: str, all_session_ids: list = None) -> str:
        """Message handler that has access to app's session_agents."""
        # Get the current agent type for this session (default to AGENT_TYPE_DEFAULT to match server)
        current_agent_type = AGENT_TYPE_DEFAULT  # Default matches server default
        if hasattr(app, 'session_agents') and session_id in app.session_agents:
            current_agent_type = app.session_agents[session_id]

        # Call the internal handler with current agent type for this session only
        return helpers.queue_message_handler_internal(message, session_id, all_session_ids, current_agent_type)
    
    # Set the message handler to wire user chat input to the queue
    app.set_message_handler(queue_message_handler_with_app)
    
    return app
