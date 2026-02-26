# Web Agent Framework

A generic framework for building queue-based web agent services with debugging UI support.

## Overview

This framework provides common utilities for creating web agent applications with:
- **Queue-based communication** using `StorageBasedQueueService`
- **Decoupled architecture** with separate service and debugger processes
- **Automatic log collection and visualization**
- **Shared constants and utilities** across test cases

## Directory Structure

```
web_agent/
├── __init__.py          # Package initialization with exports
├── constants.py         # Shared constants (queue IDs, paths, intervals)
├── common.py           # Common utilities (queue service, path management)
└── README.md           # This file
```

## Components

### Constants (`constants.py`)

Defines shared constants used across the framework:

- **Queue IDs**: `INPUT_QUEUE_ID`, `RESPONSE_QUEUE_ID`, `LOG_QUEUE_ID`
- **Directory names**: `RUNTIME_DIR`, `QUEUE_STORAGE_DIR`, `LOGS_DIR`
- **Polling intervals**: `QUEUE_POLL_INTERVAL_MS`, `LOG_REFRESH_INTERVAL_MS`

### Common Utilities (`common.py`)

Provides utility functions for:

#### Queue Management
- `get_queue_base_path(testcase_root)` - Get base path for queue storage
- `find_latest_queue_path(queue_base_path)` - Find the latest timestamped queue
- `initialize_queue_service(testcase_root, create_if_missing)` - Initialize queue service

#### Path Management
- `get_log_dir_path(testcase_root, log_name)` - Get path for log directories

## Usage

### In Web Agent Service (`web_agent_service.py`)

```python
from pathlib import Path
from web_agent import (
    INPUT_QUEUE_ID,
    RESPONSE_QUEUE_ID,
    LOG_QUEUE_ID,
    get_queue_base_path,
    get_log_dir_path
)

# Get testcase root directory
testcase_root = Path(__file__).parent

# Create timestamped queue storage
queue_base_path = get_queue_base_path(testcase_root)
queue_root_path = queue_base_path / timestamp()
queue_root_path.mkdir(parents=True, exist_ok=True)

# Create logger
log_dir_path = get_log_dir_path(testcase_root, f'web_agent_{timestamp()}.json')
log_dir_path.mkdir(parents=True, exist_ok=True)
```

### In Agent Debugger (`agent_debugger.py`)

```python
from pathlib import Path
from web_agent import (
    INPUT_QUEUE_ID,
    RESPONSE_QUEUE_ID,
    LOG_QUEUE_ID,
    get_queue_service
)

# Get queue service (finds latest queue automatically)
testcase_root = Path(__file__).parent
queue_service = get_queue_service(testcase_root)
```

## Architecture

### Queue-Based Communication

```
┌─────────────────────┐         ┌─────────────────────┐
│  Agent Debugger     │         │  Web Agent Service  │
│  (UI Process)       │         │  (Agent Process)    │
└─────────────────────┘         └─────────────────────┘
         │                                 │
         │  INPUT_QUEUE_ID                │
         ├────────────────────────────────►│
         │  (user messages)               │
         │                                 │
         │  RESPONSE_QUEUE_ID              │
         │◄────────────────────────────────┤
         │  (agent responses)             │
         │                                 │
         │  LOG_QUEUE_ID                   │
         │◄────────────────────────────────┤
         │  (log directory paths)         │
         │                                 │
         ▼                                 ▼
  ┌─────────────────────────────────────────────┐
  │  Shared Queue Storage                       │
  │  _runtime/_queue_storage/<timestamp>/       │
  │    ├── user_input/                          │
  │    ├── agent_response/                      │
  │    └── agent_logs/                          │
  └─────────────────────────────────────────────┘
```

### Directory Structure (Runtime)

```
testcase_directory/
├── _runtime/
│   ├── _queue_storage/
│   │   └── <timestamp>/          # One per service instance
│   │       ├── user_input/       # Input queue
│   │       ├── agent_response/   # Response queue
│   │       └── agent_logs/       # Log path queue
│   └── _logs/
│       └── web_agent_<timestamp>.json/  # Log directory (not a file!)
│           ├── Agent_abc123      # Individual log files by debuggable ID
│           ├── Reasoner_xyz456
│           └── ...
├── web_agent_service.py
└── agent_debugger.py
```

## Test Cases

Each test case should:

1. Import from `web_agent` package
2. Use standardized queue IDs and paths
3. Follow the queue-based communication pattern
4. Store logs in `_runtime/_logs/` with timestamped folders

### Example Test Cases

- **grocery_store_testcase** - Grocery planning agent
- **starbucks_testcase** - Starbucks ordering agent
- **info_swimming_team_testcase** - Information retrieval agent

## Design Principles

1. **Decoupled processes** - Service and debugger run independently
2. **Persistent queues** - File-based queues survive restarts
3. **Automatic discovery** - Debugger finds latest queue automatically
4. **Timestamped isolation** - Each service instance gets unique storage
5. **Generic utilities** - Reusable across all test cases
