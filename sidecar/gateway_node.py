"""OpenClaw Gateway Node client for WebAxon sidecar.

This module implements a WebSocket client that connects to OpenClaw Gateway
and registers WebAxon as a browser-capable node. When OpenClaw routes browser
requests to this node, they are handled by WebAxon's browser tools.

Usage:
    # Start alongside the HTTP server
    node = GatewayNode(
        gateway_url="ws://127.0.0.1:18789",
        gateway_token="your-token",
        browser_tools=browser_tools,
    )
    await node.connect()
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class GatewayNodeConfig:
    """Configuration for the Gateway node client."""

    # Gateway connection
    gateway_url: str = "ws://127.0.0.1:18789"
    gateway_token: Optional[str] = None

    # Node identity - client.id must be a valid GatewayClientId
    # Valid values: "node-host", "gateway-client", "cli", etc.
    client_id: str = "node-host"  # Required: must be a recognized client ID
    instance_id: str = field(default_factory=lambda: f"webaxon-{uuid.uuid4().hex[:8]}")
    display_name: str = "WebAxon Browser Agent"
    # Platform must match a known platform for command allowlist.
    # "darwin" maps to "macos" which allows browser.proxy command.
    platform: str = "darwin"
    version: str = "0.1.0"
    mode: str = "node"  # "node" for sidecar/node-host

    # Capabilities
    caps: list = field(default_factory=lambda: ["browser"])
    commands: list = field(default_factory=lambda: ["browser.proxy"])

    # Reconnection
    reconnect_interval: float = 5.0
    max_reconnect_attempts: int = 10


class GatewayNode:
    """
    WebSocket client that connects to OpenClaw Gateway as a browser-capable node.

    When OpenClaw sends browser.proxy commands, this node handles them by
    delegating to the BrowserTools instance.
    """

    def __init__(
        self,
        config: GatewayNodeConfig,
        browser_tools: Any,  # BrowserTools instance
    ):
        self.config = config
        self.browser_tools = browser_tools
        self._ws = None
        self._connected = False
        self._reconnect_task = None
        self._receive_task = None
        self._should_run = False

    async def connect(self) -> bool:
        """Connect to the Gateway and register as a browser node."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed. Run: pip install websockets")
            return False

        self._should_run = True

        try:
            url = self.config.gateway_url
            
            logger.info(f"Connecting to OpenClaw Gateway at {url}")
            
            # Connect without auth headers - auth is done via challenge-response
            self._ws = await websockets.connect(url, max_size=25 * 1024 * 1024)

            # Wait for connect.challenge from server
            challenge_raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            challenge_data = json.loads(challenge_raw)
            
            if challenge_data.get("type") != "event" or challenge_data.get("event") != "connect.challenge":
                logger.error(f"Expected connect.challenge, got: {challenge_data}")
                await self._ws.close()
                return False
            
            nonce = challenge_data.get("payload", {}).get("nonce")
            if not nonce:
                logger.error("connect.challenge missing nonce")
                await self._ws.close()
                return False
            
            logger.debug(f"Received challenge with nonce: {nonce}")

            # Send connect request with auth token and nonce
            connect_msg = {
                "type": "req",
                "id": str(uuid.uuid4()),
                "method": "connect",
                "params": {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {
                        "id": self.config.client_id,  # Must be valid GatewayClientId like "node-host"
                        "displayName": self.config.display_name,
                        "platform": self.config.platform,
                        "version": self.config.version,
                        "mode": self.config.mode,
                        "instanceId": self.config.instance_id,
                    },
                    "caps": self.config.caps,
                    "commands": self.config.commands,
                    "role": "node",  # Connect as node so we're registered as browser-capable
                    "scopes": ["node"],
                    "auth": {
                        "token": self.config.gateway_token,
                    } if self.config.gateway_token else None,
                },
            }
            await self._ws.send(json.dumps(connect_msg))

            # Wait for response
            response_raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            resp_data = json.loads(response_raw)

            if resp_data.get("type") == "res" and resp_data.get("ok"):
                self._connected = True
                logger.info(f"Connected to Gateway as node '{self.config.display_name}'")

                # Start message handler
                self._receive_task = asyncio.create_task(self._receive_loop())
                return True
            else:
                error_msg = resp_data.get("error", {}).get("message", "Unknown error")
                logger.error(f"Gateway rejected connection: {error_msg}")
                logger.error(f"Full response: {resp_data}")
                await self._ws.close()
                return False

        except asyncio.TimeoutError:
            logger.error("Timeout waiting for Gateway response")
            if self._ws:
                await self._ws.close()
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Gateway: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the Gateway."""
        self._should_run = False
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        logger.info("Disconnected from Gateway")

    async def _receive_loop(self) -> None:
        """Receive and handle messages from the Gateway."""
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from Gateway: {message[:100]}")
                except Exception as e:
                    logger.error(f"Error handling Gateway message: {e}")
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            self._connected = False
            if self._should_run:
                asyncio.create_task(self._reconnect())

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle a message from the Gateway."""
        msg_type = data.get("type")
        event = data.get("event")

        if msg_type == "event" and event == "node.invoke.request":
            await self._handle_invoke_request(data.get("payload", {}))
        elif msg_type == "ping":
            await self._send({"type": "pong"})
        else:
            logger.debug(f"Unhandled Gateway message: {msg_type}/{event}")

    async def _handle_invoke_request(self, payload: Dict[str, Any]) -> None:
        """Handle a node.invoke.request from the Gateway."""
        request_id = payload.get("id")
        command = payload.get("command")
        params_json = payload.get("paramsJSON")

        if not request_id:
            logger.warning("Invoke request missing id")
            return

        params = {}
        if params_json:
            try:
                params = json.loads(params_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid paramsJSON in invoke request")

        logger.info(f"Received invoke request: {command}")

        try:
            if command == "browser.proxy":
                result = await self._handle_browser_proxy(params)
                await self._send_invoke_result(request_id, ok=True, payload=result)
            else:
                await self._send_invoke_result(
                    request_id,
                    ok=False,
                    error={"code": "UNKNOWN_COMMAND", "message": f"Unknown command: {command}"},
                )
        except Exception as e:
            logger.error(f"Error handling invoke {command}: {e}")
            await self._send_invoke_result(
                request_id,
                ok=False,
                error={"code": "INTERNAL_ERROR", "message": str(e)},
            )

    async def _handle_browser_proxy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle browser.proxy command by routing to BrowserTools.

        OpenClaw's browser.proxy params:
            - method: GET, POST, DELETE
            - path: /snapshot, /act, /navigate, etc.
            - query: query params
            - body: request body
            - timeoutMs: timeout
            - profile: browser profile
        """
        method = params.get("method", "GET").upper()
        path = params.get("path", "").strip()
        body = params.get("body", {})
        query = params.get("query", {})

        logger.info(f"Browser proxy: {method} {path}")

        # Route based on path - handle OpenClaw's browser control routes

        # GET / - Status endpoint
        if path == "/" or path == "":
            return {
                "enabled": True,
                "profile": query.get("profile", "webaxon"),
                "running": self.browser_tools.is_initialized,
                "cdpReady": self.browser_tools.is_initialized,
                "cdpHttp": self.browser_tools.is_initialized,
                "pid": None,
                "cdpPort": None,
                "cdpUrl": None,
                "chosenBrowser": "chromium",
                "detectedBrowser": "chromium",
                "detectedExecutablePath": None,
                "detectError": None,
                "userDataDir": None,
                "color": "#4285f4",
                "headless": False,
                "noSandbox": False,
                "executablePath": None,
                "attachOnly": False,
            }

        # GET /profiles - List profiles
        elif path == "/profiles":
            return {
                "profiles": [
                    {
                        "name": "webaxon",
                        "running": self.browser_tools.is_initialized,
                        "isDefault": True,
                        "cdpPort": None,
                        "color": "#4285f4",
                    }
                ]
            }

        # POST /start - Start browser
        elif path == "/start":
            await self.browser_tools.initialize()
            return {
                "ok": True,
                "profile": query.get("profile", "webaxon"),
                "running": True,
            }

        # POST /tabs/open - Open a URL in a tab
        elif path == "/tabs/open":
            url = body.get("url") or query.get("url", "")
            if url:
                result = await self.browser_tools.navigate(url)
                state = await self.browser_tools.get_state()
                return {
                    "ok": result.success,
                    "targetId": "webaxon-tab-1",
                    "url": state.url,
                    "title": state.title,
                }
            return {"ok": False, "error": "No URL provided"}

        # GET /tabs - List tabs
        elif path == "/tabs":
            state = await self.browser_tools.get_state()
            return {
                "tabs": [
                    {
                        "targetId": "webaxon-tab-1",
                        "url": state.url,
                        "title": state.title,
                        "type": "page",
                    }
                ]
            }

        # Snapshot endpoint - returns page state
        elif path == "/snapshot" or path.startswith("/snapshot"):
            include_screenshot = body.get("includeScreenshot", False)
            snapshot = await self.browser_tools.get_snapshot(include_screenshot=include_screenshot)
            return {"result": snapshot}

        # Act endpoint - execute an action
        elif path == "/act" or path.startswith("/act"):
            result = await self.browser_tools.execute_action(
                kind=body.get("kind", ""),
                ref=body.get("ref"),
                text=body.get("text"),
                direction=body.get("direction"),
                value=body.get("value"),
                key=body.get("key"),
                duration=body.get("duration"),
            )
            return {
                "result": {
                    "ok": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            }

        # Navigate endpoint
        elif path == "/navigate" or path.startswith("/navigate"):
            url = body.get("url", "")
            result = await self.browser_tools.navigate(url)
            return {
                "result": {
                    "ok": result.success,
                    "url": result.data.get("url") if result.data else "",
                    "title": result.data.get("title") if result.data else "",
                }
            }

        # Screenshot endpoint
        elif path == "/screenshot" or path.startswith("/screenshot"):
            result = await self.browser_tools.take_screenshot()
            return {
                "result": {
                    "ok": result.success,
                    "screenshot": result.data.get("base64") if result.data else None,
                }
            }

        # Status endpoint (alternate path)
        elif path == "/status" or path.startswith("/status"):
            state = await self.browser_tools.get_state()
            return {
                "result": {
                    "ok": True,
                    "initialized": self.browser_tools.is_initialized,
                    "url": state.url,
                    "title": state.title,
                }
            }

        # Full agentic task query
        elif path == "/query" or path.startswith("/query"):
            query_text = body.get("query", "")
            start_url = body.get("startUrl") or body.get("start_url")
            result = await self.browser_tools.run_task(task=query_text, start_url=start_url)
            return {
                "result": {
                    "ok": result.success,
                    "response": result.message,
                    "data": result.data,
                }
            }

        # Stop/close browser
        elif path == "/stop":
            await self.browser_tools.shutdown()
            return {"ok": True}

        else:
            logger.warning(f"Unknown browser proxy path: {path}")
            raise ValueError(f"Unknown browser proxy path: {path}")

    async def _send_invoke_result(
        self,
        request_id: str,
        ok: bool,
        payload: Any = None,
        error: Dict[str, str] = None,
    ) -> None:
        """Send invoke result back to Gateway as a request."""
        # Gateway expects node.invoke.result as a request, not an event
        result_msg = {
            "type": "req",
            "id": str(uuid.uuid4()),
            "method": "node.invoke.result",
            "params": {
                "id": request_id,
                "nodeId": self.config.client_id,  # Must match client.id used in connect
                "ok": ok,
            },
        }

        if payload is not None:
            result_msg["params"]["payloadJSON"] = json.dumps(payload)

        if error:
            result_msg["params"]["error"] = error

        await self._send(result_msg)

    async def _send(self, data: Dict[str, Any]) -> bool:
        """Send a message to the Gateway."""
        if not self._ws or not self._connected:
            return False
        try:
            await self._ws.send(json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"Failed to send to Gateway: {e}")
            return False

    async def _reconnect(self) -> None:
        """Attempt to reconnect to the Gateway."""
        for attempt in range(self.config.max_reconnect_attempts):
            if not self._should_run:
                return

            wait_time = self.config.reconnect_interval * (attempt + 1)
            logger.info(f"Reconnecting in {wait_time}s (attempt {attempt + 1})")
            await asyncio.sleep(wait_time)

            if await self.connect():
                return

        logger.error("Max reconnection attempts reached")

    @property
    def is_connected(self) -> bool:
        """Check if connected to the Gateway."""
        return self._connected
