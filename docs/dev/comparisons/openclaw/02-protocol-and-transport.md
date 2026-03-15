# Protocol and Transport Layer

This document compares how each system communicates with browsers and exposes its API.

## API Surface

### OpenClaw: HTTP API with Client SDK

OpenClaw's browser module exposes an HTTP API on a loopback-only port:

```
Browser Control Server (Express.js)
├── GET  /                    → Status
├── GET  /profiles            → List profiles
├── POST /start               → Start browser
├── POST /stop                → Stop browser
├── GET  /tabs                → List tabs
├── POST /tabs/open           → Open new tab
├── GET  /snapshot            → Page snapshot
├── POST /act                 → Execute action
├── POST /screenshot          → Capture screenshot
├── GET  /cookies             → Get cookies
├── POST /cookies/set         → Set cookies
└── ... (30+ endpoints)
```

**Transport modes**:

1. **HTTP mode**: Full HTTP request/response (for remote access via Gateway)
2. **Local mode**: In-process dispatch via `createBrowserRouteDispatcher()` — same Express routes, no HTTP overhead

```typescript
// Same API, different transports
fetchBrowserJson("/snapshot")                         // Local: in-process
fetchBrowserJson("http://127.0.0.1:18791/snapshot")  // Remote: HTTP
```

### WebAxon: Python Library with Queue-Based Service

WebAxon exposes a Python API with optional queue-based service layer:

```python
# Direct library usage
from webaxon.automation import WebDriver
driver = WebDriver(backend="playwright")
driver.navigate("https://example.com")
driver.click_element(element)

# Service mode (queue-based)
# User → Queue → Service → Agent Pipeline → Backend → Browser
```

**Transport modes**:

1. **Library mode**: Direct Python imports, synchronous calls
2. **Service mode**: File-based queues (`user_input/`, `agent_response/`, etc.)

```
_runtime/queues/<timestamp>/
├── user_input/        # Messages to agent
├── agent_response/    # Responses from agent
├── client_control/    # Debugger → Service
└── server_control/    # Service → Debugger
```

## Comparison

| Aspect | OpenClaw (HTTP) | WebAxon (Library/Queue) |
|--------|-----------------|-------------------------|
| **Primary interface** | REST API | Python classes |
| **Remote access** | Yes (via Gateway proxy) | No (co-located) |
| **Language binding** | Any (HTTP) | Python only |
| **Overhead** | HTTP per request (mitigated by local mode) | None (direct calls) |
| **Async model** | Express async handlers | Python async/await + threads |
| **State location** | Server process | In-memory + queue files |
| **Schema validation** | Zod (TypeScript) | Pydantic + dataclasses |

## Browser Protocol Layer

### OpenClaw: CDP + Playwright Dual Stack

OpenClaw uses **two protocol layers simultaneously**:

1. **Raw CDP** (`cdp.ts`, `cdp.helpers.ts`): Direct Chrome DevTools Protocol for low-level operations
2. **Playwright** (`pw-session.ts`, `pw-tools-core*.ts`): High-level automation API

```typescript
// CDP for accessibility tree
const ariaTree = await snapshotAria(cdpClient);

// Playwright for interactions
await page.click(locator);
```

**Why dual stack?**:
- CDP provides operations Playwright doesn't expose (raw accessibility trees, DOM traversal)
- Playwright provides reliability features (auto-waiting, locator resolution)
- Best of both worlds at the cost of complexity

### WebAxon: Selenium + Playwright Dual Backend

WebAxon uses **two backends behind a unified interface**:

```python
class BackendAdapter(ABC):
    """Unified interface for both backends."""
    
    @abstractmethod
    def click_element(self, element, ...) -> bool: ...
    
    @abstractmethod
    def input_text(self, element, text, ...) -> bool: ...

class SeleniumAdapter(BackendAdapter):
    """Selenium implementation."""
    ...

class PlaywrightAdapter(BackendAdapter):
    """Playwright implementation."""
    ...
```

**Why dual backend?**:
- Selenium for legacy compatibility and broader browser support
- Playwright for modern features and better debugging
- Runtime-switchable based on configuration

## Critical Comparison

| Aspect | OpenClaw (CDP + Playwright) | WebAxon (Selenium + Playwright) |
|--------|-----------------------------|---------------------------------|
| **Protocol access** | Full CDP (WebSocket) | Via backend abstraction |
| **Selenium support** | ❌ None | ✅ Full |
| **Backend switching** | N/A (both used together) | ✅ Runtime configurable |
| **Advanced CDP** | ✅ Network interception, profiling | ⚠️ Only via Playwright |
| **IE/Legacy browsers** | ❌ None | ✅ Via Selenium |
| **Mobile (iOS/Safari)** | ❌ None | ⚠️ Via Selenium (limited) |

## CDP Operations in OpenClaw

OpenClaw's direct CDP access enables:

```typescript
// Network interception
await page.route(pattern, handler);

// Accessibility tree
const tree = await cdpClient.send("Accessibility.getFullAXTree");

// JavaScript evaluation
const result = await cdpClient.send("Runtime.evaluate", { expression });

// Screenshots
const data = await cdpClient.send("Page.captureScreenshot");

// Performance profiling
await cdpClient.send("Profiler.start");
```

These operations are exposed through the HTTP API and client SDK.

## Selenium Operations in WebAxon

WebAxon's Selenium backend provides:

```python
# Traditional WebDriver
driver.find_element(By.CSS_SELECTOR, selector)
driver.execute_script(script)

# ActionChains for complex interactions
ActionChains(driver).move_to_element(element).click().perform()

# Explicit waits
WebDriverWait(driver, timeout).until(condition)
```

OpenClaw cannot do these — it's Chromium-only.

## Recommendation

**WebAxon's dual-backend abstraction is a genuine differentiator** that OpenClaw lacks. This enables:

1. Testing on browsers Playwright doesn't support (IE11, older browsers)
2. Compliance with organizations that mandate Selenium
3. Leveraging existing Selenium infrastructure

However, **OpenClaw's direct CDP access enables capabilities WebAxon lacks**:

1. Network interception and HAR recording
2. Performance profiling
3. Full accessibility tree access

Consider:
- Adding CDP access to WebAxon's Playwright backend
- Exposing network interception through the BackendAdapter interface
