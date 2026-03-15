# Agent Orchestration: Multi-Stage Pipelines vs External Tool Model

This document examines the fundamental difference in how each system handles agent reasoning and decision-making.

## WebAxon: Multi-Stage Pipeline

WebAxon implements a sophisticated multi-agent orchestration system with distinct stages:

### Pipeline Stages

```
┌─────────────────┐
│  User Query     │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Planning Agent  │  ← Generates high-level plan
│ (planning_agent/│    Output: <Plan><Step>...</Step></Plan>
│  main/*.hbs)    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Action Agent    │  ← Decides specific browser actions
│ (action_agent/  │    Output: <PlannedActions><Action>...</Action></PlannedActions>
│  main/*.hbs)    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Execution       │  ← WebDriver executes actions
│ (BackendAdapter)│
└────────┬────────┘
         ▼
┌─────────────────┐
│ Reflection Agent│  ← Evaluates outcome, decides next step
│ (reflection/    │    Output: Success/Failure + reasoning
│  *.hbs)         │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Response Agent  │  ← Generates user-facing response
│ (response_agent/│    Output: Natural language response
│  main/*.hbs)    │
└────────┴────────┘
         │
    ┌────┴────┐
    │ Done?   │
    └────┬────┘
      No │ Yes
         ▼
    Loop to Planning
```

### Stage Gate Controller

The `StageGateController` (`agents/stage_gate_controller.py`) manages transitions between stages:

- Routes outputs from one stage to inputs of the next
- Handles conditional branching (e.g., reflection can loop back to planning)
- Maintains stage-specific context

### Template-Driven Customization

Each stage uses Handlebars templates that can be versioned and customized:

```
_workspace/prompt_templates/
├── action_agent/
│   ├── main/
│   │   ├── default.hbs
│   │   ├── default.end_customers.hbs
│   │   └── default.with_instant_learnings.hbs
│   └── reflection/
│       └── *.hbs
├── planning_agent/
│   ├── main/
│   └── reflection/
├── reflection/
│   └── default.hbs
└── response_agent/
    └── main/
```

The `TemplateManager` (`agents/template_manager.py`) loads and renders these templates with context variables.

### Memory Modes

WebAxon tracks state across stages with configurable memory modes:

```python
class ActionMemoryMode(Enum):
    NONE = "none"      # No element tracking
    TARGET = "target"  # Track target element only
    FULL = "full"      # Track all page elements
```

This enables the agent to reference previous observations and understand page state changes.

## Agent-Browser: No Built-In Orchestration

Agent-Browser takes the opposite approach: **it provides no agent orchestration at all**. The browser is a tool; orchestration is the caller's responsibility.

### External Agent Model

```
┌─────────────────────────────────────────┐
│          External Agent Framework       │
│  (Claude, GPT, LangChain, CrewAI, etc.) │
├─────────────────────────────────────────┤
│  Agent decides: "I need to click the    │
│  search button"                         │
│                                         │
│  Agent emits tool call:                 │
│    agent-browser click @e5              │
│                                         │
│  Agent receives result:                 │
│    "Clicked button 'Search'"            │
│                                         │
│  Agent reasons about next step...       │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│            Agent-Browser CLI            │
│  (Stateless from caller's perspective)  │
├─────────────────────────────────────────┤
│  • Parse command                        │
│  • Resolve ref to element               │
│  • Execute via CDP                      │
│  • Return text result                   │
└─────────────────────────────────────────┘
```

### Daemon State (Internal)

While the CLI appears stateless, the daemon maintains browser state internally:

- Browser process lifecycle
- RefMap (element index → backend node ID)
- Console/error message buffer
- Recording/trace state

This state persists across CLI calls within a session, but the calling agent doesn't need to manage it.

## Comparison

| Aspect | WebAxon (Pipeline) | Agent-Browser (External) |
|--------|-------------------|--------------------------|
| **Reasoning location** | Inside the framework | External agent framework |
| **Customization** | Template editing | Agent prompt engineering |
| **Multi-turn context** | Built-in memory modes | Caller manages context |
| **Reflection/recovery** | Built-in reflection stage | Caller implements |
| **Planning** | Dedicated planning agent | Caller's planning |
| **Complexity** | High (learn pipeline) | Low (learn CLI) |
| **Flexibility** | Constrained to pipeline | Any architecture |
| **LLM calls per action** | 2-4 (plan+action+reflect) | 1 (caller's reasoning) |

## Trade-off Analysis

### WebAxon's Pipeline: Pros

1. **Structured reasoning**: Separate stages force explicit planning and reflection, which can improve outcomes on complex tasks.

2. **Customizable without code changes**: Swapping prompt templates changes behavior without modifying Python code.

3. **Built-in recovery**: Reflection stage can detect failures and loop back to planning.

4. **Consistent output format**: XML structure ensures parseable LLM responses.

### WebAxon's Pipeline: Cons

1. **Multiple LLM calls per step**: Each stage is an LLM call. A single browser action might require 3-4 API calls, multiplying cost and latency.

2. **Rigid structure**: The pipeline assumes a specific workflow. Some tasks don't fit the plan→act→reflect pattern.

3. **Debugging complexity**: Issues can occur at any stage; tracing requires understanding the full pipeline.

4. **Template maintenance**: Multiple template files per stage, with versioning, creates maintenance burden.

### Agent-Browser's External Model: Pros

1. **Framework agnostic**: Works with any LLM, any agent architecture, any programming language.

2. **Single LLM call per step**: The calling agent reasons once per action, not multiple times.

3. **Simple mental model**: Learn CLI commands, integrate via subprocess.

4. **Composable**: Can be combined with any orchestration framework (LangGraph, CrewAI, custom).

### Agent-Browser's External Model: Cons

1. **No built-in reflection**: The caller must implement failure detection and recovery.

2. **No shared best practices**: Each integration reinvents context management, planning, etc.

3. **Quality depends on caller**: Agent-Browser's effectiveness depends entirely on how well the calling agent is implemented.

## Hybrid Consideration

A potential synthesis: **WebAxon could expose Agent-Browser-style CLI commands while maintaining its internal pipeline.**

```python
# Current WebAxon: Everything internal
result = await agent.run(task="Search for X on Google")

# Hybrid: WebAxon pipeline + CLI tool mode
# Pipeline uses CLI-style commands internally
# External callers can also use CLI directly
```

This would give WebAxon users a choice:
- Full pipeline mode for complex tasks
- Tool mode for integration with external agents

## Recommendation

WebAxon's pipeline is a strength for standalone operation, but a barrier for integration. Consider:

1. **Exposing a "tool mode"**: A simplified interface that executes single actions without the full pipeline, for integration with external agents.

2. **Reducing LLM calls**: Exploring whether planning and action can be combined into a single call for simpler tasks.

3. **Documenting the pipeline clearly**: The multi-stage architecture is powerful but complex. Clear documentation would help adoption.
