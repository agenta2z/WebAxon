"""
Web Agent Framework - Configuration Settings.

This module contains configurable options for the web agent service behavior.
Settings can be modified to change how agents are created and managed.
"""

# Agent Creation Mode Configuration
# ----------------------------------

OPTION_NEW_AGENT_ON_FIRST_SUBMISSION = False
"""
Controls when agents are created for a session.

- True (default): Lazy creation - Agent is created when the first message is submitted.
  This allows the agent type to be changed before any messages are sent.

- False: Immediate creation - Agent is created immediately when the session is created
  (e.g., when "New Chat" is clicked). This allows for manual browser pre-setup before
  agent interaction, such as logging into websites or configuring cookies.

Use Case for False:
  1. User clicks "New Chat"
  2. Agent + visible browser window opens immediately
  3. User performs manual setup in the browser (login, cookies, etc.)
  4. User sends first message to start agent interaction

Use Case for True (default):
  1. User clicks "New Chat"
  2. Session is created but agent not initialized yet
  3. User can change agent type if desired
  4. User sends first message → Agent created → Browser opens → Message processed
"""

OPTION_BASE_REASONER = 'Claude'

OPTION_DEFAULT_PROMPT_VERSION = 'end_customers'

# Debug Mode Configuration
# -------------------------

DEBUG_MODE_SERVICE = True
"""
Controls debug verbosity for the web agent service.

- True (default): Enables detailed debug logging for service operations, queue handling,
  agent lifecycle management, etc. Useful during development and troubleshooting.

- False: Production mode - Only INFO level and above messages are logged.
  Reduces log volume and improves performance.
"""

DEBUG_MODE_DEBUGGER = True
"""
Controls debug verbosity for the agent debugger UI.

- True (default): Enables detailed debug logging for UI operations, log monitoring,
  session management, auto-loading, etc. Useful during development.

- False: Production mode - Only INFO level and above messages are logged.
  Reduces console clutter in the debugger UI.
"""

CONSOLE_DISPLAY_RATE_LIMIT = 2.0
"""
Rate limit for console message display (seconds).

Controls the minimum interval between console log messages for the same message ID.
- 0.0: No rate limiting (display all messages)
- 2.0 (default): Display at most one message every 2 seconds
- Higher values reduce console flooding during monitoring loops
"""

ENABLE_CONSOLE_UPDATE = True
"""
Enable in-place console updates.

When True, status messages will update in place rather than printing new lines,
reducing console scrolling. Requires terminal support for ANSI escape codes.
"""

DEBUG_MODE_SYNCHRONOUS_AGENT = True
"""
Controls whether agents run synchronously in the main process (no threading) for debugging.

- False (default): Production mode - Agents run in separate daemon threads, allowing
  concurrent session handling and responsive control message processing.

- True: Debug mode - Agent runs synchronously in the main process, making breakpoints
  work properly. In this mode:
  * Only ONE session is allowed (additional sessions are rejected)
  * Agent processes one message at a time in the main loop
  * Control messages are checked between agent actions
  * Use this when debugging agent code with breakpoints

WARNING: Only use True during development for debugging. Not suitable for production
or multi-session scenarios.
"""

MOCK_USER_PROFILE = {
    'default': {
        'Name': {
            'FirstName': 'Tony',
            'LastName': 'Chen'
        },
        'Known URLs': [
            {
                'Name': 'Slack',
                'URL': 'https://app.slack.com/client/',
                'Description': 'Visit corporate slack chat page to access Slack channels, direct messages, etc.'
            }
        ]
    },
    'end_customers': {
        'Name': {
            'FirstName': 'Tony',
            'LastName': 'Chen'
        },
        'Family': [
            {
                'Relation': 'Son',
                'Age': 9,
                'FirstName': 'Lincoln',
                'LastName': 'Yuan'
            }
        ],
        'PhoneNumber': '206-653-6387',
        'Location': 'Seattle, Washington, USA',
        'ZipCode': '98121',
        'Grocery Stores': """- Safeway (https://www.safeway.com), member, frequent customer, free delivery for qualifying purchases
- QFC (https://www.qfc.com), member, frequent customer, free delivery for qualifying purchases"""
    }
}

DEFAULT_AGENT_REASONER_ARGS = {
    'connect_timeout': 20,
    'response_timeout': 120,
    'max_new_tokens': 8192
}

RESPONSE_AGENT_REASONER_ARGS = {
    'max_new_tokens': 16384
}
