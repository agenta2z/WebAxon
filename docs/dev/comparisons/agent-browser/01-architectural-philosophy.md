# Architectural Philosophy

## The Fundamental Divergence

WebAxon and Agent-Browser represent two fundamentally different answers to the same question: *"How should an AI agent interact with a web browser?"*

### WebAxon: The Orchestration Framework

WebAxon treats browser automation as a **multi-agent orchestration problem**. The architecture is built around a pipeline of specialised agents:

```
User Query → Planning Agent → Action Agent → Execution → Reflection Agent → Response Agent
```

Each stage has its own prompt template (Handlebars `.hbs` files), its own LLM call, and its own output format. The `StageGateController` routes data between stages. The `AgentRunner` manages the overall execution lifecycle.

**Key implications:**

- The LLM is deeply embedded — it's not just deciding actions, it's planning, reasoning about outcomes, and reflecting on results.
- The system is inherently multi-turn and stateful — conversation history, page state, and memory modes persist across stages.
- Development requires understanding the full pipeline, not just individual actions.

### Agent-Browser: The Standalone Tool

Agent-Browser treats browser automation as a **tool invocation problem**. It provides a CLI that any LLM (or human) can call:

```
LLM decides: "I need to click the search button"
LLM emits: agent-browser click @e5
CLI returns: "Clicked button 'Search'"
LLM decides next action based on result
```

There is no planning agent, no reflection agent, no stage gates. The LLM framework (Claude, GPT, custom) handles all reasoning externally. Agent-Browser is purely the "hands" — it does what it's told and reports what happened.

**Key implications:**

- Any LLM framework can use it (no Python dependency, no specific agent architecture).
- The system is stateless from the caller's perspective (daemon maintains browser state internally).
- Development is simple — learn the CLI commands, integrate via subprocess.

## Why This Matters

The architectural choice has cascading consequences:

| Consequence | WebAxon (Framework) | Agent-Browser (Tool) |
|-------------|---------------------|----------------------|
| **Flexibility** | Constrained to the pipeline model | Any agent architecture |
| **Reasoning quality** | Built-in reflection improves outcomes | Depends on external agent |
| **Complexity** | High (understand full pipeline) | Low (learn CLI commands) |
| **Reusability** | Python-only, tightly coupled | Language-agnostic, loosely coupled |
| **Debugging** | Rich internal tooling (debugger UI) | External debugging only |
| **Customisation** | Template-driven (swap prompt templates) | Flag-driven (CLI options) |

## The Composition Question

A critical question: **can WebAxon use Agent-Browser as its browser backend?**

In theory, yes. WebAxon's `BackendAdapter` abstraction could be extended with an Agent-Browser adapter that:

1. Calls `agent-browser snapshot` instead of fetching HTML directly
2. Uses `@e` refs instead of CSS/XPath selectors
3. Calls `agent-browser click @e5` instead of `backend.click_element()`

This would give WebAxon Agent-Browser's token-efficient snapshots while keeping WebAxon's superior agent orchestration. However, it would require rethinking the element identification pipeline (see [02-page-representation.md](./02-page-representation.md)).

## Internal Architecture Comparison

### WebAxon Module Structure

```
webaxon/
├── automation/
│   ├── backends/          ← Selenium + Playwright abstraction (unique)
│   ├── agents/            ← LLM-based action decision (deeply integrated)
│   ├── meta_agent/        ← Multi-agent pipeline orchestration
│   ├── schema/            ← Action type definitions + metadata registry
│   ├── web_agent_actors/  ← Action execution layer
│   ├── configs/           ← Task configuration
│   ├── web_driver.py      ← Unified WebDriver wrapper
│   └── monitor.py         ← Condition-based monitoring
├── html_utils/            ← HTML processing + element identification
├── browser_utils/         ← Chrome profile/version management
├── devsuite/              ← Debugger UI + service infrastructure
└── url_utils/             ← Search URL construction
```

### Agent-Browser Module Structure

```
src/                       ← TypeScript (Playwright-based)
├── types.ts               ← Zod-validated schemas
├── browser.ts             ← Browser lifecycle
├── actions.ts             ← Action handlers
├── snapshot.ts            ← Accessibility tree capture
├── diff.ts                ← Snapshot/screenshot comparison
├── daemon.ts              ← Socket server (session persistence)
├── domain-filter.ts       ← Security: domain restrictions
├── confirmation.ts        ← Security: human-in-the-loop
├── encryption.ts          ← Security: AES-256-GCM
└── auth-vault.ts          ← Security: credential storage

cli/src/                   ← Rust (native CLI)
├── native/
│   ├── actions.rs         ← 80+ action handlers
│   ├── snapshot.rs        ← Accessibility tree rendering
│   ├── element.rs         ← Ref resolution
│   ├── interaction.rs     ← Mouse/keyboard primitives
│   ├── cdp/               ← Chrome DevTools Protocol
│   └── webdriver/         ← Safari/iOS support
└── main.rs                ← CLI entry point
```

**Observation**: WebAxon's structure reflects an *internal framework* design — deep module nesting, shared state, rich interconnections. Agent-Browser's structure reflects a *standalone tool* design — flat modules, clear boundaries, minimal coupling.
