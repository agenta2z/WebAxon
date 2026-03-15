# Page Representation and Element Targeting

How each system represents web pages to the LLM and targets elements for interaction.

## OpenClaw: Three Snapshot Formats

OpenClaw provides three distinct snapshot formats, each optimized for different use cases:

### 1. AI Snapshot (Default)

Uses Playwright's internal `_snapshotForAI()` method:

```
navigation "Main"
  link "Home" [ref=1]
  link "Products" [ref=2]
main
  heading "Welcome to Example" [ref=3]
  textbox "Search..." [ref=4]
  button "Search" [ref=5]
  list
    listitem
      link "Product A - $29.99" [ref=6]
```

**Characteristics**:
- Compact (80,000 char limit by default)
- Numeric refs (1, 2, 3...)
- Hierarchical structure
- Relies on Playwright internal API (stability risk)

### 2. ARIA Snapshot

Raw accessibility tree via CDP `Accessibility.getFullAXTree`:

```
WebArea "Example Store"
  navigation "Main Menu"
    link "Home"
    link "Products"
  main
    heading "Welcome to Example" level=1
    search
      textbox "Search..." focused
      button "Search"
```

**Characteristics**:
- Complete accessibility information
- No refs (inspection only)
- More verbose
- Uses stable CDP API

### 3. Role Snapshot

Parsed from AI or ARIA snapshot with role-based refs:

```
[ref=e1] link "Home"
[ref=e2] link "Products"
[ref=e3] textbox "Search..."
[ref=e4] button "Search"
[ref=e5] link "Product A - $29.99"
```

**Characteristics**:
- Flat list of interactive elements
- Role-based refs (e1, e2...)
- Most compact
- Resolved via `getByRole()` + `nth()`

### Element Resolution in OpenClaw

```
ref="12" or ref="e12"
    │
    ▼
refLocator(page, ref)
    │
    ├── Numeric (12) → page.locator('[aria-ref="12"]')
    │
    └── Role-based (e12) → cached RoleRef
                            → page.getByRole(role, { name }).nth(nth)
```

## WebAxon: HTML-Centric with LLM Inference

WebAxon works primarily with HTML and traditional selectors:

### HTML Processing Pipeline

```
Raw HTML
    │
    ▼
sanitization.py (clean + normalize)
    │
    ▼
element_identification.py (find candidates)
    │
    ▼
element_rule_matching.py (apply rules)
    │
    ▼
Filtered element set
```

### Element Targeting Strategies

```python
class TargetStrategy(Enum):
    ID = "id"
    CSS = "css"
    XPATH = "xpath"
    CLASS = "class"
    NAME = "name"
    LINK_TEXT = "link_text"
    TAG_NAME = "tag_name"
```

### LLM-Based Element Inference

When selectors aren't known, `FindElementInferencer` uses an LLM call:

```handlebars
{{! find_element.hbs }}
Given this HTML:
{{page_html}}

Find the element that matches this description:
{{element_description}}

Return the element ID in <TargetElementID> tags.
```

**Process**:
1. Page HTML sent to LLM
2. Element description provided
3. LLM returns element ID
4. ID used with appropriate strategy

## Token Efficiency Comparison

| Representation | Typical Page (tokens) | Interactive Elements |
|----------------|----------------------|---------------------|
| Raw HTML | 15,000 - 50,000 | All (verbose) |
| OpenClaw AI Snapshot | 500 - 2,000 | Indexed with refs |
| OpenClaw Role Snapshot | 200 - 500 | Interactive only |
| WebAxon (sanitized HTML) | 3,000 - 10,000 | Varies by rules |

**OpenClaw achieves 10-50x better token efficiency** through accessibility tree extraction.

## Element Targeting Comparison

| Aspect | OpenClaw | WebAxon |
|--------|----------|---------|
| **Primary method** | Short refs (12, e12) | CSS/XPath selectors |
| **Selector length** | 2-4 chars | 20-100+ chars |
| **Stability** | High (refs persist in session) | Variable (DOM changes break selectors) |
| **LLM involvement** | None (refs from snapshot) | Optional (inference) |
| **Ambiguity** | None (refs are unique) | Possible (selector matches multiple) |
| **Extra LLM calls** | 0 | 1 per ambiguous element |

## Code Comparison

### OpenClaw: Click Element

```typescript
// Agent output
{ action: "click", ref: "5" }

// Resolution
const locator = await refLocator(page, "5");
await locator.click();
```

### WebAxon: Click Element

```xml
<!-- Agent output -->
<Action>
  <Type>Click</Type>
  <Target strategy="css">#search-button</Target>
</Action>
```

```python
# Resolution
element = driver.find_element(By.CSS_SELECTOR, "#search-button")
element.click()
```

Or with LLM inference:

```xml
<Action>
  <Type>Click</Type>
  <Target description="the search button">...</Target>
</Action>
```

```python
# Extra LLM call to resolve description
element_id = find_element_inferencer.infer(page_html, "the search button")
element = driver.find_element(By.ID, element_id)
element.click()
```

## Critical Analysis

### OpenClaw's Approach: Strengths

1. **Token efficiency**: 10-50x reduction is transformative for cost and context
2. **No selector brittleness**: Refs are stable within session
3. **No extra LLM calls**: Refs come from snapshot, not inference
4. **Semantic clarity**: Roles ("button", "link") are meaningful to LLMs

### OpenClaw's Approach: Weaknesses

1. **Content extraction limited**: Accessibility tree doesn't include text content
2. **Playwright internal dependency**: `_snapshotForAI()` is not a public API
3. **Chromium only**: ARIA snapshots require CDP

### WebAxon's Approach: Strengths

1. **Full HTML access**: Complete content available for extraction
2. **Backend flexibility**: Works with Selenium, not just Playwright/CDP
3. **Selector precision**: CSS/XPath can target any element
4. **LLM inference fallback**: Natural language element descriptions work

### WebAxon's Approach: Weaknesses

1. **Token expensive**: 3,000-10,000 tokens per observation
2. **Selector brittleness**: DOM changes break selectors
3. **Extra LLM calls**: Inference adds cost and latency
4. **Verbose output**: LLM must generate long selector strings

## Recommendation

WebAxon should **adopt accessibility tree snapshots** as an alternative representation mode:

```python
class AccessibilitySnapshotSerializer:
    """OpenClaw-style snapshot generation."""
    
    def capture(self, page) -> AccessibilitySnapshot:
        # For Playwright backend: use _ariaSnapshot() or CDP
        # For Selenium backend: use JavaScript injection to build tree
        ...
    
    def render(self, snapshot) -> str:
        # Render as compact text with refs
        ...
```

This would:
- Dramatically reduce token cost
- Simplify element targeting
- Align with industry direction
- Maintain backward compatibility (HTML mode still available)
