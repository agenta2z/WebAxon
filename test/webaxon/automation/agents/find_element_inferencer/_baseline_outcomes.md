# Baseline outcomes — pre-migration FindElementInferencer

Captured under the **wrapper-era** `FindElementInferencer(TemplatedInferencer)`
on 2026-05-02. After migration to `TemplatedInferencerBase`, the same suite
must produce equivalent **behavior** (LLM is non-deterministic, so byte
equality is not expected — assertions check that the xpath resolves to ≥1
element in the source HTML).

## Unit tests (`test_find_element_inferencer_unit.py`)

```
14 passed in ~6.1s
```

All 14 tests passed. No flakiness — fully mocked.

## Real-LLM tests (`test_find_element_inferencer_real.py`)

```
3 passed in ~16s
ANTHROPIC_API_KEY required; cost ~$0.05 × 3 ≈ $0.15
```

| Test | Description | Returned xpath (one sample run) | Matches |
|------|-------------|----------------------------------|---------|
| `test_real_find_google_search_submit_button` | "the Google Search submit button" | `(//input[@value='Google Search'])[2]` | 1 |
| `test_real_find_im_feeling_lucky_button` | "the I'm Feeling Lucky button" | `//input[@id='gbqfbb']` | 1 |
| `test_real_find_with_options_hint` | same + `options=['static']` | `(//input[@value='Google Search'])[2]` | 1 |

The xpaths above are illustrative — different runs may return different
xpaths because (a) the LLM picks a different `__id__` candidate, and (b) the
`elements_to_xpath` selector is choice-driven by surrounding context. The
**behavioral** assertion is that whatever xpath comes back, it resolves to
≥1 element in the source HTML.

### Characterization notes

- ``clean_html`` aggressively strips elements that lack any of the kept
  attributes (`class`, `href`, `*name`, `*label`, `alt`, `src`, `type`,
  `data*`, `*title`, `srcdoc`, `disabled`, `__id__`). Notably the actual
  Google search ``<textarea>`` does not survive sanitization, so descriptions
  like "the search input box" reliably yield ``NOT_FOUND`` end-to-end. We
  deliberately avoided those targets so the suite is deterministic-passing.
- Generated xpaths reference attributes from the **original** HTML (e.g.
  ``id='gbqfbb'``), even though the LLM never sees those attributes — because
  `elements_to_xpath` runs against the parsed tree, not the sanitized
  prompt. This is the wrapper-era contract; migration must preserve it.

## Verification commands

```bash
cd C:/Users/yxinl/OneDrive/Projects/PythonProjects/CoreProjects

# Unit (always)
python -m pytest WebAxon/test/webaxon/automation/agents/find_element_inferencer/test_find_element_inferencer_unit.py -v

# Real-LLM (with ANTHROPIC_API_KEY)
python -m pytest WebAxon/test/webaxon/automation/agents/find_element_inferencer/test_find_element_inferencer_real.py -v -m integration
```
