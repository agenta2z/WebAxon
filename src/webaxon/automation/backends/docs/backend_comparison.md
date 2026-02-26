# Selenium vs Playwright Backend Comparison

This document provides a comprehensive comparison of the `SeleniumBackend` and `PlaywrightBackend` implementations.

## Overview

Both backends implement the `WebDriverBackend` abstract interface, providing a unified API for browser automation. While signatures are compatible, there are behavioral differences and unique advantages for each backend.

## Method Compatibility Summary

| Category | Total Methods | Fully Compatible | Minor Differences | Notes |
|----------|--------------|------------------|-------------------|-------|
| Lifecycle | 3 | 3 | 0 | Playwright has extra `stealth` param |
| Properties | 7 | 7 | 0 | All compatible |
| Navigation | 4 | 4 | 0 | All compatible |
| Element Resolution | 8 | 7 | 1 | Playwright has extra `timeout` param |
| HTML Retrieval | 3 | 3 | 0 | All compatible |
| Actions | 6 | 6 | 0 | All now compatible after Tasks 16-19 |
| Window/Viewport | 6 | 4 | 2 | Semantic difference in window size |
| Other | 7 | 7 | 0 | All compatible |

---

## Detailed Method Comparison

### Lifecycle Methods

| Method | Selenium | Playwright | Status |
|--------|----------|------------|--------|
| `initialize()` | `(driver_type, headless, ...)` | `(browser_type, headless, stealth, ...)` | Compatible (+stealth) |
| `quit()` | Closes browser | Closes browser + Playwright instance | Compatible |
| `close()` | Closes current tab | Closes current page | Compatible |

**Playwright Advantage:** `stealth=True` parameter enables stealth mode to bypass bot detection.

### Properties

| Property | Selenium | Playwright | Status |
|----------|----------|------------|--------|
| `current_url` | Returns URL string | Returns URL string | Compatible |
| `title` | Returns page title | Returns page title | Compatible |
| `window_handles` | List of handle strings | List of stable handle strings | Compatible |
| `current_window_handle` | Current handle string | Current handle string | Compatible |
| `raw_driver` | Selenium WebDriver | Playwright Page | Compatible |
| `driver_type` | WebAutomationDrivers enum | WebAutomationDrivers enum | Compatible |
| `switch_to` | SwitchTo object | PlaywrightSwitchToShim | Compatible |

### Navigation

| Method | Selenium | Playwright | Status |
|--------|----------|------------|--------|
| `get(url)` | Navigates to URL | Navigates to URL | Compatible |
| `open_url(url)` | Alias for get() | Alias for get() | Compatible |
| `wait_for_page_loading(timeout)` | Waits for page load | Waits for page load | Compatible |
| `get_body_html_from_url(url)` | Navigates + returns HTML | Navigates + returns HTML | Compatible |

### Element Resolution

| Method | Selenium | Playwright | Status |
|--------|----------|------------|--------|
| `find_element(by, value)` | Returns WebElement | `find_element(by, value, timeout=10000)` | Playwright has timeout |
| `find_elements(by, value)` | Returns list | Returns list | Compatible |
| `find_element_by_xpath(xpath)` | Returns WebElement | Returns Locator shim | Compatible |
| `find_elements_by_xpath(xpath)` | Returns list | Returns list | Compatible |
| `resolve_action_target(target)` | Resolves target | Resolves target | Compatible |
| `add_unique_index_to_elements(...)` | Adds `data-unique-index` | Adds `data-unique-index` | Compatible |
| `find_element_by_unique_index(idx)` | Finds by index | Finds by index | Compatible |
| `find_element_by_html(html, ...)` | Finds by HTML | Finds by HTML | Compatible |

**Playwright Advantage:** `timeout` parameter allows per-call timeout customization.

### HTML Retrieval

| Method | Selenium | Playwright | Status |
|--------|----------|------------|--------|
| `get_body_html()` | Returns body innerHTML | Returns body innerHTML | Compatible |
| `get_element_html(element)` | Returns outerHTML | Returns outerHTML | Compatible |
| `get_element_text(element)` | Returns text content | Returns text content | Compatible |

### Actions

| Method | Selenium | Playwright | Status |
|--------|----------|------------|--------|
| `input_text(...)` | Full params | Full params | Compatible |
| `click_element(...)` | Full new-tab strategies | Full new-tab strategies | Compatible |
| `scroll_element(...)` | With `relative_distance` | With `relative_distance` | Compatible |
| `center_element_in_view(...)` | Centers element | Centers element | Compatible |
| `execute_single_action(...)` | Executes single action | Executes single action | Compatible |
| `execute_actions(...)` | Full implementation | Full implementation | Compatible |

### Window/Viewport

| Method | Selenium | Playwright | Status |
|--------|----------|------------|--------|
| `switch_to_window(handle)` | Switches window | Switches page | Compatible |
| `get_viewport_size()` | Returns viewport | Returns viewport | Compatible |
| `set_viewport_size(w, h)` | Sets viewport | Sets viewport | Compatible |
| `get_window_size()` | **Window size** | **Viewport size** | Different semantics |
| `set_window_size(w, h)` | **Window size** | **Viewport size** | Different semantics |
| `set_zoom(factor)` | Sets zoom | Sets zoom | Compatible |
| `get_zoom()` | Gets zoom | Gets zoom | Compatible |

**Important:** In Playwright, `get_window_size()` and `set_window_size()` operate on the viewport, not the actual browser window. This is because Playwright's API focuses on viewport control.

### Other Methods

| Method | Selenium | Playwright | Status |
|--------|----------|------------|--------|
| `solve_scrollable_child(...)` | 5 strategies | 5 strategies | Compatible |
| `capture_full_page_screenshot(...)` | Full page capture | Full page capture | Compatible |
| `get_element_dimension_info(...)` | Returns dimensions | Returns dimensions | Compatible |
| `get_element_scrollability(...)` | Returns scrollability | Returns scrollability | Compatible |
| `is_element_stale(element)` | Checks staleness | Checks staleness | Compatible |
| `get_cookies()` | Returns cookies | Returns cookies | Compatible |
| `get_user_agent()` | Returns user agent | Returns user agent | Compatible |

---

## Feature Comparison

### `input_text()` Comparison

See [input_text_comparison.md](input_text_comparison.md) for detailed comparison.

**Key Differences:**
| Aspect | Selenium | Playwright |
|--------|----------|------------|
| Non-BMP (emoji) handling | Must REMOVE (ChromeDriver limitation) | Can KEEP (native support) |
| Delay implementation | Manual `random_sleep()` loop | Native `delay=ms` parameter |
| JavaScript events | Manual `dispatchEvent()` | `fill()` handles automatically |

### `click_element()` New-Tab Strategies

Both backends support the same strategies in `new_tab_strategy_order`:

| Strategy | Description | Selenium | Playwright |
|----------|-------------|----------|------------|
| `URL_EXTRACT` | Extract href and open via JavaScript | Yes | Yes |
| `TARGET_BLANK` | Set `target="_blank"` attribute + click | Yes | Yes |
| `MODIFIER_KEY` | Ctrl+Click (Cmd+Click on Mac) | Yes | Yes |
| `CDP_CREATE_TARGET` | Chrome DevTools Protocol | Yes | Yes |
| `MIDDLE_CLICK` | Middle mouse button click | Yes | Yes |

**OpenInNewTabMode Options:**
- `ENABLED` - Always try to open in new tab
- `ENABLED_FOR_INTERACTABLE` - Only for interactable elements
- `ENABLED_FOR_NON_SAME_PAGE_INTERACTION` - Skip for same-page anchors (#)
- `DISABLED` - Never open in new tab

### `scroll_element()` Options

Both backends support:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `direction` | 'Up', 'Down', 'Left', 'Right' | 'Down' |
| `distance` | 'Small', 'Medium', 'Large', 'Half', 'Full', or int | 'Large' |
| `implementation` | 'javascript' | 'javascript' |
| `relative_distance` | Use percentage of element size | False |
| `try_solve_scrollable_child` | Find scrollable child first | False |

**Distance Values (when `relative_distance=True`):**
| Distance | Percentage |
|----------|------------|
| Small | 30% |
| Medium | 60% |
| Large | 90% |
| Half | 50% |
| Full | 100% |

### `solve_scrollable_child()` Strategies

Both backends support all 5 strategies:

| Strategy | Description |
|----------|-------------|
| `first_scrollable` | BFS, return first scrollable found |
| `first_largest_scrollable` | BFS, at each level return largest scrollable (default) |
| `deepest_scrollable` | DFS, return most deeply nested scrollable |
| `largest_scrollable` | Return element with largest scrollable content |
| `largest_scrollable_early_stop` | BFS with early termination on large scrollable |

---

## Backend-Specific Advantages

### Playwright Advantages

1. **Native Emoji Support** - Can use emoji in `send_keys` mode without removal
2. **Stealth Mode** - Built-in `stealth=True` parameter to bypass bot detection
3. **Per-Call Timeout** - `find_element(by, value, timeout=ms)` allows per-call timeout
4. **Auto-Waiting** - Locators automatically wait for elements
5. **Auto-Retry** - Locators auto-retry on stale element references
6. **Cleaner Delay API** - Native `delay=ms` parameter in `type()` method
7. **Automatic Events** - `fill()` triggers input/change events automatically

### Selenium Advantages

1. **True Window Size** - `get_window_size()` returns actual browser window size
2. **Mature Ecosystem** - More third-party tools and documentation
3. **WebDriver Protocol** - Standard W3C WebDriver protocol
4. **Browser Compatibility** - Supports more browser configurations

---

## Migration Guide

### From Selenium to Playwright

1. **No code changes needed** - All method signatures are compatible
2. **Emoji support** - You can now use emoji in `send_keys` mode
3. **Window size** - Be aware that `get_window_size()` returns viewport, not window
4. **Stealth mode** - Add `stealth=True` to `initialize()` to bypass bot detection

```python
# Selenium
driver = WebDriver(driver_type=WebAutomationDrivers.Chrome)

# Playwright
from webaxon.automation.backends import PlaywrightBackend

backend = PlaywrightBackend()
backend.initialize(browser_type='chromium', stealth=True)
driver = WebDriver(backend=backend)
```

### From Playwright to Selenium

1. **Emoji handling** - Use `implementation='javascript'` if text contains emoji
2. **Newlines** - In `send_keys` mode, newlines trigger Enter key presses
3. **Window size** - `get_window_size()` returns actual window size (including chrome)

```python
# Playwright text with emoji works fine
backend.input_text(element, "Hello! ")

# Selenium - use javascript implementation for emoji
backend.input_text(element, "Hello! ", implementation='javascript')
```

---

## Implementation Files

| File | Description |
|------|-------------|
| `backends/selenium/selenium_backend.py` | SeleniumBackend implementation |
| `backends/playwright/playwright_backend.py` | PlaywrightBackend implementation |
| `backends/playwright/shims.py` | Playwright compatibility shims |
| `backends/shared/text_sanitization.py` | Shared text sanitization utilities |
| `backends/shared/click_types.py` | Shared click strategy types |
| `backends/abstract.py` | WebDriverBackend abstract base class |

---

## Version History

| Version | Changes |
|---------|---------|
| 1.0 | Initial Playwright backend with basic compatibility |
| 1.1 | Added `input_text()` full compatibility |
| 1.2 | Added `click_element()` new-tab strategies (Task 16) |
| 1.3 | Added `scroll_element()` relative_distance (Task 17) |
| 1.4 | Added `solve_scrollable_child()` full strategies (Task 18) |
| 1.5 | Added `execute_actions()` full implementation (Task 19) |
