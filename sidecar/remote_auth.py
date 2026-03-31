"""Remote Authentication Module for WebAxon Browser Sidecar.

This module enables a headless browser running in Docker to authenticate
to internal websites (e.g., Atlassian with Okta SSO) by delegating
authentication to the user's local browser.

Flow:
1. WebAxon detects an auth wall (login redirect, 401, etc.)
2. Generates a unique auth session with a token
3. Returns a URL for the user to visit on their local machine
4. User authenticates normally (SSO, MFA, etc.) on that site
5. User clicks a bookmarklet or visits the auth relay page to export cookies
6. Cookies are sent back to WebAxon sidecar via the relay endpoint
7. WebAxon injects cookies into the headless browser
8. Navigation resumes with full authentication

Architecture:
    ┌─────────────────────────────────────────────────┐
    │  Docker Container (WebAxon Sidecar :18800)      │
    │                                                  │
    │  POST /auth/request  → create auth session       │
    │  GET  /auth/status   → poll for completion       │
    │  POST /auth/cookies  → receive cookies from user │
    │  GET  /auth/relay    → serve the relay HTML page │
    │  POST /auth/inject   → inject cookies to browser │
    └─────────────────────────────────────────────────┘
"""

import asyncio
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from aiohttp import web

logger = logging.getLogger(__name__)


# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class AuthSession:
    """Represents a pending remote authentication request."""

    session_id: str
    token: str  # Secret token for this session
    target_url: str  # The URL that needs authentication
    target_domain: str  # Domain to capture cookies for
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    status: str = "pending"  # pending | completed | expired | failed
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    completed_at: Optional[float] = None

    def __post_init__(self):
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + 600  # 10 minute expiry

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "target_url": self.target_url,
            "target_domain": self.target_domain,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "completed_at": self.completed_at,
            "has_cookies": len(self.cookies) > 0,
            "cookie_count": len(self.cookies),
        }


class AuthSessionManager:
    """Manages remote authentication sessions."""

    def __init__(self, sidecar_base_url: str = "http://localhost:18800"):
        self.sessions: Dict[str, AuthSession] = {}
        self.sidecar_base_url = sidecar_base_url
        self._cleanup_interval = 300  # 5 min cleanup

    def create_session(self, target_url: str, ttl: int = 600) -> AuthSession:
        """Create a new authentication session.

        Args:
            target_url: The URL requiring authentication.
            ttl: Time-to-live in seconds (default 10 minutes).

        Returns:
            AuthSession with unique ID and token.
        """
        self._cleanup_expired()

        session_id = secrets.token_urlsafe(16)
        token = secrets.token_urlsafe(32)
        parsed = urlparse(target_url)
        domain = parsed.hostname or parsed.netloc

        session = AuthSession(
            session_id=session_id,
            token=token,
            target_url=target_url,
            target_domain=domain,
            expires_at=time.time() + ttl,
        )
        self.sessions[session_id] = session

        logger.info(
            f"Created auth session {session_id} for domain {domain} "
            f"(expires in {ttl}s)"
        )
        return session

    def get_session(self, session_id: str) -> Optional[AuthSession]:
        """Get a session by ID, returning None if expired."""
        session = self.sessions.get(session_id)
        if session and session.is_expired:
            session.status = "expired"
        return session

    def complete_session(
        self, session_id: str, token: str, cookies: List[Dict[str, Any]]
    ) -> bool:
        """Complete an auth session with received cookies.

        Args:
            session_id: The session ID.
            token: The secret token (must match).
            cookies: List of cookie dicts from the user's browser.

        Returns:
            True if session was completed successfully.
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"Auth session {session_id} not found")
            return False

        if session.is_expired:
            logger.warning(f"Auth session {session_id} has expired")
            return False

        if not secrets.compare_digest(session.token, token):
            logger.warning(f"Auth session {session_id} token mismatch")
            return False

        if session.status == "completed":
            logger.info(f"Auth session {session_id} already completed")
            return True

        session.cookies = cookies
        session.status = "completed"
        session.completed_at = time.time()

        logger.info(
            f"Auth session {session_id} completed with {len(cookies)} cookies"
        )
        return True

    def get_relay_url(self, session: AuthSession) -> str:
        """Get the URL for the user to visit to relay cookies."""
        return (
            f"{self.sidecar_base_url}/auth/relay"
            f"?session_id={session.session_id}"
            f"&token={session.token}"
            f"&domain={session.target_domain}"
        )

    def get_auth_instructions(self, session: AuthSession) -> dict:
        """Get user-facing instructions for completing authentication."""
        relay_url = self.get_relay_url(session)
        return {
            "session_id": session.session_id,
            "target_url": session.target_url,
            "target_domain": session.target_domain,
            "steps": [
                f"1. Open your browser and log into: {session.target_url}",
                "2. Once logged in, open a new tab and visit the relay URL below",
                "3. The relay page will automatically capture and send your cookies",
                "4. You can close the relay tab once it says 'Success'",
            ],
            "relay_url": relay_url,
            "expires_in_seconds": int(session.expires_at - time.time()),
        }

    def _cleanup_expired(self):
        """Remove expired sessions."""
        expired = [
            sid for sid, s in self.sessions.items()
            if s.is_expired and s.status != "completed"
        ]
        for sid in expired:
            del self.sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired auth sessions")


# ── Auth Detection ────────────────────────────────────────────────────────────

# Common patterns that indicate an authentication wall
AUTH_WALL_INDICATORS = [
    # URL patterns
    "login", "signin", "sign-in", "sign_in", "sso", "oauth",
    "authenticate", "auth/realms", "okta.com", "auth0.com",
    "microsoftonline.com/common/oauth", "accounts.google.com",
    "id.atlassian.com",
    # Page content patterns
    "Enter your password", "Sign in to continue",
    "Log in to your account", "Authentication required",
]


def detect_auth_wall(current_url: str, page_title: str = "") -> bool:
    """Detect if the current page is an authentication/login page.

    Args:
        current_url: The current browser URL.
        page_title: The current page title.

    Returns:
        True if the page appears to be a login/auth page.
    """
    check_text = (current_url + " " + page_title).lower()
    return any(indicator.lower() in check_text for indicator in AUTH_WALL_INDICATORS)


# ── HTTP Handlers ─────────────────────────────────────────────────────────────

# Global auth manager - initialized by setup_auth_routes()
_auth_manager: Optional[AuthSessionManager] = None


async def auth_request_handler(request: web.Request) -> web.Response:
    """Create a new remote authentication request.

    POST /auth/request
    Body: {"target_url": "https://hello.atlassian.net/wiki", "ttl": 600}

    Returns:
        JSON with auth session details and relay URL for the user.
    """
    global _auth_manager

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"}, status=400
        )

    target_url = body.get("target_url")
    if not target_url:
        return web.json_response(
            {"ok": False, "error": "Missing 'target_url' field"}, status=400
        )

    ttl = body.get("ttl", 600)
    session = _auth_manager.create_session(target_url, ttl=ttl)
    instructions = _auth_manager.get_auth_instructions(session)

    return web.json_response({
        "ok": True,
        "auth_session": session.to_dict(),
        "instructions": instructions,
    })


async def auth_status_handler(request: web.Request) -> web.Response:
    """Check the status of an auth session.

    GET /auth/status?session_id=xxx

    Returns:
        JSON with session status (pending/completed/expired).
    """
    global _auth_manager

    session_id = request.query.get("session_id")
    if not session_id:
        return web.json_response(
            {"ok": False, "error": "Missing 'session_id' parameter"}, status=400
        )

    session = _auth_manager.get_session(session_id)
    if not session:
        return web.json_response(
            {"ok": False, "error": "Session not found"}, status=404
        )

    return web.json_response({
        "ok": True,
        "auth_session": session.to_dict(),
    })


async def auth_cookies_handler(request: web.Request) -> web.Response:
    """Receive cookies from the user's browser.

    POST /auth/cookies
    Body: {
        "session_id": "xxx",
        "token": "yyy",
        "cookies": [{"name": "...", "value": "...", "domain": "...", ...}]
    }

    This endpoint is called by the relay page running in the user's browser.
    CORS headers are set to allow cross-origin requests from the user's browser.
    """
    global _auth_manager

    # Handle CORS preflight
    if request.method == "OPTIONS":
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "3600",
            },
        )

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"},
            status=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    session_id = body.get("session_id")
    token = body.get("token")
    cookies = body.get("cookies", [])

    if not session_id or not token:
        return web.json_response(
            {"ok": False, "error": "Missing session_id or token"},
            status=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    success = _auth_manager.complete_session(session_id, token, cookies)

    if success:
        return web.json_response(
            {"ok": True, "message": f"Received {len(cookies)} cookies"},
            headers={"Access-Control-Allow-Origin": "*"},
        )
    else:
        return web.json_response(
            {"ok": False, "error": "Failed to complete session (expired or invalid token)"},
            status=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )


async def auth_inject_handler(request: web.Request) -> web.Response:
    """Inject received cookies into the headless browser.

    POST /auth/inject
    Body: {"session_id": "xxx"}

    This injects the cookies from a completed auth session into the
    headless browser, enabling authenticated browsing.
    """
    global _auth_manager

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"ok": False, "error": "Invalid JSON body"}, status=400
        )

    session_id = body.get("session_id")
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

    # The actual injection is done by the caller (server.py)
    # We just return the cookies to inject
    return web.json_response({
        "ok": True,
        "cookies": session.cookies,
        "target_domain": session.target_domain,
        "target_url": session.target_url,
        "cookie_count": len(session.cookies),
    })


async def auth_relay_handler(request: web.Request) -> web.Response:
    """Serve the cookie relay HTML page.

    GET /auth/relay?session_id=xxx&token=yyy&domain=zzz

    This serves a self-contained HTML page that the user opens in their
    local browser. The page:
    1. Reads cookies for the specified domain using document.cookie
    2. Sends them back to the sidecar via POST /auth/cookies
    3. Shows success/failure status
    """
    session_id = request.query.get("session_id", "")
    token = request.query.get("token", "")
    domain = request.query.get("domain", "")

    # Validate session exists
    if _auth_manager:
        session = _auth_manager.get_session(session_id)
        if not session:
            return web.Response(
                text="<h1>Error: Invalid or expired session</h1>",
                content_type="text/html",
                status=404,
            )

    html = _generate_relay_html(session_id, token, domain, request.host)
    return web.Response(text=html, content_type="text/html")


def _generate_relay_html(
    session_id: str, token: str, domain: str, sidecar_host: str
) -> str:
    """Generate the self-contained relay HTML page."""
    # Determine the sidecar URL based on the request
    # If accessed via localhost or IP, use that; otherwise construct from host
    if ":" in sidecar_host:
        sidecar_url = f"http://{sidecar_host}"
    else:
        sidecar_url = f"http://{sidecar_host}:18800"

    return RELAY_HTML_TEMPLATE.replace("{{SESSION_ID}}", session_id).replace(
        "{{TOKEN}}", token
    ).replace("{{DOMAIN}}", domain).replace("{{SIDECAR_URL}}", sidecar_url)


# ── Route Registration ────────────────────────────────────────────────────────


def setup_auth_routes(
    app: web.Application, sidecar_base_url: str = "http://localhost:18800"
) -> AuthSessionManager:
    """Register authentication routes on the aiohttp app.

    Args:
        app: The aiohttp application.
        sidecar_base_url: The base URL of this sidecar (for generating relay URLs).

    Returns:
        The AuthSessionManager instance.
    """
    global _auth_manager
    _auth_manager = AuthSessionManager(sidecar_base_url=sidecar_base_url)

    # Auth endpoints
    app.router.add_post("/auth/request", auth_request_handler)
    app.router.add_get("/auth/status", auth_status_handler)
    app.router.add_post("/auth/cookies", auth_cookies_handler)
    app.router.add_options("/auth/cookies", auth_cookies_handler)  # CORS preflight
    app.router.add_post("/auth/inject", auth_inject_handler)
    app.router.add_get("/auth/relay", auth_relay_handler)

    logger.info("Remote authentication routes registered")
    return _auth_manager


# ── Relay HTML Template ───────────────────────────────────────────────────────

RELAY_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WebAxon Auth Relay</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1117; color: #c9d1d9;
    display: flex; justify-content: center; align-items: center;
    min-height: 100vh; padding: 20px;
}
.container {
    max-width: 600px; width: 100%;
    background: #161b22; border: 1px solid #30363d;
    border-radius: 12px; padding: 40px;
}
h1 { color: #58a6ff; margin-bottom: 8px; font-size: 24px; }
.subtitle { color: #8b949e; margin-bottom: 24px; }
.status {
    padding: 16px; border-radius: 8px; margin: 16px 0;
    font-size: 14px; line-height: 1.6;
}
.status.pending { background: #1c2333; border: 1px solid #1f6feb; }
.status.success { background: #0d2818; border: 1px solid #238636; color: #3fb950; }
.status.error { background: #2d1117; border: 1px solid #f85149; color: #f85149; }
.steps { margin: 20px 0; }
.steps li { margin: 8px 0; padding: 4px 0; color: #c9d1d9; }
.steps li.done { color: #3fb950; }
.steps li.active { color: #58a6ff; font-weight: bold; }
.domain-badge {
    display: inline-block; background: #1f6feb; color: white;
    padding: 4px 12px; border-radius: 20px; font-size: 13px;
    margin: 8px 0;
}
button {
    background: #238636; color: white; border: none;
    padding: 12px 24px; border-radius: 8px; font-size: 16px;
    cursor: pointer; width: 100%; margin-top: 16px;
}
button:hover { background: #2ea043; }
button:disabled { background: #21262d; color: #484f58; cursor: not-allowed; }
.spinner {
    display: inline-block; width: 16px; height: 16px;
    border: 2px solid #30363d; border-top-color: #58a6ff;
    border-radius: 50%; animation: spin 0.8s linear infinite;
    vertical-align: middle; margin-right: 8px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.cookie-info { font-size: 12px; color: #8b949e; margin-top: 12px; }
</style>
</head>
<body>
<div class="container">
    <h1>🔐 WebAxon Auth Relay</h1>
    <p class="subtitle">Securely transfer your authentication to the remote browser</p>
    <div class="domain-badge">Domain: {{DOMAIN}}</div>

    <ol class="steps" id="steps">
        <li id="step1" class="active">Checking authentication status...</li>
        <li id="step2">Capture cookies for {{DOMAIN}}</li>
        <li id="step3">Send cookies to WebAxon sidecar</li>
        <li id="step4">Verification</li>
    </ol>

    <div class="status pending" id="statusBox">
        <span class="spinner"></span>
        Preparing cookie capture...
    </div>

    <button id="captureBtn" onclick="startCapture()" disabled>
        Capture & Send Cookies
    </button>

    <div class="cookie-info" id="cookieInfo"></div>
</div>

<script>
const CONFIG = {
    sessionId: "{{SESSION_ID}}",
    token: "{{TOKEN}}",
    domain: "{{DOMAIN}}",
    sidecarUrl: "{{SIDECAR_URL}}"
};

function updateStep(stepNum, status) {
    for (let i = 1; i <= 4; i++) {
        const el = document.getElementById('step' + i);
        el.className = i < stepNum ? 'done' :
                       i === stepNum ? (status || 'active') : '';
    }
}

function setStatus(type, message) {
    const box = document.getElementById('statusBox');
    box.className = 'status ' + type;
    box.innerHTML = message;
}

// Method 1: Use document.cookie (works for non-HttpOnly cookies)
function getDocumentCookies() {
    const cookies = [];
    if (document.cookie) {
        document.cookie.split(';').forEach(c => {
            const [name, ...rest] = c.trim().split('=');
            cookies.push({
                name: name.trim(),
                value: rest.join('='),
                domain: window.location.hostname,
                path: '/',
                secure: window.location.protocol === 'https:',
            });
        });
    }
    return cookies;
}

// Method 2: Manual cookie entry (fallback for HttpOnly cookies)
function promptForCookies() {
    const input = prompt(
        'HttpOnly cookies cannot be read by JavaScript.\n\n' +
        'To get ALL cookies (including HttpOnly):\n' +
        '1. Open DevTools (F12)\n' +
        '2. Go to Application → Cookies\n' +
        '3. Copy all cookies for ' + CONFIG.domain + '\n\n' +
        'Or paste cookie header value (from Network tab):'
    );
    if (!input) return [];

    // Parse "name1=val1; name2=val2" format
    return input.split(';').map(c => {
        const [name, ...rest] = c.trim().split('=');
        return {
            name: name.trim(),
            value: rest.join('='),
            domain: CONFIG.domain,
            path: '/',
        };
    }).filter(c => c.name);
}

async function startCapture() {
    const btn = document.getElementById('captureBtn');
    btn.disabled = true;
    btn.textContent = 'Capturing...';

    try {
        // Step 2: Capture cookies
        updateStep(2);
        setStatus('pending', '<span class="spinner"></span> Capturing cookies...');

        let cookies = getDocumentCookies();
        const info = document.getElementById('cookieInfo');

        if (cookies.length === 0) {
            setStatus('pending',
                'No cookies found via document.cookie.<br>' +
                'This is normal — most auth cookies are HttpOnly.<br><br>' +
                '<b>Use the DevTools method instead:</b><br>' +
                '1. On the target site tab, press F12<br>' +
                '2. Go to Application → Storage → Cookies<br>' +
                '3. Right-click → "Copy all as HAR"<br>' +
                'Or use the manual entry option below.'
            );
            cookies = promptForCookies();
        }

        if (cookies.length === 0) {
            setStatus('error', '❌ No cookies captured. Please try again.');
            btn.disabled = false;
            btn.textContent = 'Retry Capture';
            return;
        }

        info.textContent = `Captured ${cookies.length} cookie(s)`;

        // Step 3: Send to sidecar
        updateStep(3);
        setStatus('pending', '<span class="spinner"></span> Sending cookies to WebAxon...');

        const response = await fetch(CONFIG.sidecarUrl + '/auth/cookies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: CONFIG.sessionId,
                token: CONFIG.token,
                cookies: cookies
            })
        });

        const result = await response.json();

        if (result.ok) {
            // Step 4: Success
            updateStep(4, 'done');
            setStatus('success',
                '✅ Authentication transferred successfully!<br><br>' +
                `Sent ${cookies.length} cookie(s) to WebAxon.<br>` +
                'You can close this tab now.'
            );
            btn.textContent = '✅ Done!';
        } else {
            throw new Error(result.error || 'Unknown error');
        }

    } catch (err) {
        setStatus('error',
            '❌ Failed to send cookies: ' + err.message + '<br><br>' +
            'Make sure the WebAxon sidecar is running and accessible.'
        );
        btn.disabled = false;
        btn.textContent = 'Retry';
    }
}

// On page load, check if we can reach the sidecar
async function init() {
    updateStep(1);
    try {
        const resp = await fetch(CONFIG.sidecarUrl + '/auth/status?session_id=' + CONFIG.sessionId);
        const data = await resp.json();

        if (!data.ok) {
            setStatus('error', '❌ Invalid session. The auth request may have expired.');
            return;
        }

        if (data.auth_session.status === 'completed') {
            updateStep(4, 'done');
            setStatus('success', '✅ This session is already completed!');
            return;
        }

        updateStep(2);
        setStatus('pending',
            '📋 Ready to capture cookies.<br><br>' +
            '<b>Before clicking the button below:</b><br>' +
            '1. Open a new tab and go to: <code>' + CONFIG.domain + '</code><br>' +
            '2. Log in if not already logged in<br>' +
            '3. Come back to this tab and click the button'
        );
        document.getElementById('captureBtn').disabled = false;
        document.getElementById('captureBtn').textContent = 'Capture & Send Cookies';

    } catch (err) {
        setStatus('error',
            '❌ Cannot reach WebAxon sidecar at ' + CONFIG.sidecarUrl + '<br><br>' +
            'Error: ' + err.message + '<br><br>' +
            'The sidecar must be accessible from your browser. ' +
            'If running in Docker, ensure port 18800 is published.'
        );
    }
}

init();
</script>
</body>
</html>"""
