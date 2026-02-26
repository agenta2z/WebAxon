# Web Agent Service Modularization Plan

## Overview

Create `web_agent_service_nextgen` - a modularized version of `web_agent_service.py` following the same architecture pattern used for `agent_debugger_nextgen`.

## Current Structure Analysis

The current `web_agent_service.py` (~1253 lines) is a monolithic file that handles:

1. **Agent Creation** - Creates different agent types (Default, Mock)
2. **Session Management** - Tracks agent sessions, lifecycle, cleanup
3. **Queue Communication** - Listens to control queues, sends responses
4. **Message Handling** - Processes sync, control, and agent messages
5. **Thread Management** - Runs agents in separate threads
6. **Template Management** - Manages prompt templates with versioning
7. **Logging & Debugging** - Session-specific and global logging

## Proposed Modular Architecture

```
web_agent_service_nextgen/
├── __init__.py                    # Module exports
├── service.py                     # Main service class
├── launch_service.py              # Entry point script
├── README.md                      # Documentation
├── core/
│   ├── __init__.py
│   ├── config.py                  # Service configuration
│   ├── session.py                 # AgentSessionInfo, session management
│   └── agent_factory.py           # Agent creation logic
├── communication/
│   ├── __init__.py
│   ├── queue_manager.py           # Queue service management
│   └── message_handlers.py        # Control message processing
├── agents/
│   ├── __init__.py
│   ├── agent_runner.py            # Thread management for agents
│   └── template_manager.py        # Template versioning wrapper
└── monitoring/
    ├── __init__.py
    └── session_monitor.py         # Idle session cleanup, status monitoring
```

## Module Responsibilities

### 1. `core/config.py`
**Purpose**: Centralize all configuration
```python
@dataclass
class ServiceConfig:
    """Service configuration."""
    session_idle_timeout: int = 30 * 60  # 30 minutes
    cleanup_check_interval: int = 5 * 60  # 5 minutes
    debug_mode: bool = DEBUG_MODE_SERVICE
    synchronous_agent: bool = DEBUG_MODE_SYNCHRONOUS_AGENT
    new_agent_on_first_submission: bool = OPTION_NEW_AGENT_ON_FIRST_SUBMISSION
    default_agent_type: str = AGENT_TYPE_DEFAULT
    
    # Queue IDs
    input_queue_id: str = INPUT_QUEUE_ID
    response_queue_id: str = RESPONSE_QUEUE_ID
    client_control_queue_id: str = CLIENT_CONTROL_QUEUE_ID
    server_control_queue_id: str = SERVER_CONTROL_QUEUE_ID
```

### 2. `core/session.py`
**Purpose**: Session state management
```python
@dataclass
class AgentSessionInfo(SessionInfoBase):
    """Session information with service-specific fields."""
    logger: Callable = None
    log_dir_path: Path = None
    interactive: QueueInteractive = None
    agent: PromptBasedActionPlanningAgent = None
    agent_thread: threading.Thread = None
    last_agent_status: str = None
    debugger: Debugger = None
    template_version: str = ""  # NEW: Track template version per session

class SessionManager:
    """Manages agent sessions."""
    def __init__(self, config: ServiceConfig, queue_service, service_log_dir: Path):
        self.config = config
        self.queue_service = queue_service
        self.service_log_dir = service_log_dir
        self.sessions: Dict[str, AgentSessionInfo] = {}
    
    def get_or_create(self, session_id: str, agent_type: str = None, 
                      create_immediately: bool = False) -> AgentSessionInfo:
        """Get or create session."""
    
    def cleanup_session(self, session_id: str):
        """Clean up session resources."""
    
    def cleanup_idle_sessions(self):
        """Remove idle sessions."""
    
    def get_all_sessions(self) -> Dict[str, AgentSessionInfo]:
        """Get all active sessions."""
```

### 3. `core/agent_factory.py`
**Purpose**: Agent creation logic
```python
class AgentFactory:
    """Factory for creating different agent types."""
    
    def __init__(self, prompt_template_manager: TemplateManager, config: ServiceConfig):
        self.template_manager = prompt_template_manager
        self.config = config
    
    def create_agent(self, interactive: QueueInteractive, logger: Callable,
                     agent_type: str = AGENT_TYPE_DEFAULT,
                     template_version: str = "") -> PromptBasedActionPlanningAgent:
        """Create agent based on type and template version."""
        
        # Set template version if provided
        if template_version:
            self.template_manager.switch(template_version=template_version)
        
        if agent_type == AGENT_TYPE_MOCK_CLARIFICATION:
            return self._create_mock_agent(interactive, logger)
        else:
            return self._create_default_agent(interactive, logger)
    
    def _create_mock_agent(self, interactive, logger):
        """Create mock clarification agent."""
    
    def _create_default_agent(self, interactive, logger):
        """Create default planning agent with full capabilities."""
```

### 4. `communication/queue_manager.py`
**Purpose**: Queue service initialization and management
```python
class QueueManager:
    """Manages queue service lifecycle."""
    
    def __init__(self, testcase_root: Path, config: ServiceConfig):
        self.testcase_root = testcase_root
        self.config = config
        self.queue_service = None
        self.queue_root_path = None
    
    def initialize(self) -> StorageBasedQueueService:
        """Initialize queue service with timestamped path."""
    
    def create_queues(self):
        """Create all required queues."""
    
    def close(self):
        """Close queue service."""
```

### 5. `communication/message_handlers.py`
**Purpose**: Process control messages
```python
class MessageHandlers:
    """Handles different types of control messages."""
    
    def __init__(self, session_manager: SessionManager, agent_factory: AgentFactory,
                 queue_service, config: ServiceConfig):
        self.session_manager = session_manager
        self.agent_factory = agent_factory
        self.queue_service = queue_service
        self.config = config
    
    def handle_sync_active_sessions(self, message: dict):
        """Handle sync_active_sessions message."""
    
    def handle_sync_session_agent(self, message: dict):
        """Handle sync_session_agent message."""
    
    def handle_sync_session_template_version(self, message: dict):
        """Handle sync_session_template_version message - NEW!"""
    
    def handle_agent_control(self, message: dict):
        """Handle agent_control message (stop/pause/continue/step)."""
    
    def dispatch(self, message: dict):
        """Dispatch message to appropriate handler."""
```

### 6. `agents/agent_runner.py`
**Purpose**: Thread management for agent execution
```python
class AgentRunner:
    """Manages agent thread execution."""
    
    def __init__(self, config: ServiceConfig):
        self.config = config
    
    def start_agent_thread(self, session_info: AgentSessionInfo, 
                          queue_service) -> Optional[threading.Thread]:
        """Start agent in separate thread (or skip if synchronous mode)."""
    
    def run_agent_in_thread(self, session_info: AgentSessionInfo, queue_service):
        """Run agent in thread (blocking)."""
    
    def run_agent_synchronously(self, session_info: AgentSessionInfo):
        """Run agent in main process for debugging."""
```

### 7. `monitoring/session_monitor.py`
**Purpose**: Monitor session status and cleanup
```python
class SessionMonitor:
    """Monitors agent sessions for status changes and cleanup."""
    
    def __init__(self, session_manager: SessionManager, queue_service, config: ServiceConfig):
        self.session_manager = session_manager
        self.queue_service = queue_service
        self.config = config
        self.last_cleanup_time = time.time()
    
    def check_status_changes(self):
        """Monitor agent status changes and send acks."""
    
    def check_lazy_agent_creation(self):
        """Check for messages waiting and create agents lazily."""
    
    def periodic_cleanup(self):
        """Perform periodic cleanup of idle sessions."""
```

### 8. `service.py`
**Purpose**: Main service orchestration
```python
class WebAgentService:
    """Main web agent service."""
    
    def __init__(self, testcase_root: Path, config: ServiceConfig = None):
        self.testcase_root = testcase_root
        self.config = config or ServiceConfig()
        
        # Initialize components
        self.queue_manager = QueueManager(testcase_root, self.config)
        self.template_manager = self._create_template_manager()
        self.agent_factory = AgentFactory(self.template_manager, self.config)
        
        # Will be initialized in run()
        self.session_manager = None
        self.message_handlers = None
        self.agent_runner = None
        self.session_monitor = None
        self.global_debugger = None
    
    def _create_template_manager(self) -> TemplateManager:
        """Create template manager with default configuration."""
    
    def run(self):
        """Run the service loop."""
        # Initialize queue service
        # Create session manager
        # Create message handlers
        # Create agent runner
        # Create session monitor
        # Run main loop
```

### 9. `launch_service.py`
**Purpose**: Entry point
```python
"""
Launch Script for Web Agent Service

Entry point for starting the modular web agent service.
"""
from pathlib import Path
from .service import WebAgentService
from .core.config import ServiceConfig

def main():
    """Run the web agent service."""
    testcase_root = Path(__file__).parent
    
    # Create and run service
    service = WebAgentService(testcase_root)
    service.run()

if __name__ == '__main__':
    main()
```

## Key Improvements

### 1. Template Version Support
- Add `template_version` field to `AgentSessionInfo`
- Handle `sync_session_template_version` messages
- Pass template version to agent factory
- Switch template manager version when creating agents

### 2. Better Separation of Concerns
- Configuration isolated in one place
- Session management separate from message handling
- Agent creation logic encapsulated
- Queue operations centralized

### 3. Testability
- Each module can be tested independently
- Mock dependencies easily
- Clear interfaces between components

### 4. Maintainability
- Smaller, focused files
- Clear responsibilities
- Easier to understand and modify
- Better code organization

## Migration Strategy

### Phase 1: Create Module Structure
1. Create directory structure
2. Create `__init__.py` files
3. Create `config.py` with all constants

### Phase 2: Extract Core Components
1. Extract `AgentSessionInfo` to `core/session.py`
2. Create `SessionManager` class
3. Extract agent creation to `core/agent_factory.py`

### Phase 3: Extract Communication
1. Create `QueueManager` in `communication/queue_manager.py`
2. Extract message handlers to `communication/message_handlers.py`
3. Add template version message handler

### Phase 4: Extract Agent Management
1. Create `AgentRunner` in `agents/agent_runner.py`
2. Extract thread management logic

### Phase 5: Extract Monitoring
1. Create `SessionMonitor` in `monitoring/session_monitor.py`
2. Extract cleanup and status monitoring logic

### Phase 6: Create Main Service
1. Create `WebAgentService` class in `service.py`
2. Wire all components together
3. Create `launch_service.py` entry point

### Phase 7: Testing & Documentation
1. Test each module independently
2. Integration testing
3. Update README
4. Create migration guide

## Backward Compatibility

- Keep original `web_agent_service.py` in `_archive/`
- New service uses same queue protocol
- Same message formats
- Works with existing debugger

## Benefits

1. **Modularity**: Each component has single responsibility
2. **Testability**: Easy to unit test individual components
3. **Extensibility**: Easy to add new agent types or message handlers
4. **Template Versioning**: Full support for per-session template versions
5. **Maintainability**: Easier to understand and modify
6. **Reusability**: Components can be reused in other projects

## Next Steps

1. Review and approve this plan
2. Create spec document if needed
3. Begin Phase 1 implementation
4. Iterate through phases
5. Test and validate
6. Deploy and monitor

## Estimated Effort

- Phase 1-2: 2-3 hours (structure + core)
- Phase 3-4: 2-3 hours (communication + agents)
- Phase 5-6: 2-3 hours (monitoring + service)
- Phase 7: 1-2 hours (testing + docs)
- **Total**: 7-11 hours

## Success Criteria

- [ ] All modules created with clear responsibilities
- [ ] Template version support fully implemented
- [ ] Service runs and processes all message types
- [ ] Works with existing debugger
- [ ] All tests pass
- [ ] Documentation complete
- [ ] Original service archived
