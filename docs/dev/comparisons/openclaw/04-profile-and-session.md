# Profile and Session Management

Browser profiles and sessions determine isolation, state persistence, and multi-browser capabilities.

## OpenClaw: Multi-Profile System

OpenClaw has a sophisticated profile system supporting three profile types:

### Profile Types

```typescript
type ProfileType = "managed" | "remote" | "extension";
```

**1. Managed Profile (default: "openclaw")**

OpenClaw spawns and controls a local Chrome process:

```
~/.openclaw/browser/openclaw/
├── user-data/           # Chrome user data directory
│   ├── Default/         # Profile folder
│   │   ├── Cookies
│   │   ├── Local Storage/
│   │   └── ...
│   └── ...
└── config.json          # Profile configuration
```

- Dedicated user-data directory (complete isolation from personal browser)
- Unique CDP port from range 18800-18899
- Profile decoration (name + accent color in Chrome UI)
- Cookies, storage, history isolated

**2. Remote Profile**

Connect to an existing Chromium instance via CDP URL:

```json
{
  "name": "remote",
  "driver": "remote",
  "cdpUrl": "http://10.0.0.42:9222"
}
```

Use cases:
- Browserless.io or similar cloud browsers
- Pre-configured browser on another machine
- Shared browser for multiple agents

**3. Extension Profile (default: "chrome")**

Control the user's existing Chrome via extension relay:

```json
{
  "name": "chrome",
  "driver": "extension",
  "cdpUrl": "http://127.0.0.1:18792"
}
```

The Chrome extension attaches to tabs the user explicitly allows, enabling:
- Access to existing login sessions
- Real browser fingerprint (less bot detection)
- User's extensions and settings

### Profile Configuration

```json
// ~/.openclaw/openclaw.json
{
  "browser": {
    "profiles": {
      "openclaw": {
        "cdpPort": 18800,
        "color": "#FF4500"
      },
      "work": {
        "cdpPort": 18801,
        "color": "#0066CC"
      }
    },
    "defaultProfile": "openclaw"
  }
}
```

### Session State

Each profile tracks runtime state:

```typescript
interface ProfileRuntimeState {
  profile: ResolvedBrowserProfile;
  running: RunningChrome | null;
  lastTargetId?: string;  // Sticky tab selection
}
```

The `lastTargetId` enables "sticky" tab targeting — subsequent actions target the same tab without re-specifying.

## WebAxon: Chrome Profiles via browser_utils

WebAxon has simpler profile support via `browser_utils/chrome/`:

### Chrome Profile Discovery

```python
# chrome_profiles.py
class ChromeProfileManager:
    def list_profiles(self) -> List[ChromeProfile]:
        """Discover Chrome profiles in user data directory."""
        ...
    
    def get_profile_path(self, profile_name: str) -> Path:
        """Get path to specific profile's user data."""
        ...
```

### Profile Usage

```python
# In WebDriver initialization
driver = WebDriver(
    backend="playwright",
    user_data_dir="/path/to/profile",
    ...
)
```

### Session Management

WebAxon's session system is focused on agent state, not browser state:

```python
class AgentSession:
    session_id: str
    agent: PromptBasedActionPlanningAgent
    agent_thread: Thread
    interactive: QueueInteractive
    # ... agent-focused state
```

Browser state (cookies, storage) is managed by the browser itself, not explicitly by WebAxon.

## Comparison

| Aspect | OpenClaw | WebAxon |
|--------|----------|---------|
| **Profile types** | 3 (managed, remote, extension) | 1 (local only) |
| **Remote browsers** | ✅ CDP URL config | ❌ Not supported |
| **Extension relay** | ✅ Control user's Chrome | ❌ Not supported |
| **Profile isolation** | ✅ Dedicated user-data dirs | ⚠️ Manual path config |
| **Visual decoration** | ✅ Profile name + color | ❌ None |
| **Port management** | ✅ Automated allocation | ❌ Manual |
| **Sticky tab targeting** | ✅ lastTargetId tracking | ❌ Manual |
| **Session state focus** | Browser state | Agent state |

## Profile Scenarios

### Scenario 1: Isolated Automation

*Run automation in a clean, isolated browser.*

**OpenClaw**: Use default `openclaw` profile — fully isolated, no personal data.

**WebAxon**: Manually specify a dedicated `user_data_dir` path.

### Scenario 2: Use Existing Login

*Leverage existing authentication from user's browser.*

**OpenClaw**: Use `chrome` profile via extension relay. User attaches tabs explicitly.

**WebAxon**: Not directly supported. Must copy cookies/storage from existing browser.

### Scenario 3: Cloud Browser

*Connect to a cloud browser service like Browserless.*

**OpenClaw**: Create remote profile with `cdpUrl` pointing to cloud endpoint.

**WebAxon**: Not supported without custom code.

### Scenario 4: Multiple Concurrent Browsers

*Run multiple browser instances simultaneously.*

**OpenClaw**: Create multiple profiles, each gets unique CDP port. Switch with `?profile=` query param.

**WebAxon**: Create multiple WebDriver instances manually.

## Extension Relay Deep Dive

OpenClaw's extension relay is a unique capability worth understanding:

```
┌─────────────────────┐     ┌─────────────────────┐
│  Chrome Extension   │     │   Relay Server      │
│  (Manifest V3)      │◄───►│   127.0.0.1:18792   │
│  User clicks icon   │     │   Bridges to control│
│  to attach tab      │     │   server            │
└─────────────────────┘     └─────────────────────┘
          │                           │
          ▼                           ▼
    User's Chrome               Control Server
    (existing sessions)         (HTTP API)
```

**Security model**:
- User must explicitly click extension icon on each tab
- Tab attachment requires gateway token auth
- Only attached tabs are visible to the agent

**Use cases**:
- Testing logged-in workflows without credential storage
- Debugging in user's actual browser environment
- Accessing sites with aggressive bot detection

WebAxon has **nothing equivalent** to this capability.

## Recommendation

WebAxon should consider:

1. **Remote browser support**: Add CDP URL configuration for cloud browsers

```python
class WebDriver:
    def __init__(self, 
                 backend: str = "playwright",
                 cdp_url: str = None,  # New: connect to existing browser
                 ...):
        if cdp_url:
            self._browser = playwright.chromium.connect_over_cdp(cdp_url)
```

2. **Profile management**: Formalize profile configuration

```python
class BrowserProfile:
    name: str
    user_data_dir: Path
    cdp_port: int
    # ... managed lifecycle
```

3. **Session state tracking**: Track browser state (current tab, cookies) explicitly

The extension relay is a significant capability but may be out of scope for WebAxon's automation-focused use case.
