# Architectural Context

## The Fundamental Difference: Module vs Framework

The most important distinction between OpenClaw's browser system and WebAxon is their **place in a larger architecture**.

### OpenClaw: Browser as a Platform Module

OpenClaw is a **conversational AI platform** that happens to include browser automation as one of many capabilities:

```
┌─────────────────────────────────────────────────────────────────┐
│                       OpenClaw Gateway                          │
├─────────────────────────────────────────────────────────────────┤
│  Channels        │  Skills           │  Memory        │ Browser │
│  ├── Slack       │  ├── xurl         │  ├── LanceDB   │ Module  │
│  ├── Discord     │  ├── github       │  ├── Core      │         │
│  ├── Telegram    │  ├── notion       │  └── ...       │         │
│  ├── WhatsApp    │  └── ...          │                │         │
│  └── Web         │                   │                │         │
├─────────────────────────────────────────────────────────────────┤
│                     LLM Providers / Routing                      │
└─────────────────────────────────────────────────────────────────┘
```

The browser is invoked when:
1. The agent's tool profile includes `"browser"` in `alsoAllow`
2. The LLM decides to call the `browser` tool
3. The Gateway routes the tool call to the browser control server

**Key implication**: The browser doesn't own the agent loop — it's a **tool** that the OpenClaw agent calls when needed.

### WebAxon: Browser as the Primary Focus

WebAxon is a **web automation framework** where browser control is the entire purpose:

```
┌─────────────────────────────────────────────────────────────────┐
│                        WebAxon Framework                        │
├─────────────────────────────────────────────────────────────────┤
│  Agent Pipeline                                                 │
│  ├── Planning Agent    → High-level task planning              │
│  ├── Action Agent      → Browser action selection               │
│  ├── Execution         → Backend (Selenium/Playwright)          │
│  ├── Reflection Agent  → Outcome evaluation                     │
│  └── Response Agent    → User-facing response                   │
├─────────────────────────────────────────────────────────────────┤
│  DevSuite: Debugger UI │ Session Manager │ Action Tester        │
└─────────────────────────────────────────────────────────────────┘
```

**Key implication**: WebAxon owns the entire agent loop — from task reception through planning, execution, reflection, and response.

## Integration Patterns

### How OpenClaw Integrates Browser

OpenClaw's browser is integrated via:

1. **Tool registration** (`openclaw-tools.ts`): `createBrowserTool()` registers the browser as an LLM tool
2. **Tool profile gating** (`tool-catalog.ts`): Browser has `profiles: []` — must be explicitly enabled
3. **HTTP control server** (`server.ts`): Loopback-only Express server exposes browser operations
4. **Client SDK** (`client.ts`): TypeScript client abstracts HTTP transport

```typescript
// How an LLM tool call becomes a browser action
agent.tool_call("browser", { action: "click", ref: "12" })
  → Gateway routes to browser tool handler
    → client.browserAct({ kind: "click", ref: "12" })
      → HTTP POST /act to control server
        → Playwright executes click
          → Response flows back
```

### How WebAxon Integrates Browser

WebAxon's browser is integrated via:

1. **BackendAdapter abstraction** (`backends/base.py`): Unified interface for Selenium/Playwright
2. **Agent pipeline** (`agents/`): Multi-stage LLM reasoning
3. **Action schema** (`schema/webagent_action.py`): Typed action definitions
4. **Queue-based service** (`devsuite/web_agent_service_nextgen/`): Message-driven execution

```python
# How a user task becomes browser actions
service.submit_message("Search for X on Google")
  → Planning Agent generates plan
    → Action Agent selects actions (Click, InputText, etc.)
      → BackendAdapter executes via Selenium/Playwright
        → Reflection Agent evaluates outcome
          → Loop continues or Response Agent generates output
```

## Deployment Models

### OpenClaw

Multiple deployment options:

1. **Local**: Gateway runs natively, browser module controls local Chrome
2. **Docker**: Gateway in container, browser in same container (needs Xvfb) or separate container
3. **Remote**: Gateway on server, node hosts with browsers on different machines
4. **Cloud**: Integration with Browserless.io or similar

The **node host** concept is important: a node host is a machine with browser capability that the Gateway can proxy to. This enables distributed browser control.

### WebAxon

Simpler deployment:

1. **Local**: Service runs natively with Selenium/Playwright
2. **Service mode**: Queue-based service with debugger UI
3. **Embedded**: Import as Python library

WebAxon doesn't have OpenClaw's distributed node host concept — browser and service are assumed co-located.

## Implications for Comparison

When comparing these systems, we must recognize they're solving **different problems at different scopes**:

| Aspect | OpenClaw | WebAxon |
|--------|----------|---------|
| **Primary purpose** | Multi-channel AI assistant | Web automation |
| **Browser's role** | One tool among many | The entire focus |
| **Agent loop owner** | Gateway (external to browser) | WebAxon (internal pipeline) |
| **Integration burden** | Must fit OpenClaw's tool model | Can define its own patterns |
| **Ecosystem benefits** | Channels, skills, memory | None (standalone) |
| **Ecosystem constraints** | Must use OpenClaw's abstractions | Free to evolve independently |

This context is essential for understanding why certain features exist in one system but not the other.
