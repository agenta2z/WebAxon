"""
Launch Script for Agent Debugger

Entry point for starting the modular agent debugger application.
"""
from pathlib import Path
from functools import partial

# Resolve paths first before any imports
from resolve_path import resolve_path
TESTCASE_ROOT = resolve_path()

from rich_python_utils.common_objects.debuggable import Debugger
from rich_python_utils.io_utils.json_io import write_json

# Import app creation function
from webaxon.devsuite.agent_debugger_nextgen.app import create_app

# Import constants
from webaxon.devsuite import config
from webaxon.devsuite.common import DebuggerLogTypes
from webaxon.devsuite.constants import RUNTIME_DIR, FOLDER_NAME_DEBUGGER_LOGS


def _get_or_create_global_debugger():
    """Get or create the global debugger for startup logging."""
    debugger_log_dir = TESTCASE_ROOT / RUNTIME_DIR / FOLDER_NAME_DEBUGGER_LOGS / 'global'
    debugger_log_dir.mkdir(parents=True, exist_ok=True)

    debugger = Debugger(
        id='agent_debugger_global',
        log_name='AgentDebugger',
        logger=[
            print,
            partial(write_json, file_path=str(debugger_log_dir / FOLDER_NAME_DEBUGGER_LOGS), append=True)
        ],
        debug_mode=config.DEBUG_MODE_DEBUGGER,
        log_time=True,
        always_add_logging_based_logger=False,
        # Rate limiting for console output
        console_display_rate_limit=config.CONSOLE_DISPLAY_RATE_LIMIT,
        enable_console_update=config.ENABLE_CONSOLE_UPDATE
    )
    return debugger


def main():
    """Run the agent debugger UI."""
    debugger = _get_or_create_global_debugger()

    # Log startup information
    startup_info = {
        'title': 'WEB AGENT DEBUGGER - Modular Queue-Based UI',
        'version': '2.0.0',
        'architecture': {
            'modular_design': 'Separated into core, communication, UI, and monitoring modules',
            'queue_based_communication': 'Uses StorageBasedQueueService',
            'decoupled_design': 'UI and agent run in separate processes',
            'persistent_queues': 'File-based queues survive restarts'
        },
        'modules': {
            'core': 'Configuration and session management',
            'communication': 'Queue client and message handlers',
            'ui': 'Dash components and panels',
            'monitoring': 'Background log monitoring'
        },
        'setup': [
            'Start the agent service: python web_agent_service.py',
            'Start this debugger UI: python launch_debugger.py',
            'Navigate to http://localhost:8050'
        ],
        'features': [
            'Modular architecture for maintainability',
            'Asynchronous communication through queues',
            'Real web agent with browser automation',
            'Execution graph visualization',
            'Detailed log inspection',
            'Multi-process architecture'
        ]
    }
    debugger.log_info(startup_info, DebuggerLogTypes.DEBUGGER_STARTUP)

    # Create and run the app
    debugger.log_info("Creating agent debugger app...", DebuggerLogTypes.DEBUGGER_STARTUP)
    app = create_app(testcase_root=TESTCASE_ROOT)

    debugger.log_info("Starting agent debugger server...", DebuggerLogTypes.DEBUGGER_STARTUP)
    app.run()


if __name__ == '__main__':
    main()
