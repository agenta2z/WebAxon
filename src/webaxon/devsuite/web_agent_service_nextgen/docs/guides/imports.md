# Import Guide for web_agent_service_nextgen

This guide shows you how to import and use components from the web_agent_service_nextgen package.

## Quick Start

For most users, the simplest approach is to import from the main module:

```python
from web_agent_service_nextgen import WebAgentService, ServiceConfig

# Create and run service
config = ServiceConfig()
service = WebAgentService(testcase_root, config)
service.run()
```

## Import Methods

### Method 1: Convenience Imports (Recommended)

Import everything you need from the main module:

```python
from web_agent_service_nextgen import (
    WebAgentService,
    ServiceConfig,
    AgentSessionInfo,
    SessionManager,
    AgentFactory,
    QueueManager,
    MessageHandlers,
    AgentRunner,
    TemplateManagerWrapper,
    SessionMonitor
)
```

**Benefits:**
- Clean, simple imports
- All components in one place
- Easy to discover what's available
- Recommended for most use cases

### Method 2: Direct Module Imports

Import from specific submodules:

```python
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig, AgentSessionManager
from webaxon.devsuite.web_agent_service_nextgen.communication import QueueManager
from webaxon.devsuite.web_agent_service_nextgen.agents import AgentRunner
from webaxon.devsuite.web_agent_service_nextgen.session import SessionMonitor
```

**Benefits:**
- Clear module organization
- Explicit about where components come from
- Good for large projects with many imports
- Useful when you need many components from one module

### Method 3: Module-Level Imports

Import entire modules:

```python
from web_agent_service_nextgen import core, communication, agents, session

# Use components with module prefix
config = core.ServiceConfig()
manager = communication.QueueManager(testcase_root, config)
runner = agents.AgentRunner(config)
monitor = session.AgentSessionMonitor(session_manager, queue_service, config)
```

**Benefits:**
- Namespace clarity
- Avoid name conflicts
- Good for exploratory work
- Clear component origins

## Common Usage Patterns

### Pattern 1: Basic Service Setup

```python
from pathlib import Path
from web_agent_service_nextgen import WebAgentService

# Simplest possible usage
testcase_root = Path('/path/to/testcase')
service = WebAgentService(testcase_root)
service.run()
```

### Pattern 2: Custom Configuration

```python
from pathlib import Path
from web_agent_service_nextgen import WebAgentService, ServiceConfig

# Create custom configuration
config = ServiceConfig(
    session_idle_timeout=3600,  # 1 hour
    cleanup_check_interval=600,  # 10 minutes
    debug_mode_service=True,
    synchronous_agent=False,
    new_agent_on_first_submission=True
)

# Create service with custom config
testcase_root = Path('/path/to/testcase')
service = WebAgentService(testcase_root, config)
service.run()
```

### Pattern 3: Environment-Based Configuration

```python
from pathlib import Path
from web_agent_service_nextgen import WebAgentService, ServiceConfig

# Load configuration from environment variables
config = ServiceConfig.from_env()

# Create service
testcase_root = Path('/path/to/testcase')
service = WebAgentService(testcase_root, config)
service.run()
```

### Pattern 4: Component-Level Usage

```python
from pathlib import Path
from web_agent_service_nextgen import (
    ServiceConfig,
    SessionManager,
    QueueManager,
    AgentFactory
)

# Use individual components
config = ServiceConfig()
testcase_root = Path('/path/to/testcase')

# Initialize queue manager
queue_manager = QueueManager(testcase_root, config)
queue_service = queue_manager.initialize()
queue_manager.create_queues()

# Initialize session manager
service_log_dir = testcase_root / '_runtime'
session_manager = SessionManager(config, queue_service, service_log_dir)

# Create session
session = session_manager.get_or_create('session_123')

# ... use components ...
```

## Module Organization

The package is organized into focused modules:

```
web_agent_service_nextgen/
├── core/              # Core components
│   ├── ServiceConfig
│   ├── AgentSessionInfo
│   ├── SessionManager
│   └── AgentFactory
├── communication/     # Communication components
│   ├── QueueManager
│   └── MessageHandlers
├── agents/           # Agent management
│   ├── AgentRunner
│   └── TemplateManagerWrapper
└── session/          # Session lifecycle components
    ├── SessionMonitor
    ├── SessionLogManager
    └── ManifestFile
```

## Available Components

### Core Module (`core`)

- **ServiceConfig**: Configuration management with environment support
- **AgentSessionInfo**: Session state tracking
- **SessionManager**: Thread-safe session lifecycle management
- **AgentFactory**: Agent creation and configuration

### Communication Module (`communication`)

- **QueueManager**: Queue service initialization and lifecycle
- **MessageHandlers**: Control message processing and dispatch

### Agents Module (`agents`)

- **AgentRunner**: Thread management for agent execution
- **TemplateManagerWrapper**: Template versioning wrapper

### Session Module (`session`)

- **SessionMonitor**: Session health monitoring and cleanup
- **SessionLogManager**: Structured session logging and artifacts

## Package Metadata

```python
import webaxon.devsuite.web_agent_service_nextgen

print(web_agent_service_nextgen.__version__)  # '1.0.0'
print(web_agent_service_nextgen.__author__)  # 'Web Agent Service Team'
print(web_agent_service_nextgen.__license__)  # 'MIT'
```

## Best Practices

1. **Use convenience imports for simple cases**
   ```python
   from web_agent_service_nextgen import WebAgentService, ServiceConfig
   ```

2. **Use direct module imports for complex projects**
   ```python
   from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig
   from webaxon.devsuite.web_agent_service_nextgen.communication import QueueManager
   ```

3. **Import only what you need**
   ```python
   # Good
   from web_agent_service_nextgen import WebAgentService
   
   # Avoid
   from web_agent_service_nextgen import *
   ```

4. **Use type hints for better IDE support**
   ```python
   from web_agent_service_nextgen import ServiceConfig
   
   def create_service(config: ServiceConfig) -> WebAgentService:
       return WebAgentService(testcase_root, config)
   ```

## Documentation

Each module has comprehensive documentation:

```python
import webaxon.devsuite.web_agent_service_nextgen
from web_agent_service_nextgen import core, communication, agents, session

# View module documentation
print(web_agent_service_nextgen.__doc__)
print(core.__doc__)
print(communication.__doc__)
print(agents.__doc__)
print(session.__doc__)
```

## Examples

See the following files for complete examples:

- `launch_service.py` - Entry point script
- `example_agent_runner_usage.py` - AgentRunner examples
- `example_session_monitor_usage.py` - SessionMonitor examples
- `example_template_manager_usage.py` - TemplateManagerWrapper examples
- `demo_imports.py` - Import demonstrations

## Testing

To verify all imports work correctly:

```bash
python test_module_exports.py
```

This will test:
- All exports are accessible
- `__all__` lists are complete
- Direct imports work
- Convenience imports work
- Module docstrings exist

## Summary

The web_agent_service_nextgen package provides:

✓ Clean, intuitive import paths
✓ Comprehensive documentation
✓ Multiple import methods for different use cases
✓ Well-organized module structure
✓ Type-safe components
✓ Professional API design

Choose the import method that best fits your use case and enjoy working with the service!
