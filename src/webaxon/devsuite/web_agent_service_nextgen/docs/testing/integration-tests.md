# Integration Tests for Web Agent Service

## Overview

This document describes the integration tests for the modularized web agent service. These tests validate that all components work together correctly and maintain backward compatibility with the debugger.

## Test File

**Location**: `test_integration.py`

## Test Structure

### Test Classes

1. **TestServiceDebuggerCommunication** - Service-debugger communication via queue messages
2. **TestSessionLifecycle** - Session lifecycle end-to-end
3. **TestAgentLifecycle** - Agent lifecycle with control operations
4. **TestTemplateVersionSwitching** - Template version switching across components
5. **TestConcurrentSessions** - Concurrent session operations
6. **TestSessionMonitorIntegration** - Session monitor integration

## Running Tests

### Run All Integration Tests
```bash
cd WebAgent
python -m pytest src/tools/devsuite/web_agent_service_nextgen/test_integration.py -v
```

### Run Specific Test Class
```bash
python -m pytest src/tools/devsuite/web_agent_service_nextgen/test_integration.py::TestServiceDebuggerCommunication -v
```

### Run Specific Test
```bash
python -m pytest src/tools/devsuite/web_agent_service_nextgen/test_integration.py::TestServiceDebuggerCommunication::test_sync_active_sessions_message -v
```

### Run Verification Script
```bash
cd WebAgent/src/webaxon/devsuite/web_agent_service_nextgen
python verify_task15.py
```

## Test Coverage Details

### 1. Service-Debugger Communication (5 tests)

Tests the queue-based communication protocol between the service and debugger.

#### test_sync_active_sessions_message
- Creates multiple sessions
- Sends sync_active_sessions message
- Validates response contains all active session IDs
- Validates response format

#### test_sync_session_agent_message
- Sends sync_session_agent message
- Validates session is created with correct agent type
- Validates response contains agent status
- Validates response format

#### test_sync_session_template_version_message
- Sends sync_session_template_version message
- Validates template version is stored in session
- Validates response contains template version
- Validates response format

#### test_agent_control_message_pause
- Creates session with mock interactive interface
- Sends agent_control message with pause command
- Validates control is applied to agent
- Validates response indicates success

#### test_multiple_messages_in_sequence
- Sends multiple different message types in sequence
- Validates all messages are processed correctly
- Validates all responses are sent
- Validates response order and format

**Requirements Validated**: 11.3 (Debugger compatibility), 11.4 (Feature parity)

### 2. Session Lifecycle (5 tests)

Tests session creation, update, and cleanup throughout the lifecycle.

#### test_session_creation_and_retrieval
- Creates multiple sessions
- Retrieves sessions by ID
- Validates session identity
- Validates get_all_sessions returns all sessions

#### test_session_update
- Creates session
- Updates session fields (agent_type, template_version)
- Validates updates are persisted
- Validates session state consistency

#### test_session_cleanup
- Creates session
- Calls cleanup_session
- Validates session is removed
- Validates resources are released

#### test_idle_session_cleanup
- Creates session
- Sets last_active to past time
- Calls cleanup_idle_sessions
- Validates idle session is removed

#### test_session_with_template_version
- Creates session with template version
- Updates template version
- Validates template version is stored and updated correctly

**Requirements Validated**: 3.1-3.5 (Session management), 11.5 (Feature support)

### 3. Agent Lifecycle (2 tests)

Tests agent control operations and status tracking.

#### test_agent_control_operations
- Creates session with mock interactive interface
- Tests pause, resume, stop, step commands
- Validates each control operation is applied correctly
- Validates state changes

#### test_agent_status_tracking
- Creates session
- Updates agent status
- Validates status is tracked correctly
- Validates agent_created flag

**Requirements Validated**: 6.5 (Agent control), 7.5 (Status updates)

### 4. Template Version Switching (3 tests)

Tests template version management across components.

#### test_template_version_in_session
- Creates session with template version
- Validates template version is stored in session
- Validates template version persistence

#### test_template_version_via_message
- Sends sync_session_template_version message
- Validates template version is set via message
- Validates response contains correct version

#### test_template_version_switching
- Creates multiple sessions with different template versions
- Validates each session has correct version
- Validates versions are independent per session

**Requirements Validated**: 10.1-10.5 (Template version support)

### 5. Concurrent Sessions (4 tests)

Tests thread-safe concurrent operations.

#### test_concurrent_session_creation
- Creates 10 sessions concurrently using threads
- Validates all sessions are created
- Validates no race conditions or data corruption

#### test_concurrent_session_updates
- Updates same session concurrently from multiple threads
- Validates session remains consistent
- Validates no data corruption

#### test_concurrent_message_processing
- Sends messages for multiple sessions concurrently
- Validates all messages are processed
- Validates all responses are sent

#### test_concurrent_session_cleanup
- Cleans up multiple sessions concurrently
- Validates all sessions are removed
- Validates no errors during concurrent cleanup

**Requirements Validated**: 3.1 (Thread-safe operations), 11.5 (Concurrent operations)

### 6. Session Monitor Integration (2 tests)

Tests session monitor integration with other components.

#### test_monitoring_cycle_execution
- Creates sessions
- Runs monitoring cycle
- Validates cycle completes without errors

#### test_periodic_cleanup_integration
- Creates idle session
- Runs cleanup through session manager
- Validates idle session is removed

**Requirements Validated**: 8.1-8.5 (Session monitoring)

## Test Infrastructure

### Setup Helper Function

The `setup_test_environment()` helper function:
- Creates temporary test directory
- Initializes all service components
- Configures test-friendly settings
- Returns dictionary of initialized components

Components initialized:
- QueueManager
- TemplateManagerWrapper
- AgentFactory
- SessionManager
- MessageHandlers
- SessionMonitor

### Test Configuration

Test-friendly configuration:
```python
config = ServiceConfig(
    debug_mode_service=False,  # Reduce log noise
    synchronous_agent=True,  # Easier to test
    new_agent_on_first_submission=True,
    session_idle_timeout=5,  # Short timeout for testing
    cleanup_check_interval=1  # Frequent cleanup for testing
)
```

### Cleanup Handling

All tests use proper cleanup:
```python
try:
    # Test code
finally:
    # Cleanup queue service before temp directory is removed
    env['queue_manager'].close()
```

This prevents file lock issues on Windows.

## Message Format Examples

### sync_active_sessions
```python
{
    'type': 'sync_active_sessions',
    'message': {
        'active_sessions': ['session1', 'session2']
    },
    'timestamp': '2024-01-15T10:30:00'
}
```

### sync_session_agent
```python
{
    'type': 'sync_session_agent',
    'message': {
        'session_id': 'test_session',
        'agent_type': 'DefaultAgent'
    },
    'timestamp': '2024-01-15T10:30:00'
}
```

### sync_session_template_version
```python
{
    'type': 'sync_session_template_version',
    'message': {
        'session_id': 'test_session',
        'template_version': 'v2.1'
    },
    'timestamp': '2024-01-15T10:30:00'
}
```

### agent_control
```python
{
    'type': 'agent_control',
    'message': {
        'session_id': 'test_session',
        'control': 'pause'  # or 'resume', 'stop', 'step'
    },
    'timestamp': '2024-01-15T10:30:00'
}
```

## Expected Results

All 21 tests should pass:
```
21 passed, 5 warnings in ~5s
```

The warnings are deprecation warnings from external libraries and can be ignored.

## Troubleshooting

### Import Errors

If you get import errors, make sure you're running from the WebAgent directory:
```bash
cd WebAgent
python -m pytest src/tools/devsuite/web_agent_service_nextgen/test_integration.py -v
```

### File Lock Errors

If you get file lock errors on Windows, the tests now include proper cleanup in finally blocks. If issues persist, ensure no other processes are accessing the test directories.

### Timeout Issues

If tests timeout, check that:
- No long-running processes are blocking
- Queue service is properly initialized
- Cleanup is called in finally blocks

## Benefits

1. **Comprehensive Coverage**: Tests cover all major integration points
2. **Real-World Scenarios**: Tests simulate actual usage patterns
3. **Backward Compatibility**: Validates compatibility with existing debugger
4. **Thread Safety**: Validates concurrent operations work correctly
5. **Regression Prevention**: Catches integration issues early
6. **Documentation**: Tests serve as usage examples

## Related Files

- `test_integration.py` - Integration test suite
- `verify_task15.py` - Verification script
- `TASK15_INTEGRATION_TESTS_SUMMARY.md` - Implementation summary
- `test_service.py` - Service unit tests
- `test_message_handlers.py` - Message handler unit tests
- `test_session.py` - Session manager unit tests

## Next Steps

After integration tests, the next step is end-to-end tests (Task 16) that test the full workflow with a running service instance.
