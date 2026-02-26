# Configuration Examples

This document provides practical configuration examples for different use cases.

## Table of Contents

- [Development Configuration](#development-configuration)
- [Production Configuration](#production-configuration)
- [Testing Configuration](#testing-configuration)
- [Debugging Configuration](#debugging-configuration)
- [Performance Tuning](#performance-tuning)

## Development Configuration

### Standard Development Setup

```bash
# Enable debug logging
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true

# Shorter timeout for faster iteration
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=600  # 10 minutes

# More frequent cleanup
export WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=60  # 1 minute

# Create agents immediately for testing
export WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION=false

# Start service
python launch_service.py /path/to/testcase
```

### Synchronous Debugging

For step-through debugging with breakpoints:

```bash
# Run agents in main process
export WEBAGENT_SERVICE_SYNCHRONOUS_AGENT=true
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true

# Start service
python launch_service.py --synchronous --debug /path/to/testcase
```

## Production Configuration

### Optimized for Production

```bash
# Disable debug logging for performance
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=false

# Longer timeout for production workloads
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=3600  # 1 hour

# Less frequent cleanup to reduce overhead
export WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=600  # 10 minutes

# Lazy agent creation to save resources
export WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION=true

# Start service
python launch_service.py /path/to/testcase
```

### High-Availability Setup

```bash
# Moderate timeout
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=1800  # 30 minutes

# Regular cleanup
export WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=300  # 5 minutes

# Minimal logging
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=false

# Custom queue paths for multiple instances
export WEBAGENT_SERVICE_QUEUE_ROOT_PATH=/var/queues/instance1

# Start service
python launch_service.py /path/to/testcase
```

## Testing Configuration

### Unit Testing

```python
from pathlib import Path
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig

# Create test configuration
config = ServiceConfig(
    session_idle_timeout=60,  # 1 minute for fast tests
    cleanup_check_interval=10,  # 10 seconds
    debug_mode_service=True,
    synchronous_agent=True,  # Easier to test
    new_agent_on_first_submission=False,
    default_agent_type='MockClarificationAgent'
)

# Use in tests
service = WebAgentService(Path('/tmp/test'), config)
```

### Integration Testing

```bash
# Fast timeouts for quick test cycles
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=120  # 2 minutes
export WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=30  # 30 seconds

# Enable debug logging for test diagnostics
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true

# Use test-specific queue paths
export WEBAGENT_SERVICE_QUEUE_ROOT_PATH=/tmp/test_queues

# Start service
python launch_service.py /tmp/testcase
```

## Debugging Configuration

### Maximum Verbosity

```bash
# Enable all debug logging
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true

# Run synchronously for easier debugging
export WEBAGENT_SERVICE_SYNCHRONOUS_AGENT=true

# Short timeouts to see cleanup behavior
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=300  # 5 minutes
export WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=60  # 1 minute

# Start with debug flags
python launch_service.py --debug --synchronous /path/to/testcase
```

### Debugging Specific Sessions

```python
from pathlib import Path
from web_agent_service_nextgen import WebAgentService
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig

# Create configuration with specific settings
config = ServiceConfig(
    debug_mode_service=True,
    synchronous_agent=True,  # Run in main process
    session_idle_timeout=7200,  # 2 hours - don't cleanup while debugging
    cleanup_check_interval=3600  # 1 hour
)

# Start service
service = WebAgentService(Path('/path/to/testcase'), config)
service.run()
```

### Debugging Queue Communication

```bash
# Enable debug mode
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true

# Use custom queue path for inspection
export WEBAGENT_SERVICE_QUEUE_ROOT_PATH=/tmp/debug_queues

# Start service
python launch_service.py --debug /path/to/testcase

# In another terminal, monitor queues
watch -n 1 'ls -la /tmp/debug_queues/*/client_control/'
```

## Performance Tuning

### Low-Latency Configuration

```bash
# Disable debug logging
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=false

# Aggressive cleanup
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=300  # 5 minutes
export WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=60  # 1 minute

# Lazy agent creation
export WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION=true

# Start service
python launch_service.py /path/to/testcase
```

### High-Throughput Configuration

```bash
# Minimal logging
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=false

# Keep sessions alive longer
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=7200  # 2 hours

# Less frequent cleanup
export WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=1800  # 30 minutes

# Lazy agent creation
export WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION=true

# Start service
python launch_service.py /path/to/testcase
```

### Memory-Constrained Configuration

```bash
# Aggressive cleanup to free memory
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=600  # 10 minutes
export WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=120  # 2 minutes

# Minimal logging
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=false

# Lazy agent creation
export WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION=true

# Start service
python launch_service.py /path/to/testcase
```

## Custom Queue Configuration

### Separate Queue Paths

```bash
# Use custom queue IDs for isolation
export WEBAGENT_SERVICE_INPUT_QUEUE_ID=custom_input
export WEBAGENT_SERVICE_RESPONSE_QUEUE_ID=custom_response
export WEBAGENT_SERVICE_CLIENT_CONTROL_QUEUE_ID=custom_client_control
export WEBAGENT_SERVICE_SERVER_CONTROL_QUEUE_ID=custom_server_control

# Custom queue root
export WEBAGENT_SERVICE_QUEUE_ROOT_PATH=/var/queues/custom

# Start service
python launch_service.py /path/to/testcase
```

### Multiple Service Instances

```bash
# Instance 1
export WEBAGENT_SERVICE_QUEUE_ROOT_PATH=/var/queues/instance1
export WEBAGENT_SERVICE_LOG_ROOT_PATH=_runtime/instance1
python launch_service.py /path/to/testcase &

# Instance 2
export WEBAGENT_SERVICE_QUEUE_ROOT_PATH=/var/queues/instance2
export WEBAGENT_SERVICE_LOG_ROOT_PATH=_runtime/instance2
python launch_service.py /path/to/testcase &
```

## Template Version Configuration

### Using Specific Template Versions

```python
from pathlib import Path
from web_agent_service_nextgen import WebAgentService
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig

# Standard configuration
config = ServiceConfig.from_env()

# Create service
service = WebAgentService(Path('/path/to/testcase'), config)

# Template versions are set per-session via control messages
# or when creating sessions programmatically
```

### Testing Multiple Template Versions

```bash
# Start service with debug mode
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true
python launch_service.py /path/to/testcase

# Send control messages to test different versions
# (via debugger UI or programmatically)
```

## Environment-Specific Configurations

### Development Environment

```bash
# .env.development
WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true
WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=600
WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=60
WEBAGENT_SERVICE_SYNCHRONOUS_AGENT=false
WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION=true
```

### Staging Environment

```bash
# .env.staging
WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=true
WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=1800
WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=300
WEBAGENT_SERVICE_SYNCHRONOUS_AGENT=false
WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION=true
```

### Production Environment

```bash
# .env.production
WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=false
WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=3600
WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL=600
WEBAGENT_SERVICE_SYNCHRONOUS_AGENT=false
WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION=true
```

## Loading Environment Files

### Using dotenv

```python
from pathlib import Path
from dotenv import load_dotenv
from web_agent_service_nextgen import WebAgentService
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig

# Load environment file
load_dotenv('.env.production')

# Create configuration from environment
config = ServiceConfig.from_env()

# Start service
service = WebAgentService(Path('/path/to/testcase'), config)
service.run()
```

### Using Shell Scripts

```bash
#!/bin/bash
# start_service.sh

# Load environment
source .env.production

# Start service
python launch_service.py /path/to/testcase
```

## Validation

### Verify Configuration

```python
from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig

# Load configuration
config = ServiceConfig.from_env()

# Validate
try:
    config.validate()
    print("Configuration is valid")
    print(f"Session timeout: {config.session_idle_timeout}s")
    print(f"Cleanup interval: {config.cleanup_check_interval}s")
    print(f"Debug mode: {config.debug_mode_service}")
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Best Practices

1. **Use environment variables** for deployment-specific settings
2. **Keep debug mode off** in production for performance
3. **Adjust timeouts** based on your workload patterns
4. **Monitor memory usage** and adjust cleanup intervals accordingly
5. **Use synchronous mode** only for debugging, never in production
6. **Test configuration changes** in staging before production
7. **Document custom configurations** for your team
8. **Use separate queue paths** for multiple instances
9. **Enable debug logging** when troubleshooting issues
10. **Validate configuration** before starting the service
