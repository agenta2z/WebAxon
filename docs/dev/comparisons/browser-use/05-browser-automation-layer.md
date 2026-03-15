# Browser Automation Layer: Browser-Use vs WebAxon

**Date:** 2026-03-12

---

## 1. Overview

The browser automation layer is responsible for launching browsers, managing sessions, executing actions on web pages, and handling the lifecycle of browser instances. This is where the "rubber meets the road" — all the LLM reasoning ultimately results in calls to this layer.

Browser-use is built on a **CDP-first architecture** with a custom client library (`cdp_use`) that communicates directly with Chrome DevTools Protocol. WebAxon uses a **backend-agnostic architecture** with a `BackendAdapter` ABC that supports both Selenium WebDriver and Playwright as interchangeable backends.

---

## 2. Browser Connection and Session Management

### Browser-Use: CDP Sessions with Cloud Support

Browser-use manages browser sessions through `BrowserSession`:

```python
# Simplified from browser/session.py
class BrowserSession:
    def __init__(self, browser_profile: BrowserProfile):
        self.event_bus = EventBus()
        self.watchdogs = []
        self._cdp_session = None
        self._browser_context = None

    async def start(self):
        if self.browser_profile.cloud:
            # Connect to cloud-hosted browser via WebSocket
            self._cdp_session = await connect_cdp(
                ws_url=cloud_service.create_session()
            )
        else:
            # Launch local Chromium via CDP
            self._cdp_session = await launch_browser(
                args=self.browser_profile.launch_args,
                headless=self.browser_profile.headless,
            )
        
        # Initialize watchdogs
        for watchdog_cls in self._get_watchdog_classes():
            watchdog = watchdog_cls(self._cdp_session, self.event_bus)
            await watchdog.start()
            self.watchdogs.append(watchdog)
```

**Key features:**

1. **CDP-native:** All browser communication goes through Chrome DevTools Protocol. This provides access to low-level browser internals that higher-level APIs (Selenium, Playwright) abstract away: network interception, console logs, performance metrics, accessibility tree, DOM snapshots with paint order.

2. **Cloud-native sessions:** One-line switch from local to cloud:
   ```python
   BrowserProfile(cloud=CloudConfig(api_key="..."))
   ```
   Cloud sessions provide: remote browser execution, video recording, HAR capture, session persistence, and geographic distribution.

3. **Session persistence:** Browser state (cookies, localStorage, sessionStorage) can be saved to disk and restored:
   ```python
   BrowserProfile(
       storage_state="./saved_state.json",
       save_storage_state_on_close=True,
   )
   ```

4. **Multi-tab management:** The session tracks all open tabs and can switch between them. New tabs opened by page actions are automatically detected via CDP events.

5. **Recording:** Built-in video recording of browser sessions via the `RecordingWatchdog`, useful for debugging and audit trails.

6. **HAR logging:** Network traffic can be captured in HAR format via the `HARRecordingWatchdog`.

### WebAxon: BackendAdapter ABC

WebAxon manages browser sessions through the `WebDriver` class, which delegates to a `BackendAdapter`:

```python
# Simplified from automation/backends/base.py
class BackendAdapter(ABC):
    @abstractmethod
    def launch(self, config: BrowserConfig) -> None: ...
    
    @abstractmethod
    def navigate(self, url: str) -> None: ...
    
    @abstractmethod
    def get_page_html(self) -> str: ...
    
    @abstractmethod
    def click_element(self, xpath: str) -> None: ...
    
    @abstractmethod
    def type_text(self, xpath: str, text: str) -> None: ...
    
    @abstractmethod
    def get_screenshot(self) -> bytes: ...
    
    @abstractmethod
    def execute_javascript(self, script: str) -> Any: ...
    
    @abstractmethod
    def wait_for_element(self, xpath: str, timeout: float) -> bool: ...
    
    @abstractmethod
    def get_current_url(self) -> str: ...
    
    @abstractmethod
    def get_window_handles(self) -> list[str]: ...
    
    @abstractmethod
    def switch_to_window(self, handle: str) -> None: ...
    
    # ... ~40+ abstract methods total
```

Two implementations exist:

1. **`SeleniumBackend`** — Wraps Selenium WebDriver with ChromeDriver/GeckoDriver. Communicates via WebDriver protocol (W3C standard).

2. **`PlaywrightBackend`** — Wraps Playwright's synchronous API. Communicates via CDP (Chromium) or browser-specific protocols (Firefox, WebKit).

**Key features:**

1. **True backend portability:** The same WebAxon code runs on Selenium or Playwright:
   ```python
   # Selenium
   driver = WebDriver(backend=SeleniumBackend(BrowserConfig(browser="chrome")))
   
   # Playwright
   driver = WebDriver(backend=PlaywrightBackend(BrowserConfig(browser="chromium")))
   ```

2. **Multi-window tracking:** The `WebDriver` maintains a `windows` dict mapping window handles to `WindowInfo` objects, each with its own `ContentMemory`:
   ```python
   class WindowInfo:
       handle: str
       url: str
       title: str
       content_memory: ContentMemory
       last_action: ActionResult | None
   ```

3. **Monitor system:** The `create_monitor()` factory creates `Monitor` objects that asynchronously watch for conditions in browser tabs:
   ```python
   monitor = driver.create_monitor(
       window_handle=handle,
       conditions=[
           ElementPresent("//div[@class='success']"),
           TextChanged("//span[@id='status']"),
           CustomCondition(lambda html: "error" in html),
       ],
       confirmation_time=2.0,  # debounce
   )
   result = monitor.wait(timeout=30)
   ```

4. **Action execution pipeline:** The `execute_action()` method handles the full lifecycle:
   ```python
   def execute_action(self, action_type, target, args, config):
       # 1. Resolve target (__id__ -> XPath)
       xpath = self._resolve_target(target)
       
       # 2. Wait for element if configured
       if config.wait_for_target:
           self.backend.wait_for_element(xpath, config.timeout)
       
       # 3. Execute the action
       result = self._dispatch_action(action_type, xpath, args)
       
       # 4. Wait for page to stabilize
       if config.wait_after_action:
           self._wait_for_stability()
       
       # 5. Capture post-action state
       new_html = self.get_body_html()
       self._update_content_memory(new_html)
       
       return ActionResult(
           success=True,
           html_before=old_html,
           html_after=new_html,
           action_skipped=False,
       )
   ```

### Critical Comparison

| Aspect | Browser-Use (CDP) | WebAxon (BackendAdapter) |
|--------|-------------------|------------------------|
| **Protocol** | CDP only (Chromium) | WebDriver (Selenium) or CDP (Playwright) |
| **Browser support** | Chromium-based only | Chrome, Firefox, WebKit, Edge |
| **Low-level access** | Full CDP access (AX tree, network, performance) | Limited to backend API surface |
| **Cloud browsers** | Built-in cloud session support | Not supported |
| **Recording** | Video + HAR recording | Not supported |
| **Session persistence** | Built-in save/restore | Not built-in |
| **Multi-tab** | CDP event-driven detection | Handle-based tracking |
| **Backend swapping** | Not possible (CDP-only) | Swap Selenium/Playwright freely |
| **Cross-browser testing** | No (Chromium only) | Yes (Chrome, Firefox, WebKit) |

**Verdict:** Browser-use's CDP-native approach provides deeper browser access and richer features (cloud, recording, HAR). WebAxon's backend abstraction provides portability and cross-browser support. The right choice depends on whether you need deep browser integration (browser-use) or browser-engine flexibility (WebAxon).

---

## 3. Action Execution

### Browser-Use: Event-Bus Dispatched Actions

Actions in browser-use flow through the event bus:

```
LLM Response → parse AgentOutput → for each action:
    Registry.get_action(action_name) → action_handler(params)
        → ActorService.element_action(index, action_type)
            → CDP command (click, type, etc.)
                → EventBus.emit(ActionCompletedEvent)
                    → Watchdogs react
```

**Available actions** (from `tools/registry/`):

| Category | Actions |
|----------|---------|
| **Navigation** | `go_to_url`, `go_back`, `go_forward`, `refresh` |
| **Element interaction** | `click_element`, `input_text`, `select_option`, `check_checkbox` |
| **Scrolling** | `scroll_down`, `scroll_up`, `scroll_to_element` |
| **Tab management** | `switch_tab`, `open_tab`, `close_tab` |
| **Data extraction** | `extract_page_content`, `get_dropdown_options` |
| **Keyboard** | `send_keys`, `key_combination` |
| **File** | `upload_file` |
| **Completion** | `done` |
| **Waiting** | `wait` |

Actions are registered via decorators in the registry:

```python
@registry.action("click_element", "Click an element by index")
async def click_element(index: int, browser_session: BrowserSession):
    element = await browser_session.get_element_by_index(index)
    await browser_session.actor.click(element)
```

**New actions can be added** by registering them in the registry — either in code or via the skills system.

### WebAxon: Type-Dispatched Actions

Actions in WebAxon flow through the `WebDriver.execute_action()` dispatch:

```
LLM Response → parse XML → ActionType + Target + Args
    → WebDriver.execute_action(type, target, args)
        → _resolve_target(target) → XPath
        → _dispatch_action(type, xpath, args)
            → backend.click_element(xpath) / backend.type_text(xpath, text) / ...
        → _update_content_memory(new_html)
```

**Available action types** (from `schema/webagent_action.py`):

| Category | Actions |
|----------|---------|
| **Navigation** | `Navigation.GoTo`, `Navigation.GoBack`, `Navigation.Refresh` |
| **Element interaction** | `ElementInteraction.Click`, `ElementInteraction.Type`, `ElementInteraction.Select` |
| **Composite** | `ElementInteraction.InputAndSubmit`, `ElementInteraction.ClearAndType` |
| **Scrolling** | `Scroll.Down`, `Scroll.Up`, `Scroll.ToElement` |
| **Tab management** | `Tab.Switch`, `Tab.Open`, `Tab.Close` |
| **Data extraction** | `Extract.Text`, `Extract.Attribute`, `Extract.TableData` |
| **Waiting** | `Wait.ForElement`, `Wait.ForText`, `Wait.Duration` |
| **Completion** | `Task.Complete`, `Task.Fail` |

Actions are defined as string enum values in `WebAgentAction`:

```python
class WebAgentAction(str, Enum):
    CLICK = "ElementInteraction.Click"
    TYPE = "ElementInteraction.Type"
    SELECT = "ElementInteraction.Select"
    INPUT_AND_SUBMIT = "ElementInteraction.InputAndSubmit"
    # ...
```

**New actions are added** by extending the enum, adding an entry to `ActionMetadataRegistry`, and implementing the handler in `WebDriver._dispatch_action()`.

### Critical Comparison

| Aspect | Browser-Use | WebAxon |
|--------|------------|---------|
| **Dispatch mechanism** | Registry + event bus | Enum + dispatch method |
| **Action granularity** | Atomic (one operation per action) | Mixed (atomic + composite like `InputAndSubmit`) |
| **Dynamic registration** | Yes (decorator-based) | No (enum + registry update) |
| **Post-action hooks** | Watchdog events | ContentMemory update |
| **Error recovery** | Watchdog-triggered | `execute_with_retry` wrapper |
| **Target resolution** | Index → element node | `__id__` → XPath → element |
| **Wait integration** | Separate `wait` action | Configurable per-action wait |

**Verdict:** Browser-use's event-bus dispatch is more extensible (new actions can be added without modifying core code). WebAxon's composite actions (like `InputAndSubmit`) reduce LLM round-trips for common patterns. The ideal would be browser-use's extensibility model with WebAxon's composite action concept.

---

## 4. Watchdog System (Browser-Use Exclusive)

This is one of browser-use's most architecturally distinctive features and deserves special attention.

### Architecture

```
BaseWatchdog
    |
    +-- CrashWatchdog           (browser/tab crash recovery)
    +-- CaptchaWatchdog         (CAPTCHA detection and delegation)
    +-- PopupsWatchdog          (cookie banners, modals, overlays)
    +-- DownloadsWatchdog       (file download monitoring)
    +-- DOMWatchdog             (DOM staleness detection)
    +-- SecurityWatchdog        (security warnings, cert errors)
    +-- StorageStateWatchdog    (cookie/storage persistence)
    +-- ScreenshotWatchdog      (screenshot capture management)
    +-- HARRecordingWatchdog    (HTTP traffic recording)
    +-- PermissionsWatchdog     (browser permission prompts)
    +-- AboutBlankWatchdog      (blank page recovery)
    +-- DefaultActionWatchdog   (action dispatch coordination)
    +-- LocalBrowserWatchdog    (local browser lifecycle)
    +-- RecordingWatchdog       (video recording management)
    +-- ... (extensible via custom watchdogs)
```

### How it Works

```python
# Simplified from browser/watchdog_base.py
class BaseWatchdog:
    def __init__(self, cdp_session, event_bus):
        self.cdp = cdp_session
        self.bus = event_bus
        self._register_handlers()
    
    def _register_handlers(self):
        # Auto-discover methods named on_EventType
        for name in dir(self):
            if name.startswith("on_"):
                event_type = name[3:]  # "on_NavigationComplete" -> "NavigationComplete"
                handler = getattr(self, name)
                self.bus.subscribe(event_type, handler)
    
    async def _safe_handle(self, handler, event):
        # Circuit breaker: skip if CDP is dead
        if not self.cdp.is_connected:
            return
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Watchdog handler failed: {e}")
            # Watchdog errors are logged but never crash the agent
```

**Example: CaptchaWatchdog**

```python
class CaptchaWatchdog(BaseWatchdog):
    async def on_NavigationComplete(self, event):
        # Check if the new page contains a CAPTCHA
        if await self._detect_captcha():
            # Emit event for the agent to handle
            await self.bus.emit(CaptchaDetectedEvent(
                url=event.url,
                captcha_type=self._identify_type(),
            ))
    
    async def _detect_captcha(self):
        # Check for reCAPTCHA, hCaptcha, Cloudflare, etc.
        indicators = await self.cdp.evaluate("""
            document.querySelector('[class*="captcha"]') !== null ||
            document.querySelector('iframe[src*="recaptcha"]') !== null ||
            document.querySelector('#challenge-form') !== null
        """)
        return indicators
```

### What WebAxon Would Need to Replicate This

WebAxon currently has no equivalent. To add a similar system, it would need:

1. **An event bus** — Either `bubus` or a simpler pub/sub implementation
2. **A watchdog base class** — With auto-registration and circuit breaker
3. **Backend-specific event sources** — Selenium and Playwright have different event APIs
4. **At minimum these watchdogs:**
   - Crash recovery (critical for long-running automations)
   - Popup dismissal (cookie banners are ubiquitous)
   - Download monitoring (if file downloads are needed)
   - Page stability detection (replace the current `_wait_for_stability` heuristic)

The `Monitor` system in WebAxon is a partial substitute (it can watch for conditions), but it is pull-based (you must poll) rather than push-based (watchdogs react to events). The push-based model is more efficient and more robust.

---

## 5. Screenshot and Vision Capabilities

### Browser-Use: First-Class Vision

Browser-use captures screenshots at each step and includes them in the LLM prompt:

```python
# From browser/session.py
async def take_screenshot(self, full_page=False):
    screenshot_bytes = await self.cdp.send("Page.captureScreenshot", {
        "format": "png",
        "quality": 80,
        "fromSurface": True,
        "captureBeyondViewport": full_page,
    })
    return base64.b64decode(screenshot_bytes["data"])
```

Screenshots can optionally include **bounding box overlays** — colored rectangles drawn around interactive elements with their index numbers, helping the LLM associate visual elements with their indices.

The system also supports **element highlighting** — when an element is about to be acted upon, it is visually highlighted in the browser for recording/debugging purposes.

### WebAxon: No Vision Support

WebAxon's `BackendAdapter` defines a `get_screenshot()` abstract method, but it is used only for debugging/recording purposes and is **never included in LLM prompts**. The LLM operates entirely on cleaned HTML text.

### Impact

For tasks that require understanding:
- **Visual layout** (where is the button relative to the form?)
- **Images and charts** (what does this graph show?)
- **CSS-rendered content** (color-coded status indicators)
- **Canvas elements** (interactive visualizations)
- **PDF viewers** (embedded documents)

Browser-use has a fundamental advantage. WebAxon is blind to all of these.

However, for tasks that involve:
- **Dense text content** (reading long articles, extracting structured data)
- **Complex forms** (many fields with validation rules)
- **Table data** (extracting from HTML tables)

Clean HTML is more token-efficient and precise than screenshots. The LLM does not need to "read" text from an image when it can get the text directly.

**Recommendation:** WebAxon should add optional screenshot support that is included in the LLM prompt when visual context is needed, while keeping HTML as the primary representation for text-heavy tasks. A hybrid approach would combine the strengths of both systems.

---

**Next:** [06 -- Extensibility and Ecosystem](./06-extensibility-and-ecosystem.md)
