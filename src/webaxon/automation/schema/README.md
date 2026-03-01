# WebAgent Action Schema Integration

This package provides WebAgent-specific integration with the action sequence execution system from ScienceModelingTools. It enables UI automation workflows to be defined as JSON documents and executed via WebDriver.

## Architecture Overview

```mermaid
flowchart TB
    subgraph SMT["ScienceModelingTools (Source of Truth)"]
        direction TB
        constants["constants.py
        • ActionMemoryMode enum
        • TargetStrategy enum
        • Action name constants
        • get_default_actions()"]
        
        metadata["action_metadata.py
        • ActionTypeMetadata
        • ActionMetadataRegistry"]
        
        executor["action_flow_executor.py
        • ActionFlowExecutor"]
        
        constants --> metadata
        metadata --> executor
    end
    
    subgraph WA["WebAgent"]
        direction TB
        waaction["webagent_action.py
        • WebAgentAction
        • DEFAULT_ACTION_CONFIGS
        • ElementNotFoundError"]
        
        webdriver["web_driver.py
        • WebDriver class
        • Memory capture
        • Target resolution"]
        
        actions["selenium/actions.py
        • execute_single_action()
        • execute_composite_action()
        • click, input, scroll, etc."]
        
        waaction --> webdriver
        webdriver --> actions
    end
    
    SMT --> WA
```

## Data Flow: From Schema to Execution

```mermaid
sequenceDiagram
    participant User
    participant WebDriver
    participant ActionConfig as WebAgentAction
    participant Memory as ContentMemory
    participant Actions as selenium/actions.py
    participant Browser as Selenium WebDriver
    
    User->>WebDriver: __call__(action_type, target, args)
    WebDriver->>ActionConfig: Get action config
    ActionConfig-->>WebDriver: WebAgentAction instance
    
    alt Not Follow-up Action
        WebDriver->>Memory: _capture_base_memory()
        Note over Memory: Based on base_memory_mode
    end
    
    alt Composite Action
        WebDriver->>Actions: execute_composite_action()
        loop For each step
            Actions->>Browser: Execute sub-action
        end
    else Simple Action
        WebDriver->>Actions: execute_single_action()
        Actions->>Browser: Execute action
    end
    
    alt capture_incremental_memory_after_action
        WebDriver->>Memory: _capture_incremental_memory()
        Note over Memory: Based on incremental_change_mode
    end
    
    WebDriver-->>User: WebDriverActionResult
```

## Module Dependency Graph

```mermaid
graph LR
    subgraph ScienceModelingTools
        C[constants.py] --> AM[action_metadata.py]
        AM --> AFE[action_flow_executor.py]
        CM[common.py] --> AFE
    end
    
    subgraph WebAgent
        WAA[webagent_action.py] --> WD[web_driver.py]
        WD --> SA[selenium/actions.py]
        SA --> SE[selenium/element_selection.py]
        SA --> SC[selenium/common.py]
    end
    
    AM --> WAA
    AFE --> WAA
    
    style C fill:#e1f5fe
    style AM fill:#e1f5fe
    style AFE fill:#e1f5fe
    style WAA fill:#fff3e0
    style WD fill:#fff3e0
    style SA fill:#fff3e0
```

## Memory Mode State Machine

```mermaid
stateDiagram-v2
    [*] --> CheckBaseMode: Action starts
    
    CheckBaseMode --> CaptureFullBase: base_memory_mode = FULL
    CheckBaseMode --> CaptureTargetBase: base_memory_mode = TARGET
    CheckBaseMode --> NoCapture: base_memory_mode = NONE
    
    CaptureFullBase --> ExecuteAction
    CaptureTargetBase --> ExecuteAction
    NoCapture --> ExecuteAction
    
    ExecuteAction --> CheckIncrementalMode
    
    CheckIncrementalMode --> CaptureFullIncr: incremental_change_mode = FULL
    CheckIncrementalMode --> CaptureTargetIncr: incremental_change_mode = TARGET
    CheckIncrementalMode --> Done: incremental_change_mode = NONE
    
    CaptureFullIncr --> Done
    CaptureTargetIncr --> Done
    Done --> [*]
```

## Execution Flow Details

### 1. Action Configuration Loading

```python
# In webagent_action.py - loads from ScienceModelingTools
registry = ActionMetadataRegistry()  # Loads defaults from constants.py
DEFAULT_ACTION_CONFIGS = {
    'click': WebAgentAction(name='click', base_memory_mode=NONE, ...),
    'scroll': WebAgentAction(name='scroll', base_memory_mode=TARGET, ...),
    'visit_url': WebAgentAction(name='visit_url', base_memory_mode=NONE, ...),
    ...
}
```

### 2. WebDriver Initialization

```python
# In web_driver.py
class WebDriver:
    def __init__(self, action_configs=None):
        self._action_configs = action_configs or DEFAULT_ACTION_CONFIGS
```

### 3. Action Execution via __call__

```python
# WebDriver.__call__() flow:
def __call__(self, action_type, action_target, action_args, ...):
    # 1. Get action config
    action_config = self._action_configs.get(action_type)
    
    # 2. Memory capture (based on action_config.base_memory_mode)
    if not action_is_follow_up:
        self._capture_base_memory(action_config, element, action_memory)
    
    # 3. Execute action
    if action_config.composite_action:
        execute_composite_action(driver, elements, action_config, ...)
    else:
        self.execute_single_action(element, action_type, action_args, ...)
    
    # 4. Incremental memory capture
    if action_config.capture_incremental_memory_after_action:
        self._capture_incremental_memory(action_config, element, action_memory)
```

### 4. Action Dispatch in selenium/actions.py

```python
def execute_single_action(driver, element, action_type, action_args, ...):
    if action_type == 'click':
        click_element(driver, element, ...)
    elif action_type == 'input_text':
        input_text(driver, element, **action_args)
    elif action_type == 'scroll':
        scroll_element(driver, element, **action_args)
    elif action_type == 'visit_url':
        open_url(driver, element, ...)  # element is URL string
    ...
```

## Memory Modes (ActionMemoryMode)

Memory modes control HTML capture for tracking UI changes:

| Action | base_memory_mode | incremental_change_mode | Rationale |
|--------|-----------------|------------------------|-----------|
| click | NONE | NONE | Click doesn't predictably change content |
| input_text | NONE | NONE | Text input doesn't change visible structure |
| scroll | TARGET | TARGET | Scroll reveals new content in target area |
| visit_url | NONE | NONE | Navigation replaces page entirely |
| wait | NONE | NONE | Wait doesn't change content |

### Memory Mode Constraints

```mermaid
graph TD
    NONE_BASE["base_memory_mode = NONE"] --> NONE_INCR["incremental_change_mode = NONE only"]
    TARGET_BASE["base_memory_mode = TARGET"] --> TARGET_OR_NONE["incremental_change_mode = TARGET or NONE"]
    FULL_BASE["base_memory_mode = FULL"] --> ANY_INCR["incremental_change_mode = FULL, TARGET, or NONE"]
    
    style NONE_BASE fill:#ffcdd2
    style TARGET_BASE fill:#fff9c4
    style FULL_BASE fill:#c8e6c9
```

## Default Actions

| Action | Default Strategy | Memory Mode | Description |
|--------|-----------------|-------------|-------------|
| click | FRAMEWORK_ID | NONE/NONE | Click on a UI element |
| input_text | FRAMEWORK_ID | NONE/NONE | Input text into a field |
| append_text | FRAMEWORK_ID | NONE/NONE | Append text to existing content |
| visit_url | LITERAL | NONE/NONE | Navigate to a URL |
| scroll | FRAMEWORK_ID | TARGET/TARGET | Scroll an element or page |
| scroll_up_to_element | FRAMEWORK_ID | TARGET/TARGET | Scroll until element visible |
| wait | None | NONE/NONE | Wait for specified duration |
| input_and_submit | FRAMEWORK_ID | NONE/NONE | Composite: input + click |

## Target Resolution Strategies

```mermaid
graph LR
    subgraph Strategies
        FID["FRAMEWORK_ID (__id__)
        Framework-assigned unique ID"]
        ID["ID (id)
        Native HTML id attribute"]
        XP["XPATH (xpath)
        XPath expression"]
        CSS["CSS (css)
        CSS selector"]
        TXT["TEXT (text)
        Text content matching"]
        LIT["LITERAL (literal)
        Value used as-is"]
    end
    
    FID --> |Default for most actions| Actions
    LIT --> |Used by visit_url| Actions
```

| Strategy | Value | Description |
|----------|-------|-------------|
| FRAMEWORK_ID | `__id__` | Framework-assigned unique ID (default) |
| ID | `id` | Native HTML id attribute |
| XPATH | `xpath` | XPath expression |
| CSS | `css` | CSS selector |
| TEXT | `text` | Text content matching |
| LITERAL | `literal` | Value used as-is (for URLs) |

## Composite Actions

```mermaid
sequenceDiagram
    participant WD as WebDriver
    participant CA as execute_composite_action
    participant SA as execute_single_action
    
    WD->>CA: elements=[input_el, btn_el], config
    
    loop For each step in composite_steps
        CA->>CA: Extract step (action_type, element_index)
        CA->>CA: Get element from elements[element_index]
        CA->>CA: Extract action-specific args
        CA->>SA: execute_single_action(element, action_type, args)
    end
    
    CA-->>WD: Complete
```

Composite actions decompose into multiple sub-actions:

```python
# input_and_submit = input_text + click
action_config.composite_steps = [
    ('input_text', 0),  # First element
    ('click', 1),       # Second element
]

# Usage: target contains space-separated element IDs
{
    "type": "input_and_submit",
    "target": "search-input submit-button",
    "args": {"text": "query"}
}
```

## Package Contents

- `__init__.py` - Re-exports from ScienceModelingTools + WebAgent-specific
- `webagent_action.py` - WebAgentAction class, DEFAULT_ACTION_CONFIGS, ElementNotFoundError
- `README.md` - This documentation

## Usage Examples

### Direct WebDriver Usage

```python
from webaxon.automation.web_driver import WebDriver

driver = WebDriver(headless=True)
driver.open_url("https://example.com")

# Execute action via __call__
result = driver(
    action_type='click',
    action_target='submit-button',  # Element ID
    action_args={}
)
```

### With ActionFlowExecutor

```python
from webaxon.automation.schema import (
    load_sequence,
    ActionFlow,
    ActionMetadataRegistry,
)
from webaxon.automation.web_driver import WebDriver

driver = WebDriver(headless=True)
sequence = load_sequence("actions.json")

executor = ActionFlow(
    action_executor=driver,
    action_metadata=ActionMetadataRegistry()
)
result = executor.execute(sequence)
```

## Import Hierarchy

```python
# From ScienceModelingTools (source of truth)
from agent_foundation.automation.schema import (
    ActionMemoryMode,  # Enum: FULL, TARGET, NONE
    TargetStrategy,  # Enum: FRAMEWORK_ID, ID, XPATH, CSS, TEXT, LITERAL
    ActionTypeMetadata,  # Base Pydantic model
    ActionMetadataRegistry,  # Registry with defaults
    ActionFlow,  # Sequence executor
)

# From WebAgent (extends ScienceModelingTools)
from webaxon.automation.schema import (
    WebAgentAction,  # Extends ActionTypeMetadata
    DEFAULT_ACTION_CONFIGS,  # Pre-loaded action configs
    ActionMemoryMode,  # Re-exported
    ElementNotFoundError,  # Selenium-specific exception
)
```

## Testing

```bash
pytest WebAgent/test/webaxon/automation/schema/ -v
```
