# Page Representation: How Each System "Sees" Web Pages

This is the single most important technical difference between WebAxon and Agent-Browser. How a system represents a web page to the LLM determines everything — token consumption, action reliability, and the quality of agent reasoning.

## WebAxon: HTML-Centric Representation

WebAxon works with the actual DOM. The `html_utils` module provides utilities for:

- **HTML sanitization** (`sanitization.py`): Cleaning and normalizing HTML
- **Element identification** (`element_identification.py`): Finding elements by various criteria
- **Rule matching** (`element_rule_matching.py`): Pattern-based element selection

When the agent needs to understand a page, WebAxon typically provides:

1. The page URL and title
2. Relevant portions of the DOM (often filtered/sanitized)
3. Element candidates matching certain rules

### Element Targeting in WebAxon

WebAxon uses traditional web automation targeting strategies:

```python
# From backends/types.py and base.py
class TargetStrategy(Enum):
    ID = "id"
    CSS = "css"
    XPATH = "xpath"
    CLASS = "class"
    NAME = "name"
    LINK_TEXT = "link_text"
    PARTIAL_LINK_TEXT = "partial_link_text"
    TAG_NAME = "tag_name"
```

When the LLM needs to specify an element, it must produce a CSS selector, XPath, or element ID. The `FindElementInferencer` can help — it takes an element description and page HTML, then returns the element ID:

```handlebars
{{! From find_element.hbs - conceptual }}
Given this HTML:
{{page_html}}

Find the element that matches this description:
{{element_description}}

Return the element ID in <TargetElementID> tags.
```

### Token Cost Analysis

A typical e-commerce page might have 50,000+ characters of HTML. Even after sanitization, sending significant DOM portions to the LLM consumes 3,000–10,000 tokens per observation. This is:

- **Expensive**: At $15/million input tokens (GPT-4o), each observation costs ~$0.05–0.15
- **Context-hungry**: Leaves less room for conversation history, reasoning, and instructions
- **Fragile**: HTML structure varies wildly; LLM must understand DOM semantics

## Agent-Browser: Accessibility Tree Snapshots

Agent-Browser takes a fundamentally different approach. Instead of HTML, it extracts the browser's **accessibility tree** — the same representation used by screen readers.

### How Snapshots Work

```
1. Call CDP Accessibility.getFullAXTree()
   → Returns semantic tree: roles, names, states

2. Filter to interactive elements
   → buttons, links, inputs, etc.

3. Assign short refs: @e1, @e2, @e3...
   → Monotonic, stable within session

4. Render as compact text
```

**Example output:**

```
navigation "Main Menu"
  link "Home" [ref=@e1]
  link "Products" [ref=@e2]
main
  heading "Welcome" [level=1]
  form "Search"
    searchbox "Search products..." [ref=@e3]
    button "Search" [ref=@e4]
  list "Products"
    link "Widget A — $29.99" [ref=@e5]
    link "Widget B — $49.99" [ref=@e6]
```

### Token Cost Analysis

The same e-commerce page that produces 50,000 characters of HTML becomes ~500 characters of accessibility snapshot. This is:

- **87–95% token reduction**: Each observation costs ~$0.003–0.01
- **Context-efficient**: More room for reasoning and history
- **Semantic**: Based on accessibility roles, not DOM structure

### Element Targeting with Refs

Instead of CSS selectors, Agent-Browser uses short refs:

```bash
# WebAxon style (conceptual)
backend.click_element(strategy="css", target="#search-button")

# Agent-Browser style
agent-browser click @e4
```

The ref `@e4` maps internally to a CDP backend node ID. This mapping is stable within a session and survives across CLI invocations (the daemon maintains the RefMap).

## Critical Comparison

| Aspect | WebAxon (HTML) | Agent-Browser (A11y Snapshot) |
|--------|----------------|-------------------------------|
| **Token cost per observation** | 3,000–10,000 | 200–500 |
| **Element targeting** | CSS/XPath selectors | Short refs (@e1, @e5) |
| **Semantic clarity** | Low (LLM must parse HTML) | High (roles + names) |
| **Non-interactive elements** | Included (noise) | Filtered out |
| **Stability** | Fragile (DOM changes) | Stable (refs persist) |
| **Content extraction** | Good (full HTML) | Poor (need separate calls) |
| **Hidden elements** | Included unless filtered | Excluded by default |

## Where WebAxon's Approach Wins

1. **Content extraction**: When the task is "extract all product details," having full HTML is advantageous. The accessibility tree omits text content.

2. **Complex selectors**: Some elements can only be targeted via complex CSS/XPath that has no accessibility equivalent.

3. **JavaScript-heavy SPAs**: Accessibility trees can be incomplete on poorly-structured SPAs.

## Where Agent-Browser's Approach Wins

1. **Token efficiency**: 10–50x reduction is transformative for cost and context management.

2. **Interaction tasks**: For clicking, filling, navigating — 90% of agent tasks — refs are more reliable than selectors.

3. **LLM reasoning quality**: Semantic roles ("button", "textbox") are easier for LLMs to reason about than HTML tags.

4. **Robustness**: Accessibility trees are more stable across minor DOM changes than CSS selectors.

## Recommendation for WebAxon

**Consider a hybrid approach:**

1. **Primary observation**: Accessibility tree snapshot (like Agent-Browser)
2. **Fallback for content**: Full HTML extraction on demand
3. **Element targeting**: Short refs for interactions, selectors for complex cases

This could be implemented as a new serialization mode in the DOM processing pipeline, potentially integrating Agent-Browser's snapshot code as a dependency or porting the approach.
