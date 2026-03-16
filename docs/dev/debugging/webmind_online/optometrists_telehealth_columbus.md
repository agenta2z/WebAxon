# Debugging: Optometrists Telehealth Columbus (Task 26a0e5c21c145dd8)

## Task

- **Description**: Browse optometrists who offer telehealth services in Columbus, OH.
- **Start URL**: https://www.healthgrades.com/
- **Template**: `end_customers`
- **Session ID**: `eval_run005_177359634617`
- **Session status**: `error`
- **Duration**: ~4 minutes (10:39:06 - 10:43:14)
- **Final answer**: `[Task incomplete] I'm now on the Healthgrades homepage. I'll search for optometrists in Columbus, OH and then filter for telehealth services.`

## Verdict

- **WebJudge**: FAIL (correct verdict — agent never reached search results)
- **Root cause**: React component re-render after typing in search field caused `__id__` attributes to point to wrong elements

## Timeline

| Turn | Time | Agent | Actions | Outcome |
|------|------|-------|---------|---------|
| 1 | 10:40:28-39 | Planning | Decomposed task into single problem | OK |
| 2 | 10:40:39-52 | Action | `Navigation.VisitURL [healthgrades.com]` | OK — homepage loaded |
| 3 | 10:40:52-10:41:20 | Action | Examined DOM, planned 3 actions in one response | Batched 3 ElementInteractions (violates prompt rule but actions are correct) |
| 4 | 10:41:20-10:43:14 | WorkGraph executing 3 actions | Action 1 OK, Action 2 crashed | **FATAL ERROR** |

### The 3 planned actions (all correct from UI perspective)

The agent correctly identified the search form and planned a perfectly logical sequence:
1. `ElementInteraction.InputText [475]` → type "optometrist" in the search field
2. `ElementInteraction.InputText [483]` → type "Columbus, OH" in the location field
3. `ElementInteraction.Click [490]` → click the search button

This is exactly how a human would fill out the form. The actions themselves are not wrong.

### Turn 4: The crash — React re-render shifts `__id__` attributes

**Action 1 (10:41:20 → 10:41:32)**: `InputText "optometrist"` into element 475 — **succeeded**.

Side effect: Typing triggered Healthgrades' **autocomplete/typeahead** feature, which added ~83 new DOM nodes (the dropdown suggestions). The page did NOT fully refresh. The existing form elements (including the location input) remained intact and interactable.

**What this did to `__id__` attributes**:

After action 1 completed, our framework (`web_driver.py:1454`) called `add_unique_index_to_elements()` which **re-numbered all elements** in the DOM. Because ~83 new autocomplete nodes were inserted above the location input in DOM order, all subsequent elements got higher `__id__` values. The location input shifted from `__id__="483"` to `__id__="566"`, and the autocomplete container `<div>` inherited `__id__="483"`.

Evidence from the raw HTML snapshots:

| | BEFORE action 1 (turn 3 HTML) | AFTER action 1 (turn 4 HTML) |
|---|---|---|
| `__id__="483"` points to | `<input id="home-location-input" type="text" value="Seattle, WA">` | `<div class="wQyf- kkSfQ">` (autocomplete suggestions container!) |
| Location input `<input id="home-location-input">` has | `__id__="483"` | `__id__="566"` (re-indexed by framework) |

**Action 2 (10:41:32 → 10:41:34)**: `InputText "Columbus, OH"` into element 483 — **CRASHED**.

`find_element_by_unique_index("483")` queries the live DOM via XPath: `//*[@__id__='483']`. It finds the `<div>` (autocomplete container), not the location input. Calling `element.clear()` on a `<div>` throws `InvalidElementStateException` — you can only `clear()` input/textarea elements.

**Action 3**: Never executed (search never submitted).

## Exception Details

```
File: agent_foundation/agents/agent.py:829  (_run_single_action)
  → webaxon/automation/web_driver.py:1410  (__call__)
  → webaxon/automation/web_driver.py:693   (execute_single_action)
  → webaxon/automation/backends/selenium/selenium_backend.py:494  (execute_single_action)
  → webaxon/automation/backends/selenium/actions.py:1628  (execute_single_action → input_text)
  → webaxon/automation/backends/selenium/actions.py:915   (input_text → send_keys_with_random_delay)
  → webaxon/automation/backends/selenium/actions.py:766   (send_keys_with_random_delay → element.clear())

selenium.common.exceptions.InvalidElementStateException: Message: invalid element state
  (Session info: chrome=145.0.7632.162)
```

## Root Cause Analysis

### Core issue: Our own `__id__` re-indexing between batched actions (OUR BUG)

**The DOM elements are fine. React did NOT destroy or recreate them.** The `__id__` shift is caused entirely by our own code.

At `web_driver.py:1454`, after EVERY action execution, our code calls:
```python
self.add_unique_index_to_elements(index_name=ATTR_NAME_INCREMENTAL_ID)
```

This re-runs the JavaScript that iterates `document.getElementsByTagName('*')` and sequentially assigns `__id__` attributes to every element. When action 1 typed "optometrist", the autocomplete dropdown added ~83 new DOM nodes. Our re-indexing then shifted ALL subsequent `__id__` values:

**The bug sequence:**
1. LLM sees DOM snapshot where `__id__="483"` = location input. Plans 3 actions targeting elements 475, 483, 490.
2. Action 1 executes: `InputText [475]` types "optometrist" → succeeds.
3. Autocomplete dropdown appears → ~83 new DOM nodes inserted above the location input.
4. **`web_driver.py:1454`: `add_unique_index_to_elements()` RE-INDEXES the entire DOM.**
5. Location input is now `__id__="566"`. The autocomplete container `<div>` is now `__id__="483"`.
6. Action 2 executes: `find_element_by_unique_index("483")` → finds the `<div>` (not the input).
7. `element.clear()` on a `<div>` → `InvalidElementStateException` → fatal crash.

**The original DOM nodes (including the location input) are perfectly intact and interactable.** Our framework just re-numbered them, making the LLM's planned target IDs point to wrong elements.

### Why this only affects batched actions

In a normal turn-by-turn flow:
1. Turn N: Framework indexes DOM → LLM sees `__id__="475"` = search input → plans InputText [475]
2. Action executes → DOM changes → framework re-indexes (line 1454)
3. Turn N+1: LLM sees the **re-indexed** DOM where `__id__="566"` = location input → plans InputText [566]

The LLM always sees fresh `__id__` values. But with batched actions, the LLM planned ALL actions based on the Turn N snapshot. Actions 2 and 3 use stale `__id__` values that were invalidated by our own re-indexing after action 1.

### Contributing issue: No error recovery

`InvalidElementStateException` terminates the session. No retry, no re-indexing, no fallback.

## Potential Fixes

### Fix A: Don't re-index DOM between batched actions (targeted fix)

Move or conditionally skip the `add_unique_index_to_elements()` call at `web_driver.py:1454` so it does NOT run between actions in the same batch. Only re-index when a new turn begins (i.e., when the LLM will see the new DOM).

**Location**: `web_driver.py:1454`

**Pros**: Directly fixes the bug. Batched actions keep using the same `__id__` values the LLM planned against.
**Cons**: The post-action HTML captured between batched actions would have stale `__id__` values in the HTML used for logging/debugging, but this is cosmetic.

### Fix B: Enforce single-ElementInteraction at framework level (safest)

If the LLM returns multiple `ElementInteraction.*` actions, only execute the first one. Discard the rest and force a new turn with fresh DOM observation and re-indexing.

**Pros**: Simple, bulletproof. Each action gets its own DOM snapshot and fresh `__id__` numbering. The LLM always plans against current DOM state.
**Cons**: Increases turn count (and latency/cost) for simple form fills.

### Fix C: Catch `InvalidElementStateException` and report meaningful error

At minimum, catch the exception in `send_keys_with_random_delay` and provide a clear error message like "Element __id__=483 is a <div>, not an input — DOM may have changed". This enables the agent to retry with re-indexed DOM rather than crashing fatally.

**Pros**: Low-effort, improves debuggability and resilience.
**Cons**: Doesn't fix the root cause, only makes failure more graceful.

## Files Referenced

| File | Relevance |
|------|-----------|
| `webaxon/automation/web_driver.py:1454` | **THE BUG**: `add_unique_index_to_elements()` called after every action, re-numbering DOM and invalidating `__id__` values planned by the LLM |
| `webaxon/automation/backends/selenium/element_selection.py:58-64` | `add_unique_index_to_elements()` — the JS that assigns positional `__id__` attributes |
| `webaxon/automation/backends/selenium/element_selection.py:67-92` | `find_element_by_unique_index()` — XPath lookup by `__id__` |
| `webaxon/automation/backends/selenium/actions.py:766` | Crash point: `element.clear()` on a `<div>` |
| `webaxon/automation/web_driver.py:1336` | Where `__id__` is resolved to WebElement via `find_element_by_unique_index` |
| `web_agent_service_nextgen/_workspace/prompt_templates/action_agent/main/default.end_customers.hbs:85` | Single-ElementInteraction prompt rule (workaround, not root cause) |

## Key Evidence

```
BEFORE action 1:  __id__="483" → <input id="home-location-input" type="text" value="Seattle, WA">
AFTER  action 1:  __id__="483" → <div class="wQyf- kkSfQ">  (autocomplete container)
                  <input id="home-location-input"> moved to __id__="566"
```

The DOM elements themselves were never destroyed or recreated. The autocomplete dropdown simply added new nodes, and our own `add_unique_index_to_elements()` at `web_driver.py:1454` re-numbered everything, making the LLM's planned `__id__` values point to wrong elements.

## Session Artifacts

- **Session dir**: `web_agent_service_nextgen/_workspace/_runtime/agent_logs/eval_run005_177359634617_20260315_103906/`
- **Screenshots**: `0_screenshot.png` (Chrome new tab), `0_post_screenshot.png` (Healthgrades homepage), `1_screenshot.png` (homepage before typing), `1_post_screenshot.png` (autocomplete visible after typing "optometrist"), `2_screenshot.png` (same as 1_post, just before crash)
- **Turn 3 HTML** (BEFORE): `turn_003/session.jsonl/action_agent.parts/AgentActionResults/ui_source/20260315_104059_body_html_after_last_action_77954712.html`
- **Turn 4 HTML** (AFTER): `turn_004/session.jsonl/action_agent.parts/AgentActionResults/ui_source/20260315_104132_body_html_after_last_action_f1e0cf30.html`
- **Error log**: `turn_004/session.jsonl/action_agent` line 2 — full `InvalidElementStateException` traceback
