# WebAxon Docker Sidecar — OpenClaw Integration Guide

## Overview

The WebAxon browser agent runs as a Docker sidecar service alongside the OpenClaw gateway. It provides browser automation capabilities — navigating websites, extracting content, and executing multi-step browser tasks powered by the AG Claude inferencer via the Atlassian AI Gateway.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Docker Compose Network                              │
│                                                      │
│  ┌──────────────┐    ┌─────────────────────────┐    │
│  │  OpenClaw     │◄──►│  WebAxon Sidecar        │    │
│  │  Gateway      │    │  (port 18800)           │    │
│  │  (port 18789) │    │                         │    │
│  └──────────────┘    │  ┌─────────────────┐    │    │
│                       │  │ Chromium + Driver│    │    │
│  ┌──────────────┐    │  │ (apt, ARM native)│    │    │
│  │  Atlassian    │    │  └─────────────────┘    │    │
│  │  Agent        │    │                         │    │
│  │  (port 5001)  │    │  ┌─────────────────┐    │    │
│  └──────────────┘    │  │ AG Claude        │────┼──► SLAUTH (host:5000)
│                       │  │ Inferencer       │    │    │    ↓
│                       │  └─────────────────┘    │    │  AI Gateway
│                       └─────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

## Components

### Sidecar Files (`WebAxon/sidecar/`)

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage build: Python 3.12, Chromium, ChromeDriver, Playwright, all deps |
| `requirements.txt` | Python dependencies including `atlassian-ai-gateway-sdk` |
| `__main__.py` | Entry point — reads env vars or CLI args |
| `server.py` | aiohttp web server with REST endpoints |
| `config.py` | Configuration from env vars + OpenClaw JSON config |
| `browser_tools.py` | Browser automation wrapper using WebAxon agent infrastructure |
| `setup-docker.sh` | Build & run script with prerequisite checks |

### Local Package Dependencies

Three local packages are copied into the Docker image via `PYTHONPATH` (no setup.py needed):

| Package | Source Path | Docker Path |
|---|---|---|
| WebAxon | `WebAxon/src/` | `/app/packages/webaxon_src/` |
| RichPythonUtils | `RichPythonUtils/src/` | `/app/packages/richpythonutils_src/` |
| AgentFoundation | `AgentFoundation/src/` | `/app/packages/agentfoundation_src/` |

### Key Design Decisions

1. **ARM-native Chromium**: Uses `apt`'s `chromium` + `chromium-driver` packages (version-matched) instead of Google's Chrome for Testing (which only supports x86_64 Linux). This is critical for Apple Silicon Macs running Docker.

2. **System chromedriver auto-detection**: `driver_factory.py` was modified to auto-detect `/usr/bin/chromedriver` before falling back to `webdriver-manager` downloads. This avoids arch mismatches.

3. **Docker compatibility flags**: When running inside Docker (detected via `/.dockerenv`), Chrome gets `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu` flags automatically.

4. **Playwright coexistence**: Both Playwright and Selenium backends work. Playwright's Chromium is installed but NOT symlinked to `/usr/bin/chromium` (so it doesn't conflict with apt's version-matched chromium/chromedriver pair).

5. **SLAUTH via host**: The AG Claude inferencer authenticates through the host machine's `atlas slauth server` via `host.docker.internal:5000`.

## Prerequisites

1. **Docker Desktop** running
2. **`atlas slauth server`** running on your Mac (port 5000):
   ```bash
   atlas slauth server
   ```
3. **Atlassian internal PyPI credentials** in `~/.config/pip/pip.conf`:
   ```ini
   [global]
   extra-index-url = https://username:token@packages.atlassian.com/pypi/pypi/simple
   ```
4. **`PACKAGES_TOKEN`** in `openclaw-dist/.env`:
   ```
   PACKAGES_TOKEN=username:token
   ```

## Quick Start

### Option 1: Using the setup script

```bash
cd CoreProjects/WebAxon/sidecar

# Build and start
./setup-docker.sh

# Build, start, and run tests
./setup-docker.sh --test

# Use playwright backend instead of selenium
./setup-docker.sh --backend playwright
```

### Option 2: Using docker-compose directly

```bash
cd CoreProjects/atlassian-packages/openclaw-dist

# Build
docker compose build webaxon-agent

# Start
docker compose up webaxon-agent -d

# Check health
curl http://localhost:18800/health
```

### Option 3: Start everything together

```bash
cd CoreProjects/atlassian-packages/openclaw-dist

# Start all services (gateway + atlassian-agent + webaxon-agent)
docker compose up -d
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check — returns `{"ok": true, "backend": "selenium"}` |
| `/navigate` | POST | Navigate to URL — `{"url": "https://..."}` |
| `/snapshot` | POST | Get page state — returns title, URL, cleaned HTML, element refs |
| `/screenshot` | POST | Capture screenshot — returns base64 PNG |
| `/act` | POST | Execute action — `{"action": "click", "ref": "e12"}` |
| `/query` | POST | Full agent task — `{"query": "Go to ... and extract ..."}` |

### Example: Full agent query

```bash
curl -X POST http://localhost:18800/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Go to https://www.atlassian.com/software/jira/pricing and extract all pricing tiers"
  }'
```

The agent will:
1. Launch headless Chromium
2. Navigate to the page
3. Use AG Claude (via AI Gateway) to reason about what it sees
4. Execute multi-step browser actions (click, scroll, extract)
5. Return the result

Typical query takes 1-5 minutes depending on complexity.

## Environment Variables

### WebAxon Sidecar

| Variable | Default | Description |
|---|---|---|
| `WEBAXON_HOST` | `0.0.0.0` | Server bind address |
| `WEBAXON_PORT` | `18800` | Server port |
| `WEBAXON_HEADLESS` | `true` | Run Chrome headless |
| `WEBAXON_BACKEND` | `selenium` | Browser backend: `selenium` or `playwright` |
| `WEBAXON_AGENT_TYPE` | `DefaultAgent` | Agent type for /query |
| `WEBAXON_MAX_STEPS` | `50` | Max agent reasoning steps |
| `WEBAXON_AGENT_TIMEOUT` | `300` | Agent timeout in seconds |
| `WEBAXON_DEBUG` | `false` | Enable debug logging |

### AI Gateway (AG Claude Inferencer)

| Variable | Default | Description |
|---|---|---|
| `SLAUTH_SERVER_URL` | `http://host.docker.internal:5000` | SLAUTH server for auth tokens |
| `AI_GATEWAY_BASE_URL` | `https://ai-gateway.us-east-1.staging.atl-paas.net` | AI Gateway endpoint |
| `AI_GATEWAY_USER_ID` | `$ROVODEV_EMAIL` | User ID for AI Gateway |
| `AI_GATEWAY_CLOUD_ID` | `local` | Cloud ID for AI Gateway |

## Files Modified in Core Packages

### `WebAxon/src/webaxon/automation/backends/selenium/driver_factory.py`

Added system chromedriver auto-detection and Docker compatibility:

```python
# Line 244: Use system chromedriver if available (ARM Linux)
system_chromedriver = os.environ.get("CHROMEDRIVER_PATH") or shutil.which("chromedriver")
if system_chromedriver:
    webdriver_service = ChromeService(system_chromedriver)

# Line 267: Auto-detect system Chromium binary
if not binary_location and system_chromedriver:
    system_chromium = shutil.which("chromium") or ...

# Line 418: Docker container flags
if os.environ.get("WEBAXON_DOCKER") or os.path.exists("/.dockerenv"):
    _options.add_argument("--no-sandbox")
    _options.add_argument("--disable-dev-shm-usage")
    _options.add_argument("--disable-gpu")
```

### `openclaw-dist/docker-compose.yml`

Added `webaxon-agent` service definition with:
- Build context pointing to `CoreProjects/` (parent of WebAxon, RichPythonUtils, AgentFoundation)
- AI Gateway env vars with SLAUTH host forwarding
- Health check on port 18800
- `host.docker.internal` mapping for SLAUTH access

## Troubleshooting

### "No supported browser found"
Chrome/Chromium isn't installed. Rebuild with the Dockerfile that installs `chromium` via apt.

### "ChromeDriver version mismatch"
The Playwright symlink is overriding apt's Chromium. Make sure the Dockerfile does NOT create a `/usr/bin/chromium` symlink after Playwright install.

### "user_id is required" (AG inferencer)
Set `AI_GATEWAY_USER_ID` in docker-compose.yml environment.

### "SLAUTH connection refused"
Start `atlas slauth server` on your Mac. The container reaches it via `host.docker.internal:5000`.

### "atlassian-ai-gateway-sdk not found" (build failure)
Set `PACKAGES_TOKEN` in `openclaw-dist/.env` with your Atlassian packages credentials.

### Agent returns "Task completed" but no data
Check session logs inside the container:
```bash
docker compose exec webaxon-agent bash -c 'ls /root/.webaxon/workspace/_runtime/agent_logs/'
```
