# Runtime Log Paths — E2E Test Run 2026-02-13 03:17:35

Base path: `C:\Users\yxinl\OneDrive\Projects\PythonProjects\WebAgent\src\webagent\devsuite\_runtime`

## Agent Logs (SessionLogManager output)

```
agent_logs\e2e_test_20260213_031735\manifest.json
agent_logs\e2e_test_20260213_031735\session.jsonl                                              (84 MB)
agent_logs\e2e_test_20260213_031735\turn_001_20260213_031759.jsonl                             (1 KB)
agent_logs\e2e_test_20260213_031735\turn_002_20260213_031759.jsonl                             (102 MB)
agent_logs\e2e_test_20260213_031735\artifacts\turn_000_001_PromptBasedActionPlanningAgent_ReasonerInput_20260213_031744.txt
agent_logs\e2e_test_20260213_031735\artifacts\turn_000_002_PromptBasedActionPlanningAgent_AgentResponse_20260213_031759.txt    (50 MB)
agent_logs\e2e_test_20260213_031735\artifacts\turn_001_001_PromptBasedActionPlanningAgent_AgentState_20260213_031759.txt
agent_logs\e2e_test_20260213_031735\artifacts\turn_002_001_PromptBasedActionPlanningAgent_AgentState_20260213_031759.txt
agent_logs\e2e_test_20260213_031735\artifacts\turn_002_002_PromptBasedActionPlanningAgent_AgentResponse_20260213_031802.txt    (50 MB)
agent_logs\e2e_test_20260213_031735\artifacts\turn_002_003_PromptBasedActionPlanningAgent_AgentNextActions_20260213_031805.json (50 MB)
agent_logs\e2e_test_20260213_031735\overflow\                                                  (empty)
```

## Service Logs

```
service_logs\e2e_test_20260213_031735\service_e2e_test.jsonl
service_logs\global\global_service.jsonl
```

## Debugger Logs

```
debugger_logs\e2e_test_20260213_031735\debugger_e2e_test.jsonl\web_agent_service_e2e_test      (2.4 GB, 184 JSON lines)
```

## Quick Access Commands

### Extract all AgentNextActions (action decisions with reasoning):
```python
import json
log_file = r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\WebAgent\src\webagent\devsuite\_runtime\debugger_logs\e2e_test_20260213_031735\debugger_e2e_test.jsonl\web_agent_service_e2e_test'
with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line: continue
        data = json.loads(line)
        msg = data.get('item', {})
        if not isinstance(msg, dict): continue
        msg_msg = msg.get('message', {})
        if isinstance(msg_msg, dict) and msg_msg.get('type') == 'AgentNextActions':
            print(f"Line {i} time={msg_msg.get('time')}")
            print(f"  {str(msg_msg.get('item', ''))[:500]}")
            print()
```

### Extract all AgentActionResults (URLs and skip status):
```python
import json
log_file = r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\WebAgent\src\webagent\devsuite\_runtime\debugger_logs\e2e_test_20260213_031735\debugger_e2e_test.jsonl\web_agent_service_e2e_test'
with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line: continue
        data = json.loads(line)
        msg = data.get('item', {})
        if not isinstance(msg, dict): continue
        msg_msg = msg.get('message', {})
        if isinstance(msg_msg, dict) and msg_msg.get('type') == 'AgentActionResults':
            item = msg_msg.get('item', {})
            if isinstance(item, dict):
                print(f"Line {i} time={msg_msg.get('time')} skipped={item.get('action_skipped')} source={str(item.get('source',''))[:100]}")
```

## Relevant Source Files

| File | Description |
|------|-------------|
| `WebAgent/src/webagent/automation/backends/selenium/actions.py:395-560` | `click_element()` — Selenium click with new-tab support |
| `WebAgent/src/webagent/automation/backends/selenium/actions.py:470-488` | `_normal_click()` — default click path (element.click → JS fallback) |
| `WebAgent/src/webagent/automation/backends/selenium/actions.py:1376-1455` | `execute_single_action()` — action dispatch (click, input_text, etc.) |
| `WebAgent/src/webagent/automation/web_driver.py:1170-1282` | `__call__()` — action execution pipeline with __id__ re-injection |
| `WebAgent/src/webagent/automation/web_driver.py:1263` | `add_unique_index_to_elements()` — re-injects __id__ after each action |
| `WebAgent/src/webagent/automation/backends/selenium/element_selection.py:46-64` | `add_unique_index_to_elements()` — sequential __id__ assignment |
| `WebAgent/src/webagent/automation/backends/selenium/element_selection.py:67-92` | `find_element_by_unique_index()` — XPath lookup by __id__ |
