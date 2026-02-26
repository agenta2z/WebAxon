"""End-to-end test: Real service + knowledge ingestion + agent request.

1. Starts WebAgentService in a daemon thread
2. Registers Tony Chen knowledge via /add (real Claude API)
3. Sends agent request: "check egg prices on safeway"
4. Waits for agent response
5. Shuts down
"""
import sys
import resolve_path  # Setup import paths

import json
import shutil
import signal
import threading
import time
from pathlib import Path

from rich_python_utils.datetime_utils.common import timestamp as ts

from webaxon.devsuite.web_agent_service_nextgen.service import WebAgentService
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.cli.client import CLIClient
from webaxon.devsuite.constants import (
    INPUT_QUEUE_ID,
    RESPONSE_QUEUE_ID,
    CLIENT_CONTROL_QUEUE_ID,
    SERVER_CONTROL_QUEUE_ID,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Use the real devsuite testcase root (persistent knowledge store)
TESTCASE_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "src" / "webaxon" / "devsuite"

FREE_TEXT = """Name: Tony Chen
Location 2801 Western Ave, Seattle, WA, 98121
Family: wife
child born Dec 29, 2023
Frequent Grocery Stores:
Safeway - member tzchen86@gmail.com, google log in
QFC - member tzchen86@gmail.com
Whole Foods - prime member tuf72841@temple.edu

Grocery store skills:
1 - Login first if user is a member to apply member pricing and discounts
2 - Find right store and location first before further operations
3 - Must add items to cart, and apply all coupons, and check out to view final price"""

AGENT_REQUEST = "what is the organic egg price in safeway right now"

SESSION_ID = "e2e_test"


def main():
    print("=" * 80)
    print("END-TO-END TEST: Knowledge Ingestion + Agent Request")
    print("=" * 80)
    print(f"Testcase root: {TESTCASE_ROOT}")

    # Clean up transient runtime data (queues, logs) but preserve knowledge_store
    runtime_dir = TESTCASE_ROOT / "_runtime"
    if runtime_dir.exists():
        for subdir_name in ("queues", "service_logs"):
            subdir = runtime_dir / subdir_name
            if subdir.exists():
                print(f"  Cleaning up {subdir}")
                shutil.rmtree(str(subdir), ignore_errors=True)

    # Snapshot existing queue dirs (stale ones that cleanup couldn't delete)
    queues_base = TESTCASE_ROOT / "_runtime" / "queues"
    stale_dirs = set()
    if queues_base.exists():
        stale_dirs = {d.name for d in queues_base.iterdir() if d.is_dir()}
        if stale_dirs:
            print(f"  (stale queue dirs that couldn't be deleted: {stale_dirs})")

    # Create service config (async agent — runs in its own thread)
    config = ServiceConfig(
        synchronous_agent=False,
        debug_mode_service=True,
        new_agent_on_first_submission=True,
        session_idle_timeout=1800,
        cleanup_check_interval=300,
    )

    # Create and start service in a daemon thread
    service = WebAgentService(TESTCASE_ROOT, config)
    service_thread = threading.Thread(target=service.run, daemon=True, name="service")
    service_thread.start()

    # Wait for service to initialize (queue dirs created)
    # Only look for NEW directories (not stale ones from previous runs)
    print("Waiting for service to start...")
    deadline = time.time() + 15
    queue_root_path = None
    while time.time() < deadline:
        if queues_base.exists():
            new_dirs = [
                d for d in queues_base.iterdir()
                if d.is_dir() and d.name not in stale_dirs
            ]
            if new_dirs:
                queue_root_path = max(new_dirs, key=lambda d: d.name)
                break
        time.sleep(0.5)

    if queue_root_path is None:
        print("[FATAL] Service did not create queue directory in time")
        return

    print(f"Service started. Queue root: {queue_root_path}")
    time.sleep(1)  # Give the service a moment to fully initialize

    # Create CLI client
    cli = CLIClient(
        TESTCASE_ROOT,
        session_id=SESSION_ID,
        queue_root_path=queue_root_path,
    )
    connected = cli.connect()
    if not connected:
        print("[FATAL] CLI failed to connect")
        return

    # -----------------------------------------------------------------------
    # Step 1: Register knowledge (skip if already ingested)
    # -----------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("STEP 1: Registering knowledge via /add (real Claude API)")
    print("-" * 80)

    # Check if the same knowledge text was already ingested
    already_ingested = False
    ingestion_logs_dir = TESTCASE_ROOT / "_runtime" / "knowledge_store" / "ingestion_logs"
    if ingestion_logs_dir.exists():
        for raw_input_file in ingestion_logs_dir.rglob("raw_input.txt"):
            try:
                existing_text = raw_input_file.read_text(encoding="utf-8")
                if existing_text.strip() == FREE_TEXT.strip():
                    already_ingested = True
                    print(f"  [SKIP] Same knowledge already ingested ({raw_input_file.parent.name})")
                    break
            except Exception:
                continue

    if not already_ingested:
        t0 = time.time()
        cli.register_knowledge(FREE_TEXT)
        print(f"  (took {time.time() - t0:.1f}s)")

    # Verify on disk
    pieces_dir = TESTCASE_ROOT / "_runtime" / "knowledge_store" / "pieces"
    if pieces_dir.exists():
        piece_files = list(pieces_dir.rglob("*.json"))
        print(f"  Pieces on disk: {len(piece_files)}")
    else:
        print("  [WARN] No pieces directory yet")

    # -----------------------------------------------------------------------
    # Step 2: Set template version to end_customers
    # -----------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("STEP 2: Setting template version to 'end_customers'")
    print("-" * 80)
    cli.set_template_version("end_customers")

    # -----------------------------------------------------------------------
    # Step 3: Send agent request
    # -----------------------------------------------------------------------
    print("\n" + "-" * 80)
    print(f"STEP 3: Sending agent request: \"{AGENT_REQUEST}\"")
    print("-" * 80)
    print("  (Agent will open a browser, navigate to Safeway, and look for egg prices)")
    print("  (This may take several minutes...)")
    print()

    t0 = time.time()
    cli.send_agent_request(AGENT_REQUEST, timeout=600.0)
    print(f"\n  (agent request took {time.time() - t0:.1f}s)")

    # -----------------------------------------------------------------------
    # Shutdown
    # -----------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("Shutting down service...")
    service._shutdown_requested = True
    service_thread.join(timeout=10)
    print("Done.")


if __name__ == "__main__":
    main()
