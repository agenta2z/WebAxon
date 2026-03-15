# Action Systems: Types, Execution, and Element Targeting

Both systems need to translate LLM decisions into browser operations. This document compares how each system defines, validates, and executes actions.

## WebAxon's Action System

### Action Metadata Registry

WebAxon defines actions through `ActionTypeMetadata` (from `agent_foundation`) extended by `WebAgentAction`:

```python
# From webagent_action.py
class WebAgentAction(ActionTypeMetadata):
    """
    Extends ActionTypeMetadata with backward-compatible properties.
    
    Memory Mode Constraints:
    - NONE: No element tracking needed
    - TARGET: Track target element only
    - FULL: Track all elements on page
    
    Composite Action:
    - Can decompose into multiple sub-actions
    """
    
    @property
    def composite_steps(self) -> Optional[List[Tuple[str, int]]]:
        """Get composite steps for multi-step actions."""
        ...
```

**Built-in action types:**
- `Click`, `InputText`, `AppendText`
- `Scroll`, `ScrollUpToElement`
- `VisitUrl`, `Wait`, `NoOp`
- `InputAndSubmit` (composite: InputText + Click)

### LLM Output Format

WebAxon uses structured XML for LLM responses:

```xml
<StructuredResponse>
  <PlannedActions>
    <Action>
      <Type>Click</Type>
      <Target strategy="id">submit-button</Target>
    </Action>
    <Action>
      <Type>InputText</Type>
      <Target strategy="css">#email-input</Target>
      <Args><text>user@example.com</text></Args>
    </Action>
  </PlannedActions>
</StructuredResponse>
```

### Element Resolution

When `<Target description="...">` is used instead of explicit selectors, the `FindElementInferencer` makes an LLM call to resolve:

```
Page HTML + Element Description → LLM → Element ID
```

This is powerful (natural language element descriptions) but expensive (extra LLM call per ambiguous element).

## Agent-Browser's Action System

### CLI Commands

Agent-Browser exposes 80+ commands as CLI operations:

```bash
# Navigation
agent-browser open https://example.com
agent-browser navigate https://example.com
agent-browser back / forward / reload

# Interaction
agent-browser click @e5
agent-browser fill @e3 "hello world"
agent-browser type @e3 "hello"     # Without clearing
agent-browser select @e2 "Option A"
agent-browser hover @e5
agent-browser scroll @e5

# Observation
agent-browser snapshot
agent-browser screenshot
agent-browser gettext @e5

# State
agent-browser state save mysite
agent-browser state load mysite
agent-browser cookies

# Advanced
agent-browser route "*/api/*" --status 404  # Request interception
agent-browser har start / stop               # Network recording
agent-browser profiler start / stop          # CPU profiling
agent-browser record start / stop            # Video recording
```

### Element Resolution

Agent-Browser uses refs from the most recent snapshot:

```bash
# Take snapshot (assigns refs)
agent-browser snapshot
# Output includes: button "Submit" [ref=@e5]

# Use ref in action
agent-browser click @e5
# Resolution: @e5 → RefMap → backend_node_id → DOM element
```

The ref system avoids the need for LLM element inference — the snapshot already provides indexed elements.

## Action Coverage Comparison

| Category | WebAxon | Agent-Browser |
|----------|---------|---------------|
| **Navigation** | VisitUrl | open, navigate, back, forward, reload, wait |
| **Click** | Click | click, dblclick |
| **Text input** | InputText, AppendText | fill, type, clear |
| **Selection** | (via Click) | select, check, uncheck |
| **Scrolling** | Scroll, ScrollUpToElement | scroll, scroll_to_element |
| **Keyboard** | (limited) | key, send_keys |
| **Hover** | (not explicit) | hover |
| **Tabs** | (limited) | tab_new, tab_switch, tab_close, tab_list |
| **Network** | None | route, unroute, har, offline |
| **Profiling** | None | profiler, trace |
| **Video** | None | record |
| **Storage** | None | cookies, storage |
| **Downloads** | None | download |
| **Screenshots** | (implicit) | screenshot, screenshot --annotate |
| **Extraction** | (via HTML) | gettext, getattr, source |

**Key gap**: WebAxon lacks network interception, profiling, video recording, and fine-grained storage management. These are powerful debugging and automation features in Agent-Browser.

## Execution Layer Comparison

### WebAxon: BackendAdapter

WebAxon's `BackendAdapter` (in `backends/base.py`) provides a unified interface across Selenium and Playwright:

```python
class BackendAdapter(ABC):
    @abstractmethod
    def click_element(self, element: Any, ...) -> bool: ...
    
    @abstractmethod
    def input_text(self, element: Any, text: str, ...) -> bool: ...
    
    @abstractmethod
    def scroll_element(self, element: Any, ...) -> bool: ...
    
    @abstractmethod
    def execute_script(self, script: str, ...) -> Any: ...
```

Each backend (Selenium, Playwright) implements these methods with backend-specific code.

**Strength**: True backend abstraction — same code works on both Selenium and Playwright.

### Agent-Browser: DaemonState + CDP

Agent-Browser's Rust implementation uses direct CDP commands:

```rust
// Simplified from cli/src/native/actions.rs
impl DaemonState {
    async fn execute_click(&mut self, ref_str: &str) -> Result<()> {
        let entry = self.ref_map.get(ref_str)?;
        let (x, y) = self.resolve_element_center(entry.backend_node_id)?;
        
        self.cdp.send("Input.dispatchMouseEvent", json!({
            "type": "mouseMoved", "x": x, "y": y
        })).await?;
        self.cdp.send("Input.dispatchMouseEvent", json!({
            "type": "mousePressed", "x": x, "y": y, "button": "left"
        })).await?;
        self.cdp.send("Input.dispatchMouseEvent", json!({
            "type": "mouseReleased", "x": x, "y": y, "button": "left"
        })).await?;
        
        Ok(())
    }
}
```

**Strength**: Direct CDP control — full protocol access, no abstraction overhead.

## Error Handling

### WebAxon

Errors propagate through the backend abstraction:

```python
# From backends/exceptions.py
class ElementNotFoundError(WebAxonBackendError): ...
class StaleElementError(WebAxonBackendError): ...
class ElementNotInteractableError(WebAxonBackendError): ...
```

The agent pipeline can catch these and include them in the next LLM observation for recovery.

### Agent-Browser

Errors are translated to LLM-friendly messages:

```
CDP Error: "Could not compute box model"
→ AI-Friendly: "Element is not visible — try scrolling into view"
```

This `toAIFriendlyError()` pattern ensures the LLM gets actionable guidance, not cryptic protocol errors.

## Composite Actions

### WebAxon

Supports composite actions that decompose into multiple steps:

```python
# InputAndSubmit decomposes to:
# 1. InputText on element 0
# 2. Click on element 1
composite_steps = [("InputText", 0), ("Click", 1)]
```

### Agent-Browser

No built-in composite actions — the LLM is expected to sequence individual actions. However, `max_actions_per_step` in the TypeScript daemon allows batching multiple actions in a single LLM turn.

## Recommendation

WebAxon should consider:

1. **Adopting ref-based targeting**: Even without Agent-Browser's snapshot format, generating short refs for elements would simplify LLM output parsing.

2. **Adding AI-friendly error messages**: The `toAIFriendlyError()` pattern is cheap to implement and improves recovery.

3. **Expanding action coverage**: Network interception and HAR recording would be valuable for debugging and testing workflows.
