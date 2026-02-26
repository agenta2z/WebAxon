# Manual Testing Guide

Quick end-to-end test of `web_agent_service_nextgen`.

The prompt templates already live under `src/webagent/devsuite/prompt_templates/`,
so we use `src/webagent/devsuite/` as the testcase root directly — no copying needed.

## Prerequisites

- Python 3.12+ with project dependencies installed
- Chrome browser
- Anthropic API key

## 1. Set environment (both terminals)

```bash
set ANTHROPIC_API_KEY=sk-ant-...your-key...

:: Align queue paths so CLI can discover the service
set WEBAGENT_SERVICE_QUEUE_ROOT_PATH=%USERPROFILE%\OneDrive\Projects\PythonProjects\WebAgent\src\webagent\devsuite\_runtime\queue_storage\session1
```

## 2. Start the service (Terminal 1)

```bash
python %USERPROFILE%\OneDrive\Projects\PythonProjects\WebAgent\src\webagent\devsuite\web_agent_service_nextgen\launch_service.py  %USERPROFILE%\OneDrive\Projects\PythonProjects\WebAgent\src\webagent\devsuite
```

Wait for the startup banner, leave running.

## 3. Start the CLI (Terminal 2)

```bash
python %USERPROFILE%\OneDrive\Projects\PythonProjects\WebAgent\src\webagent\devsuite\web_agent_service_nextgen\cli\launch_cli.py  %USERPROFILE%\OneDrive\Projects\PythonProjects\WebAgent\src\webagent\devsuite
```

## 4. Test

```
> /add User is a Safeway Plus member with free delivery on orders over $50
> /add User lives in Bellevue, WA 98004
> what is the organic egg price in safeway right now
```

The agent opens Chrome, navigates to Safeway, and returns the result.

## 5. Stop

- Terminal 1: `Ctrl+C`
- Terminal 2: `/quit`
- Cleanup: `rmdir /s /q src\webagent\devsuite\_runtime`

## Notes

**Queue path alignment**: The nextgen service defaults queues to `_runtime/queues/<timestamp>/`
but CLI auto-discovery looks under `_runtime/queue_storage/`.
The `WEBAGENT_SERVICE_QUEUE_ROOT_PATH` env var overrides the service to write queues
where the CLI expects them.

**Runtime files** are created under `src/webagent/devsuite/_runtime/`:

| Directory | Contents |
|---|---|
| `queue_storage/session1/` | Message queues and archive |
| `knowledge_store/` | Registered knowledge pieces (persisted as JSON) |
| `service_logs/` | Service and per-session agent logs |

## Troubleshooting

| Problem | Fix |
|---|---|
| CLI: "No queue storage found" | Ensure `WEBAGENT_SERVICE_QUEUE_ROOT_PATH` is set in the **service** terminal before starting |
| `ANTHROPIC_API_KEY` error | Set the env var in the service terminal |
| Chrome window closes / crashes | Ensure Chrome is up to date; don't close the window manually |
| No response after 120s | Agent may still be running — check `_runtime/service_logs/` |
| `.lock` PermissionError on cleanup | Stop both service and CLI before deleting `_runtime/` |
