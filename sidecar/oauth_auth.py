"""Atlassian OAuth 2.0 Authentication for WebAxon Browser Sidecar.

This module generates a REAL Atlassian authentication URL
(https://auth.atlassian.com/authorize?...) that can be pasted
anywhere — Slack, email, terminal, phone — for the user to authenticate.

Two approaches for handling the OAuth callback:

1. **Direct Callback** (sidecar must be reachable):
   The redirect_uri points to the sidecar's /oauth/callback endpoint.
   Best when the sidecar has a public URL (ngrok, Cloudflare Tunnel, etc.)

2. **Manual Code Paste** (works from anywhere):
   Uses a special redirect that shows the auth code on screen.
   The user copies the code and pastes it back (via API, Slack, etc.)
   The sidecar exchanges the code for tokens.

Flow:
    ┌─────────────────────────────────────────────────────────┐
    │  Agent/Script:                                          │
    │  POST /oauth/start                                      │
    │    → Returns Atlassian auth URL (paste anywhere!)        │
    │                                                          │
    │  User clicks: https://auth.atlassian.com/authorize?...   │
    │    → Logs in via SSO/Okta/MFA on their own device        │
    │    → Redirected back with auth code                      │
    │                                                          │
    │  Option A: Callback hits sidecar automatically           │
    │  Option B: User pastes auth code via POST /oauth/code    │
    │                                                          │
    │  Sidecar exchanges code for access_token                 │
    │  Token injected into browser as Authorization header     │
    │  or used via API proxy                                   │
    └─────────────────────────────────────────────────────────┘

Environment Variables:
    ATLASSIAN_OAUTH_CLIENT_ID     - OAuth app client ID
    ATLASSIAN_OAUTH_CLIENT_SECRET - OAuth app client secret
    ATLASSIAN_OAUTH_SCOPES        - Space-separated scopes (optional)
    WEBAXON_BASE_URL              - Sidecar's public URL (for callback mode)
"""

import asyncio
import json
import logging
import os
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from aiohttp import web

logger = logging.getLogger(__name__)


# ── Atlassian OAuth2 Constants ────────────────────────────────────────────────

AUTH_SERVER = "https://auth.atlassian.com"
AUTHORIZE_URL = f"{AUTH_SERVER}/authorize"
TOKEN_URL = f"{AUTH_SERVER}/oauth/token"
ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

DEFAULT_SCOPES = [
    "offline_access",
    "read:me",
    "read:jira-user",
    "read:jira-work",
    "write:jira-work",
    "read:confluence-user",
    "read:confluence-content.all",
    "write:confluence-content",
    "search:confluence",
]


# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class OAuthSession:
    """Represents an OAuth authentication session."""

    session_id: str
    state: str  # OAuth state parameter (CSRF protection)
    target_url: str  # What we ultimately want to visit
    auth_url: str  # The Atlassian auth URL to give to the user
    callback_mode: str  # "direct" or "manual"
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    status: str = "pending"  # pending | code_received | token_acquired | injected | expired
    authorization_code: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[float] = None
    cloud_id: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + 600

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def has_token(self) -> bool:
        return self.access_token is not None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "target_url": self.target_url,
            "auth_url": self.auth_url,
            "callback_mode": self.callback_mode,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "has_token": self.has_token,
            "error": self.error,
        }


class OAuthManager:
    """Manages Atlassian OAuth2 authentication sessions."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        sidecar_base_url: str = "http://localhost:18800",
        scopes: Optional[List[str]] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.sidecar_base_url = sidecar_base_url
        self.scopes = scopes or DEFAULT_SCOPES
        self.sessions: Dict[str, OAuthSession] = {}

        if not client_id:
            logger.warning(
                "ATLASSIAN_OAUTH_CLIENT_ID not set. "
                "OAuth authentication will not work. "
                "Register an OAuth app at https://developer.atlassian.com/console/myapps/"
            )

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def create_auth_session(
        self,
        target_url: str,
        callback_mode: str = "manual",
        ttl: int = 600,
    ) -> OAuthSession:
        """Create an OAuth session and generate the Atlassian auth URL.

        Args:
            target_url: The internal URL the browser needs to visit.
            callback_mode: "direct" (sidecar handles callback) or "manual"
                          (user pastes the auth code back).
            ttl: Time-to-live in seconds.

        Returns:
            OAuthSession with the Atlassian auth URL ready to share.
        """
        session_id = secrets.token_urlsafe(16)
        state = secrets.token_urlsafe(32)

        # Build the redirect URI
        if callback_mode == "direct":
            # Callback comes directly to the sidecar
            redirect_uri = f"{self.sidecar_base_url}/oauth/callback"
        else:
            # "Manual" mode: redirect to a page that displays the code
            # We use the sidecar's own page that shows the code for copy-paste
            redirect_uri = f"{self.sidecar_base_url}/oauth/code-display"

        # Build Atlassian authorization URL
        params = {
            "audience": "api.atlassian.com",
            "client_id": self.client_id,
            "scope": " ".join(self.scopes),
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
        auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

        session = OAuthSession(
            session_id=session_id,
            state=state,
            target_url=target_url,
            auth_url=auth_url,
            callback_mode=callback_mode,
            expires_at=time.time() + ttl,
        )

        self.sessions[session_id] = session
        # Also index by state for callback lookup
        self.sessions[f"state:{state}"] = session

        logger.info(
            f"Created OAuth session {session_id} for {target_url} "
            f"(mode={callback_mode})"
        )
        return session

    def get_session(self, session_id: str) -> Optional[OAuthSession]:
        session = self.sessions.get(session_id)
        if session and session.is_expired and session.status == "pending":
            session.status = "expired"
        return session

    def get_session_by_state(self, state: str) -> Optional[OAuthSession]:
        return self.sessions.get(f"state:{state}")

    async def exchange_code_for_token(
        self, session: OAuthSession, code: str
    ) -> bool:
        """Exchange an authorization code for access + refresh tokens.

        Args:
            session: The OAuth session.
            code: The authorization code from the callback.

        Returns:
            True if token exchange succeeded.
        """
        import aiohttp as aiohttp_lib

        if session.callback_mode == "direct":
            redirect_uri = f"{self.sidecar_base_url}/oauth/callback"
        else:
            redirect_uri = f"{self.sidecar_base_url}/oauth/code-display"

        token_data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }

        try:
            async with aiohttp_lib.ClientSession() as http_session:
                async with http_session.post(
                    TOKEN_URL,
                    json=token_data,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(
                            f"Token exchange failed ({resp.status}): {error_text}"
                        )
                        session.status = "error"
                        session.error = f"Token exchange failed: {error_text}"
                        return False

                    token_resp = await resp.json()

            session.access_token = token_resp.get("access_token")
            session.refresh_token = token_resp.get("refresh_token")
            expires_in = token_resp.get("expires_in", 3600)
            session.token_expiry = time.time() + expires_in
            session.authorization_code = code
            session.status = "token_acquired"

            logger.info(
                f"OAuth session {session.session_id}: token acquired "
                f"(expires in {expires_in}s)"
            )

            # Optionally fetch accessible resources to get cloud_id
            await self._fetch_cloud_id(session, http_session=None)

            return True

        except Exception as e:
            logger.exception(f"Token exchange error: {e}")
            session.status = "error"
            session.error = str(e)
            return False

    async def _fetch_cloud_id(
        self, session: OAuthSession, http_session=None
    ):
        """Fetch the cloud ID for the authenticated user's site."""
        import aiohttp as aiohttp_lib

        try:
            async with aiohttp_lib.ClientSession() as hs:
                async with hs.get(
                    ACCESSIBLE_RESOURCES_URL,
                    headers={
                        "Authorization": f"Bearer {session.access_token}",
                        "Accept": "application/json",
                    },
                ) as resp:
                    if resp.status == 200:
                        resources = await resp.json()
                        if resources:
                            session.cloud_id = resources[0].get("id")
                            logger.info(
                                f"Cloud ID: {session.cloud_id} "
                                f"({resources[0].get('name', 'unknown')})"
                            )
        except Exception as e:
            logger.warning(f"Failed to fetch cloud ID: {e}")

    def get_auth_instructions(self, session: OAuthSession) -> dict:
        """Get user-facing instructions with the Atlassian auth URL."""
        instructions = {
            "session_id": session.session_id,
            "target_url": session.target_url,
            "auth_url": session.auth_url,
            "callback_mode": session.callback_mode,
            "expires_in_seconds": int(session.expires_at - time.time()),
        }

        if session.callback_mode == "manual":
            instructions["steps"] = [
                "1. Click the auth URL below (works from any device/browser)",
                "2. Log in with your Atlassian account (SSO/MFA supported)",
                "3. Grant access when prompted",
                "4. You'll see an authorization code — copy it",
                f"5. Send the code back: POST {self.sidecar_base_url}/oauth/code",
            ]
        else:
            instructions["steps"] = [
                "1. Click the auth URL below (works from any device/browser)",
                "2. Log in with your Atlassian account (SSO/MFA supported)",
                "3. Grant access when prompted",
                "4. The callback will be handled automatically",
            ]

        return instructions


# ── HTTP Handlers ─────────────────────────────────────────────────────────────

_oauth_manager: Optional[OAuthManager] = None


async def oauth_start_handler(request: web.Request) -> web.Response:
    """Start an OAuth authentication flow.

    POST /oauth/start
    Body: {
        "target_url": "https://hello.atlassian.net/wiki",
        "callback_mode": "manual",  // or "direct"
        "ttl": 600
    }

    Returns the Atlassian auth URL that can be pasted ANYWHERE.
    """
    global _oauth_manager

    if not _oauth_manager or not _oauth_manager.is_configured:
        return web.json_response({
            "ok": False,
            "error": "OAuth not configured. Set ATLASSIAN_OAUTH_CLIENT_ID and ATLASSIAN_OAUTH_CLIENT_SECRET.",
            "setup_instructions": {
                "step_1": "Go to https://developer.atlassian.com/console/myapps/",
                "step_2": "Create an OAuth 2.0 (3LO) app",
                "step_3": "Add callback URL: http://localhost:18800/oauth/callback",
                "step_4": "Set ATLASSIAN_OAUTH_CLIENT_ID and ATLASSIAN_OAUTH_CLIENT_SECRET",
            },
        }, status=400)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"}, status=400
        )

    target_url = body.get("target_url")
    if not target_url:
        return web.json_response(
            {"ok": False, "error": "Missing 'target_url'"}, status=400
        )

    callback_mode = body.get("callback_mode", "manual")
    ttl = body.get("ttl", 600)

    session = _oauth_manager.create_auth_session(
        target_url=target_url,
        callback_mode=callback_mode,
        ttl=ttl,
    )

    instructions = _oauth_manager.get_auth_instructions(session)

    return web.json_response({
        "ok": True,
        "oauth_session": session.to_dict(),
        "instructions": instructions,
        "message": (
            "🔐 Share this Atlassian auth URL with the user. "
            "It works from any device or browser."
        ),
    })


async def oauth_callback_handler(request: web.Request) -> web.Response:
    """Handle OAuth callback from Atlassian (direct mode).

    GET /oauth/callback?code=xxx&state=yyy

    Atlassian redirects here after user authenticates.
    """
    global _oauth_manager

    code = request.query.get("code")
    state = request.query.get("state")
    error = request.query.get("error")

    if error:
        return web.Response(
            text=f"<h1>Authentication Failed</h1><p>Error: {error}</p>",
            content_type="text/html",
        )

    if not code or not state:
        return web.Response(
            text="<h1>Error: Missing code or state</h1>",
            content_type="text/html",
            status=400,
        )

    session = _oauth_manager.get_session_by_state(state)
    if not session:
        return web.Response(
            text="<h1>Error: Invalid or expired session</h1>",
            content_type="text/html",
            status=400,
        )

    # Exchange code for token
    success = await _oauth_manager.exchange_code_for_token(session, code)

    if success:
        return web.Response(
            text=(
                "<html><body style='font-family:sans-serif;text-align:center;padding:50px;background:#0d1117;color:#c9d1d9'>"
                "<h1 style='color:#3fb950'>✅ Authentication Successful!</h1>"
                "<p>Tokens acquired. The remote browser is being configured.</p>"
                "<p>You can close this tab.</p>"
                "</body></html>"
            ),
            content_type="text/html",
        )
    else:
        return web.Response(
            text=(
                f"<html><body style='font-family:sans-serif;text-align:center;padding:50px;background:#0d1117;color:#c9d1d9'>"
                f"<h1 style='color:#f85149'>❌ Token Exchange Failed</h1>"
                f"<p>{session.error}</p>"
                f"</body></html>"
            ),
            content_type="text/html",
            status=500,
        )


async def oauth_code_display_handler(request: web.Request) -> web.Response:
    """Display the auth code for manual copy-paste (manual mode).

    GET /oauth/code-display?code=xxx&state=yyy

    This page is shown after authentication. It displays the code
    so the user can copy it and paste it via API/Slack/CLI.
    """
    code = request.query.get("code", "")
    state = request.query.get("state", "")
    error = request.query.get("error")

    if error:
        return web.Response(
            text=f"<h1>Authentication Failed</h1><p>{error}</p>",
            content_type="text/html",
        )

    # Also try to auto-exchange if we can find the session
    session = _oauth_manager.get_session_by_state(state) if state else None
    auto_exchanged = False
    if session and code:
        auto_exchanged = await _oauth_manager.exchange_code_for_token(session, code)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
body {{ font-family: -apple-system, sans-serif; background: #0d1117; color: #c9d1d9;
       display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
.container {{ max-width: 500px; background: #161b22; border: 1px solid #30363d;
             border-radius: 12px; padding: 40px; text-align: center; }}
h1 {{ color: #3fb950; font-size: 22px; }}
.code {{ background: #0d1117; border: 2px solid #238636; border-radius: 8px;
         padding: 16px; font-family: monospace; font-size: 18px; color: #58a6ff;
         word-break: break-all; margin: 20px 0; cursor: pointer; user-select: all; }}
.info {{ color: #8b949e; font-size: 13px; margin-top: 16px; }}
.auto {{ color: #3fb950; margin-top: 12px; }}
</style></head><body>
<div class="container">
    <h1>✅ Authentication Successful!</h1>
    {"<p class='auto'>✅ Token automatically acquired — the remote browser is being configured. You can close this tab.</p>" if auto_exchanged else f'''
    <p>Your authorization code:</p>
    <div class="code" onclick="navigator.clipboard.writeText(this.textContent).then(()=>this.style.borderColor='#3fb950')">{code}</div>
    <p class="info">Click the code to copy it, then paste it back to complete authentication.</p>
    <p class="info">Or use: <code>curl -X POST {_oauth_manager.sidecar_base_url}/oauth/code -H "Content-Type: application/json" -d '{{"session_id":"{session.session_id if session else "YOUR_SESSION_ID"}","code":"{code}"}}'</code></p>
    '''}
</div></body></html>"""

    return web.Response(text=html, content_type="text/html")


async def oauth_code_submit_handler(request: web.Request) -> web.Response:
    """Manually submit an authorization code (manual mode).

    POST /oauth/code
    Body: {"session_id": "xxx", "code": "yyy"}

    Used when the user copies the code from the code-display page
    and pastes it back via API.
    """
    global _oauth_manager

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"}, status=400
        )

    session_id = body.get("session_id")
    code = body.get("code")

    if not session_id or not code:
        return web.json_response(
            {"ok": False, "error": "Missing session_id or code"}, status=400
        )

    session = _oauth_manager.get_session(session_id)
    if not session:
        return web.json_response(
            {"ok": False, "error": "Session not found"}, status=404
        )

    if session.has_token:
        return web.json_response({
            "ok": True,
            "message": "Token already acquired",
            "oauth_session": session.to_dict(),
        })

    success = await _oauth_manager.exchange_code_for_token(session, code)

    if success:
        return web.json_response({
            "ok": True,
            "message": "Token acquired successfully",
            "oauth_session": session.to_dict(),
        })
    else:
        return web.json_response({
            "ok": False,
            "error": session.error or "Token exchange failed",
        }, status=500)


async def oauth_status_handler(request: web.Request) -> web.Response:
    """Check OAuth session status.

    GET /oauth/status?session_id=xxx
    """
    session_id = request.query.get("session_id")
    if not session_id:
        return web.json_response(
            {"ok": False, "error": "Missing session_id"}, status=400
        )

    session = _oauth_manager.get_session(session_id)
    if not session:
        return web.json_response(
            {"ok": False, "error": "Session not found"}, status=404
        )

    return web.json_response({
        "ok": True,
        "oauth_session": session.to_dict(),
    })


async def oauth_poll_handler(request: web.Request) -> web.Response:
    """Poll until OAuth token is acquired.

    POST /oauth/poll
    Body: {"session_id": "xxx", "timeout": 300}

    Blocks until the user completes authentication and token is acquired.
    """
    global _oauth_manager

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON"}, status=400
        )

    session_id = body.get("session_id")
    timeout = body.get("timeout", 300)

    session = _oauth_manager.get_session(session_id)
    if not session:
        return web.json_response(
            {"ok": False, "error": "Session not found"}, status=404
        )

    start = asyncio.get_event_loop().time()
    while not session.has_token and not session.is_expired and session.status != "error":
        elapsed = asyncio.get_event_loop().time() - start
        if elapsed > timeout:
            return web.json_response({
                "ok": False, "error": "Timeout waiting for authentication",
            }, status=408)
        await asyncio.sleep(2)

    if session.has_token:
        return web.json_response({
            "ok": True,
            "message": "Token acquired",
            "oauth_session": session.to_dict(),
        })
    elif session.status == "error":
        return web.json_response({
            "ok": False, "error": session.error,
        }, status=500)
    else:
        return web.json_response({
            "ok": False, "error": "Session expired",
        }, status=410)


# ── Route Registration ────────────────────────────────────────────────────────


def setup_oauth_routes(
    app: web.Application,
    sidecar_base_url: str = "http://localhost:18800",
) -> OAuthManager:
    """Register OAuth authentication routes.

    Args:
        app: The aiohttp application.
        sidecar_base_url: Public URL of this sidecar.

    Returns:
        OAuthManager instance.
    """
    global _oauth_manager

    client_id = os.getenv("ATLASSIAN_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv("ATLASSIAN_OAUTH_CLIENT_SECRET", "")
    scopes_str = os.getenv("ATLASSIAN_OAUTH_SCOPES", "")
    scopes = scopes_str.split() if scopes_str else None

    _oauth_manager = OAuthManager(
        client_id=client_id,
        client_secret=client_secret,
        sidecar_base_url=sidecar_base_url,
        scopes=scopes,
    )

    app.router.add_post("/oauth/start", oauth_start_handler)
    app.router.add_get("/oauth/callback", oauth_callback_handler)
    app.router.add_get("/oauth/code-display", oauth_code_display_handler)
    app.router.add_post("/oauth/code", oauth_code_submit_handler)
    app.router.add_get("/oauth/status", oauth_status_handler)
    app.router.add_post("/oauth/poll", oauth_poll_handler)

    if _oauth_manager.is_configured:
        logger.info("OAuth routes registered (client_id configured ✅)")
    else:
        logger.warning(
            "OAuth routes registered but NOT configured. "
            "Set ATLASSIAN_OAUTH_CLIENT_ID and ATLASSIAN_OAUTH_CLIENT_SECRET."
        )

    return _oauth_manager
