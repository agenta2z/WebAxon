# Developer Experience

Developer experience encompasses tooling, debugging capabilities, documentation, and the day-to-day workflow of building with each system.

## WebAxon: Rich Internal Tooling

WebAxon's devsuite provides a comprehensive development environment:

### Agent Debugger (NextGen)

A web-based UI for monitoring and controlling agent execution:

**Features:**
- **Chat Tab**: Send messages, view conversation history, see agent responses
- **Log Debugging Tab**: Real-time structured log visualization with turn-aware formatting
- **Settings Tab**: Agent type selection, session management, configuration
- **Action Tester Tab**: Interactive browser action testing without full agent loop
- **Floating Log Monitor**: Background polling with rate-limiting

**Agent Control:**
- Stop / Pause / Continue / Step buttons
- Session switching dropdown
- Template version selection
- Real-time status updates

### Queue-Based Architecture

```
_runtime/queues/<timestamp>/
├── user_input/       # User → Agent
├── agent_response/   # Agent → UI
├── client_control/   # Debugger → Service (pause, resume, step)
└── server_control/   # Service → Debugger (status)
```

**Benefits:**
- **Persistence**: Messages survive restarts; can replay sessions
- **Decoupling**: Debugger and service run independently
- **Debugging**: Can inspect queue contents directly
- **Isolation**: Each service run gets unique timestamp directory

### Session Management

```python
# From session/agent_session_manager.py
class AgentSessionManager:
    """Thread-safe session lifecycle management."""
    
    def create_session(self, session_type: str) -> AgentSession:
        # Creates session with full logging infrastructure
        # JsonLogger, SessionLogger, Debuggable pattern
        ...
    
    def get_session(self, session_id: str) -> Optional[AgentSession]:
        # Thread-safe retrieval
        ...
    
    def cleanup_idle_sessions(self, timeout: int = 1800):
        # Auto-cleanup after 30 minutes
        ...
```

**Session lifecycle:**
1. Create session (assigns ID, initializes logging)
2. Optionally create agent lazily (on first message)
3. Process messages through agent pipeline
4. Monitor for idle timeout
5. Cleanup on completion or timeout

### Action Tester

A dedicated tool for testing individual browser actions:

- **Browser session management**: Start/stop browser independent of agent
- **Action execution**: Run click, fill, scroll without LLM involvement
- **Template system**: Save and replay action sequences
- **Chrome profile support**: Test with specific browser profiles

### Structured Logging

WebAxon uses the `Debuggable` pattern (from `rich_python_utils`):

```python
class AgentSession(SessionBase):  # SessionBase provides Debuggable
    def process_message(self, message: str):
        self.debug("Processing message", message=message)
        # ... 
        self.debug("Action completed", action=action, result=result)
```

Logs are structured JSON with:
- Timestamps, session IDs, turn numbers
- Artifact tracking (screenshots, page states)
- Hierarchical context (session → turn → action)

## Agent-Browser: Minimal Tooling

Agent-Browser's developer experience is deliberately minimal:

### CLI-Centric Workflow

```bash
# Start session
agent-browser open https://example.com

# Observe
agent-browser snapshot
agent-browser screenshot --annotate

# Interact
agent-browser click @e5
agent-browser fill @e3 "hello"

# Debug
agent-browser console     # View console messages
agent-browser errors      # View JS errors
agent-browser requests    # View network requests

# Advanced debugging
agent-browser trace start
# ... perform actions ...
agent-browser trace stop trace.zip
# Open trace.zip in Playwright Trace Viewer
```

### Screenshot Annotations

```bash
agent-browser screenshot --annotate
```

Produces a screenshot with:
- Red-bordered boxes around interactive elements
- Numbered labels matching ref IDs
- Useful for visual debugging and documentation

### Playwright Trace Integration

Agent-Browser can record Playwright traces (`.zip` files) that open in the Playwright Trace Viewer:

- Timeline of actions
- DOM snapshots at each step
- Console/network logs
- Screenshots before/after each action

### HAR Recording

```bash
agent-browser har start
# ... perform actions ...
agent-browser har stop output.har
```

Records HTTP Archive for network debugging.

### Video Recording

```bash
agent-browser record start
# ... perform actions ...
agent-browser record stop output.webm
```

Records browser session as video.

## Comparison

| Capability | WebAxon | Agent-Browser |
|------------|---------|---------------|
| **Web-based debugger** | ✅ Full UI | ❌ None |
| **Session management UI** | ✅ Visual | ❌ CLI only |
| **Real-time log streaming** | ✅ Yes | ❌ No |
| **Action tester** | ✅ Interactive | ❌ CLI only |
| **Pause/step execution** | ✅ Built-in | ❌ Manual |
| **Screenshot annotations** | ⚠️ Not default | ✅ Built-in |
| **Playwright traces** | ⚠️ Via backend | ✅ Built-in |
| **HAR recording** | ❌ None | ✅ Built-in |
| **Video recording** | ❌ None | ✅ Built-in |
| **Profiling** | ❌ None | ✅ CPU profiler |
| **Structured logging** | ✅ Debuggable pattern | ⚠️ Basic |

## Documentation

### WebAxon

Documentation is scattered across multiple locations:
- `devsuite/README.md`: Overview
- `web_agent_service_nextgen/README.md`: Service docs
- `docs/getting-started/`: Quick start guides
- `docs/guides/`: Configuration, sessions, templates
- Module-level README files
- Inline docstrings

**Observation**: Good coverage but fragmented. Could benefit from a unified documentation site.

### Agent-Browser

Documentation is centralized:
- `README.md`: Comprehensive getting started
- `docs/` folder: MDX-based documentation site
- `skills/agent-browser/SKILL.md`: AI agent instructions
- `skills/*/`: Domain-specific guidance
- Inline CLI help (`--help`)

**Observation**: Well-organized with clear separation between human docs and AI agent instructions (SKILL.md).

## Installation & Setup

### WebAxon

```bash
# Assuming internal package
pip install webaxon

# Configure
export WEBAGENT_SERVICE_WORKSPACE=/path/to/workspace

# Launch service
python -m webaxon.devsuite.web_agent_service_nextgen.launch_service

# Launch debugger (separate terminal)
python -m webaxon.devsuite.agent_debugger_nextgen.launch_debugger
```

### Agent-Browser

```bash
# Install
npm install -g agent-browser

# Use immediately
agent-browser open https://example.com
```

**Observation**: Agent-Browser has zero-configuration startup. WebAxon requires workspace setup and multi-process orchestration.

## Recommendation

WebAxon's developer tooling is a significant strength — the debugger UI, session management, and action tester provide capabilities Agent-Browser lacks. These should be highlighted as differentiators.

However, consider:

1. **Unifying documentation**: Create a single documentation site with clear navigation.

2. **Simplifying startup**: A single `webaxon serve` command that launches both service and debugger.

3. **Adding recording capabilities**: Video and HAR recording would enhance debugging.

4. **Screenshot annotations**: Add ref-style annotations to screenshots for visual debugging.
