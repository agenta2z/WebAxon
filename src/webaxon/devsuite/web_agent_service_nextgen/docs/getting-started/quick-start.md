# Web Agent Service - Quick Start Guide

This guide provides quick commands and examples to get you started with the Web Agent Service.

## Installation

No installation required! The service runs directly from the source directory.

## Starting the Service

### Basic Start

```bash
cd WebAgent/src/webaxon/devsuite/web_agent_service_nextgen
python launch_service.py /path/to/testcase
```

### With Debug Mode

```bash
python launch_service.py --debug /path/to/testcase
```

### With Synchronous Agents (for debugging)

```bash
python launch_service.py --synchronous /path/to/testcase
```

## Common Configuration

### Set Session Timeout (1 hour)

```bash
# Linux/Mac
export WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=3600
python launch_service.py /path/to/testcase

# Windows PowerShell
$env:WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=3600
python launch_service.py /path/to/testcase
```

### Disable Debug Logging

```bash
# Linux/Mac
export WEBAGENT_SERVICE_DEBUG_MODE_SERVICE=false
python launch_service.py /path/to/testcase

# Windows PowerShell
$env:WEBAGENT_SERVICE_DEBUG_MODE_SERVICE="false"
python launch_service.py /path/to/testcase
```

## Using with Agent Debugger

### Step 1: Start the Service

```bash
cd WebAgent/src/webaxon/devsuite/web_agent_service_nextgen
python launch_service.py /path/to/testcase
```

### Step 2: Start the Debugger (in a new terminal)

```bash
cd WebAgent/src/webaxon/devsuite/agent_debugger_nextgen
python launch_debugger.py /path/to/testcase
```

### Step 3: Open Browser

Navigate to: `http://localhost:8050`

## Stopping the Service

Press `Ctrl+C` in the terminal where the service is running. The service will:
1. Stop all running agents
2. Clean up all sessions
3. Close queue connections
4. Exit gracefully

## Checking Logs

### Service Logs

```bash
# View global service logs
cat _runtime/service_logs/global/service_logs.json

# View session-specific logs
cat _runtime/service_logs/<session_id>/session_logs.json
```

### Queue Messages

```bash
# List queue directories
ls -la _runtime/queues/

# View control messages
cat _runtime/queues/<timestamp>/client_control/*.json

# View responses
cat _runtime/queues/<timestamp>/server_control/*.json
```

## Common Issues

### "Testcase root does not exist"

**Solution:** Create the directory first:
```bash
mkdir -p /path/to/testcase
```

### "Module not found" errors

**Solution:** Ensure you're running from the correct directory:
```bash
cd WebAgent/src/webaxon/devsuite/web_agent_service_nextgen
python launch_service.py /path/to/testcase
```

### Service not responding to debugger

**Solution:** 
1. Check both service and debugger are using the same testcase root
2. Verify queue directories exist in `_runtime/queues/`
3. Check service logs for errors

## Quick Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT` | 1800 | Session timeout (seconds) |
| `WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL` | 300 | Cleanup interval (seconds) |
| `WEBAGENT_SERVICE_DEBUG_MODE_SERVICE` | true | Enable debug logging |
| `WEBAGENT_SERVICE_SYNCHRONOUS_AGENT` | false | Run agents synchronously |
| `WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION` | true | Create agents lazily |
| `WEBAGENT_SERVICE_DEFAULT_AGENT_TYPE` | DefaultAgent | Default agent type |

### Command Line Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message |
| `--debug` | Enable debug mode |
| `--synchronous` | Run agents synchronously |
| `--config-file PATH` | Load config from file |

### Queue IDs

| Queue | Default ID | Purpose |
|-------|-----------|----------|
| Input | `user_input` | User messages to agents |
| Response | `agent_response` | Agent responses |
| Client Control | `client_control` | Debugger → Service |
| Server Control | `server_control` | Service → Debugger |

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [ARCHITECTURE.md](ARCHITECTURE.md) for design details
- Review example scripts in the repository
- Explore the modular components in `core/`, `communication/`, `agents/`, and `monitoring/`

## Getting Help

If you encounter issues:

1. Check the logs in `_runtime/service_logs/`
2. Review the troubleshooting section in README.md
3. Verify your configuration with `--help`
4. Run with `--debug` for detailed logging
