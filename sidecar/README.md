# WebAxon Browser Sidecar

HTTP sidecar server that exposes WebAxon's browser automation capabilities for integration with OpenClaw.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           OpenClaw                                       │
│                    (or any HTTP client)                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    HTTP requests to http://127.0.0.1:18800
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               WebAxon Browser Sidecar                                   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ GET  /health     → Server status and capabilities                  ││
│  │ POST /query      → Full agentic task execution                     ││
│  │ POST /navigate   → Navigate to URL                                 ││
│  │ POST /snapshot   → Get page state (HTML, refs, URL)               ││
│  │ POST /act        → Execute action (click, type, scroll, etc.)     ││
│  │ POST /screenshot → Capture screenshot (base64)                    ││
│  │ POST /shutdown   → Shutdown browser                               ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                    WebAgentService                                  ││
│  │  - Playwright / Selenium backend                                   ││
│  │  - clean_html() pipeline                                           ││
│  │  - Planning Agent → Action Agent                                   ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd WebAxon/sidecar
pip install -r requirements.txt

# Also ensure WebAxon is installed
cd ..
pip install -e .
```

### 2. Run the Server

```bash
# From WebAxon root directory
python -m sidecar

# Or with options
python -m sidecar --port 18800 --headless --backend playwright
```

### 3. Test the Server

```bash
# Health check
curl http://127.0.0.1:18800/health

# Navigate to a URL
curl -X POST http://127.0.0.1:18800/navigate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.google.com"}'

# Get page snapshot
curl -X POST http://127.0.0.1:18800/snapshot \
  -H "Content-Type: application/json" \
  -d '{}'

# Execute an action
curl -X POST http://127.0.0.1:18800/act \
  -H "Content-Type: application/json" \
  -d '{"kind": "type", "ref": "e1", "text": "hello world"}'

# Run a full agentic task
curl -X POST http://127.0.0.1:18800/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Search for Python tutorials", "start_url": "https://www.google.com"}'
```

## API Reference

### GET /health

Returns server status and capabilities.

**Response:**
```json
{
  "status": "ok",
  "service": "webaxon-browser-sidecar",
  "version": "0.1.0",
  "backend": "playwright",
  "capabilities": ["browser", "automation", "agent"]
}
```

### POST /query

Execute a full agentic task using WebAxon's planning agent.

**Request:**
```json
{
  "query": "Search for Python tutorials and click the first result",
  "start_url": "https://www.google.com"  // optional
}
```

**Response:**
```json
{
  "ok": true,
  "response": "Task completed successfully",
  "data": {
    "success": true,
    "steps": [...],
    "final_url": "..."
  }
}
```

### POST /navigate

Navigate to a URL.

**Request:**
```json
{
  "url": "https://www.example.com"
}
```

**Response:**
```json
{
  "ok": true,
  "message": "Navigated to https://www.example.com",
  "data": {
    "url": "https://www.example.com",
    "title": "Example Domain"
  }
}
```

### POST /snapshot

Get current page state including cleaned HTML and element references.

**Request:**
```json
{
  "include_screenshot": false  // optional
}
```

**Response:**
```json
{
  "ok": true,
  "snapshot": {
    "url": "https://www.example.com",
    "title": "Example Domain",
    "html": "<html>...</html>",
    "refs": [
      {"ref": "e1", "tag": "input", "id": "1", "text": ""},
      {"ref": "e2", "tag": "button", "id": "2", "text": "Submit"}
    ],
    "screenshot": "base64..."  // if requested
  }
}
```

### POST /act

Execute a browser action.

**Request:**
```json
{
  "kind": "click",     // click, type, scroll, select, hover, press, wait
  "ref": "e12",        // element reference
  "text": "hello",     // for type action
  "direction": "down", // for scroll action
  "value": "option1",  // for select action
  "key": "Enter",      // for press action
  "duration": 1.0      // for wait action
}
```

**Response:**
```json
{
  "ok": true,
  "message": "Clicked element e12",
  "data": null
}
```

### POST /screenshot

Capture a screenshot of the current page.

**Response:**
```json
{
  "ok": true,
  "message": "Screenshot captured",
  "screenshot": "base64-encoded-image..."
}
```

### POST /shutdown

Shutdown the browser (server keeps running).

**Response:**
```json
{
  "ok": true,
  "message": "Browser shutdown complete"
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBAXON_HOST` | `127.0.0.1` | Host to bind to |
| `WEBAXON_PORT` | `18800` | Port to bind to |
| `WEBAXON_HEADLESS` | `false` | Run browser in headless mode |
| `WEBAXON_CHROME_VERSION` | (auto) | Chrome version override |
| `WEBAXON_BACKEND` | `playwright` | Browser backend (`playwright` or `selenium`) |
| `WEBAXON_AGENT_TYPE` | `DefaultAgent` | Agent type to use |
| `WEBAXON_MAX_STEPS` | `50` | Max steps per task |
| `WEBAXON_AGENT_TIMEOUT` | `300` | Task timeout in seconds |
| `WEBAXON_WORKSPACE` | `~/.webaxon/workspace` | Workspace directory |
| `WEBAXON_DEBUG` | `false` | Enable debug mode |
| `WEBAXON_SYNC_AGENT` | `true` | Synchronous agent (for debugging) |

### OpenClaw Integration

The sidecar automatically loads configuration from `~/.openclaw/openclaw.json` if present,
following the pattern from `ai-lab-atlassian-agent`.

## Integration with OpenClaw

There are two ways to integrate WebAxon with OpenClaw:

### Option 1: Gateway Node (Recommended)

The sidecar connects to OpenClaw Gateway as a **browser-capable node**. OpenClaw automatically routes browser requests to WebAxon.

**Setup:**

1. Start OpenClaw Gateway (via docker-compose or directly)

2. Set environment variables for the sidecar:
   ```bash
   export OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
   export OPENCLAW_GATEWAY_TOKEN=your-gateway-token  # Must match OpenClaw's token
   ```

3. Start the WebAxon sidecar:
   ```bash
   python -m sidecar
   ```

4. The sidecar will:
   - Connect to Gateway via WebSocket
   - Register as a node with `commands: ["browser.proxy"]`
   - Handle all `browser.proxy` requests from OpenClaw

5. In OpenClaw, browser requests will automatically route to WebAxon:
   ```
   User: "Go to google.com and search for AI"
   OpenClaw: [detects browser task] → routes to WebAxon node → WebAxon executes
   ```

**Verification:**
```bash
# Check if WebAxon is connected as a node
curl http://127.0.0.1:18789/nodes  # Should show webaxon-* node
```

### Option 2: Direct HTTP

OpenClaw calls the sidecar directly via HTTP (requires OpenClaw code changes).

**If OpenClaw runs on the host (same machine):**
```typescript
const response = await fetch("http://127.0.0.1:18800/query", { ... });
```

**If OpenClaw runs inside a Docker container:**
```typescript
// Use host.docker.internal to reach the host machine from inside Docker
const response = await fetch("http://host.docker.internal:18800/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "Navigate to Google and search for AI",
    start_url: "https://www.google.com"
  })
});
const result = await response.json();
```

> **Note:** The sidecar binds to `0.0.0.0` by default to accept connections from Docker containers.

### Docker Compose Integration

To run WebAxon sidecar alongside OpenClaw, add to your `docker-compose.yml`:

```yaml
services:
  # ... existing openclaw services ...

  # WebAxon Browser Agent (runs on host, not in Docker)
  # Just set these environment variables in openclaw-gateway:
  #   WEBAXON_SIDECAR_URL: http://host.docker.internal:18800
```

Or for Gateway node mode, the sidecar runs on your Mac and connects to the Gateway:

```bash
# Terminal 1: Start OpenClaw
cd openclaw-dist && docker-compose up

# Terminal 2: Start WebAxon sidecar (connects to Gateway)
export OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
export OPENCLAW_GATEWAY_TOKEN=your-token
cd WebAxon && python -m sidecar
```

## Development

### Running Tests

```bash
cd WebAxon
pytest sidecar/tests/ -v
```

### Debug Mode

```bash
python -m sidecar --debug

# Or set environment variable
WEBAXON_DEBUG=true python -m sidecar
```

## Port Allocation

| Sidecar | Port |
|---------|------|
| Atlassian Agent (Jira/Confluence) | 18790 |
| **WebAxon Browser** | **18800** |

## License

See the main WebAxon repository for license information.
