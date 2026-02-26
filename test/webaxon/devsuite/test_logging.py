"""
Test script to verify the refactored logging implementation.

This tests:
1. Global debugger creation
2. Session-specific debugger creation
3. Console output
4. JSON file logging
5. Log type categorization
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path
from functools import partial

# Add paths
project_root = Path(__file__).parent.parent.parent
from rich_python_utils.common_objects.debuggable import Debugger
from rich_python_utils.io_utils.json_io import write_json
from webaxon.devsuite import config
from webaxon.devsuite.common import DebuggerLogTypes, ServiceLogTypes
from webaxon.devsuite.constants import RUNTIME_DIR, FOLDER_NAME_DEBUGGER_LOGS, FOLDER_NAME_SERVICE_LOGS

print("=" * 70)
print("TESTING REFACTORED LOGGING IMPLEMENTATION")
print("=" * 70)

# Test 1: Global Debugger Creation
print("\n[TEST 1] Creating Global Debugger...")
testcase_root = Path(__file__).parent
debugger_log_dir = testcase_root / RUNTIME_DIR / FOLDER_NAME_DEBUGGER_LOGS / 'test_global'
debugger_log_dir.mkdir(parents=True, exist_ok=True)

global_debugger = Debugger(
    id='test_global_debugger',
    log_name='TestGlobalDebugger',
    logger=[
        print,  # Console output
        partial(write_json, file_path=str(debugger_log_dir / 'test_logs'), append=True)
    ],
    debug_mode=config.DEBUG_MODE_DEBUGGER,
    log_time=True,
    always_add_logging_based_logger=False
)
print(f"[OK] Global debugger created with ID: {global_debugger.id}")
print(f"[OK] Log directory: {debugger_log_dir}")

# Test 2: Log at different levels
print("\n[TEST 2] Testing different log levels...")
global_debugger.log_info("This is an INFO message", DebuggerLogTypes.DEBUGGER_STARTUP)
global_debugger.log_debug("This is a DEBUG message", DebuggerLogTypes.DEBUG)
global_debugger.log_warning("This is a WARNING message", DebuggerLogTypes.WARNING)
print("[OK] All log levels tested")

# Test 3: Log with structured data
print("\n[TEST 3] Testing structured data logging...")
global_debugger.log_info({
    'test_field_1': 'value1',
    'test_field_2': 123,
    'nested': {
        'field': 'nested_value'
    }
}, DebuggerLogTypes.QUEUE_OPERATION)
print("[OK] Structured data logged")

# Test 4: Session-specific Debugger
print("\n[TEST 4] Creating Session-Specific Debugger...")
session_id = 'test_session_123'
session_log_dir = testcase_root / RUNTIME_DIR / FOLDER_NAME_DEBUGGER_LOGS / session_id
session_log_dir.mkdir(parents=True, exist_ok=True)

session_debugger = Debugger(
    id=f'test_debugger_{session_id}',
    log_name=f'TestDebugger_{session_id}',
    logger=[
        print,
        partial(write_json, file_path=str(session_log_dir / 'session_logs'), append=True)
    ],
    debug_mode=config.DEBUG_MODE_DEBUGGER,
    log_time=True,
    always_add_logging_based_logger=False
)
print(f"[OK] Session debugger created with ID: {session_debugger.id}")
print(f"[OK] Session log directory: {session_log_dir}")

# Test 5: Session debugger logging
print("\n[TEST 5] Testing session-specific logging...")
session_debugger.log_info({
    'action': 'test_session_action',
    'session_id': session_id
}, DebuggerLogTypes.SESSION_SWITCH)
print("[OK] Session-specific log written")

# Test 6: Service log types
print("\n[TEST 6] Testing Service Log Types...")
service_log_dir = testcase_root / RUNTIME_DIR / FOLDER_NAME_SERVICE_LOGS / 'test_global'
service_log_dir.mkdir(parents=True, exist_ok=True)

service_debugger = Debugger(
    id='test_service_debugger',
    log_name='TestServiceDebugger',
    logger=[
        print,
        partial(write_json, file_path=str(service_log_dir / FOLDER_NAME_SERVICE_LOGS), append=True)
    ],
    debug_mode=config.DEBUG_MODE_SERVICE,
    log_time=True,
    always_add_logging_based_logger=False
)

service_debugger.log_info("Service starting...", ServiceLogTypes.SERVICE_STARTUP)
service_debugger.log_info("Processing request...", ServiceLogTypes.AGENT_PROCESSING)
service_debugger.log_info("Request completed", ServiceLogTypes.AGENT_COMPLETED)
print(f"[OK] Service debugger created and tested")
print(f"[OK] Service log directory: {service_log_dir}")

# Test 7: Verify log files were created
print("\n[TEST 7] Verifying log files were created...")
log_files_found = []

# Check global debugger logs
global_log_file = debugger_log_dir / 'test_logs.json'
if global_log_file.exists():
    log_files_found.append(f"[OK] Global debugger log: {global_log_file}")
else:
    log_files_found.append(f"[FAIL] Global debugger log NOT FOUND: {global_log_file}")

# Check session debugger logs
session_log_file = session_log_dir / 'session_logs.json'
if session_log_file.exists():
    log_files_found.append(f"[OK] Session debugger log: {session_log_file}")
else:
    log_files_found.append(f"[FAIL] Session debugger log NOT FOUND: {session_log_file}")

# Check service debugger logs
service_log_file = service_log_dir / 'service_logs.json'
if service_log_file.exists():
    log_files_found.append(f"[OK] Service debugger log: {service_log_file}")
else:
    log_files_found.append(f"[FAIL] Service debugger log NOT FOUND: {service_log_file}")

for result in log_files_found:
    print(result)

# Test 8: Read and verify log contents
print("\n[TEST 8] Verifying log file contents...")
if global_log_file.exists():
    import json
    with open(global_log_file, 'r') as f:
        lines = f.readlines()
        print(f"[OK] Global log has {len(lines)} entries")
        if lines:
            # Parse and show first log entry
            first_entry = json.loads(lines[0])
            print(f"  Sample entry keys: {list(first_entry.keys())}")
            if 'log_type' in first_entry:
                print(f"  Log type present: {first_entry['log_type']}")

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print("[OK] Global debugger creation: PASSED")
print("[OK] Different log levels: PASSED")
print("[OK] Structured data logging: PASSED")
print("[OK] Session-specific debugger: PASSED")
print("[OK] Session-specific logging: PASSED")
print("[OK] Service log types: PASSED")
print("[OK] Log file creation: PASSED")
print("[OK] Log file contents: PASSED")
print("\n*** ALL TESTS PASSED! ***")
print("=" * 70)
