# Template Versioning Guide

## Overview

The `TemplateManagerWrapper` provides per-session template versioning capabilities for the web agent service. This allows different agent sessions to use different versions of prompt templates simultaneously.

## Architecture

```
WebAgentService
    ↓
AgentFactory (uses TemplateManagerWrapper)
    ↓
TemplateManagerWrapper (wraps TemplateManager)
    ↓
TemplateManager (from science_python_utils)
```

## Key Components

### TemplateManagerWrapper

Located in `agents/template_manager.py`, this wrapper provides:

- **Version Tracking**: Maintains current template version state
- **Version Switching**: Switches underlying TemplateManager to specific versions
- **Delegation**: Provides convenient access to TemplateManager operations
- **Debugging Support**: Enables logging of which version each session uses

### Integration Points

#### 1. AgentFactory

The `AgentFactory` uses `TemplateManagerWrapper` to create agents with specific template versions:

```python
class AgentFactory:
    def __init__(self, template_manager: TemplateManagerWrapper, config: ServiceConfig):
        self._template_manager = template_manager
        # ...
    
    def create_agent(self, ..., template_version: str = ""):
        # Switch version before creating agent
        if template_version:
            self._template_manager.switch_version(template_version)
        
        # Create agent with switched templates
        agent = self._create_default_agent(...)
        return agent
```

#### 2. SessionManager

Sessions track their template version:

```python
@dataclass
class AgentSessionInfo:
    template_version: str = ""  # Empty string = default version
    # ... other fields
```

#### 3. MessageHandlers

The debugger can query template versions:

```python
def handle_sync_session_template_version(self, message):
    session_id = message['session_id']
    session = self._session_manager.get(session_id)
    
    response = {
        'type': 'sync_session_template_version_response',
        'session_id': session_id,
        'template_version': session.template_version,
        'timestamp': datetime.now().isoformat()
    }
    
    self._queue_service.put(self._config.server_control_queue_id, response)
```

## Usage Examples

### Basic Usage

```python
from agents.template_manager import TemplateManagerWrapper
from rich_python_utils.string_utils.formatting.handlebars_format import (
    format_template as handlebars_template_format
)

# Create wrapper
wrapper = TemplateManagerWrapper(
    template_dir=Path('templates'),
    template_formatter=handlebars_template_format
)

# Switch to specific version
wrapper.switch_version('v2.1')

# Check current version
print(wrapper.get_current_version())  # 'v2.1'

# Get underlying manager
tm = wrapper.get_template_manager()
```

### Per-Session Versioning

```python
# Session 1 uses v2.0
session1 = AgentSessionInfo(
    session_id='session1',
    template_version='v2.0'
)

# Session 2 uses v2.1
session2 = AgentSessionInfo(
    session_id='session2',
    template_version='v2.1'
)

# Session 3 uses default
session3 = AgentSessionInfo(
    session_id='session3',
    template_version=''
)

# When creating agents, factory switches to session's version
agent1 = factory.create_agent(..., template_version=session1.template_version)
agent2 = factory.create_agent(..., template_version=session2.template_version)
agent3 = factory.create_agent(..., template_version=session3.template_version)
```

### Template Operations

```python
# Version switching
wrapper.switch_version('v2.0')

# Template space switching (delegation)
wrapper.switch(active_template_root_space='response_agent')

# Template type switching (delegation)
wrapper.switch(active_template_type='reflection')

# Direct access for complex operations
tm = wrapper.get_template_manager()
tm.switch(active_template_root_space='planning_agent')
```

## Version Management

### Version Naming

Template versions should follow a consistent naming scheme:

- **Semantic versions**: `v1.0`, `v2.0`, `v2.1`
- **Named versions**: `experimental`, `stable`, `beta`
- **Default version**: Empty string `""`

### Version Storage

Template versions are stored in the file system:

```
templates/
├── default/
│   ├── planning_agent/
│   ├── action_agent/
│   └── response_agent/
├── v2.0/
│   ├── planning_agent/
│   ├── action_agent/
│   └── response_agent/
└── v2.1/
    ├── planning_agent/
    ├── action_agent/
    └── response_agent/
```

### Switching Behavior

When switching versions:

1. `switch_version()` is called with version identifier
2. Wrapper calls `TemplateManager.switch(template_version=...)`
3. TemplateManager loads templates from version directory
4. Wrapper updates `_current_version` for tracking
5. Returns TemplateManager for method chaining

## Design Properties

The implementation satisfies these correctness properties:

### Property 37: Template Version Storage
*For any* session created, the session information should include a template_version field

### Property 38: Template Version Usage
*For any* agent creation with a specified template version, that version should be used when creating the agent

### Property 40: Default Template Version
*For any* agent creation without a specified template version, the default template version should be used

### Property 41: Template Manager Update Order
*For any* template version switch, the template manager should be updated before the agent is created

## Benefits

### 1. Flexibility
Different sessions can use different template versions simultaneously without interference.

### 2. Testing
Easy to test new template versions with specific sessions while keeping others on stable versions.

### 3. Debugging
Version tracking enables logging which template version each agent uses, making debugging easier.

### 4. Gradual Rollout
New template versions can be rolled out gradually by assigning them to specific sessions.

### 5. Backward Compatibility
Existing code continues to work with default templates (empty version string).

## Best Practices

### 1. Version Tracking
Always log the template version when creating agents:

```python
logger.info(f"Creating agent with template version: {wrapper.get_current_version()}")
```

### 2. Version Validation
Validate template versions before switching:

```python
def validate_version(version: str) -> bool:
    if not version:
        return True  # Default version always valid
    
    version_dir = template_dir / version
    return version_dir.exists() and version_dir.is_dir()
```

### 3. Error Handling
Handle version switching errors gracefully:

```python
try:
    wrapper.switch_version(template_version)
except Exception as e:
    logger.error(f"Failed to switch to version {template_version}: {e}")
    # Fall back to default version
    wrapper.switch_version('')
```

### 4. Session Consistency
Ensure template version stays consistent throughout session lifecycle:

```python
# Store version in session
session.template_version = 'v2.0'

# Always use session's version when creating agents
agent = factory.create_agent(..., template_version=session.template_version)
```

## Testing

### Unit Tests
See `test_template_manager.py` for comprehensive unit tests covering:
- Initialization
- Version switching
- Version tracking
- Manager access
- Delegation

### Integration Tests
See `test_template_manager_integration.py` for integration tests covering:
- ServiceConfig integration
- API compliance
- Version switching order
- Empty version handling

### Verification
Run `verify_task8.py` to verify all requirements and design properties are satisfied.

## Troubleshooting

### Issue: Version not switching
**Symptom**: Agent uses wrong template version

**Solution**: Ensure `switch_version()` is called before agent creation:
```python
# Correct order
wrapper.switch_version('v2.0')
agent = create_agent(...)

# Wrong order
agent = create_agent(...)
wrapper.switch_version('v2.0')  # Too late!
```

### Issue: Version tracking incorrect
**Symptom**: `get_current_version()` returns wrong version

**Solution**: Always use `switch_version()` instead of directly calling `TemplateManager.switch()`:
```python
# Correct
wrapper.switch_version('v2.0')

# Wrong - bypasses tracking
wrapper.get_template_manager().switch(template_version='v2.0')
```

### Issue: Template not found
**Symptom**: Error when switching to version

**Solution**: Verify version directory exists:
```python
version_dir = template_dir / version
if not version_dir.exists():
    logger.error(f"Template version directory not found: {version_dir}")
```

## Future Enhancements

Potential future improvements:

1. **Version Validation**: Add method to validate version exists before switching
2. **Version Listing**: Add method to list available template versions
3. **Version Metadata**: Store metadata about each version (description, date, author)
4. **Version Comparison**: Add method to compare template versions
5. **Hot Reloading**: Support reloading templates without restarting service

## Conclusion

The `TemplateManagerWrapper` provides a clean, tested interface for per-session template versioning. It integrates seamlessly with the existing `TemplateManager` while adding the version tracking capabilities needed for the modularized web agent service.
