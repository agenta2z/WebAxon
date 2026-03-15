# DOM Processing and Element Handling: Browser-Use vs WebAxon

**Date:** 2026-03-12

---

## 1. Overview

How a browser automation agent represents the page to the LLM and how it resolves element references into actual browser actions are among the most consequential architectural decisions in any web agent framework. These two systems take fundamentally different approaches, each with distinct tradeoffs.

**Browser-Use** combines an accessibility tree snapshot with CDP DOM snapshots, serializing interactive elements into a compact indexed format with optional screenshot overlays. Elements are referenced by ephemeral integer indices.

**WebAxon** processes raw HTML through a multi-stage sanitization pipeline, producing cleaned HTML with persistent `__id__` attributes. Elements are resolved to stable XPaths via a sophisticated multi-strategy identification system.

---

## 2. DOM Extraction

### Browser-Use: Accessibility Tree + CDP Snapshot

Browser-use extracts DOM state via two complementary CDP APIs:

1. **`Accessibility.getFullAXTree()`** — Returns the accessibility tree, which represents the page as assistive technologies see it. This naturally filters out decorative elements and surfaces semantic roles, labels, and states.

2. **`DOMSnapshot.captureSnapshot()`** — Returns a detailed DOM snapshot with layout information (bounding boxes, paint order, visibility).

These two data sources are merged in `DomService`:

```python
# Simplified from dom/service.py
async def get_dom_state(self):
    # Get accessibility tree nodes
    ax_nodes = await cdp_session.send("Accessibility.getFullAXTree")
    
    # Get DOM snapshot with layout
    dom_snapshot = await cdp_session.send("DOMSnapshot.captureSnapshot", {
        "computedStyles": ["display", "visibility", "opacity"],
        "includePaintOrder": True,
        "includeDOMRects": True,
    })
    
    # Merge: use AX tree for semantics, snapshot for layout
    return self._build_element_tree(ax_nodes, dom_snapshot)
```

**Why this matters:** The accessibility tree is a natural fit for LLM consumption because it already represents the page in terms of *purpose* (buttons, links, inputs, headings) rather than *structure* (divs, spans, custom elements). It inherently filters out `display: none` elements, decorative images, and CSS-only content.

**Paint order processing** (`serializer/paint_order.py`) sorts elements by their z-index and rendering order. This means the LLM sees elements in the order they visually appear, not the order they exist in the source HTML. For pages with overlapping modals, dropdowns, or fixed-position elements, this is critical for correct interaction.

### WebAxon: BeautifulSoup HTML Sanitization

WebAxon extracts the raw page HTML via the browser backend and processes it through a sophisticated multi-stage pipeline:

```python
# From html_utils/sanitization.py
def clean_html(
    html: str,
    rules: CleaningRules | None = None,
    max_elements: int = 500,
    preserve_attributes: list[str] = None,
    remove_hidden: bool = True,
    remove_disabled: bool = False,
    incremental_base: str | None = None,
) -> CleanedHTML:
```

**Stage 1 — Tag filtering:** Removes non-interactive structural tags (`script`, `style`, `noscript`, `svg`, `path`, `meta`, `link`, `head`) entirely.

**Stage 2 — Attribute filtering:** Strips most attributes, preserving only semantically useful ones: `href`, `type`, `name`, `placeholder`, `value`, `role`, `aria-label`, `aria-expanded`, `class` (partial), `id`, `data-testid`.

**Stage 3 — Hidden element removal:** Inspects inline `style` attributes and `hidden`/`aria-hidden` attributes to remove elements that are not visible.

**Stage 4 — Noise reduction:** Collapses empty `div`/`span` wrappers, removes elements with only whitespace text, and flattens deeply nested container hierarchies.

**Stage 5 — Element ID assignment:** Assigns sequential `__id__` attributes to all remaining interactive elements, creating the mapping used for action targeting.

**Stage 6 — Incremental change detection** (optional): If `incremental_base` is provided (the cleaned HTML from the previous step), the system diffs the two and marks changed regions with `<!-- CHANGED -->` / `<!-- NEW -->` comments, allowing the LLM to focus on what's different.

**Stage 7 — Size limiting:** If the cleaned HTML exceeds `max_elements`, it applies progressively aggressive pruning: first removing text-only nodes, then collapsing repeated structures, then truncating.

**Why this matters:** This pipeline produces HTML that is dramatically smaller than the original (typically 10-30% of the raw HTML) while preserving all interactive elements and their semantic context. The incremental change detection is particularly valuable — it lets the LLM understand *what happened* after an action without re-reading the entire page.

### Critical Comparison

| Aspect | Browser-Use | WebAxon |
|--------|------------|---------|
| **Input source** | Accessibility tree + DOM snapshot (two CDP calls) | Raw HTML from `page.content()` or `innerHTML` |
| **Semantic filtering** | Automatic via AX tree (built into the browser) | Manual via BeautifulSoup rules (hand-maintained) |
| **Layout awareness** | Full (bounding boxes, paint order, z-index) | None (text-only, no spatial information) |
| **Change tracking** | None (full snapshot each time) | Incremental diff with `<!-- CHANGED -->` markers |
| **Size control** | Configurable max elements; `include_dynamic_attributes` toggle | Progressive pruning with `max_elements` limit |
| **Robustness to custom elements** | AX tree handles custom elements well if ARIA is used | BeautifulSoup handles any HTML but may not understand custom semantics |
| **Performance** | Two CDP round-trips + tree merge (~50-200ms) | HTML fetch + BeautifulSoup parse + multi-stage filter (~20-100ms) |

**Verdict:** Browser-use's AX tree approach is more robust for unknown pages because the browser itself handles semantic interpretation. WebAxon's sanitization pipeline produces leaner output and supports incremental change tracking, but requires maintenance of filtering rules and cannot handle cases where visual layout matters.

---

## 3. DOM Serialization (Representation to the LLM)

### Browser-Use: Indexed Element Tree

After extraction, browser-use serializes the DOM into a compact text format:

```
[1]<nav role=navigation />
    [2]<a href="/home" />
        Home
    [3]<a href="/about" />
        About
    [4]<a href="/contact" />
        Contact
[5]<main />
    [6]<h1 />
        Welcome to Our Site
    [7]<form />
        [8]<label for=email />
            Email Address
        [9]<input type=email id=email placeholder="you@example.com" />
        *[10]<button type=submit />
            Sign Up
```

Key features of this format:
- **Bracketed indices** (`[9]`) uniquely identify each element for action targeting
- **Asterisk prefix** (`*[10]`) marks the currently focused element
- **Indentation** represents DOM hierarchy
- **Concise attribute syntax** — only key attributes are shown
- **Text content inline** — element text is shown directly after the tag

The `ClickableElements` serializer further filters to only show interactive elements (links, buttons, inputs, selects, textareas, elements with click handlers), dramatically reducing token count.

#### Multiple Serialization Strategies

Browser-use provides four serializer variants, selectable via configuration:

| Serializer | Output | Best For |
|-----------|--------|----------|
| `ClickableElements` | Indexed tree of interactive elements only | Standard agent tasks (default) |
| `HTMLSerializer` | Full HTML with indices injected | Tasks needing structural context |
| `PaintOrder` | Elements ordered by visual layer | Pages with overlays/modals |
| `CodeUseSerializer` | Python-style element descriptions | Code generation mode |

### WebAxon: Cleaned HTML with `__id__` Attributes

WebAxon sends cleaned HTML directly:

```html
<nav>
  <a href="/home" __id__="1">Home</a>
  <a href="/about" __id__="2">About</a>
  <a href="/contact" __id__="3">Contact</a>
</nav>
<main>
  <h1>Welcome to Our Site</h1>
  <form>
    <label>Email Address</label>
    <input type="email" name="email" placeholder="you@example.com" __id__="4" />
    <button type="submit" __id__="5">Sign Up</button>
  </form>
</main>
```

Key features:
- **Standard HTML** — The LLM sees real HTML, leveraging its pre-training on web content
- **`__id__` attributes** — Only interactive elements get IDs; non-interactive elements are shown for context but cannot be targeted
- **Structural preservation** — Full DOM hierarchy is visible (labels associated with inputs, forms wrapping fields, etc.)
- **Semantic HTML** — The original semantic tags are preserved, not abstracted

### Critical Comparison

| Aspect | Browser-Use (Indexed Tree) | WebAxon (Cleaned HTML) |
|--------|---------------------------|----------------------|
| **Token efficiency** | Very high (minimal syntax, no closing tags) | Moderate (standard HTML syntax has overhead) |
| **LLM familiarity** | Custom format; LLM must learn convention | Standard HTML; LLM has strong pre-training | 
| **Structural context** | Partial (indentation only, no closing tags) | Full (proper nesting, all context elements) |
| **Interactive-only filtering** | Yes (`ClickableElements` serializer) | Partial (IDs only on interactive, but all elements shown) |
| **Multiple strategies** | Yes (4 serializers) | No (single format) |
| **Suitability for code gen** | Needs `CodeUseSerializer` | Direct use in automation scripts |

**Verdict:** Browser-use's indexed format is more token-efficient and better for pure LLM reasoning about actions. WebAxon's HTML format leverages LLM pre-training on web content and provides richer structural context, which is important for understanding form-field associations, table structures, and page semantics.

---

## 4. Element Identification and Resolution

This is where the two systems diverge most significantly and where WebAxon has a clear architectural advantage.

### Browser-Use: Ephemeral Integer Indices

When the LLM wants to interact with an element, it references it by index:

```json
{"click_element": {"index": 10}}
```

The index is resolved at action time by looking up the element in the current DOM tree:

```python
# Simplified from tools/service.py
async def click_element(self, index: int):
    element = self.dom_state.get_element_by_index(index)
    if element is None:
        raise ElementNotFound(f"Element with index {index} not found")
    # Use CDP to find and click via backend_node_id
    await self.cdp_session.dom_click(element.backend_node_id)
```

**Problems with this approach:**

1. **Index instability:** If the DOM changes between the snapshot and the action (e.g., an element loads lazily), the index may point to the wrong element or no element at all.
2. **Non-reproducibility:** The same logical action ("click the Submit button") gets different indices on different page loads, making recorded actions impossible to replay.
3. **No persistent identity:** There is no way to save an element reference for later use (e.g., in an action graph) because the index only means something in the context of one specific snapshot.
4. **Multi-step fragility:** In a sequence like "scroll down → click element 42", the scroll might cause a re-render that shifts all indices.

**Mitigations browser-use employs:**
- Re-extract DOM before each action if `re_extract_dom_before_action` is enabled
- The `CodeUseSerializer` generates CSS selectors alongside indices for the code generation use case
- Hash-based element matching can fall back to attribute-based lookup

### WebAxon: Stable XPath Generation

When the LLM wants to interact with an element, it references it by `__id__`:

```xml
<ActionTarget>__id__=5</ActionTarget>
```

The `__id__` is then resolved to a stable XPath through a multi-strategy pipeline in `element_identification.py`:

```python
# Simplified from html_utils/element_identification.py
def elements_to_xpath(elements: list[Element]) -> dict[str, str]:
    xpaths = {}
    for element in elements:
        xpath = _generate_best_xpath(element)
        xpaths[element.attrs["__id__"]] = xpath
    return xpaths

def _generate_best_xpath(element):
    strategies = [
        _try_unique_id,           # //*[@id="submit-btn"]
        _try_unique_data_testid,  # //*[@data-testid="submit"]
        _try_unique_name,         # //input[@name="email"]
        _try_unique_aria_label,   # //*[@aria-label="Submit form"]
        _try_text_content,        # //button[text()="Sign Up"]
        _try_class_combination,   # //button[@class="btn primary"]
        _try_positional,          # (//button)[3]
    ]
    
    for strategy in strategies:
        xpath = strategy(element)
        if xpath and _is_unique(xpath, element.owner_document):
            return xpath
    
    # Fallback: full path from root
    return _absolute_path(element)
```

**Key features of this system:**

1. **Readability scoring:** Each generated XPath gets a readability score. `//button[@id="submit"]` scores higher than `(//div/div/button)[2]`. The system prefers human-readable selectors.
2. **Hash detection:** If an `id` or `class` contains a hash-like string (e.g., `id="btn_a8f3e2"`), it is deprioritized because it is likely generated and unstable across deployments.
3. **Uniqueness validation:** Every candidate XPath is tested against the full document to ensure it resolves to exactly one element.
4. **Fallback chain:** If no semantic strategy produces a unique match, the system falls back to positional XPaths and ultimately to absolute paths.
5. **Stability across page loads:** Because XPaths are based on semantic attributes (id, name, aria-label, text content), they remain valid across page reloads and even across different sessions — enabling persistent action graphs.

**Why this matters for action graphs:** The meta-agent pipeline can observe an agent performing actions, record the XPaths, and synthesize a reproducible `ActionGraph`. Because the XPaths are stable, this graph can be replayed on any page load without re-running the agent. This is fundamentally impossible with browser-use's index-based approach.

### Critical Comparison

| Aspect | Browser-Use (Index) | WebAxon (XPath) |
|--------|-------------------|-----------------|
| **Stability** | Ephemeral (changes every snapshot) | Persistent (survives page reloads) |
| **Readability** | Opaque number (`42`) | Human-readable (`//button[@id="submit"]`) |
| **Reproducibility** | Cannot replay across sessions | Can replay via stable XPaths |
| **Resolution speed** | O(1) array lookup | O(n) XPath evaluation |
| **Robustness to DOM changes** | Fragile (index shifts) | Moderate (XPath may break if attributes change) |
| **Action graph support** | Not possible | Native support |
| **Debugging** | Hard (what is element 42?) | Easy (XPath describes the element) |

**Verdict:** WebAxon's XPath-based identification is architecturally superior for any use case that requires reproducibility, debugging, or action graph synthesis. Browser-use's index-based approach is simpler and faster for one-shot agent runs but creates a fundamental barrier to recording and replaying automations.

---

## 5. Incremental Change Detection

### Browser-Use: No Native Support

Browser-use takes a fresh DOM snapshot at each step. There is no built-in mechanism to tell the LLM "here is what changed since your last action." The agent must rely on the LLM's ability to compare the current state to its memory of the previous state — which is token-expensive and error-prone.

The `AgentBrain.memory` field (a free-text string the LLM updates each step) is the only mechanism for tracking state changes, and it is entirely managed by the LLM itself, not computed from the DOM.

### WebAxon: First-Class ContentMemory

WebAxon's `ContentMemory` system provides **computed** change tracking:

```python
# From automation/web_driver.py
class ContentMemory:
    def __init__(self):
        self.base_html = None          # HTML at start of task
        self.last_action_html = None   # HTML after last action
        self.mode = "base"             # "base" or "incremental"
    
    def get_changes(self, current_html):
        if self.mode == "base":
            return diff(self.base_html, current_html)
        else:
            return diff(self.last_action_html, current_html)
```

The LLM prompt can include markers like:
```html
<!-- CHANGED: was "0 items" -->
<span __id__="12">1 item</span>
<!-- /CHANGED -->

<!-- NEW -->
<div __id__="13" class="notification">Item added to cart</div>
<!-- /NEW -->
```

This means the LLM does not have to re-read the entire page to understand what its action did — it can focus on the `CHANGED` and `NEW` regions. For large pages (e-commerce catalogs, dashboards), this dramatically reduces token usage and improves accuracy.

**Verdict:** WebAxon's incremental change detection is a significant advantage. It reduces token cost, improves LLM accuracy, and provides a foundation for more sophisticated reasoning about action outcomes. Browser-use should consider adding a similar capability.

---

## 6. Recommendations for WebAxon

Based on this analysis, WebAxon could benefit from adopting several browser-use innovations:

1. **Add optional screenshot support** — Even if HTML remains the primary representation, an optional screenshot can help the LLM understand visual layout for CSS-heavy pages.
2. **Add paint-order awareness** — For pages with modals/overlays, knowing which elements are visually on top prevents the LLM from trying to interact with obscured elements.
3. **Consider accessibility tree extraction** — The AX tree could complement the HTML sanitization pipeline, especially for pages with complex ARIA widgets.
4. **Multiple serialization strategies** — Different tasks benefit from different DOM representations. A strategy pattern (like browser-use's serializers) would add flexibility.

At the same time, WebAxon's element identification and change tracking are areas where browser-use could learn from WebAxon.

---

**Next:** [04 -- Agent Loop and LLM Integration](./04-agent-loop-and-llm-integration.md)
