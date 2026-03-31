#!/usr/bin/env python3
"""
Remote Authentication Example for WebAxon Browser Sidecar.

This example demonstrates the full remote authentication flow:

1. An agent/script needs the headless browser to visit an internal site
2. The sidecar detects that authentication is required
3. It creates an auth session and provides a relay URL
4. The user opens the relay URL in their local browser, authenticates,
   and exports their cookies back to the sidecar
5. The sidecar injects the cookies into the headless browser
6. The headless browser can now access the internal site as the user

Usage:
    # Start the sidecar first:
    python -m CoreProjects.WebAxon.sidecar.server --port 18800

    # Then run this example:
    python CoreProjects/WebAxon/examples/remote_auth_example.py

    # Or use curl directly:
    # Step 1: Request auth
    curl -X POST http://localhost:18800/auth/request \\
        -H 'Content-Type: application/json' \\
        -d '{"target_url": "https://hello.atlassian.net/wiki"}'

    # Step 2: User authenticates via the relay URL (from step 1 response)

    # Step 3: Poll and inject (blocks until user completes auth)
    curl -X POST http://localhost:18800/auth/poll-and-inject \\
        -H 'Content-Type: application/json' \\
        -d '{"session_id": "<session_id_from_step_1>", "timeout": 300}'
"""

import asyncio
import json
import sys
import time

import aiohttp


SIDECAR_URL = "http://localhost:18800"


async def request_authentication(target_url: str) -> dict:
    """Request a new authentication session from the sidecar.

    Args:
        target_url: The internal URL that requires authentication.

    Returns:
        Dict with session details and relay URL.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SIDECAR_URL}/auth/request",
            json={"target_url": target_url, "ttl": 600},
        ) as resp:
            result = await resp.json()
            if not result.get("ok"):
                raise RuntimeError(f"Failed to create auth session: {result}")
            return result


async def poll_auth_status(session_id: str) -> dict:
    """Poll the authentication session status.

    Args:
        session_id: The auth session ID.

    Returns:
        Dict with session status.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{SIDECAR_URL}/auth/status",
            params={"session_id": session_id},
        ) as resp:
            return await resp.json()


async def inject_cookies(session_id: str) -> dict:
    """Inject cookies from a completed auth session into the browser.

    Args:
        session_id: The completed auth session ID.

    Returns:
        Dict with injection result.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SIDECAR_URL}/auth/inject-browser",
            json={"session_id": session_id, "navigate_after": True},
        ) as resp:
            return await resp.json()


async def poll_and_inject(session_id: str, timeout: int = 300) -> dict:
    """Wait for auth completion and auto-inject (convenience wrapper).

    This calls the sidecar's /auth/poll-and-inject endpoint which handles
    the full flow: waiting for the user → injecting cookies → navigating.

    Args:
        session_id: The auth session ID.
        timeout: Max seconds to wait for user authentication.

    Returns:
        Dict with final result.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SIDECAR_URL}/auth/poll-and-inject",
            json={"session_id": session_id, "timeout": timeout},
            timeout=aiohttp.ClientTimeout(total=timeout + 30),
        ) as resp:
            return await resp.json()


async def main():
    """Run the remote authentication example."""

    # The internal URL we want to visit
    target_url = "https://hello.atlassian.net/wiki"
    if len(sys.argv) > 1:
        target_url = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"  WebAxon Remote Authentication Example")
    print(f"{'='*60}\n")

    # Step 1: Request authentication
    print(f"🎯 Target URL: {target_url}\n")
    print("📡 Creating auth session...")

    try:
        auth_result = await request_authentication(target_url)
    except Exception as e:
        print(f"\n❌ Failed to create auth session: {e}")
        print(f"\nMake sure the WebAxon sidecar is running:")
        print(f"  python -m CoreProjects.WebAxon.sidecar.server --port 18800")
        return

    instructions = auth_result["instructions"]
    session_id = auth_result["auth_session"]["session_id"]

    # Step 2: Display instructions to user
    print(f"\n✅ Auth session created!\n")
    print(f"{'─'*60}")
    print(f"  🔐 AUTHENTICATION REQUIRED")
    print(f"{'─'*60}\n")

    for step in instructions["steps"]:
        print(f"  {step}")

    print(f"\n  📎 Relay URL:")
    print(f"  {instructions['relay_url']}\n")
    print(f"  ⏱️  Expires in: {instructions['expires_in_seconds']}s\n")
    print(f"{'─'*60}\n")

    # Method A: Use the Chrome extension for HttpOnly cookies
    print("💡 TIP: For best results, use the Chrome extension:")
    print("   1. Load CoreProjects/WebAxon/sidecar/cookie_export_extension/")
    print("      as an unpacked extension in Chrome (chrome://extensions)")
    print("   2. Log into the target site")
    print("   3. Click the extension icon")
    print(f"   4. Paste Session ID: {session_id}")
    print(f"   5. Paste Token: {auth_result['auth_session'].get('token', '(see relay URL)')}")
    print(f"   6. Click 'Export Cookies'\n")

    # Step 3: Wait for user to authenticate
    print("⏳ Waiting for authentication...")
    print("   (Press Ctrl+C to cancel)\n")

    try:
        result = await poll_and_inject(session_id, timeout=600)
    except asyncio.CancelledError:
        print("\n🚫 Cancelled by user.")
        return
    except KeyboardInterrupt:
        print("\n🚫 Cancelled by user.")
        return

    # Step 4: Show result
    if result.get("ok"):
        print(f"✅ Authentication successful!")
        print(f"   Cookies injected: {result.get('cookies_injected', 0)}")
        print(f"   Current URL: {result.get('current_url', 'unknown')}")
        print(f"   Page title: {result.get('page_title', 'unknown')}")
        if result.get("authenticated"):
            print(f"   Status: ✅ Authenticated (not on a login page)")
        else:
            print(f"   Status: ⚠️  May still need login")
            if result.get("warning"):
                print(f"   Warning: {result['warning']}")
    else:
        print(f"❌ Authentication failed: {result.get('error', 'unknown')}")


if __name__ == "__main__":
    asyncio.run(main())
