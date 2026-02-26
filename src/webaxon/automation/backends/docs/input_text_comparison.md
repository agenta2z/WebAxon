# Input Text: Selenium vs Playwright Comparison

This document compares the `input_text` method implementations between Selenium and Playwright backends.

## Signature Comparison

Both backends now have fully compatible signatures:

| Parameter | Selenium Default | Playwright Default | Compatible? |
|-----------|-----------------|-------------------|-------------|
| `element` | required | required | ✅ Yes |
| `text` | required | required | ✅ Yes |
| `clear_content` | `False` | `False` | ✅ Yes |
| `implementation` | `'auto'` | `'auto'` | ✅ Yes |
| `default_implementation` | `'send_keys'` | `'send_keys'` | ✅ Yes |
| `fast_implementation` | `'send_keys_fast'` | `'send_keys_fast'` | ✅ Yes |
| `fast_threshold` | `20` | `20` | ✅ Yes |
| `min_delay` | `0.1` | `0.1` | ✅ Yes |
| `max_delay` | `1.0` | `1.0` | ✅ Yes |
| `sanitize` | `True` | `True` | ✅ Yes |
| `auto_sanitization` | `True` | `True` | ✅ Yes |
| `non_bmp_handling` | `REMOVE` | `REMOVE` | ✅ Yes |
| `newline_handling` | `SPACE` | `SPACE` | ✅ Yes |
| `whitespace_handling` | `NORMALIZE` | `NORMALIZE` | ✅ Yes |

## Implementation Strategy Mapping

| Strategy | Selenium | Playwright | Speed |
|----------|----------|------------|-------|
| `'send_keys'` | `send_keys_with_random_delay()` - char-by-char loop | `locator.type(text, delay=ms)` - native delay support | Slowest (human-like) |
| `'send_keys_fast'` | `element.send_keys(text)` - entire string | `locator.type(text, delay=0)` | Medium |
| `'javascript'` | `execute_script()` + manual event dispatch | `locator.fill(text)` - native | Fastest |
| `'auto'` | `len(text) <= 20` → default, else → fast | Same logic | Same |

## Auto Mode Logic

Both backends use the same auto mode logic:

```python
if implementation == 'auto':
    if len(text) <= fast_threshold:  # default: 20
        implementation = default_implementation  # default: 'send_keys'
    else:
        implementation = fast_implementation  # default: 'send_keys_fast'
```

## Auto-Sanitization Behavior

When `auto_sanitization=True`, the backends apply different sanitization based on the implementation:

### Selenium

| Implementation | Non-BMP | Newline | Whitespace |
|----------------|---------|---------|------------|
| `send_keys` / `send_keys_fast` | `REMOVE` | `SPACE` | `NORMALIZE` |
| `javascript` | `KEEP` | `KEEP` | `KEEP` |

**Reason**: ChromeDriver's `send_keys()` cannot handle non-BMP characters (emoji, etc.) and treats newlines as Enter key presses.

### Playwright

| Implementation | Non-BMP | Newline | Whitespace |
|----------------|---------|---------|------------|
| `send_keys` / `send_keys_fast` | `KEEP` | `SPACE` | `NORMALIZE` |
| `javascript` | `KEEP` | `KEEP` | `KEEP` |

**Reason**: Playwright's `type()` handles non-BMP characters natively, so we can keep them. Newlines are still converted to spaces for single-line inputs.

## Key Behavioral Differences

| Aspect | Selenium | Playwright | Winner |
|--------|----------|------------|--------|
| **Non-BMP (emoji) handling** | Must REMOVE for `send_keys` (ChromeDriver limitation) | Can KEEP (native support) | 🏆 Playwright |
| **Delay implementation** | Manual `random_sleep()` loop per char | Native `delay=ms` parameter | 🏆 Playwright (cleaner) |
| **JavaScript events** | Manual `dispatchEvent()` for input/change/blur | `fill()` handles automatically | 🏆 Playwright |
| **Append mode** | `send_keys()` naturally appends | `fill()` clears first, need workaround | 🏆 Selenium |
| **Clear behavior** | `element.clear()` | `locator.clear()` or `fill()` | Tie |

## Internal Implementation Details

| Feature | Selenium | Playwright |
|---------|----------|------------|
| Click before input | Yes (`element.click()`) | No (handled by locator) |
| Events triggered | Manual: `input`, `change`, `blur` | Automatic by `fill()`/`type()` |
| Error on non-interactable | Warning + return | Playwright throws |
| Stale element handling | Manual check needed | Auto-retry by locator |

## Usage Examples

### Basic Usage (Same for Both)

```python
# Short text - uses send_keys with delays (human-like)
backend.input_text(element, "hello")

# Long text - automatically uses send_keys_fast
backend.input_text(element, "this is a very long text that exceeds the threshold")

# Clear and replace
backend.input_text(element, "new text", clear_content=True)
```

### Force Specific Implementation

```python
# Force JavaScript (fastest)
backend.input_text(element, "text", implementation='javascript')

# Force slow typing with custom delays
backend.input_text(element, "text", implementation='send_keys', min_delay=0.05, max_delay=0.15)

# Force fast send_keys (no delays)
backend.input_text(element, "text", implementation='send_keys_fast')
```

### Custom Auto Mode Thresholds

```python
# Use JavaScript for text longer than 10 chars
backend.input_text(
    element,
    "medium text",
    fast_threshold=10,
    fast_implementation='javascript'
)
```

### Disable Sanitization

```python
# Keep text exactly as-is (may cause errors with special chars in Selenium)
backend.input_text(element, "raw text\nwith newlines", sanitize=False)

# Custom sanitization options
backend.input_text(
    element,
    "text with emoji 😀",
    auto_sanitization=False,
    non_bmp_handling=NonBMPHandling.TRANSLITERATE,  # Convert emoji to :grinning:
    newline_handling=NewlineHandling.KEEP
)
```

## Text Sanitization Options

### NonBMPHandling

| Value | Description |
|-------|-------------|
| `KEEP` | Keep non-BMP characters as-is (safe in Playwright, unsafe in Selenium send_keys) |
| `REMOVE` | Remove non-BMP characters entirely |
| `REPLACE` | Replace with U+FFFD (replacement character) |
| `TRANSLITERATE` | Convert emoji to text (e.g., 😀 → `:grinning:`) |
| `RAISE` | Raise an exception if non-BMP found |

### NewlineHandling

| Value | Description |
|-------|-------------|
| `KEEP` | Keep newlines as-is |
| `SPACE` | Replace with single space |
| `REMOVE` | Remove entirely |
| `NORMALIZE` | Normalize to `\n` only (remove `\r`) |

### WhitespaceHandling

| Value | Description |
|-------|-------------|
| `KEEP` | Keep as-is |
| `NORMALIZE` | Collapse multiple spaces to single |
| `STRIP` | Strip leading/trailing only |
| `FULL` | Both normalize and strip |

## Performance Comparison

Approximate timing for 100 characters:

| Implementation | Selenium | Playwright |
|----------------|----------|------------|
| `send_keys` (default delays 0.1-1s) | ~50-100s | ~50-100s |
| `send_keys_fast` | ~0.1s | ~0.1s |
| `javascript` | ~0.01s | ~0.01s |

## Migration Notes

### From Selenium to Playwright

1. **No code changes needed** - signatures are compatible
2. **Emoji support** - Playwright handles emoji natively, so you can use them in `send_keys` mode
3. **Events** - Playwright's `fill()` triggers events automatically, no need for manual dispatch

### From Playwright to Selenium

1. **Emoji handling** - If your text contains emoji, use `implementation='javascript'` or they will be stripped
2. **Newlines** - In `send_keys` mode, newlines trigger Enter key presses in Selenium
