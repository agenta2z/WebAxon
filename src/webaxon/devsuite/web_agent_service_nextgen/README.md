# Web Agent Service - Modularized Architecture

This is a modular, maintainable implementation of the web agent service with clear separation of concerns and improved testability.

## 📚 Documentation

**Comprehensive documentation is available in the [docs/](docs/) folder:**

- **[Getting Started](docs/getting-started/quick-start.md)** - Quick start guide
- **[User Guides](docs/guides/)** - Configuration, session management, monitoring, and more
- **[Testing](docs/testing/)** - Integration test documentation
- **[Documentation Index](docs/index.md)** - Complete documentation hub

For a quick overview, continue reading below. For detailed guides, visit the [docs/](docs/) folder.

---

## Architecture Overview

The service is organized into focused modules:

```
web_agent_service_nextgen/
├── core/                      # Core components
│   ├── config.py             # Service configuration
│   ├── session.py            # Session state management
│   └── agent_factory.py      # Agent creation logic
├── communication/             # Communication layer
│   ├── queue_manager.py      # Queue service management
│   └── message_handlers.py   # Control message processing
├── agents/                    # Agent management
│   ├── agent_runner.py       # Thread management for agents
│   └── template_manager.py   # Template versioning wrapper
├── session/                   # Session lifecycle
│   ├── manifest.py           # Session manifest data model
│   ├── session_log_manager.py # Structured session logging
│   └── session_monitor.py    # Session health monitoring
├── service.py                 # Main service orchestration
└── launch_service.py          # Entry point script
```

## Key Features

- **Modular Design**: Each component has a single responsibility
- **Template Versioning**: Full support for per-session template versions
- **Thread-Safe**: All session operations are thread-safe
- **Configurable**: Extensive configuration via environment variables
- **Testable**: Easy to unit test with mocked dependencies
- **Backward Compatible**: Works with existing agent debugger

## Configuration

Configuration is managed through the `ServiceConfig` class with environment variable support:

```python
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig

# Load from environment variables
config = ServiceConfig.from_env()

# Or create with custom values
config = ServiceConfig(
    session_idle_timeout=1800,  # 30 minutes
    debug_mode_service=True,
    synchronous_agent=False
)
```

### Environment Variables

All configuration can be set via environment variables with the `WEBAGENT_SERVICE_` prefix:

- `WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT`: Session idle timeout in seconds (default: 1800)
- `WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL`: Cleanup check interval in seconds (default: 300)
- `WEBAGENT_SERVICE_DEBUG_MODE_SERVICE`: Enable debug logging (default: true)
- `WEBAGENT_SERVICE_SYNCHRONOUS_AGENT`: Run agents synchronously (default: false)
- `WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION`: Create agents lazily (default: true)
- `WEBAGENT_SERVICE_DEFAULT_AGENT_TYPE`: Default agent type (default: DefaultAgent)
- `WEBAGENT_SERVICE_INPUT_QUEUE_ID`: Input queue ID (default: user_input)
- `WEBAGENT_SERVICE_RESPONSE_QUEUE_ID`: Response queue ID (default: agent_response)
- `WEBAGENT_SERVICE_CLIENT_CONTROL_QUEUE_ID`: Client control queue ID (default: client_control)
- `WEBAGENT_SERVICE_SERVER_CONTROL_QUEUE_ID`: Server control queue ID (default: server_control)
- `WEBAGENT_SERVICE_QUEUE_ROOT_PATH`: Custom queue root path (optional)
- `WEBAGENT_SERVICE_LOG_ROOT_PATH`: Log root path (default: _runtime)

## Usage

### Quick Start

The easiest way to start the service is using the launch script:

```bash
# Navigate to the service directory
cd WebAgent/src/webaxon/devsuite/web_agent_service_nextgen

# Start the service
python launch_service.py /path/to/testcase
```

The service will:
1. Load configuration from environment variables
2. Initialize all components
3. Create timestamped queue directories
4. Start the main service loop
5. Wait for messages from the debugger UI

### Command Line Options

```bash
# Show help and all options
python launch_service.py --help

# Enable debug mode
python launch_service.py --debug /path/to/testcase

# Run agents synchronously for debugging
python launch_service.py --synchronous /path/to/testcase

# Combine options
python launch_service.py --debug --synchronous /path/to/testcase
```

### Environment Variable Configuration

Set environment variables before starting the service:

```bash
# Linux/Mac
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=3600
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true
python launch_service.py /path/to/testcase

# Windows (PowerShell)
$env:WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=3600
$env:WEBAGENT_SERVICE_DEBUG_MODE_SERVICE="true"
python launch_service.py /path/to/testcase

# Windows (CMD)
set WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=3600
set WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true
python launch_service.py /path/to/testcase
```

### Programmatic Usage

You can also use the service programmatically in your own scripts:

```python
from pathlib import Path
from web_agent_service_nextgen import WebAgentService
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig

# Create configuration
config = ServiceConfig.from_env()

# Or create with custom values
config = ServiceConfig(
    session_idle_timeout=3600,  # 1 hour
    cleanup_check_interval=600,  # 10 minutes
    debug_mode_service=True,
    synchronous_agent=False,
    new_agent_on_first_submission=True,
    default_agent_type='DefaultAgent'
)

# Create and run service
testcase_root = Path('path/to/testcase')
service = WebAgentService(testcase_root, config)
service.run()  # Blocks until shutdown signal
```

### Integration with Agent Debugger

The service is designed to work with the agent debugger UI:

1. **Start the service first:**
   ```bash
   cd WebAgent/src/webaxon/devsuite/web_agent_service_nextgen
   python launch_service.py /path/to/testcase
   ```

2. **Start the debugger UI:**
   ```bash
   cd WebAgent/src/webaxon/devsuite/agent_debugger_nextgen
   python launch_debugger.py /path/to/testcase
   ```

3. **Access the UI:**
   Open your browser to `http://localhost:8050`

The debugger and service communicate through file-based queues, allowing them to run independently and survive restarts.

## Component Details

### Core Components

#### ServiceConfig
Centralized configuration with environment variable support and validation.

#### SessionManager
Thread-safe session lifecycle management with automatic cleanup of idle sessions.

#### AgentFactory
Factory for creating different types of agents with proper configuration and template version support.

### Communication Components

#### QueueManager
Manages queue service lifecycle, initialization, and cleanup.

#### MessageHandlers
Processes control messages from the debugger UI and coordinates with other components.

### Agent Management

#### AgentRunner
Manages agent execution in threads or synchronously for debugging.

#### TemplateManagerWrapper
Wraps the existing TemplateManager to provide version tracking and switching.

### Monitoring

#### SessionMonitor
Monitors session health, detects status changes, and performs periodic cleanup.

## Message Protocol

The service communicates via queue-based messages using the StorageBasedQueueService. Messages are JSON objects sent through file-based queues.

### Queue Architecture

The service uses four queues:

1. **Input Queue** (`user_input`): User messages to agents
2. **Response Queue** (`agent_response`): Agent responses to users
3. **Client Control Queue** (`client_control`): Control messages from debugger to service
4. **Server Control Queue** (`server_control`): Status updates from service to debugger

### Control Messages

Control messages are sent from the debugger UI to the service via the `client_control` queue.

#### sync_active_sessions

Get a list of all active session IDs.

**Request:**
```json
{
    "type": "sync_active_sessions",
    "timestamp": "2024-01-15T10:30:00"
}
```

**Response** (sent to `server_control` queue):
```json
{
    "type": "sync_active_sessions_response",
    "active_sessions": ["session1", "session2", "session3"],
    "timestamp": "2024-01-15T10:30:01"
}
```

#### sync_session_agent

Get the agent status for a specific session.

**Request:**
```json
{
    "type": "sync_session_agent",
    "session_id": "session1",
    "timestamp": "2024-01-15T10:30:00"
}
```

**Response** (sent to `server_control` queue):
```json
{
    "type": "sync_session_agent_response",
    "session_id": "session1",
    "agent_type": "DefaultAgent",
    "agent_status": "running",
    "agent_created": true,
    "timestamp": "2024-01-15T10:30:01"
}
```

**Response when no agent exists:**
```json
{
    "type": "sync_session_agent_response",
    "session_id": "session1",
    "agent_type": null,
    "agent_status": "not_created",
    "agent_created": false,
    "timestamp": "2024-01-15T10:30:01"
}
```

#### sync_session_template_version

Get the template version for a specific session.

**Request:**
```json
{
    "type": "sync_session_template_version",
    "session_id": "session1",
    "timestamp": "2024-01-15T10:30:00"
}
```

**Response** (sent to `server_control` queue):
```json
{
    "type": "sync_session_template_version_response",
    "session_id": "session1",
    "template_version": "v2.1",
    "timestamp": "2024-01-15T10:30:01"
}
```

**Response when no template version is set:**
```json
{
    "type": "sync_session_template_version_response",
    "session_id": "session1",
    "template_version": "",
    "timestamp": "2024-01-15T10:30:01"
}
```

#### agent_control

Control agent execution (pause, resume, stop, step).

**Request:**
```json
{
    "type": "agent_control",
    "session_id": "session1",
    "control": "pause",
    "timestamp": "2024-01-15T10:30:00"
}
```

**Valid control values:**
- `"pause"`: Pause agent execution
- `"resume"` or `"continue"`: Resume paused agent
- `"stop"`: Stop agent execution
- `"step"`: Execute one step (when paused)

**Response** (sent to `server_control` queue):
```json
{
    "type": "agent_control_response",
    "session_id": "session1",
    "control": "pause",
    "success": true,
    "message": "Agent paused successfully",
    "timestamp": "2024-01-15T10:30:01"
}
```

**Error response:**
```json
{
    "type": "agent_control_response",
    "session_id": "session1",
    "control": "pause",
    "success": false,
    "message": "Agent not found for session",
    "timestamp": "2024-01-15T10:30:01"
}
```

### Status Update Messages

The service sends status updates to the `server_control` queue when agent status changes.

#### agent_status_changed

Sent automatically when an agent's status changes (e.g., from running to paused).

```json
{
    "type": "agent_status_changed",
    "session_id": "session1",
    "old_status": "running",
    "new_status": "paused",
    "timestamp": "2024-01-15T10:30:00"
}
```

### User Messages

User messages flow through the `user_input` queue to agents, and agent responses flow back through the `agent_response` queue.

#### User Input Message

```json
{
    "session_id": "session1",
    "message": "Search for flights to Paris",
    "timestamp": "2024-01-15T10:30:00"
}
```

#### Agent Response Message

```json
{
    "session_id": "session1",
    "response": "I found 5 flights to Paris. Here are the options...",
    "status": "completed",
    "timestamp": "2024-01-15T10:30:15"
}
```

### Message Flow Example

Here's a typical message flow:

1. **Debugger UI** sends `sync_active_sessions` to `client_control` queue
2. **Service** receives message, processes it, sends response to `server_control` queue
3. **Debugger UI** receives response with list of sessions
4. **User** types message in debugger UI
5. **Debugger UI** sends message to `user_input` queue
6. **Service** creates agent (if needed) and processes message
7. **Agent** performs actions and generates response
8. **Service** sends response to `agent_response` queue
9. **Debugger UI** receives and displays response

## Testing

The service is designed for testability:

- **Unit Tests**: Test each component in isolation with mocked dependencies
- **Integration Tests**: Test component interactions
- **Property-Based Tests**: Verify correctness properties using hypothesis
- **End-to-End Tests**: Test full workflows

## Migration from Original Service

The modularized service maintains backward compatibility with the original `web_agent_service.py`:

1. Same queue protocol and message formats
2. Same external behavior
3. Works with existing agent debugger
4. All features preserved

See `COMPARISON.md` for detailed differences and improvements.

## Development

### Adding New Agent Types

1. Implement agent creation logic in `AgentFactory._create_<type>_agent()`
2. Add type to `get_available_types()`
3. Update documentation

### Adding New Message Handlers

1. Add handler method to `MessageHandlers`
2. Register in `dispatch()` method
3. Update message protocol documentation

### Adding New Monitoring Features

1. Add monitoring logic to `SessionMonitor`
2. Call from `run_monitoring_cycle()`
3. Update monitoring documentation

## Advanced Usage

### Custom Agent Types

To add a new agent type:

1. **Implement the agent creation method in `AgentFactory`:**

```python
def _create_custom_agent(
    self,
    interactive: QueueInteractive,
    logger: Callable
) -> PromptBasedActionPlanningAgent:
    """Create custom agent with specific capabilities."""
    # Create reasoner
    reasoner = create_custom_reasoner()
    
    # Create agent
    agent = CustomAgent(
        interactive=interactive,
        reasoner=reasoner,
        logger=logger
    )
    
    return agent
```

2. **Register the agent type:**

```python
def get_available_types(self) -> List[str]:
    """Get list of available agent types."""
    return ['DefaultAgent', 'MockClarificationAgent', 'CustomAgent']
```

3. **Update the creation logic:**

```python
def create_agent(self, ...):
    if agent_type == 'CustomAgent':
        return self._create_custom_agent(interactive, logger)
    # ... existing logic
```

### Template Version Management

The service supports per-session template versions:

```python
# In your code or via control messages
session_info = session_manager.get_or_create(
    session_id='session1',
    template_version='v2.1'
)

# The agent will be created with the specified template version
agent = agent_factory.create_agent(
    interactive=session_info.interactive,
    logger=session_info.logger,
    template_version='v2.1'
)
```

### Monitoring and Debugging

#### Enable Detailed Logging

```bash
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true
python launch_service.py /path/to/testcase
```

Logs are written to:
- Console (stdout)
- JSON files in `_runtime/service_logs/global/`
- Session-specific logs in `_runtime/service_logs/<session_id>/`

#### Synchronous Mode for Debugging

Run agents synchronously to enable debugger attachment:

```bash
python launch_service.py --synchronous /path/to/testcase
```

In synchronous mode:
- Agents run in the main process (not in threads)
- You can attach a Python debugger
- Easier to trace execution flow
- Not suitable for production

#### Monitor Queue Activity

Check queue directories to see message flow:

```bash
# List queue directories
ls -la _runtime/queues/<timestamp>/

# View messages in a queue
cat _runtime/queues/<timestamp>/client_control/*.json
```

## Troubleshooting

### Service Won't Start

**Problem:** Service fails to start with "Queue service not initialized" error.

**Solution:** Ensure the testcase root directory exists and is writable:
```bash
mkdir -p /path/to/testcase
chmod 755 /path/to/testcase
```

### Agent Not Responding

**Problem:** Messages sent but no response from agent.

**Solution:** 
1. Check if agent was created: Look for "Agent created" in logs
2. Verify queue paths match between service and debugger
3. Check for errors in session-specific logs
4. Ensure `new_agent_on_first_submission` is enabled

### Session Cleanup Issues

**Problem:** Sessions not being cleaned up after idle timeout.

**Solution:**
1. Check `session_idle_timeout` configuration
2. Verify `cleanup_check_interval` is reasonable
3. Look for cleanup errors in service logs
4. Ensure no active agent threads are blocking cleanup

### Template Version Not Applied

**Problem:** Agent uses wrong template version.

**Solution:**
1. Verify template version is set before agent creation
2. Check template directory exists and contains the version
3. Look for template switching errors in logs
4. Ensure template version string matches directory name

### High Memory Usage

**Problem:** Service memory usage grows over time.

**Solution:**
1. Reduce `session_idle_timeout` to cleanup sessions faster
2. Check for agent threads that aren't terminating
3. Review session cleanup logs for errors
4. Consider restarting service periodically

### Queue Message Backlog

**Problem:** Messages accumulating in queues.

**Solution:**
1. Check if agents are processing messages
2. Verify agent threads are running (not crashed)
3. Look for errors in agent execution logs
4. Consider increasing agent processing capacity

## Performance Tuning

### Optimize Session Cleanup

```python
config = ServiceConfig(
    session_idle_timeout=600,      # 10 minutes (shorter)
    cleanup_check_interval=60      # 1 minute (more frequent)
)
```

### Reduce Logging Overhead

```python
config = ServiceConfig(
    debug_mode_service=False  # Disable debug logging in production
)
```

### Adjust Queue Polling

The service polls queues every 0.1 seconds. To reduce CPU usage:

```python
# In service.py main loop
time.sleep(0.5)  # Increase from 0.1 to 0.5 seconds
```

## Architecture Benefits

### Modularity

Each component has a single responsibility:
- **ServiceConfig**: Configuration management
- **SessionManager**: Session lifecycle
- **AgentFactory**: Agent creation
- **QueueManager**: Queue service management
- **MessageHandlers**: Message processing
- **AgentRunner**: Thread management
- **SessionMonitor**: Health monitoring

### Testability

Components can be tested in isolation:

```python
# Test SessionManager without running full service
session_manager = SessionManager(config, mock_queue_service, log_dir)
session = session_manager.get_or_create('test_session')
assert session.session_id == 'test_session'
```

### Maintainability

Clear interfaces make changes easier:
- Add new message types: Update `MessageHandlers.dispatch()`
- Add new agent types: Update `AgentFactory`
- Change monitoring logic: Update `SessionMonitor`

### Extensibility

Easy to extend without modifying core code:
- Custom agent types via `AgentFactory`
- Custom message handlers via `MessageHandlers`
- Custom monitoring via `SessionMonitor`

## Migration Guide

### From Original Service

The modularized service is backward compatible:

1. **Same queue protocol**: No changes to message formats
2. **Same behavior**: All features preserved
3. **Same integration**: Works with existing debugger

To migrate:

1. Replace `web_agent_service.py` with `launch_service.py`
2. Update any hardcoded paths to use configuration
3. Test with existing debugger UI
4. Gradually adopt new features (template versioning, etc.)

### Configuration Migration

Old hardcoded values → New configuration:

```python
# Old: Hardcoded in service
SESSION_IDLE_TIMEOUT = 30 * 60

# New: Configuration
config = ServiceConfig(session_idle_timeout=1800)
```

## License

Same as parent project.
