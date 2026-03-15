# Architecture Comparison: Browser-Use vs WebAxon

**Date:** 2026-03-12

---

## 1. High-Level Architecture

### Browser-Use: Event-Driven Monolith

```
+-----------------------------------------------------------+
|                      Agent Service                         |
|  +----------+  +--------------+  +---------------------+  |
|  | SystemPr |  | MessageMgr   |  |  AgentLoop          |  |
|  | ompt     |  | (compaction, |  |  (step -> LLM ->    |  |
|  |          |  |  history)    |  |   actions -> state)  |  |
|  +----------+  +--------------+  +---------------------+  |
+-----------------------------------------------------------+
|                    Tools (Registry)                         |
|  click . type . scroll . navigate . extract . done . ...   |
+---------------------------+-------------------------------+
|   Browser Session         |         DOM Service            |
|  +-------------------+    |  +-------------------------+   |
|  |  EventBus         |    |  |  AX Tree + Snapshot DOM |   |
|  |  (bubus)          |    |  |  -> Serializer Pipeline |   |
|  |                   |    |  |    |- ClickableElements |   |
|  |  Watchdogs:       |    |  |    |- PaintOrder        |   |
|  |  |- crash         |    |  |    |- HTMLSerializer    |   |
|  |  |- captcha       |    |  |    +- CodeUseSerializer |   |
|  |  |- popup         |    |  +-------------------------+   |
|  |  |- download      |    |                                |
|  |  +- ...(15+)      |    |                                |
|  +-------------------+    |                                |
+---------------------------+-------------------------------+
|                   CDP Layer (cdp_use)                       |
|          Chromium DevTools Protocol connection              |
+-----------------------------------------------------------+
```

**Key architectural characteristics:**

- **Async-first:** The entire stack is built on `asyncio`. The agent loop, browser operations, LLM calls, and event handlers are all coroutines.
- **Event-driven:** The `bubus` EventBus is the communication backbone. Browser events (`NavigationCompleteEvent`, `TabCreatedEvent`, `FileDownloadedEvent`, etc.) decouple producers from consumers.
- **Watchdog pattern:** 15+ watchdog classes (each extending `BaseWatchdog`) attach to the event bus and proactively monitor browser state. They auto-register handlers via naming convention (`on_EventTypeName` methods).
- **Pydantic-heavy:** Nearly every data structure is a Pydantic `BaseModel`, enabling serialization, validation, and schema generation for LLM tool-calling.
- **Tool-calling native:** Actions are registered in a `Registry` and dynamically composed into a `Union[ActionModel]` Pydantic type that maps directly to LLM tool-calling schemas.

### WebAxon: Layered Agent Pipeline

```
+-----------------------------------------------------------+
|                  DevSuite Service Layer                     |
|  +--------------+ +--------------+ +------------------+    |
|  | AgentRunner  | | SessionMgr   | | QueueManager     |    |
|  | (thread/     | | (lifecycle,  | | (message-based   |    |
|  |  sync exec)  | |  monitoring) | |  communication)  |    |
|  +--------------+ +--------------+ +------------------+    |
+-----------------------------------------------------------+
|              Multi-Agent Pipeline                          |
|  +---------+  +----------+  +----------+  +---------+     |
|  |Planning |->| Action   |->|Reflection|->|Response |     |
|  | Agent   |  | Agent    |  |  Loop    |  | Agent   |     |
|  +---------+  +----------+  +----------+  +---------+     |
+-----------------------------------------------------------+
|           Meta-Agent Pipeline (optional)                    |
|  COLLECT -> EVALUATE -> SYNTHESIZE -> VALIDATE             |
|  (trace recording -> action graph generation)              |
+-----------------------------------------------------------+
|                     WebDriver                              |
|  +--------------------+  +--------------------------+      |
|  |  Action Execution  |  |  HTML Processing          |     |
|  |  (execute_action)  |  |  |- clean_html()          |     |
|  |  Action Memory     |  |  |- element_identification|     |
|  |  (ContentMemory)   |  |  |- rule matching         |     |
|  |  Window Tracking   |  |  +- sanitization          |     |
|  +--------------------+  +--------------------------+      |
+-----------------------------------------------------------+
|              BackendAdapter (ABC)                           |
|     +--------------+       +----------------+              |
|     | Selenium     |       |  Playwright    |              |
|     | Backend      |       |  Backend       |              |
|     +--------------+       +----------------+              |
+-----------------------------------------------------------+
```

**Key architectural characteristics:**

- **Synchronous with threading:** The core agent loop is synchronous. Concurrent execution uses threading (`AgentRunner` spawns daemon threads). This simplifies debugging but limits I/O parallelism.
- **Multi-agent separation:** Distinct agents for planning, action execution, and response generation. Each has its own prompt templates managed by `TemplateManager`.
- **Backend abstraction:** The `BackendAdapter` ABC defines ~40+ abstract methods that both `SeleniumBackend` and `PlaywrightBackend` implement, providing true backend portability.
- **HTML-centric context:** The LLM sees cleaned HTML (not screenshots), with elements identified by `__id__` attributes and resolved to stable XPaths.
- **Agent Foundation dependency:** Core agent logic (prompt-based agents, action graphs, inferencers) lives in the external `agent_foundation` library, making WebAxon a domain-specific layer on top.
- **Meta-agent synthesis:** The unique COLLECT -> EVALUATE -> SYNTHESIZE -> VALIDATE pipeline transforms observed agent traces into reproducible `ActionGraph` artifacts.

## 2. Control Flow Comparison

### Browser-Use Agent Loop

```python
# Simplified from agent/service.py (~4000 lines)
async def run(self, max_steps):
    for step in range(max_steps):
        # 1. Get browser state (DOM + screenshot + tabs)
        state = await browser_session.get_state_summary()

        # 2. Build messages (system + history + current state + screenshot)
        messages = message_manager.get_messages(state, step_info)

        # 3. Call LLM with tool-calling schema
        response = await llm.ainvoke(messages, output_format=AgentOutput)

        # 4. Execute actions (potentially multiple per step)
        for action in response.actions:
            result = await tools.execute_action(action, browser_session)

        # 5. Update history, check loop detection, handle errors
        history.add(step_result)

        # 6. Run judge if configured
        if use_judge and is_done:
            judgement = await judge(state)
```

**Notable design decisions:**
- **Multi-action per step:** Up to `max_actions_per_step` (default 5) actions can be executed in a single LLM call, reducing round-trips.
- **Message compaction:** When conversation history grows too large, older messages are summarized by an LLM into a compact memory block.
- **Loop detection:** A rolling window tracks action similarity to detect and break out of unproductive loops.
- **Judge system:** An optional secondary LLM call validates task completion before declaring success.
- **Flash mode:** A stripped-down mode that disables thinking, evaluation, and planning for faster execution.

### WebAxon Agent Loop

```python
# Simplified from the PromptBasedActionAgent pattern
def __call__(self, user_input):
    while not done:
        # 1. Get page HTML and clean it
        body_html = webdriver.get_body_html()
        cleaned_html = clean_html(body_html, ...)

        # 2. Format prompt from templates
        prompt = template_manager.format(
            user_input=user_input,
            html_context=cleaned_html,
            action_history=memory,
        )

        # 3. Call LLM via inferencer
        response = reasoner.infer(prompt)

        # 4. Parse structured XML response
        action = parse_xml_response(response)

        # 5. Execute action on WebDriver
        result = webdriver.execute_action(
            action_type=action.type,
            action_target=action.target,
            action_args=action.args,
        )

        # 6. Track HTML changes (action memory)
        memory.update(result.cleaned_body_html_after_last_action)
```

**Notable design decisions:**
- **Single action per step:** One action per LLM call (though actions can be composite, e.g., `input_and_submit`).
- **Template-driven prompts:** Handlebars-style templates managed by `TemplateManager` with hot-swappable template spaces (action_agent, planning_agent, reflection, etc.).
- **XML response format:** The LLM responds in XML (delimited by `<StructuredResponse>` tags) rather than tool-calling, parsed by the agent framework.
- **Action memory:** The `ContentMemory` system captures HTML before and after each action, tracking incremental changes at the DOM level.
- **Window-aware state:** Each browser window/tab has its own `WindowInfo` with independent action memory and last action tracking.

## 3. Data Flow: How the LLM Sees the Page

### Browser-Use

The LLM receives a **multi-modal prompt** containing:

1. **System prompt** (~2000 tokens) loaded from markdown templates, with variants for thinking/flash/model-specific modes
2. **Agent history** — summarized past actions and results
3. **Browser state** — serialized accessible elements in a tree-style XML format:
   ```
   [33]<div />
       User form
       [35]<input type=text placeholder=Enter name />
       *[38]<button aria-label=Submit form />
           Submit
   ```
4. **Screenshot** — base64-encoded PNG with bounding boxes around interactive elements
5. **Tool schemas** — Pydantic-derived JSON schemas for available actions

The LLM responds with a **structured AgentOutput**:
```json
{
  "current_state": {
    "thinking": "I need to fill in the form...",
    "evaluation_previous_goal": "Success - page loaded",
    "memory": "On the registration page",
    "next_goal": "Fill in the name field"
  },
  "action": [
    {"input_text": {"index": 35, "text": "John Doe"}}
  ]
}
```

### WebAxon

The LLM receives a **text-only prompt** containing:

1. **System prompt** — assembled from Handlebars templates with role instructions and action type definitions
2. **Cleaned HTML** — the page DOM after sanitization:
   ```html
   <a href="/home" __id__="3">Home</a>
   <button __id__="7" class="submit-btn">Submit</button>
   <input __id__="12" type="text" name="email" placeholder="Enter email" />
   ```
3. **Action history** — past actions and their HTML-level results
4. **User input** — the task description in conversational format

The LLM responds with **structured XML**:
```xml
<StructuredResponse>
  <ActionType>ElementInteraction.Click</ActionType>
  <ActionTarget>__id__=7</ActionTarget>
  <PlannedActions>Click submit button to complete form</PlannedActions>
</StructuredResponse>
```

**Critical difference:** Browser-use targets elements by **ephemeral integer index** (`35`), while WebAxon targets by **`__id__` attribute** which gets resolved to a **stable XPath** for actual execution. This means WebAxon actions are inherently more reproducible.

## 4. Dependency Architecture

### Browser-Use Dependencies

```
browser_use
|- cdp_use          (CDP client library -- core dependency)
|- bubus            (Event bus -- core dependency)
|- pydantic         (Data validation -- core dependency)
|- Pillow           (Image processing for screenshots)
|- anthropic SDK    (Anthropic LLM provider)
|- openai SDK       (OpenAI LLM provider)
|- google SDK       (Google/Vertex LLM provider)
|- groq SDK         (Groq LLM provider)
|- mistral SDK      (Mistral LLM provider)
|- ollama SDK       (Ollama LLM provider)
|- ... (10+ more LLM SDKs)
|- browser_use_sdk  (Cloud service SDK)
|- mcp SDK          (Model Context Protocol)
|- pyotp            (TOTP 2FA support)
+- lmnr             (Observability -- optional)
```

**Observation:** Browser-use carries a heavy dependency footprint because it bundles all LLM provider SDKs. This is convenient (everything works out of the box) but increases install size, dependency conflicts risk, and cold start time.

### WebAxon Dependencies

```
webaxon
|- agent_foundation     (Core agent framework -- owned internally)
|  |- PromptBasedActionAgent
|  |- MetaAgentPipeline
|  |- ActionGraph / ActionFlow
|  +- InferencerBase
|- rich_python_utils    (Utility library -- owned internally)
|  |- TemplateManager
|  |- string formatting
|  +- common utilities
|- selenium             (Browser backend -- optional)
|- playwright           (Browser backend -- optional)
|- beautifulsoup4       (HTML parsing)
|- lxml                 (XPath generation)
+- attrs                (Data classes)
```

**Observation:** WebAxon has a leaner external dependency footprint but relies heavily on internal libraries (`agent_foundation`, `rich_python_utils`). This creates a different kind of coupling — not to the open-source ecosystem but to internal codebases.

## 5. Error Handling Philosophy

### Browser-Use: Proactive Monitoring

Browser-use's error handling is **proactive** — problems are detected by watchdogs before they crash the agent:

| Watchdog | Purpose |
|----------|---------|
| `CrashWatchdog` | Detects browser/tab crashes and triggers recovery |
| `CaptchaWatchdog` | Detects CAPTCHA challenges and delegates to solver |
| `PopupsWatchdog` | Dismisses cookie banners, modals, overlays |
| `DownloadsWatchdog` | Monitors file downloads and surfaces results |
| `DOMWatchdog` | Detects DOM staleness and triggers re-extraction |
| `SecurityWatchdog` | Monitors for security warnings and certificate errors |
| `StorageStateWatchdog` | Persists cookies/storage for session continuity |
| `ScreenshotWatchdog` | Manages screenshot capture and caching |
| `HARRecordingWatchdog` | Records HTTP traffic for debugging |
| `PermissionsWatchdog` | Handles browser permission prompts |
| `AboutBlankWatchdog` | Recovers from `about:blank` navigation failures |
| `DefaultActionWatchdog` | Handles action dispatching via event bus |
| `LocalBrowserWatchdog` | Manages local browser lifecycle |
| `RecordingWatchdog` | Manages video recording of sessions |

Each watchdog extends `BaseWatchdog` and auto-registers event handlers. Watchdogs can emit their own events, creating a reactive pipeline. The `BaseWatchdog` also includes a **circuit breaker** — if the CDP WebSocket is dead, handlers are skipped to prevent hangs.

### WebAxon: Defensive Execution

WebAxon's error handling is **defensive** — errors are caught and handled at the point of action execution:

- **`execute_with_retry`** wraps action execution with configurable retry logic
- **`ElementNotFoundError`** is a specific exception type for element resolution failures
- **`no_action_if_target_not_found`** flag allows graceful skipping of actions on missing elements
- **Action memory** tracks whether actions were skipped (`action_skipped`, `skip_reason`) for downstream reasoning
- **Monitor conditions** include `event_confirmation_time` (debounce) to avoid false positives

The key difference: browser-use detects problems **systemically** (any watchdog can fire at any time), while WebAxon handles problems **locally** (each action execution handles its own errors). Browser-use's approach is more robust for unknown scenarios; WebAxon's is more predictable for known failure modes.

## 6. Configuration Architecture

### Browser-Use

Configuration is split across multiple Pydantic models:

- **`BrowserProfile`** (~50 fields): Browser launch args, context args, proxy, extensions, cloud config, DOM extraction settings
- **`AgentSettings`** (~30 fields): Vision, thinking, flash mode, max actions, loop detection, message compaction, planning
- **`CONFIG`** (global): System-wide settings from `config.py`
- **`BrowserSession.__init__`** (~60 parameters): A massive constructor that accepts BrowserProfile fields directly for convenience

**Observation:** The configuration surface area is very large. `BrowserSession.__init__` alone accepts ~60 parameters with complex defaulting logic. This provides flexibility but can be overwhelming for new users.

### WebAxon

Configuration is distributed across:

- **`BrowserConfig`** (dataclass): Browser type, headless mode, user agent, timeout, options
- **`TaskConfig`** (dataclass): Task-specific parameters, action configs
- **`ServiceConfig`** (Pydantic): Service-level settings (sync vs async, queue IDs)
- **`DEFAULT_ACTION_CONFIGS`** (immutable dict): Action metadata loaded from `ActionMetadataRegistry`
- **Template overrides** via `TemplateManager`: Prompt behavior is configured through template selection, not code parameters

**Observation:** WebAxon's configuration is more modular but less centralized. The use of `MappingProxyType` for immutable defaults and template-based prompt configuration is cleaner, but there is no single "here is everything you can configure" entry point.

---

**Next:** [03 -- DOM and Element Handling](./03-dom-and-element-handling.md)
