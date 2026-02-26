# Agent Debugger Next Generation

Modular Dash UI for Queue-Based Agent Interaction.

## Structure

```
agent_debugger_nextgen/
├── core/                    # Core abstractions
│   ├── config.py           # DebuggerConfig - centralized configuration
│   └── session.py          # SessionManager - thread-safe session management
├── communication/           # Queue-based communication (TODO)
│   ├── queue_client.py     # Queue operations wrapper
│   └── message_handlers.py # Message processing logic
├── ui/                      # UI components (TODO)
│   ├── components/         # Reusable UI components
│   │   └── settings_panel.py
│   └── tabs/               # Tab implementations
│       └── action_tester_tab.py
├── monitoring/              # Logging and monitoring (TODO)
│   └── log_monitor.py      # Background log file monitoring
├── app.py                   # Main Dash app (TODO)
└── launch_debugger.py       # Entry point (TODO)
```

## Current Status

**Phase 1 Complete: Core Modules**
- ✅ DebuggerConfig - Configuration with environment variable support
- ✅ SessionManager - Thread-safe session state management
- ✅ DebuggerSessionInfo - Session data model

**Phase 2 Complete: Communication Modules**
- ✅ QueueClient - Queue operations wrapper with typed methods
- ✅ MessageHandlers - Message processing for agent_status, agent_control_ack, log_path

**Phase 3 Complete: UI Components**
- ✅ SettingsPanel - Settings UI component extending BaseComponent

**Phase 4 Complete: Monitoring**
- ✅ LogMonitor - Background log file monitoring service

**Ready for Integration:**
All core modules are implemented and tested. Next step is to create the main app.py
that wires everything together, or integrate these modules into the existing debugger.

## Usage

```python
from tools.devsuite.agent_debugger_nextgen.core import DebuggerConfig, SessionManager

# Create configuration
config = DebuggerConfig.from_env()
config.validate()

# Create session manager
session_manager = SessionManager()

# Get or create a session
session = session_manager.get_or_create('session_1')
print(session.agent_status)  # 'not_started'

# Update session
session_manager.update_session('session_1', agent_status='running')

# Get active sessions
active_ids = session_manager.get_active_ids()
```

## Migration from agent_debugger_ng

The old `agent_debugger_ng` folder has been archived. This new implementation provides:
- Better modularity and separation of concerns
- Thread-safe session management
- Centralized configuration
- Easier testing and maintenance

## Development

See `.kiro/specs/agent-debugger-modularization/` for full design and implementation plan.
