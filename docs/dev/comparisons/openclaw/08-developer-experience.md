# Developer Experience

Comparing tooling, debugging, documentation, and development workflow.

## OpenClaw: CLI-Centric with Gateway Integration

### Command-Line Interface

OpenClaw exposes browser operations through a CLI integrated with the main `openclaw` command:

```bash
# Browser status
openclaw browser status

# List profiles
openclaw browser profiles

# Take snapshot
openclaw browser snapshot

# Execute action
openclaw browser act --kind click --ref 12

# Screenshot
openclaw browser screenshot --output page.png

# Manage tabs
openclaw browser tabs
openclaw browser open https://example.com
openclaw browser close
```

### Gateway UI (Control UI)

OpenClaw includes a web-based Gateway UI (`src/gateway/control-ui.ts`) that provides:

- Browser status monitoring
- Profile management
- Tab list visualization
- Basic action testing

However, this is primarily for Gateway administration, not browser debugging.

### Debugging Tools

**Playwright Trace Export**:
```bash
openclaw browser trace start
# ... perform actions ...
openclaw browser trace stop --output trace.zip
# Open trace.zip in Playwright Trace Viewer
```

**Screenshot with Labels**:
```bash
openclaw browser snapshot --labels
# Produces screenshot with ref labels overlaid
```

**Console and Error Capture**:
```bash
openclaw browser console
openclaw browser errors
openclaw browser requests
```

### Logging

OpenClaw uses structured logging (`src/logging/`):
- Request/response logging
- Error tracking with stack traces
- Performance timing

But logging is infrastructure-focused, not specifically designed for browser debugging.

## WebAxon: Rich Debugging UI

### Agent Debugger (NextGen)

WebAxon provides a comprehensive web-based debugger:

**Chat Tab**:
- Send messages to agent
- View conversation history
- See agent responses in real-time

**Log Debugging Tab**:
- Structured log visualization
- Turn-aware formatting
- Artifact tracking (screenshots, page states)
- Filtering and search

**Settings Tab**:
- Agent type selection
- Session management
- Template version selection
- Configuration overrides

**Action Tester Tab**:
- Browser control without agent involvement
- Direct action execution (click, fill, scroll)
- Template save/replay
- Chrome profile selection

### Agent Control

```
┌─────────────────────────────────────────────────────────┐
│  [Stop] [Pause] [Continue] [Step]                       │
│                                                         │
│  Session: [dropdown] ▼    Template: [dropdown] ▼       │
│                                                         │
│  Status: Running (Step 5 of 20)                         │
└─────────────────────────────────────────────────────────┘
```

- **Stop**: Terminate agent execution
- **Pause**: Suspend at next step boundary
- **Continue**: Resume paused execution
- **Step**: Execute single step then pause

### Queue-Based Architecture

```
_runtime/queues/<timestamp>/
├── user_input/        # User → Agent (JSON files)
├── agent_response/    # Agent → UI (JSON files)
├── client_control/    # Debugger → Service (pause/resume/step)
└── server_control/    # Service → Debugger (status updates)
```

**Benefits**:
- Messages persist across restarts
- Can inspect queue contents directly
- Replay sessions by re-submitting queue files
- Decoupled components (debugger can restart independently)

### Session Monitor

```python
class AgentSessionMonitor:
    """Background monitoring of session health."""
    
    def check_idle(self, timeout: int = 1800):
        # Auto-cleanup after 30 minutes idle
        ...
    
    def check_health(self):
        # Verify agent responsiveness
        ...
```

### Structured Logging

WebAxon uses the `Debuggable` pattern from `rich_python_utils`:

```python
class AgentSession(SessionBase):  # Provides Debuggable
    def process_message(self, message: str):
        self.debug("Processing message", message=message)
        # ...
        self.debug("Action completed", action=action, result=result)
```

Logs include:
- Session ID, turn number
- Artifact references
- Hierarchical context

## Comparison

| Capability | OpenClaw | WebAxon |
|------------|----------|---------|
| **Web-based debugger** | ⚠️ Gateway UI (limited) | ✅ Full debugger |
| **Chat interface** | ❌ CLI only | ✅ Built-in |
| **Log visualization** | ❌ File-based | ✅ Real-time UI |
| **Pause/step execution** | ❌ Not available | ✅ Full control |
| **Action tester** | ⚠️ Via CLI | ✅ Interactive UI |
| **Session management** | ⚠️ Profile system | ✅ Visual sessions |
| **Template management** | ❌ N/A | ✅ Version selection |
| **Screenshot with labels** | ✅ Built-in | ❌ Not default |
| **Playwright traces** | ✅ Built-in | ⚠️ Via backend |
| **HAR recording** | ⚠️ Limited | ❌ None |
| **Video recording** | ❌ None | ❌ None |
| **Queue inspection** | ❌ N/A | ✅ File-based |

## Documentation

### OpenClaw

Documentation lives in multiple places:
- `docs/` folder with markdown files
- `README.md` at project root
- Inline JSDoc comments
- Skills have their own `SKILL.md` files

**Browser-specific docs**:
- `docs/tools/browser.md`
- `docs/tools/chrome-extension.md`
- `docs/tools/browser-login.md`
- `docs/tools/browser-linux-troubleshooting.md`

### WebAxon

Documentation is distributed across:
- `devsuite/README.md`
- `web_agent_service_nextgen/README.md`
- `docs/guides/` folder
- `docs/getting-started/`
- Module-level READMEs

**Notable**: The `backends/docs/` folder contains comparison documentation:
- `backend_comparison.md`
- `input_text_comparison.md`

## Installation & Setup

### OpenClaw

```bash
# Clone and install
pnpm install

# Configure
cp .env.example .env
# Edit ~/.openclaw/openclaw.json

# Start gateway
pnpm start
# or
openclaw gateway
```

Browser requires additional setup:
- Chrome/Chromium installed
- Optional: Chrome extension for relay
- Optional: Xvfb for Docker deployments

### WebAxon

```bash
# Install (internal package)
pip install webaxon

# Configure workspace
export WEBAGENT_SERVICE_WORKSPACE=/path/to/workspace

# Start service
python -m webaxon.devsuite.web_agent_service_nextgen.launch_service

# Start debugger (separate terminal)
python -m webaxon.devsuite.agent_debugger_nextgen.launch_debugger
```

**Observation**: WebAxon requires two processes (service + debugger); OpenClaw is a single gateway process.

## Recommendation

WebAxon's developer tooling is significantly more sophisticated for browser debugging. OpenClaw's tooling is more focused on the overall platform.

Consider:

1. **Single-process launch**: `webaxon serve` that starts both service and debugger

2. **Screenshot annotations**: Add ref-style labels like OpenClaw

3. **Trace export**: Add Playwright trace support for detailed debugging

4. **Video recording**: Would enhance documentation and debugging

OpenClaw could benefit from:

1. **Richer browser debugging UI**: Beyond CLI commands
2. **Session visualization**: See agent state over time
3. **Action replay**: Re-execute recorded action sequences
