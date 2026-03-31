"""WebAxon Browser Sidecar HTTP Server.

This module implements an HTTP server that exposes WebAxon's browser
automation capabilities for integration with OpenClaw.

Following the pattern from ai-lab-atlassian-agent sidecar.

Integration modes:
1. HTTP-only: OpenClaw calls http://host.docker.internal:18800 directly
2. Gateway Node: Sidecar connects to OpenClaw Gateway as a browser-capable node
"""

import asyncio
import json
import logging
import os
import signal
import sys
from typing import Optional

from aiohttp import web

from .browser_tools import BrowserTools
from .config import WebAxonSidecarConfig, load_openclaw_config
from .gateway_node import GatewayNode, GatewayNodeConfig
from .remote_auth import (
    AuthSessionManager,
    detect_auth_wall,
    setup_auth_routes,
)
from .oauth_auth import (
    OAuthManager,
    setup_oauth_routes,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global state
_browser_tools: Optional[BrowserTools] = None
_gateway_node: Optional[GatewayNode] = None
_request_lock: Optional[asyncio.Lock] = None
_config: Optional[WebAxonSidecarConfig] = None
_auth_manager: Optional[AuthSessionManager] = None


async def health_handler(request: web.Request) -> web.Response:
    """
    Health check endpoint.

    GET /health

    Returns:
        JSON with server status and capabilities.
    """
    global _browser_tools

    status = "ok" if _browser_tools and _browser_tools.is_initialized else "starting"

    return web.json_response({
        "status": status,
        "service": "webaxon-browser-sidecar",
        "version": "0.1.0",
        "backend": _browser_tools.backend_type if _browser_tools else "unknown",
        "capabilities": ["browser", "automation", "agent"],
    })


async def query_handler(request: web.Request) -> web.Response:
    """
    Full agentic task execution endpoint.

    POST /query
    Body: {"query": "...", "start_url": "..."}

    This endpoint invokes WebAxon's planning agent to autonomously
    complete a task, similar to the ai-lab-atlassian-agent pattern.

    Returns:
        JSON with task result.
    """
    global _browser_tools, _request_lock

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"},
            status=400,
        )

    query = body.get("query")
    if not query:
        return web.json_response(
            {"ok": False, "error": "Missing 'query' field"},
            status=400,
        )

    start_url = body.get("start_url")

    logger.info(f"Executing query: {query[:100]}...")

    async with _request_lock:
        try:
            result = await _browser_tools.run_task(task=query, start_url=start_url)
            return web.json_response({
                "ok": result.success,
                "response": result.message,
                "data": result.data,
            })
        except Exception as e:
            logger.exception(f"Query execution failed: {e}")
            return web.json_response(
                {"ok": False, "error": str(e)},
                status=500,
            )


async def navigate_handler(request: web.Request) -> web.Response:
    """
    Navigate to a URL.

    POST /navigate
    Body: {"url": "..."}

    Returns:
        JSON with navigation result.
    """
    global _browser_tools, _request_lock

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"},
            status=400,
        )

    url = body.get("url")
    if not url:
        return web.json_response(
            {"ok": False, "error": "Missing 'url' field"},
            status=400,
        )

    logger.info(f"Navigating to: {url}")

    async with _request_lock:
        try:
            result = await _browser_tools.navigate(url)
            return web.json_response({
                "ok": result.success,
                "message": result.message,
                "data": result.data,
            })
        except Exception as e:
            logger.exception(f"Navigation failed: {e}")
            return web.json_response(
                {"ok": False, "error": str(e)},
                status=500,
            )


async def snapshot_handler(request: web.Request) -> web.Response:
    """
    Get current page snapshot.

    POST /snapshot
    Body: {"include_screenshot": false}

    Returns:
        JSON with page state (HTML, refs, URL, title).
    """
    global _browser_tools, _request_lock

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}

    include_screenshot = body.get("include_screenshot", False)

    logger.info("Getting page snapshot")

    async with _request_lock:
        try:
            snapshot = await _browser_tools.get_snapshot(
                include_screenshot=include_screenshot
            )
            return web.json_response({
                "ok": True,
                "snapshot": snapshot,
            })
        except Exception as e:
            logger.exception(f"Snapshot failed: {e}")
            return web.json_response(
                {"ok": False, "error": str(e)},
                status=500,
            )


async def act_handler(request: web.Request) -> web.Response:
    """
    Execute a browser action.

    POST /act
    Body: {
        "kind": "click|type|scroll|select|hover|press|wait",
        "ref": "e12",      // element reference
        "text": "...",     // for type action
        "direction": "...", // for scroll action
        "value": "...",    // for select action
        "key": "...",      // for press action
        "duration": 1.0    // for wait action
    }

    Returns:
        JSON with action result.
    """
    global _browser_tools, _request_lock

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"},
            status=400,
        )

    kind = body.get("kind")
    if not kind:
        return web.json_response(
            {"ok": False, "error": "Missing 'kind' field"},
            status=400,
        )

    logger.info(f"Executing action: {kind}")

    async with _request_lock:
        try:
            result = await _browser_tools.execute_action(
                kind=kind,
                ref=body.get("ref"),
                text=body.get("text"),
                direction=body.get("direction"),
                value=body.get("value"),
                key=body.get("key"),
                duration=body.get("duration"),
            )
            return web.json_response({
                "ok": result.success,
                "message": result.message,
                "data": result.data,
            })
        except Exception as e:
            logger.exception(f"Action failed: {e}")
            return web.json_response(
                {"ok": False, "error": str(e)},
                status=500,
            )


async def screenshot_handler(request: web.Request) -> web.Response:
    """
    Take a screenshot.

    POST /screenshot
    Body: {
        "fullPage": false,  (optional)
        "type": "png"       (optional, "png" or "jpeg")
    }

    Returns:
        JSON with base64-encoded screenshot, compatible with OpenClaw browser tool format.
        - "data": base64 string (OpenClaw format)
        - "screenshot": base64 string (legacy WebAxon format)
        - "path": temp file path where screenshot was saved
        - "mimeType": "image/png" or "image/jpeg"
    """
    global _browser_tools, _request_lock

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    img_type = body.get("type", "png")
    mime_type = f"image/{img_type}"

    logger.info("Taking screenshot")

    async with _request_lock:
        try:
            result = await _browser_tools.take_screenshot()
            base64_data = result.data.get("base64") if result.data else None

            # Save to temp file for OpenClaw compatibility (imageResultFromFile)
            path = None
            if base64_data:
                import base64 as b64
                import tempfile
                suffix = ".png" if img_type == "png" else ".jpg"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="webaxon_screenshot_") as f:
                    f.write(b64.b64decode(base64_data))
                    path = f.name

            return web.json_response({
                "ok": result.success,
                "message": result.message,
                # OpenClaw format
                "data": base64_data,
                "path": path,
                "mimeType": mime_type,
                "url": result.data.get("url") if result.data else None,
                # Legacy WebAxon format
                "screenshot": base64_data,
            })
        except Exception as e:
            logger.exception(f"Screenshot failed: {e}")
            return web.json_response(
                {"ok": False, "error": str(e)},
                status=500,
            )


async def shutdown_handler(request: web.Request) -> web.Response:
    """
    Shutdown the browser (but keep server running).

    POST /shutdown

    Returns:
        JSON with shutdown status.
    """
    global _browser_tools, _request_lock

    logger.info("Shutting down browser")

    async with _request_lock:
        try:
            await _browser_tools.shutdown()
            return web.json_response({
                "ok": True,
                "message": "Browser shutdown complete",
            })
        except Exception as e:
            logger.exception(f"Shutdown failed: {e}")
            return web.json_response(
                {"ok": False, "error": str(e)},
                status=500,
            )


# ── OpenClaw Browser Tool Compatibility Endpoints ─────────────────────────────
# These endpoints make the WebAxon sidecar a drop-in replacement for
# OpenClaw's built-in browser control server.

async def openclaw_status_handler(request: web.Request) -> web.Response:
    """GET / — Browser status (OpenClaw format)."""
    global _browser_tools
    running = _browser_tools is not None and _browser_tools._webdriver is not None
    return web.json_response({
        "running": running,
        "backend": os.environ.get("WEBAXON_BACKEND", "selenium"),
        "profiles": {"default": {"driver": "webaxon-sidecar"}},
    })

async def openclaw_start_handler(request: web.Request) -> web.Response:
    """POST /start — Start browser (no-op, browser is always running)."""
    return web.json_response({
        "ok": True,
        "message": "Browser is managed by WebAxon sidecar",
    })

async def openclaw_stop_handler(request: web.Request) -> web.Response:
    """POST /stop — Stop browser (no-op for sidecar)."""
    return web.json_response({
        "ok": True,
        "message": "Browser lifecycle managed by WebAxon sidecar",
    })

async def openclaw_profiles_handler(request: web.Request) -> web.Response:
    """GET /profiles — List browser profiles."""
    return web.json_response({
        "profiles": {
            "default": {
                "driver": "webaxon-sidecar",
                "status": "running",
            },
        },
        "defaultProfile": "default",
    })

async def openclaw_tabs_open_handler(request: web.Request) -> web.Response:
    """POST /tabs/open — Open a new tab / navigate."""
    global _browser_tools, _request_lock

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    url = body.get("url", "about:blank")

    async with _request_lock:
        try:
            result = await _browser_tools.navigate(url)
            return web.json_response({
                "ok": result.success,
                "targetId": "default",
                "url": url,
            })
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

async def openclaw_tabs_focus_handler(request: web.Request) -> web.Response:
    """POST /tabs/focus — Focus a tab (no-op for single-tab sidecar)."""
    return web.json_response({"ok": True, "targetId": "default"})


# ── Remote Authentication Endpoints ──────────────────────────────────────────

async def auth_inject_with_browser_handler(request: web.Request) -> web.Response:
    """Inject cookies from a completed auth session into the headless browser.

    POST /auth/inject
    Body: {"session_id": "xxx", "navigate_after": true}

    This is the full injection flow:
    1. Gets cookies from the completed auth session
    2. Navigates the headless browser to the target domain (required for cookie domain matching)
    3. Injects all cookies into the browser
    4. Optionally re-navigates to the original target URL

    Returns:
        JSON with injection result.
    """
    global _browser_tools, _auth_manager, _request_lock

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"}, status=400
        )

    session_id = body.get("session_id")
    navigate_after = body.get("navigate_after", True)

    if not session_id:
        return web.json_response(
            {"ok": False, "error": "Missing 'session_id'"}, status=400
        )

    session = _auth_manager.get_session(session_id)
    if not session:
        return web.json_response(
            {"ok": False, "error": "Session not found"}, status=404
        )

    if not session.is_completed:
        return web.json_response(
            {"ok": False, "error": f"Session not completed (status: {session.status})"},
            status=400,
        )

    if not session.cookies:
        return web.json_response(
            {"ok": False, "error": "No cookies in session"}, status=400
        )

    async with _request_lock:
        try:
            # Step 1: Navigate to the target domain to set cookie context
            target_domain = session.target_domain
            target_url = session.target_url
            scheme = "https" if any(
                c.get("secure") for c in session.cookies
            ) else "https"  # Default to https for internal sites
            domain_url = f"{scheme}://{target_domain}/"

            logger.info(f"Navigating to {domain_url} for cookie domain context")
            await _browser_tools.navigate(domain_url)

            # Step 2: Inject cookies via the backend adapter
            webdriver = _browser_tools._webdriver
            if webdriver and webdriver._backend:
                # Clear existing cookies for clean state
                webdriver._backend.delete_all_cookies()
                # Inject the received cookies
                webdriver._backend.add_cookies(session.cookies)
                injected_count = len(session.cookies)
                logger.info(f"Injected {injected_count} cookies for {target_domain}")
            else:
                return web.json_response(
                    {"ok": False, "error": "Browser backend not initialized"},
                    status=500,
                )

            # Step 3: Navigate to the actual target URL with cookies active
            if navigate_after:
                logger.info(f"Navigating to target URL: {target_url}")
                result = await _browser_tools.navigate(target_url)
                return web.json_response({
                    "ok": True,
                    "message": f"Injected {injected_count} cookies and navigated to {target_url}",
                    "cookies_injected": injected_count,
                    "current_url": result.data.get("url") if result.data else target_url,
                    "page_title": result.data.get("title") if result.data else "",
                })
            else:
                return web.json_response({
                    "ok": True,
                    "message": f"Injected {injected_count} cookies for {target_domain}",
                    "cookies_injected": injected_count,
                })

        except Exception as e:
            logger.exception(f"Cookie injection failed: {e}")
            return web.json_response(
                {"ok": False, "error": str(e)}, status=500
            )


async def auth_poll_and_inject_handler(request: web.Request) -> web.Response:
    """Poll for auth completion and auto-inject when ready.

    POST /auth/poll-and-inject
    Body: {"session_id": "xxx", "timeout": 300}

    This is a convenience endpoint that:
    1. Waits for the user to complete authentication (polls the session)
    2. Automatically injects cookies into the browser when ready
    3. Navigates to the target URL

    Returns:
        JSON with final result after injection.
    """
    global _browser_tools, _auth_manager, _request_lock

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"}, status=400
        )

    session_id = body.get("session_id")
    timeout = body.get("timeout", 300)  # 5 min default

    if not session_id:
        return web.json_response(
            {"ok": False, "error": "Missing 'session_id'"}, status=400
        )

    session = _auth_manager.get_session(session_id)
    if not session:
        return web.json_response(
            {"ok": False, "error": "Session not found"}, status=404
        )

    # Poll until completed or timeout
    start = asyncio.get_event_loop().time()
    while not session.is_completed and not session.is_expired:
        elapsed = asyncio.get_event_loop().time() - start
        if elapsed > timeout:
            return web.json_response({
                "ok": False,
                "error": "Timed out waiting for authentication",
                "elapsed_seconds": int(elapsed),
            }, status=408)
        await asyncio.sleep(2)  # Poll every 2 seconds
        session = _auth_manager.get_session(session_id)

    if session.is_expired:
        return web.json_response({
            "ok": False,
            "error": "Authentication session expired",
        }, status=410)

    # Session is completed — inject cookies
    # Reuse the inject handler logic by creating a fake request
    inject_body = {"session_id": session_id, "navigate_after": True}

    # Direct injection
    async with _request_lock:
        try:
            target_domain = session.target_domain
            target_url = session.target_url
            domain_url = f"https://{target_domain}/"

            await _browser_tools.navigate(domain_url)

            webdriver = _browser_tools._webdriver
            if webdriver and webdriver._backend:
                webdriver._backend.delete_all_cookies()
                webdriver._backend.add_cookies(session.cookies)
                injected_count = len(session.cookies)
            else:
                return web.json_response(
                    {"ok": False, "error": "Browser backend not initialized"},
                    status=500,
                )

            result = await _browser_tools.navigate(target_url)

            # Check if we ended up on a login page again
            current_url = result.data.get("url", "") if result.data else ""
            current_title = result.data.get("title", "") if result.data else ""
            still_auth_wall = detect_auth_wall(current_url, current_title)

            return web.json_response({
                "ok": True,
                "message": f"Injected {injected_count} cookies and navigated to {target_url}",
                "cookies_injected": injected_count,
                "current_url": current_url,
                "page_title": current_title,
                "authenticated": not still_auth_wall,
                "warning": "Still on login page — cookies may not include HttpOnly auth tokens. Try the DevTools export method." if still_auth_wall else None,
            })

        except Exception as e:
            logger.exception(f"Poll-and-inject failed: {e}")
            return web.json_response(
                {"ok": False, "error": str(e)}, status=500
            )


def create_app(config: WebAxonSidecarConfig) -> web.Application:
    """Create the aiohttp application with all routes."""
    global _browser_tools, _request_lock, _config, _auth_manager

    _config = config
    _browser_tools = BrowserTools(config)
    _request_lock = asyncio.Lock()

    app = web.Application()

    # Register routes
    app.router.add_get("/health", health_handler)
    app.router.add_post("/query", query_handler)
    app.router.add_post("/navigate", navigate_handler)
    app.router.add_post("/snapshot", snapshot_handler)
    app.router.add_post("/act", act_handler)
    app.router.add_post("/screenshot", screenshot_handler)
    app.router.add_post("/shutdown", shutdown_handler)

    # OpenClaw browser tool compatibility endpoints
    app.router.add_get("/", openclaw_status_handler)
    app.router.add_post("/start", openclaw_start_handler)
    app.router.add_post("/stop", openclaw_stop_handler)
    app.router.add_get("/profiles", openclaw_profiles_handler)
    app.router.add_post("/tabs/open", openclaw_tabs_open_handler)
    app.router.add_post("/tabs/focus", openclaw_tabs_focus_handler)

    # Remote authentication endpoints
    sidecar_base_url = os.getenv(
        "WEBAXON_BASE_URL",
        f"http://{config.host}:{config.port}"
    )
    _auth_manager = setup_auth_routes(app, sidecar_base_url=sidecar_base_url)

    # Atlassian OAuth2 authentication endpoints
    # Generates real https://auth.atlassian.com/authorize URLs
    # that can be pasted ANYWHERE for authentication
    setup_oauth_routes(app, sidecar_base_url=sidecar_base_url)

    # Override the /auth/inject route with the browser-aware version
    # (remote_auth.py registers a basic one; we replace with full injection)
    # The routes below are added after setup_auth_routes, so they take priority
    # for these specific paths via a dedicated sub-app or by re-registering
    app.router.add_post("/auth/inject-browser", auth_inject_with_browser_handler)
    app.router.add_post("/auth/poll-and-inject", auth_poll_and_inject_handler)

    # Startup and cleanup handlers
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app


async def on_startup(app: web.Application) -> None:
    """Startup handler - connect to Gateway if configured."""
    global _gateway_node, _browser_tools, _config

    # Check if Gateway connection is configured
    gateway_url = os.getenv("OPENCLAW_GATEWAY_URL")
    gateway_token = os.getenv("OPENCLAW_GATEWAY_TOKEN")

    if gateway_url:
        logger.info(f"Gateway URL configured: {gateway_url}")
        node_config = GatewayNodeConfig(
            gateway_url=gateway_url,
            gateway_token=gateway_token,
            display_name="WebAxon Browser Agent",
            platform="darwin",  # Must be a known platform for command allowlist
        )
        _gateway_node = GatewayNode(config=node_config, browser_tools=_browser_tools)

        # Connect in background (don't block server startup)
        asyncio.create_task(_connect_gateway_with_retry())
    else:
        logger.info("No OPENCLAW_GATEWAY_URL configured - running in HTTP-only mode")
        logger.info("OpenClaw can call this sidecar at http://host.docker.internal:18800")


async def _connect_gateway_with_retry() -> None:
    """Connect to Gateway with retry logic."""
    global _gateway_node

    if not _gateway_node:
        return

    # Wait a bit for browser tools to initialize
    await asyncio.sleep(2)

    success = await _gateway_node.connect()
    if success:
        logger.info("Successfully registered with OpenClaw Gateway as browser node")
    else:
        logger.warning("Failed to connect to Gateway - will retry in background")


async def on_cleanup(app: web.Application) -> None:
    """Cleanup handler for graceful shutdown."""
    global _browser_tools, _gateway_node

    logger.info("Cleaning up resources...")

    # Disconnect from Gateway
    if _gateway_node:
        await _gateway_node.disconnect()

    # Shutdown browser
    if _browser_tools:
        await _browser_tools.shutdown()


def run_server(config: Optional[WebAxonSidecarConfig] = None) -> None:
    """
    Run the WebAxon browser sidecar server.

    Args:
        config: Server configuration. If None, loads from environment.
    """
    # Load OpenClaw config (sets environment variables)
    load_openclaw_config()

    # Create config from environment if not provided
    if config is None:
        config = WebAxonSidecarConfig.from_env()

    logger.info(f"Starting WebAxon Browser Sidecar on {config.host}:{config.port}")
    logger.info(f"Backend: {config.backend}, Headless: {config.headless}")

    app = create_app(config)
    web.run_app(app, host=config.host, port=config.port)


def main() -> None:
    """Main entry point for the sidecar server."""
    import argparse

    parser = argparse.ArgumentParser(description="WebAxon Browser Sidecar Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (0.0.0.0 for Docker access)")
    parser.add_argument("--port", type=int, default=18800, help="Port to bind to")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--backend", default="selenium", choices=["playwright", "selenium"],
                        help="Browser backend to use")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--workspace", help="Workspace directory path")

    args = parser.parse_args()

    config = WebAxonSidecarConfig(
        host=args.host,
        port=args.port,
        headless=args.headless,
        backend=args.backend,
        debug_mode=args.debug,
        workspace=args.workspace or os.path.expanduser("~/.webaxon/workspace"),
    )

    run_server(config)


if __name__ == "__main__":
    main()
