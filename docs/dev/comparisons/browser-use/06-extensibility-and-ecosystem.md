# Extensibility and Ecosystem: Browser-Use vs WebAxon

**Date:** 2026-03-12

---

## 1. Overview

A framework's extensibility determines how well it adapts to new requirements without modifying core code. Both browser-use and WebAxon provide extension points, but they differ significantly in philosophy: browser-use favors **plugin-style extensibility** (skills, custom tools, watchdogs, MCP servers), while WebAxon favors **compositional extensibility** (template swapping, backend adapters, agent pipeline configuration, meta-agent stages).

---

## 2. Action/Tool Extensibility

### Browser-Use: Dynamic Registry with Decorator API

Browser-use provides a `Registry` class for registering custom actions:

```python
from browser_use.tools.registry import Registry

registry = Registry()

@registry.action(
    name="search_database",
    description="Search an internal database for records",
)
async def search_database(query: str, limit: int = 10) -> str:
    results = await db.search(query, limit)
    return json.dumps(results)
```

**Key features:**
- **Decorator-based registration** — Natural Python API, discovered at import time
- **Automatic schema generation** — Pydantic models are generated from function signatures, producing JSON Schema for LLM tool-calling
- **Namespace support** — Actions can be grouped into namespaces to avoid name collisions
- **Parameter validation** — Pydantic validates action parameters before execution
- **Async-native** — All action handlers are async functions
- **Runtime composition** — The set of available actions can be modified between agent steps

**How custom tools appear to the LLM:**
When a custom action is registered, its Pydantic-generated schema is automatically included in the tool-calling prompt. The LLM sees it alongside built-in browser actions and can invoke it the same way. No prompt engineering is required.

### WebAxon: Enum + Registry Extension

WebAxon requires extending multiple components to add new actions:

1. **Add to `WebAgentAction` enum:**
   ```python
   class WebAgentAction(str, Enum):
       # ... existing actions ...
       SEARCH_DATABASE = "Custom.SearchDatabase"
   ```

2. **Register metadata in `ActionMetadataRegistry`:**
   ```python
   ActionMetadata(
       action_type="Custom.SearchDatabase",
       description="Search an internal database",
       requires_target=False,
       args_schema={"query": "str", "limit": "int"},
   )
   ```

3. **Add dispatch handler in `WebDriver._dispatch_action()`:**
   ```python
   elif action_type == WebAgentAction.SEARCH_DATABASE:
       return self._search_database(args["query"], args.get("limit", 10))
   ```

4. **Update prompt templates** to include the new action in the action types section.

**Key observations:**
- **Multi-file change** — Adding an action requires modifying 3-4 files
- **Static registration** — Actions are defined at development time, not runtime
- **Template updates required** — The LLM must be told about the new action via prompt templates
- **No automatic schema generation** — Action metadata is hand-authored

### Critical Comparison

| Aspect | Browser-Use | WebAxon |
|--------|------------|---------|
| **Registration effort** | 1 decorator | 3-4 file changes |
| **Schema generation** | Automatic from type hints | Manual |
| **Runtime registration** | Yes | No |
| **LLM prompt update** | Automatic | Manual template edit |
| **Validation** | Pydantic (automatic) | Manual |
| **Discoverability** | Registry introspection | Enum iteration |

**Verdict:** Browser-use's decorator-based registry is dramatically more developer-friendly. WebAxon should consider adopting a similar pattern, at least for the action registration layer.

---

## 3. Skills System (Browser-Use Exclusive)

Browser-use includes a **Skills** framework that goes beyond simple action registration:

```python
# From skills/service.py
class SkillsService:
    def __init__(self, api_key: str):
        self.api = SkillsAPI(api_key)
    
    async def load_skill(self, skill_name: str) -> Skill:
        """Load a skill from the central marketplace."""
        skill_def = await self.api.get_skill(skill_name)
        return Skill(
            name=skill_def.name,
            description=skill_def.description,
            parameters=skill_def.parameters,
            steps=skill_def.steps,  # Pre-defined action sequences
        )
    
    async def execute_skill(self, skill: Skill, params: dict):
        """Execute a skill's pre-defined steps."""
        for step in skill.steps:
            action = step.render(params)  # Template substitution
            await self.tools.execute_action(action)
```

**What makes skills different from actions:**
- **Reusable across agents** — Skills are stored in a central API and can be shared
- **Parameterized workflows** — A skill encapsulates a multi-step workflow with parameters (e.g., "login_to_gmail(email, password)" might be 5 steps)
- **Pre-validated** — Skills are tested and validated before publication
- **Composable** — Skills can invoke other skills

**WebAxon equivalent:** The `ActionGraph` from `agent_foundation` serves a similar purpose — it captures multi-step workflows that can be replayed. However, ActionGraphs are generated from observed agent behavior (via the meta-agent pipeline), not authored directly. There is no marketplace or sharing mechanism.

**Recommendation:** WebAxon could benefit from a skill-like layer on top of ActionGraphs — allowing validated, parameterized ActionGraphs to be published and reused.

---

## 4. MCP (Model Context Protocol) Integration

### Browser-Use: Native MCP Server

Browser-use includes an MCP server implementation in `mcp/`:

```python
# Simplified from mcp/server.py
class BrowserUseMCPServer:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.server = MCPServer()
    
    @self.server.tool("browse_web")
    async def browse_web(url: str, task: str) -> str:
        """Browse a webpage and perform a task."""
        result = await self.agent.run(task, start_url=url)
        return result.final_result
```

This allows any MCP-compatible client (Claude Desktop, Cursor, other agents) to invoke browser-use as a tool. The integration is bidirectional — browser-use can also be an MCP client, invoking external MCP servers as additional tools.

### WebAxon: No MCP Support

WebAxon does not implement MCP. Its service layer uses a custom queue-based communication protocol (via the devsuite `QueueManager`), which serves a similar purpose (external systems can send tasks) but is not standardized.

**Recommendation:** Adding MCP server support to WebAxon would enable integration with the growing MCP ecosystem (Claude, Cursor, VS Code agents, etc.) without changing the core architecture. The `WebDriver` service could be exposed as an MCP tool.

---

## 5. Code Generation (Browser-Use Exclusive)

Browser-use's `code_use/` module can export agent traces as executable Python code:

```python
# From code_use/service.py
class CodeUseService:
    def trace_to_code(self, agent_history: AgentHistory) -> str:
        """Convert agent trace to executable Python script."""
        code_lines = []
        for step in agent_history.steps:
            for action in step.actions:
                code_lines.append(
                    self._action_to_code(action, step.dom_state)
                )
        return self._format_notebook(code_lines)
```

This produces code like:
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    # Step 1: Navigate to login page
    page.goto("https://example.com/login")
    
    # Step 2: Enter username
    page.fill('input[name="username"]', "john@example.com")
    
    # Step 3: Enter password
    page.fill('input[name="password"]', "secret")
    
    # Step 4: Click login button
    page.click('button[type="submit"]')
```

**Key insight:** The `CodeUseSerializer` generates CSS selectors alongside DOM indices specifically to enable this code generation — the indices target elements during the agent run, while the selectors become the targeting mechanism in the generated code.

**WebAxon equivalent:** The `ActionGraph` from the meta-agent pipeline serves a somewhat similar purpose — it captures a reproducible workflow. However, ActionGraphs are an internal representation executed by the WebAxon runtime, not standalone Playwright/Selenium scripts. WebAxon's XPath-based identification makes code generation more straightforward than browser-use's index-based system, because XPaths are directly usable in both Selenium and Playwright.

---

## 6. Event Bus Architecture (Browser-Use Exclusive)

The `bubus` EventBus is the backbone of browser-use's extensibility:

```python
# Core event bus usage patterns
class EventBus:
    def subscribe(self, event_type: str, handler: Callable): ...
    async def emit(self, event: Event): ...
    def unsubscribe(self, event_type: str, handler: Callable): ...
```

**Events flow through the system:**
```
Browser Action → CDP Event → EventBus.emit() → Watchdog Handlers
                                              → Agent Listeners
                                              → External Subscribers
```

**Why this matters for extensibility:**
- **Decoupled architecture** — New features (recording, logging, analytics) can subscribe to events without modifying existing code
- **Composable middleware** — Multiple handlers can react to the same event
- **External integration** — External systems can subscribe to browser events for monitoring, logging, or coordination
- **Testability** — Events can be mocked in tests without launching a browser

**WebAxon has no equivalent.** The `Monitor` system provides condition-watching but is not an event bus. Adding a lightweight event bus to WebAxon would enable:
- Watchdog-style resilience features
- Plugin architecture for logging and analytics
- Decoupled feature additions

---

## 7. Developer Experience

### Browser-Use

- **Getting started:** Install package → configure LLM → `Agent(task, llm).run()` — minimal code to first result
- **Debugging:** Screenshot at each step + action trace + event log + optional video recording
- **Testing:** Integration test examples in `examples/` directory; LLM provider unit tests
- **Configuration:** Large but well-documented Pydantic models with sensible defaults
- **Community:** Open-source with active GitHub community, issues, and discussions

### WebAxon

- **Getting started:** Install package + agent_foundation + rich_python_utils → configure backend + inferencer + templates → create WebDriver → create Agent → run — more setup required
- **Debugging:** DevSuite with interactive UI, queue-based message inspection, session management, template hot-swapping
- **Testing:** (Internal testing infrastructure, not externally visible)
- **Configuration:** Modular but distributed across multiple files and libraries
- **Community:** Internal-only; knowledge concentrated in the development team

### Critical Comparison

| Aspect | Browser-Use | WebAxon |
|--------|------------|---------|
| **Time to first result** | ~5 minutes | ~30 minutes |
| **Debugging tools** | Screenshots + traces + video | Interactive debugger UI |
| **Learning curve** | Low (one Agent class) | Medium (multi-agent pipeline, templates) |
| **Documentation** | README + examples + community | Internal docs |
| **Iterability** | Fast (change task, rerun) | Fast with devSuite (hot-swap templates) |

**Verdict:** Browser-use has a lower barrier to entry and faster time-to-first-result. WebAxon's devSuite provides richer debugging for power users once the initial setup is complete.

---

## 8. Observability and Monitoring

### Browser-Use

- **Token tracking:** Built-in input/output token counting per step and cumulative
- **Cost estimation:** Per-model pricing tables, cost reported per run
- **Step timing:** Wall-clock time per step
- **Tracing:** Optional integration with `lmnr` for distributed tracing
- **Recording:** Video recording and HAR capture for post-mortem analysis

### WebAxon

- **Action logging:** Structured logs of actions, targets, and results
- **HTML change tracking:** ContentMemory captures before/after HTML
- **Session state:** WindowInfo tracks per-tab state
- **Queue messages:** All devsuite communication is logged

### Critical Comparison

| Aspect | Browser-Use | WebAxon |
|--------|------------|---------|
| **Token tracking** | Yes (per-step + cumulative) | No |
| **Cost estimation** | Yes (per-model pricing) | No |
| **Visual recording** | Video + screenshots | Screenshots only |
| **Network traffic** | HAR recording | No |
| **Distributed tracing** | lmnr integration | No |
| **DOM change history** | No | Yes (ContentMemory) |

**Verdict:** Browser-use has significantly richer observability. WebAxon's ContentMemory provides unique DOM-level insight that browser-use lacks, but browser-use covers more observability dimensions overall.

---

**Next:** [07 -- Recommendations](./07-recommendations.md)
