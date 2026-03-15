# Agent Orchestration

How each system handles the agent loop — the cycle of observation, reasoning, and action.

## OpenClaw: Browser as External Tool

OpenClaw's browser is a **tool** that the Gateway's agent calls when needed:

```
┌───────────────────────────────────────────────────────────────────┐
│                        OpenClaw Gateway                           │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                      Agent Loop                              │  │
│  │  1. Receive message from channel                            │  │
│  │  2. Build context (memory, skills, conversation history)    │  │
│  │  3. Call LLM with system prompt + tools                     │  │
│  │  4. LLM returns: reasoning + tool calls                     │  │
│  │  5. Execute tools (including browser if called)             │  │
│  │  6. Return results to LLM                                   │  │
│  │  7. LLM generates response                                  │  │
│  │  8. Send response to channel                                │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Browser Tool (when called)                      │  │
│  │  • Registered via createBrowserTool()                       │  │
│  │  • Gated by tool profile system                             │  │
│  │  • Executes single action per call                          │  │
│  │  • Returns result to agent loop                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

### Key Characteristics

1. **Single LLM call decides actions**: The Gateway's agent makes one LLM call that may include multiple tool calls (including browser).

2. **No browser-specific planning**: The browser doesn't have its own planning stage — planning happens in the Gateway's agent.

3. **Tool-level granularity**: Each browser operation is a separate tool call:
   - `browser snapshot` → returns page state
   - `browser act kind=click ref=12` → clicks element
   - `browser screenshot` → captures image

4. **Context shared with Gateway**: Browser observations become part of the conversation that the Gateway manages.

## WebAxon: Multi-Stage Pipeline

WebAxon owns the entire agent loop with specialized stages:

```
┌───────────────────────────────────────────────────────────────────┐
│                       WebAxon Agent Pipeline                      │
│                                                                   │
│  ┌─────────────────┐     ┌─────────────────┐                     │
│  │ Planning Agent  │────►│  Action Agent   │                     │
│  │                 │     │                 │                     │
│  │ Input: Task     │     │ Input: Plan +   │                     │
│  │ Output: Plan    │     │        State    │                     │
│  │                 │     │ Output: Actions │                     │
│  └─────────────────┘     └────────┬────────┘                     │
│                                   │                               │
│                                   ▼                               │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                     Execution Layer                          │  │
│  │  • BackendAdapter (Selenium/Playwright)                      │  │
│  │  • Action dispatch (Click, InputText, Scroll, etc.)         │  │
│  │  • Result capture                                            │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                   │                               │
│                                   ▼                               │
│  ┌─────────────────┐     ┌─────────────────┐                     │
│  │ Reflection Agent│────►│ Response Agent  │                     │
│  │                 │     │                 │                     │
│  │ Input: Results  │     │ Input: All      │                     │
│  │ Output: Eval    │     │ Output: User    │                     │
│  │                 │     │         Response│                     │
│  └────────┬────────┘     └─────────────────┘                     │
│           │                                                       │
│           └─── Loop back to Planning if not done                  │
└───────────────────────────────────────────────────────────────────┘
```

### Key Characteristics

1. **Multiple LLM calls per iteration**: Planning, action selection, reflection, and response are separate LLM calls.

2. **Explicit planning stage**: The Planning Agent generates a high-level plan before action selection.

3. **Built-in reflection**: After execution, the Reflection Agent evaluates outcomes and decides whether to continue.

4. **Template-driven**: Each stage uses Handlebars templates that can be customized per use case.

5. **Memory modes**: Configurable state tracking across stages (NONE, TARGET, FULL).

## Comparison

| Aspect | OpenClaw | WebAxon |
|--------|----------|---------|
| **Agent loop owner** | Gateway (external) | WebAxon (internal) |
| **LLM calls per iteration** | 1 (combined reasoning) | 2-4 (staged) |
| **Planning** | Implicit (LLM decides) | Explicit (Planning Agent) |
| **Reflection** | None built-in | Built-in stage |
| **Customization** | System prompt editing | Template editing |
| **Memory/state** | Gateway manages | Memory modes |
| **Browser role** | Tool (reactive) | Core focus (proactive) |

## Trade-off Analysis

### OpenClaw's Approach: Strengths

1. **Efficiency**: Single LLM call handles reasoning + tool selection
2. **Simplicity**: Browser doesn't need its own agent logic
3. **Integration**: Browser shares context with other tools seamlessly
4. **Flexibility**: Any agent framework can use the browser tool

### OpenClaw's Approach: Weaknesses

1. **No browser-specific planning**: Complex multi-step workflows rely entirely on LLM's implicit planning
2. **No reflection**: No built-in mechanism to evaluate action outcomes
3. **Context overhead**: Full Gateway context included even for simple browser tasks

### WebAxon's Approach: Strengths

1. **Explicit planning**: Structured approach to complex tasks
2. **Reflection loop**: Can detect and recover from failures
3. **Template customization**: Behavior changes without code changes
4. **Browser-optimized**: Pipeline designed for web automation

### WebAxon's Approach: Weaknesses

1. **Multiple LLM calls**: Higher cost and latency per iteration
2. **Complexity**: Learning curve for the pipeline model
3. **Over-engineering**: Simple tasks don't need full pipeline
4. **Integration friction**: Can't easily use with external agent frameworks

## Prompt Templates

### OpenClaw

Browser tool has a simple description injected into system prompt:

```typescript
createBrowserTool(): ToolDefinition {
  return {
    name: "browser",
    description: "Control browser via OpenClaw's browser control server...",
    parameters: {
      action: "snapshot | navigate | act | screenshot | ..."
    }
  }
}
```

The LLM learns browser usage through the tool description and examples in the system prompt.

### WebAxon

Each pipeline stage has dedicated templates:

```handlebars
{{! action_agent/main/default.hbs }}
You are an action planning agent for web automation.

Current page state:
{{page_state}}

Plan step to execute:
{{current_plan_step}}

Select the appropriate action from:
{{available_actions}}

Respond with your action selection in <StructuredResponse> tags.
```

Templates can be versioned and customized:
- `default.hbs` — Standard behavior
- `default.with_instant_learnings.hbs` — With learning context
- `default.end_customers.hbs` — Customer-facing variant

## Recommendation

WebAxon's pipeline is more sophisticated but may be over-engineered for many use cases. Consider:

1. **Simplified mode**: Offer a single-LLM-call mode for simple tasks (like OpenClaw)

```python
# Full pipeline (existing)
result = await agent.run(task, mode="full")

# Simplified mode (new)
result = await agent.run(task, mode="simple")
```

2. **Exposing as tool**: Enable WebAxon to be used as a tool within external agents

```python
# WebAxon as OpenClaw-style tool
from webaxon import browser_tool

@tool
async def browser(action: str, **kwargs):
    return await browser_tool.execute(action, **kwargs)
```

3. **Configurable pipeline depth**: Let users choose which stages to include

```python
agent = WebAgent(
    planning=True,    # Include planning stage
    reflection=False, # Skip reflection
    response=False,   # Skip response generation
)
```

This would give WebAxon the flexibility to operate in both "full pipeline" and "simple tool" modes depending on the use case.
