# Control Message Specification

All control messages exchanged between the Agent Debugger and Agent Service use a standardized three-field format:

```json
{
    "type": "<message_type>",
    "message": { /* type-specific payload */ },
    "timestamp": "<timestamp_string>"
}
```

## Message Structure

- **type** (string): Message type discriminator for routing/filtering
- **message** (object): Type-specific payload containing the actual data
- **timestamp** (string): ISO timestamp or custom timestamp format for tracking

---

## Messages: Debugger → Service

These messages are sent on the **SERVER_CONTROL_QUEUE_ID** queue.

### 1. Sync Active Sessions

Sent periodically to inform the service which sessions are currently active.

```json
{
    "type": "sync_active_sessions",
    "message": {
        "active_sessions": ["session_1_20251112101617", "session_2_20251112102030"]
    },
    "timestamp": "176297138219"
}
```

**Purpose**: Allows service to:
- Create agents for new sessions
- Close agents for sessions that are no longer active

### 2. Sync Session Inferencer

Sent when user changes the inferencer for a specific session via Settings tab.

```json
{
    "type": "sync_session_inferencer",
    "message": {
        "session_id": "session_1_20251112101617",
        "inferencer_name": "MockClarificationInferencer"
    },
    "timestamp": "176297138220"
}
```

**Purpose**: Updates the inferencer used by the agent for a specific session.

**Supported inferencer names**:
- `"ClaudeApiInferencer"` (default)
- `"MockClarificationInferencer"`

---

## Messages: Service → Debugger

These messages are sent on the **CLIENT_CONTROL_QUEUE_ID** queue.

### 1. Log Path Available

Sent when a new agent session is created and log path is available.

```json
{
    "type": "log_path_available",
    "message": {
        "log_path": "/path/to/logs/session_1_20251112101617"
    },
    "timestamp": "176297138221"
}
```

**Purpose**: Informs debugger where to find the agent's execution logs.

**Consumed by**: `check_for_log_paths()` function in agent_debugger.py

### 2. Agent Status

Sent when agent status changes (creation, inferencer update, errors).

```json
{
    "type": "agent_status",
    "message": {
        "session_id": "session_1_20251112101617",
        "status": "created",  // or "inferencer_updated" or "error"
        "inferencer": "ClaudeApiInferencer",
        "error": "Optional error message"  // only present when status is "error"
    },
    "timestamp": "176297138222"
}
```

**Status values**:
- `"created"`: Agent was successfully created for the session
- `"inferencer_updated"`: Inferencer was successfully changed
- `"error"`: An error occurred during agent operations

**Purpose**: Provides real-time feedback to user about agent lifecycle events.

**Consumed by**: `poll_agent_status()` callback in Settings tab (agent_debugger.py lines 764-836)

---

## Implementation Notes

### Service Implementation

The agent service should:

1. **Send log_path_available** immediately after creating an agent:
```python
control_message = {
    "type": "log_path_available",
    "message": {"log_path": agent.log_dir},
    "timestamp": timestamp()
}
queue_service.put(CLIENT_CONTROL_QUEUE_ID, control_message)
```

2. **Send agent_status** for lifecycle events:
```python
# On agent creation
control_message = {
    "type": "agent_status",
    "message": {
        "session_id": session_id,
        "status": "created",
        "inferencer": inferencer_name
    },
    "timestamp": timestamp()
}
queue_service.put(CLIENT_CONTROL_QUEUE_ID, control_message)

# On inferencer update
control_message = {
    "type": "agent_status",
    "message": {
        "session_id": session_id,
        "status": "inferencer_updated",
        "inferencer": new_inferencer_name
    },
    "timestamp": timestamp()
}
queue_service.put(CLIENT_CONTROL_QUEUE_ID, control_message)

# On error
control_message = {
    "type": "agent_status",
    "message": {
        "session_id": session_id,
        "status": "error",
        "inferencer": current_inferencer_name,
        "error": str(exception)
    },
    "timestamp": timestamp()
}
queue_service.put(CLIENT_CONTROL_QUEUE_ID, control_message)
```

### Debugger Implementation

The debugger:

1. **Filters messages by type**: Each callback only processes messages matching its expected type
2. **Handles concurrent access**: Multiple callbacks may read from CLIENT_CONTROL_QUEUE_ID simultaneously
3. **Stores structured messages**: Preserves the full message envelope for timestamp tracking

### Benefits of Standardization

✅ **Predictable parsing**: All messages have the same top-level structure
✅ **Easy routing**: Filter by `type` field without inspecting payload
✅ **Clean separation**: Metadata (type, timestamp) separate from payload (message)
✅ **Extensibility**: Easy to add new message types or metadata fields
✅ **Debugging**: Consistent timestamp format across all messages
