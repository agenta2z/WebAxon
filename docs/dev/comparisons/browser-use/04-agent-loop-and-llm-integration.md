# Agent Loop and LLM Integration: Browser-Use vs WebAxon

**Date:** 2026-03-12

---

## 1. Overview

The agent loop is the heartbeat of any LLM-driven automation system — the cycle of observe, reason, act, and evaluate that drives task completion. Browser-use and WebAxon implement this loop with fundamentally different philosophies: browser-use uses a **single-agent, multi-action loop** with native tool-calling, while WebAxon uses a **multi-agent pipeline** with template-driven XML responses.

---

## 2. Agent Loop Architecture

### Browser-Use: Single-Agent with Tool-Calling

Browser-use runs a **single agent** that handles all reasoning, planning, and action execution within one continuous conversation. The agent receives the full page state each step and can request multiple actions.

```
Step 1: System prompt + task + page state → LLM → [click, type, click] → Execute all
Step 2: Updated page state → LLM → [scroll] → Execute
Step 3: Updated page state → LLM → [extract_data, done] → Complete
```

**Key implementation details from `agent/service.py`:**

1. **AgentOutput structure:** Each LLM response contains:
   - `current_state.thinking` — Chain-of-thought reasoning (optional, controlled by `use_thinking`)
   - `current_state.evaluation_previous_goal` — Assessment of what just happened
   - `current_state.memory` — Persistent memory updated each step
   - `current_state.next_goal` — What the agent plans to do next
   - `action` — Array of 1-N actions to execute (up to `max_actions_per_step`)

2. **Multi-action batching:** The agent can request up to 5 actions in a single LLM call (configurable via `max_actions_per_step`). Actions execute sequentially, and if any action fails, remaining actions in the batch are skipped. This reduces LLM round-trips for simple sequences (e.g., "fill form field, then click submit").

3. **Message compaction:** When the conversation exceeds a token threshold, the `MessageManager` triggers a "memory squeeze" — an LLM call that summarizes older messages into a compact memory block. The original messages are then dropped. This prevents unbounded context growth.

   ```python
   # Simplified from agent/message_manager/service.py
   async def _compact_history(self):
       summary_prompt = "Summarize the key actions and outcomes so far..."
       summary = await llm.ainvoke([summary_prompt])
       self.history = [SystemMessage(summary)] + self.recent_messages[-N:]
   ```

4. **Loop detection:** A rolling window (configurable via `max_failures_per_action`) tracks the last N actions. If the same action appears repeatedly with the same result, the agent injects a "you appear to be stuck" message and forces a different approach.

5. **Judge system:** When the agent declares `done`, an optional secondary LLM call (`judge`) reviews the final state and decides if the task is truly complete. This prevents premature completion claims.

6. **Flash mode vs. thinking mode:**
   - **Thinking mode** (default): The LLM produces `thinking`, `evaluation`, `memory`, and `next_goal` fields alongside actions. More tokens, better reasoning.
   - **Flash mode**: Only actions are produced — no reasoning fields. Faster and cheaper, suitable for simple tasks.

### WebAxon: Multi-Agent Pipeline

WebAxon separates the agent loop into **distinct specialized agents**, each with its own prompt templates and responsibilities:

```
User Task
    |
    v
[Planning Agent] --- "Break this task into steps" --> Plan
    |
    v
[Action Agent] --- "Given this HTML, execute step N" --> Action
    |
    v
[WebDriver] --- Execute action on browser --> Result
    |
    v
[Reflection Loop] --- "Did the action succeed?" --> Assessment
    |
    v (if more steps)
[Action Agent] --- Next step --> ...
    |
    v (when complete)
[Response Agent] --- "Summarize what was accomplished" --> Final Response
```

**Key implementation details:**

1. **PromptBasedActionAgent:** The core action agent from `agent_foundation`. It uses `TemplateManager` to assemble prompts from modular templates:
   - `system_template` — Role and capabilities definition
   - `action_types_template` — Available action types with examples
   - `context_template` — Current page HTML and state
   - `history_template` — Previous actions and results
   - `instruction_template` — Current step to execute

2. **Action types as an enum system:** Actions are defined in `ActionMetadataRegistry` with rich metadata:
   ```python
   ActionMetadata(
       action_type="ElementInteraction.Click",
       description="Click on an interactive element",
       requires_target=True,
       target_type="element_id",
       example_target="__id__=7",
       args_schema=None,
   )
   ```
   The agent receives a formatted list of available actions in its prompt, not as tool schemas but as text descriptions.

3. **XML response format:** Instead of LLM tool-calling, the agent responds in structured XML:
   ```xml
   <StructuredResponse>
     <Reasoning>The submit button is visible and the form is filled</Reasoning>
     <ActionType>ElementInteraction.Click</ActionType>
     <ActionTarget>__id__=5</ActionTarget>
     <ActionArgs></ActionArgs>
     <PlannedActions>Submit the form, then verify success message</PlannedActions>
   </StructuredResponse>
   ```
   This is parsed by `parse_structured_response()` in the agent framework.

4. **Reflection loops:** After each action, a reflection step evaluates whether the action achieved its intended effect. This uses the incremental HTML change data from `ContentMemory`:
   - "The button was clicked and a success notification appeared" → proceed
   - "The form shows a validation error" → modify approach
   - "No visible change occurred" → retry or try alternative

5. **StageGateController (Meta-Agent):** For the meta-agent pipeline, the `StageGateController` manages transitions between stages:
   ```
   COLLECT: Record agent traces (actions + page states)
   EVALUATE: Score trace quality and completeness
   SYNTHESIZE: Generate ActionGraph from traces
   VALIDATE: Verify the ActionGraph reproduces the task
   ```
   Each stage has a gate condition that must be met before advancing.

### Critical Comparison

| Aspect | Browser-Use (Single Agent) | WebAxon (Multi-Agent) |
|--------|---------------------------|----------------------|
| **Reasoning depth** | All reasoning in one model call | Separated: planning, action, reflection, response |
| **Token efficiency** | Higher (one call per step) | Lower (multiple calls per step) |
| **Error recovery** | Loop detection + retry | Reflection loop + explicit assessment |
| **Task decomposition** | Implicit (agent decides what to do) | Explicit (planning agent creates steps) |
| **Multi-action per step** | Yes (up to 5) | No (one action per step) |
| **Context management** | Message compaction via summarization | Template-based context assembly |
| **Completion verification** | Optional judge system | Reflection loop + response agent |
| **Debugging** | Single conversation trace | Separate traces per agent phase |

**Verdict:** Browser-use's single-agent approach is more token-efficient and simpler to reason about. WebAxon's multi-agent separation provides better task decomposition and error recovery, at the cost of more LLM calls. For simple tasks, browser-use is faster; for complex multi-step workflows, WebAxon's structure prevents the "confused agent" problem where a single agent loses track of where it is in a multi-step plan.

---

## 3. LLM Provider Integration

### Browser-Use: Built-In Multi-Provider Abstraction

Browser-use ships with a comprehensive LLM abstraction layer in `llm/`:

```
llm/
  base.py                    # BaseChatModel ABC
  anthropic/
    chat.py                  # AnthropicChat
    serializer.py            # Message format conversion
  openai/
    chat.py                  # OpenAIChat  
    serializer.py
  google/
    chat.py                  # GoogleChat (Vertex AI)
    serializer.py
  azure/
    chat.py                  # AzureOpenAIChat
    serializer.py
  groq/
    chat.py                  # GroqChat
  mistral/
    chat.py                  # MistralChat
  ollama/
    chat.py                  # OllamaChat
  deepseek/
    chat.py                  # DeepSeekChat
  cerebras/
    chat.py                  # CerebrasChat
  ... (OCI, OpenRouter, Vercel, Bedrock, etc.)
```

**Key design:**

- **`BaseChatModel`** defines the interface: `ainvoke(messages, output_format)` returns structured output
- Each provider has a **serializer** that converts browser-use's internal message format to the provider's API format (handling differences in tool-calling syntax, image encoding, system message placement, etc.)
- **Structured output** is handled per-provider:
  - Anthropic: Uses `tool_use` blocks with JSON schema
  - OpenAI: Uses `tools` parameter with function definitions
  - Google: Uses `function_declarations`
  - Providers without tool support: Falls back to JSON-in-text parsing
- **Token counting** is provider-specific (each provider has its own tokenizer)
- **Cost estimation** uses per-model pricing tables

**Advantage:** Zero lock-in. Switch from `AnthropicChat("claude-sonnet-4-20250514")` to `OpenAIChat("gpt-4o")` with a one-line change, and all tool schemas, message formatting, and structured output parsing adapt automatically.

**Disadvantage:** Each provider SDK is a dependency. The full install pulls in 15+ SDKs, most of which a given deployment will never use. This could be mitigated with optional extras (`pip install browser-use[anthropic]`), which browser-use does partially support.

### WebAxon: Delegated to agent_foundation

WebAxon does not contain any LLM integration code itself. It delegates entirely to `agent_foundation`:

```python
# From agent_foundation (external library)
class InferencerBase(ABC):
    @abstractmethod
    def infer(self, prompt: str, **kwargs) -> str:
        ...

class AnthropicInferencer(InferencerBase):
    def infer(self, prompt, **kwargs):
        return self.client.messages.create(...)

class OpenAIInferencer(InferencerBase):
    def infer(self, prompt, **kwargs):
        return self.client.chat.completions.create(...)
```

The `PromptBasedActionAgent` accepts an `InferencerBase` instance and calls `infer()` to get text responses, which are then parsed from XML.

**Advantage:** Clean separation of concerns. WebAxon does not need to know or care about LLM providers. The `agent_foundation` library handles all provider differences.

**Disadvantage:** No native tool-calling support. The LLM must produce structured XML in its text response, which is less reliable than native tool-calling (the LLM might produce malformed XML, or hallucinate fields). This also means WebAxon cannot take advantage of provider-specific features like Anthropic's extended thinking or OpenAI's parallel tool calls.

### Critical Comparison

| Aspect | Browser-Use | WebAxon |
|--------|------------|---------|
| **Provider count** | 15+ built-in | Depends on agent_foundation (typically 3-5) |
| **Response format** | Native tool-calling (JSON schema) | Text-based XML parsing |
| **Structured output reliability** | High (validated by provider) | Moderate (XML parsing can fail) |
| **Token counting** | Built-in, per-provider | Not built-in |
| **Cost tracking** | Built-in pricing tables | Not built-in |
| **Provider features** | Can leverage provider-specific features | Lowest common denominator |
| **Dependency weight** | Heavy (all SDKs bundled) | Light (only used providers) |
| **Switching effort** | One-line change | One-line change (at agent_foundation level) |

**Verdict:** Browser-use's native tool-calling integration is a significant advantage. Tool-calling is more reliable than XML text parsing, enables multi-action responses, and gives access to provider-specific features. However, the dependency cost is real. WebAxon's approach is cleaner architecturally but sacrifices reliability and features.

---

## 4. Prompt Engineering

### Browser-Use: Markdown System Prompts with Dynamic Injection

Browser-use stores system prompts as markdown files in `agent/system_prompts/`:

```
system_prompts/
  system_prompt.md              # Main system prompt
  system_prompt_thinking.md     # Extended version with thinking instructions
  system_prompt_flash.md        # Minimal version for flash mode
```

The `SystemPrompt` class loads the appropriate template and injects dynamic content:

```python
# Simplified from agent/prompts.py
class SystemPrompt:
    def format(self, dom_content, step_info, action_schemas):
        template = self._load_template(self.mode)
        return template.format(
            max_actions_per_step=self.settings.max_actions_per_step,
            available_actions=self._format_action_schemas(action_schemas),
            important_rules=self._get_rules(),
            dom_content=dom_content,
            current_date_time=datetime.now().isoformat(),
        )
```

The system prompt includes:
- Role definition ("You are a browser automation agent")
- Available action descriptions with parameter schemas
- Rules for element interaction (use index, handle popups, etc.)
- Output format specification (AgentOutput JSON)
- Current date/time for time-sensitive tasks

**Notable features:**
- **Model-specific prompt variants:** Different prompts for different model capabilities
- **Dynamic action schema injection:** Available actions are formatted from the tool registry's Pydantic schemas
- **Planning instructions:** When `use_planning` is enabled, the prompt includes planning-specific guidance
- **Image handling instructions:** When vision is enabled, instructions for interpreting screenshots are included

### WebAxon: Template-Managed Handlebars Prompts

WebAxon uses `TemplateManager` from `rich_python_utils` to manage Handlebars-style templates:

```python
# From automation/agents/action_agent_factory.py
template_manager = TemplateManager(
    template_space="action_agent",
    templates={
        "system": "system_prompt.hbs",
        "action_types": "action_types.hbs",
        "context": "context.hbs",
        "examples": "examples.hbs",
        "history": "history.hbs",
    }
)
```

Templates use Handlebars syntax with helpers:
```handlebars
{{#if action_history}}
## Previous Actions
{{#each action_history}}
- Step {{@index}}: {{this.action_type}} on {{this.target}} -> {{this.result}}
{{/each}}
{{/if}}

## Current Page
```html
{{{cleaned_html}}}
```

## Your Task
{{user_input}}
```

**Notable features:**
- **Modular composition:** Prompt is assembled from multiple small templates, each swappable independently
- **Template spaces:** Different agent roles (action_agent, planning_agent, reflection) have different template sets
- **Hot-swapping:** Templates can be changed at runtime without code changes
- **Conditional sections:** Handlebars `{{#if}}` and `{{#each}}` enable context-dependent prompt assembly
- **Example injection:** Task-specific few-shot examples can be injected via the `examples` template

### Critical Comparison

| Aspect | Browser-Use | WebAxon |
|--------|------------|---------|
| **Template format** | Markdown with Python f-string substitution | Handlebars with helpers and conditionals |
| **Modularity** | Monolithic (one file per mode) | Modular (composable template fragments) |
| **Hot-swapping** | Requires code change | Runtime template replacement |
| **Few-shot examples** | Embedded in system prompt | Separate template, dynamically injected |
| **Action descriptions** | Auto-generated from Pydantic schemas | Hand-authored in template |
| **Context length mgmt** | Message compaction via summarization | Template-level conditional inclusion |

**Verdict:** WebAxon's template system is more flexible and maintainable. The modular composition and hot-swapping capabilities make it easier to experiment with prompt engineering without code changes. Browser-use's approach is simpler but less adaptable.

---

## 5. State Management and Memory

### Browser-Use

State is managed through three mechanisms:

1. **`AgentBrain.memory`** — A free-text field the LLM updates each step. This is the agent's "working memory" and is included in every subsequent prompt. The LLM decides what to remember and what to forget.

2. **`MessageManager` history** — The full conversation history (system prompt + all user/assistant messages). When this grows too large, it is "compacted" by summarizing older messages. A configurable `max_input_tokens` threshold triggers compaction.

3. **`AgentHistory`** — A structured log of all actions, results, screenshots, and metadata. This is used for post-run analysis and code generation but is not fed back to the LLM (only the brain memory and message history are).

### WebAxon

State is managed through:

1. **`ContentMemory`** — Per-window HTML tracking with base and incremental modes. This is computed state (HTML diffs), not LLM-generated.

2. **Action history** — A structured list of previous actions, their targets, and results, formatted into the prompt via the `history` template.

3. **`WindowInfo` state** — Per-tab tracking of last action, last URL, and content memory state.

4. **Planning agent output** — When a planning agent is used, the plan persists across action steps, providing a structured "what to do next" rather than relying on the LLM's free-form memory.

### Critical Comparison

| Aspect | Browser-Use | WebAxon |
|--------|------------|---------|
| **Memory type** | LLM-managed free text | Computed HTML diffs + structured history |
| **Reliability** | Depends on LLM memory quality | Deterministic (computed from DOM) |
| **Token cost** | Grows until compaction | Controlled by template size limits |
| **Cross-window** | Shared memory across tabs | Per-window independent memory |
| **Persistence** | In-memory only | Action graphs persist to disk |

**Verdict:** WebAxon's computed memory (HTML diffs) is more reliable than browser-use's LLM-managed memory. The LLM can forget or misremember previous state; the DOM diff cannot. However, browser-use's free-text memory is more flexible and can capture semantic understanding that raw HTML diffs miss.

---

**Next:** [05 -- Browser Automation Layer](./05-browser-automation-layer.md)
