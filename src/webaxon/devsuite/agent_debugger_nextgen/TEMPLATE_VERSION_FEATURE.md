# Template Version Feature

## Overview

Added per-session template version support to the Agent Debugger, allowing users to select different template versions for each debugging session through the Settings UI.

## What Was Implemented

### 1. UI Components (app.py)

Added to Settings tab:
- **Template Version Dropdown**: Allows selection of template versions
  - Default (No Version)
  - End Customers
  - Internal Users
  - Beta Testing
  - Production
- **Current Template Version Display**: Shows the active template version for the session
- **Apply Changes Button**: Syncs both agent type and template version

### 2. Session Tracking (app.py)

- Added `session_template_versions` dictionary to track template version per session
- Updated apply settings callback to handle template version
- Updated poll callback to display current template version

### 3. Backend Communication (queue_client.py)

Added `sync_session_template_version()` method:
- Sends template version updates to agent service via server control queue
- Message format:
  ```python
  {
      "type": "sync_session_template_version",
      "message": {
          "session_id": "session_123",
          "template_version": "end_customers"  # or "" for default
      },
      "timestamp": "2024-01-01T12:00:00"
  }
  ```

### 4. Helper Functions (helpers.py)

Added `sync_session_template_version()` helper function:
- Provides convenient interface for syncing template version
- Integrates with queue client
- Supports optional debugger logging

### 5. Module Exports (__init__.py)

- Exported `sync_session_template_version` for external use
- Added to `__all__` list

## How It Works

### User Workflow:

1. User opens Settings tab
2. Selects desired template version from dropdown
3. Clicks "Apply Changes"
4. Template version is:
   - Stored in `session_template_versions` dict
   - Synced to agent service via queue message
   - Displayed in "Current Template Version" field

### Message Flow:

```
UI (Settings Tab)
    ↓ (user clicks Apply)
app.py: apply_settings callback
    ↓
helpers.sync_session_template_version()
    ↓
queue_client.sync_session_template_version()
    ↓
Queue Message → server_control queue
    ↓
Agent Service (receives and applies template version)
```

## Template Version Options

The dropdown provides these options:

| Label | Value | Description |
|-------|-------|-------------|
| Default (No Version) | `""` | Uses unversioned templates |
| End Customers | `end_customers` | Customer-facing templates |
| Internal Users | `internal_users` | Internal team templates |
| Beta Testing | `beta` | Beta/experimental templates |
| Production | `production` | Production-ready templates |

## Agent Service Integration

The agent service needs to handle the `sync_session_template_version` message:

```python
# In agent service message handler:
if message_type == "sync_session_template_version":
    session_id = message["message"]["session_id"]
    template_version = message["message"]["template_version"]
    
    # Update the agent's template manager for this session
    agent = get_agent_for_session(session_id)
    if agent and hasattr(agent, 'template_manager'):
        agent.template_manager.switch(template_version=template_version)
```

## Template Manager Integration

When the agent receives a template version update, it should call:

```python
# Switch template version dynamically
template_manager.switch(template_version="end_customers")

# Now all template lookups will use the versioned templates
# e.g., "BrowseLink.end_customers" instead of "BrowseLink"
```

## Session Isolation

- Each session maintains its own template version
- Switching sessions automatically displays the correct template version
- Template versions persist for the session lifetime
- Different sessions can use different template versions simultaneously

## UI Display

The Settings tab now shows:

```
⚙️ Session Settings

Agent Configuration:
[Dropdown: Default Agent ▼]

Template Version:
[Dropdown: End Customers ▼]

[Apply Changes Button]

Current Agent: DefaultAgent
Current Template Version: end_customers
Agent Status: active: DefaultAgent

ℹ️ Settings are session-specific
```

## Benefits

1. **A/B Testing**: Test different template versions side-by-side in different sessions
2. **Customer Segmentation**: Use different templates for different user types
3. **Development**: Test new templates without affecting production
4. **Debugging**: Easily switch between template versions to debug issues
5. **Flexibility**: Change template version without restarting the agent

## Files Modified

- `app.py`: Added UI components and callbacks
- `helpers.py`: Added sync_session_template_version helper
- `queue_client.py`: Added sync_session_template_version method
- `__init__.py`: Exported new function

## Next Steps

To fully utilize this feature, the agent service needs to:

1. Handle `sync_session_template_version` messages from the server control queue
2. Update the TemplateManager for the appropriate session
3. Ensure template lookups use the session-specific version

## Example Usage

```python
# In agent service:
def handle_control_message(message):
    if message["type"] == "sync_session_template_version":
        session_id = message["message"]["session_id"]
        template_version = message["message"]["template_version"]
        
        # Get or create agent for session
        agent = session_agents.get(session_id)
        if agent:
            # Update template version
            agent.template_manager.switch(
                template_version=template_version if template_version else None
            )
            
            print(f"Session {session_id} template version updated to: {template_version or 'default'}")
```

## Testing

To test the feature:

1. Launch the debugger
2. Create a new session
3. Go to Settings tab
4. Select a template version
5. Click "Apply Changes"
6. Verify the "Current Template Version" updates
7. Check agent service logs for the sync message
8. Verify agent uses the correct template version

## Compatibility

- Backward compatible: Empty string (`""`) means no version (default behavior)
- Works with existing TemplateManager versioning system
- No changes required to existing templates
- Agent service can ignore messages if template versioning not implemented yet
