# SessionMonitor Implementation Guide

## Overview

The SessionMonitor class provides background monitoring functionality for the Web Agent Service, including:
- Agent status change detection and acknowledgment
- Lazy agent creation when messages arrive
- Periodic cleanup of idle sessions
- Error-resilient operation

## Architecture

```
SessionMonitor
├── check_status_changes()      # Detect and acknowledge status changes
├── check_lazy_agent_creation() # Create agents on-demand
├── periodic_cleanup()           # Clean up idle sessions
└── run_monitoring_cycle()       # Execute all checks
```

## Key Features

### 1. Status Change Detection

The monitor continuously checks for changes in agent status and sends acknowledgments to the control queue:

```python
# Status flow
Agent starts → Status: 'running' → Acknowledgment sent
Agent completes → Status: 'completed' → Acknowledgment sent
Agent errors → Status: 'error' → Acknowledgment sent
```

**Possible statuses:**
- `not_created` - Agent not yet created
- `ready` - Agent created but not running
- `running` - Agent thread is active
- `stopped` - Agent thread has stopped
- `completed` - Agent finished successfully
- `error` - Agent encountered an error

### 2. Lazy Agent Creation

When `new_agent_on_first_submission` is enabled, agents are created on-demand:

```python
# Lazy creation flow
Message arrives → Check if agent exists → Create agent if needed → Process message
```

**Benefits:**
- Reduces resource usage
- Allows agent type changes before first message
- Agents only created when actually needed

### 3. Periodic Cleanup

Idle sessions are cleaned up at regular intervals:

```python
# Cleanup flow
Check elapsed time → If interval passed → Cleanup idle sessions → Update timestamp
```

**Configuration:**
- `cleanup_check_interval`: How often to check (default: 5 minutes)
- `session_idle_timeout`: How long before session is idle (default: 30 minutes)

### 4. Error Resilience

All monitoring operations handle errors gracefully:

```python
# Error handling pattern
try:
    # Monitoring operation
except Exception as e:
    # Log error
    # Continue monitoring other sessions
    # Don't crash service
```

## Usage

### Basic Usage

```python
from webaxon.devsuite.web_agent_service_nextgen.session import SessionMonitor

# Create monitor
monitor = SessionMonitor(
    session_manager=session_manager,
    queue_service=queue_service,
    config=config,
    agent_factory=agent_factory
)

# Run monitoring cycle (call repeatedly in main loop)
monitor.run_monitoring_cycle()
```

### Integration with WebAgentService

```python
class WebAgentService:
    def __init__(self, testcase_root: Path, config: Optional[ServiceConfig] = None):
        # Initialize components
        self._session_manager = SessionManager(...)
        self._agent_factory = AgentFactory(...)
        queue_service = self._queue_manager.initialize()
        
        # Create monitor
        self._session_monitor = SessionMonitor(
            session_manager=self._session_manager,
            queue_service=queue_service,
            config=self._config,
            agent_factory=self._agent_factory
        )
    
    def run(self):
        while not self._shutdown_requested:
            # Process messages
            # ...
            
            # Run monitoring
            self._session_monitor.run_monitoring_cycle()
            
            # Sleep to prevent tight loop
            time.sleep(0.1)
```

## Configuration

### ServiceConfig Options

```python
config = ServiceConfig(
    # Cleanup settings
    session_idle_timeout=30 * 60,      # 30 minutes
    cleanup_check_interval=5 * 60,     # 5 minutes
    
    # Agent creation
    new_agent_on_first_submission=True,  # Enable lazy creation
    
    # Queue IDs
    input_queue_id='user_input',
    server_control_queue_id='server_control',
)
```

## Monitoring Operations

### Status Change Detection

**When it runs:** Every monitoring cycle

**What it does:**
1. Iterates through all active sessions
2. Gets current agent status
3. Compares with last known status
4. If changed:
   - Logs the change
   - Sends acknowledgment to control queue
   - Updates session's last_agent_status

**Message format:**
```python
{
    'type': 'agent_status_change',
    'session_id': 'session_123',
    'status': 'running',
    'timestamp': '2024-01-15T10:30:00'
}
```

### Lazy Agent Creation

**When it runs:** Every monitoring cycle (if enabled)

**What it does:**
1. Checks if lazy creation is enabled
2. Iterates through sessions without agents
3. Checks for waiting messages
4. If messages exist:
   - Creates QueueInteractive
   - Creates agent via AgentFactory
   - Updates session with agent
   - Logs creation

**Requirements:**
- `new_agent_on_first_submission` must be True
- Session must not have agent created yet
- Messages must be waiting in input queue

### Periodic Cleanup

**When it runs:** When cleanup interval elapses

**What it does:**
1. Checks time since last cleanup
2. If interval elapsed:
   - Calls SessionManager.cleanup_idle_sessions()
   - Updates last cleanup timestamp
   - Logs cleanup execution

**Cleanup criteria:**
- Session idle time > session_idle_timeout
- Handled by SessionManager

## Error Handling

### Per-Session Errors

Errors in individual sessions don't affect other sessions:

```python
for session_id, session_info in sessions.items():
    try:
        # Process session
    except Exception as e:
        # Log error for this session
        # Continue with next session
```

### Global Errors

Errors in monitoring don't crash the service:

```python
def check_status_changes(self):
    try:
        # All monitoring logic
    except Exception as e:
        # Log error
        # Don't raise - service continues
```

## Testing

### Unit Tests

```bash
python test_session_monitor.py
```

Tests cover:
- Initialization
- Status change detection
- Lazy agent creation
- Periodic cleanup
- Error resilience
- Helper methods

### Verification

```bash
python verify_task10.py
```

Validates:
- All requirements met
- Integration with other components
- Error handling works correctly

## Performance Considerations

### Monitoring Overhead

The monitor is designed to be lightweight:
- Status checks are fast (just checking thread state)
- Lazy creation only checks when needed
- Cleanup runs at intervals, not continuously
- All operations are non-blocking

### Recommended Settings

For production:
```python
config = ServiceConfig(
    cleanup_check_interval=5 * 60,    # 5 minutes
    session_idle_timeout=30 * 60,     # 30 minutes
)
```

For development/testing:
```python
config = ServiceConfig(
    cleanup_check_interval=30,        # 30 seconds
    session_idle_timeout=5 * 60,      # 5 minutes
)
```

## Debugging

### Enable Debug Logging

```python
config = ServiceConfig(
    debug_mode_service=True  # Enable detailed logging
)
```

### Monitor Logs

Look for these log types:
- `AGENT_LIFECYCLE` - Agent status changes
- `SESSION_MANAGEMENT` - Session operations
- `ERROR` - Errors in monitoring

### Common Issues

**Issue:** Status changes not detected
- Check: Is agent_created True?
- Check: Does session have agent?
- Check: Is monitoring cycle running?

**Issue:** Lazy creation not working
- Check: Is new_agent_on_first_submission True?
- Check: Are messages in input queue?
- Check: Is agent_created False?

**Issue:** Cleanup not running
- Check: Has cleanup interval elapsed?
- Check: Are sessions actually idle?
- Check: Is SessionManager working?

## Best Practices

1. **Call monitoring cycle regularly** - Every 0.1-1 second in main loop
2. **Don't block monitoring** - Keep monitoring operations fast
3. **Handle errors gracefully** - Never let monitoring crash service
4. **Log important events** - Status changes, agent creation, cleanup
5. **Configure intervals appropriately** - Balance responsiveness vs overhead

## Future Enhancements

Potential improvements:
- Configurable status change filters
- Metrics collection (status change frequency, cleanup counts)
- Health checks for stuck agents
- Automatic agent restart on errors
- Session priority-based cleanup

## Related Components

- **SessionManager** - Manages session lifecycle
- **AgentFactory** - Creates agents
- **QueueService** - Communication infrastructure
- **ServiceConfig** - Configuration management

## References

- Design Document: `.kiro/specs/web-agent-service-modularization/design.md`
- Requirements: `.kiro/specs/web-agent-service-modularization/requirements.md`
- Task List: `.kiro/specs/web-agent-service-modularization/tasks.md`
