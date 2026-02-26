# Session Management Overview

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SessionManager                          │
│  (Thread-safe session lifecycle management)                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Private State:                                              │
│  • _sessions: Dict[str, AgentSessionInfo]                   │
│  • _lock: threading.RLock                                    │
│  • _config: ServiceConfig                                    │
│  • _queue_service: StorageBasedQueueService                 │
│  • _service_log_dir: Path                                    │
│                                                              │
│  Public Methods:                                             │
│  • get_or_create(session_id, agent_type, create_immediately)│
│  • get(session_id) -> Optional[AgentSessionInfo]            │
│  • update_session(session_id, **updates)                    │
│  • cleanup_session(session_id)                              │
│  • cleanup_idle_sessions()                                   │
│  • get_all_sessions() -> Dict[str, AgentSessionInfo]        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ manages
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    AgentSessionInfo                          │
│  (Dataclass extending SessionInfoBase)                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  From SessionInfoBase:                                       │
│  • session_id: str                                           │
│  • created_at: float                                         │
│  • last_active: float                                        │
│  • agent_type: str                                           │
│  • agent_created: bool                                       │
│                                                              │
│  Service-Specific Fields:                                    │
│  • logger: Optional[Callable]                                │
│  • log_dir_path: Optional[Path]                              │
│  • interactive: Optional[QueueInteractive]                   │
│  • agent: Optional[PromptBasedActionPlanningAgent]          │
│  • agent_thread: Optional[threading.Thread]                  │
│  • last_agent_status: Optional[str]                          │
│  • debugger: Optional[Debugger]                              │
│  • template_version: str                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Session Lifecycle

```
┌──────────────┐
│   Request    │
│   Session    │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────┐
│  SessionManager.get_or_create()      │
│                                      │
│  1. Check if session exists          │
│  2. If not, create:                  │
│     • Session log directory          │
│     • Session debugger               │
│     • Session logger function        │
│     • AgentSessionInfo (no agent)    │
│  3. Return session info              │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Session Active                      │
│                                      │
│  • Agent created lazily              │
│  • Messages processed                │
│  • last_active updated               │
│  • Status tracked                    │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Session Idle                        │
│                                      │
│  • No activity for timeout period    │
│  • Detected by cleanup_idle_sessions │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  SessionManager.cleanup_session()    │
│                                      │
│  1. Stop agent thread                │
│  2. Close interactive interface      │
│  3. Clear agent reference            │
│  4. Remove from sessions dict        │
└──────────────────────────────────────┘
```

## Thread Safety

All operations use `threading.RLock` for thread safety:

```python
with self._lock:
    # Critical section
    # Multiple threads can safely:
    # - Create sessions
    # - Update sessions
    # - Query sessions
    # - Cleanup sessions
```

**Why RLock?**
- Allows same thread to acquire lock multiple times
- Supports nested method calls
- Prevents deadlocks in complex operations

## Usage Examples

### Creating a Session

```python
from webaxon.devsuite.web_agent_service_nextgen.core import AgentSessionManager, ServiceConfig

# Initialize
config = ServiceConfig()
session_manager = AgentSessionManager(config, queue_service, log_dir)

# Create or get session
session_info = session_manager.get_or_create(
    session_id="user_123",
    agent_type="DefaultAgent"
)

# Session info contains:
# - session_id: "user_123"
# - agent_type: "DefaultAgent"
# - logger: function for logging
# - debugger: Debugger instance
# - agent: None (created lazily)
```

### Updating a Session

```python
# Update template version
session_manager.update_session(
    "user_123",
    template_version="v2.0"
)

# Update agent reference
session_manager.update_session(
    "user_123",
    agent=agent_instance,
    agent_created=True
)

# last_active is automatically updated
```

### Querying Sessions

```python
# Get specific session
session = session_manager.get("user_123")
if session:
    print(f"Agent type: {session.agent_type}")
    print(f"Agent created: {session.agent_created}")

# Get all sessions
all_sessions = session_manager.get_all_sessions()
for session_id, session_info in all_sessions.items():
    print(f"{session_id}: {session_info.agent_type}")
```

### Cleanup

```python
# Manual cleanup
session_manager.cleanup_session("user_123")

# Automatic idle cleanup
session_manager.cleanup_idle_sessions()
# Removes sessions idle > session_idle_timeout
```

## Integration with Other Components

### AgentFactory (Task 3)
```python
# AgentFactory will use SessionManager to:
# 1. Get session info
# 2. Create agent for session
# 3. Update session with agent reference
session_info = session_manager.get(session_id)
agent = agent_factory.create_agent(
    interactive=session_info.interactive,
    logger=session_info.logger,
    agent_type=session_info.agent_type,
    template_version=session_info.template_version
)
session_manager.update_session(
    session_id,
    agent=agent,
    agent_created=True
)
```

### MessageHandlers (Task 6)
```python
# MessageHandlers will use SessionManager to:
# 1. Query active sessions
# 2. Get session agent status
# 3. Update session state

# Handle sync_active_sessions
all_sessions = session_manager.get_all_sessions()
active_ids = list(all_sessions.keys())

# Handle sync_session_agent
session = session_manager.get(session_id)
agent_status = session.last_agent_status if session else None
```

### SessionMonitor (Task 10)
```python
# SessionMonitor will use SessionManager to:
# 1. Monitor status changes
# 2. Perform periodic cleanup

# In monitoring loop
session_manager.cleanup_idle_sessions()

# Check status changes
for session_id, session in session_manager.get_all_sessions().items():
    if session.agent and session.agent.status != session.last_agent_status:
        # Status changed, send acknowledgment
        session_manager.update_session(
            session_id,
            last_agent_status=session.agent.status
        )
```

## Key Design Decisions

1. **Lazy Agent Creation**
   - Sessions created without agents initially
   - Allows agent type changes before activation
   - Reduces resource usage for inactive sessions

2. **Automatic Timestamp Updates**
   - `last_active` updated on every `update_session()` call
   - Simplifies idle detection
   - No manual timestamp management needed

3. **Copy-on-Read for Collections**
   - `get_all_sessions()` returns copy
   - Prevents external modification of internal state
   - Thread-safe iteration

4. **Graceful Resource Cleanup**
   - Handles threads that can't be force-killed
   - Logs cleanup actions for debugging
   - Continues on errors (doesn't crash)

5. **Session-Specific Logging**
   - Each session has own log directory
   - Each session has own debugger instance
   - Simplifies log analysis and debugging

## Performance Considerations

- **Lock Contention**: RLock is efficient for low-contention scenarios
- **Memory**: Sessions kept in memory until cleanup
- **Cleanup Frequency**: Configurable via `cleanup_check_interval`
- **Thread Safety Overhead**: Minimal due to RLock efficiency

## Future Enhancements

1. **Persistence**: Save/restore sessions across service restarts
2. **Metrics**: Track session creation/cleanup rates
3. **Limits**: Maximum concurrent sessions
4. **Priorities**: Priority-based cleanup (keep important sessions longer)
5. **Events**: Callbacks for session lifecycle events
