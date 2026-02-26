"""Manual test: Real Claude API knowledge ingestion (no mocks).

This script uses the same service_tick pattern as the integration tests,
but with a real ClaudeApiInferencer instead of MockIngestionInferencer.
It runs everything in a single process to avoid inter-process queue issues.
"""
import sys
import resolve_path  # Setup import paths

import json
import shutil
import tempfile
import time
from pathlib import Path

from rich_python_utils.string_utils.formatting.handlebars_format import (
    format_template as handlebars_template_format,
)

from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.communication.queue_manager import QueueManager
from webaxon.devsuite.web_agent_service_nextgen.communication.message_handlers import MessageHandlers
from webaxon.devsuite.web_agent_service_nextgen.agents.template_manager import TemplateManagerWrapper
from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import AgentRunner
from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_monitor import AgentSessionMonitor
from webaxon.devsuite.web_agent_service_nextgen.cli.client import CLIClient

# Source prompt templates
_WEBAGENT_SRC = Path(__file__).resolve().parent.parent.parent.parent / "src" / "webaxon"
PROMPT_TEMPLATES_SRC = _WEBAGENT_SRC / "devsuite" / "prompt_templates"


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


def service_tick(env):
    qs = env["queue_service"]
    config = env["config"]
    control_msg = qs.get(config.server_control_queue_id, blocking=False)
    if control_msg:
        print(f"  [service_tick] dispatching: {control_msg.get('type')}")
        env["message_handlers"].dispatch(control_msg)
    env["session_monitor"].run_monitoring_cycle()


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        testcase_root = Path(tmpdir)
        print(f"Testcase root: {testcase_root}")

        # Copy prompt templates
        template_dir = testcase_root / "prompt_templates"
        if PROMPT_TEMPLATES_SRC.exists():
            shutil.copytree(str(PROMPT_TEMPLATES_SRC), str(template_dir))
        else:
            template_dir.mkdir(parents=True, exist_ok=True)

        # Config — synchronous so everything runs inline
        config = ServiceConfig(
            synchronous_agent=True,
            debug_mode_service=False,
            new_agent_on_first_submission=True,
            session_idle_timeout=60,
            cleanup_check_interval=60,
        )

        # Queue manager
        queue_manager = QueueManager(testcase_root, config)
        queue_service = queue_manager.initialize()
        queue_manager.create_queues()

        # Template manager
        template_manager = TemplateManagerWrapper(
            template_dir=template_dir,
            template_formatter=handlebars_template_format,
        )

        # Agent factory — NO ingestion_inferencer passed
        # so it will create a real ClaudeApiInferencer lazily
        agent_factory = AgentFactory(
            template_manager.get_template_manager(),
            config,
            testcase_root=testcase_root,
            ingestion_inferencer=None,  # Real Claude API
        )

        # Session manager
        service_log_dir = testcase_root / config.log_root_path
        session_manager = SessionManager(
            id='test', log_name='Test', logger=[print],
            always_add_logging_based_logger=False,
            config=config, queue_service=queue_service,
            service_log_dir=service_log_dir,
        )

        # Agent runner
        agent_runner = AgentRunner(config)

        # Message handlers
        message_handlers = MessageHandlers(
            session_manager, agent_factory, queue_service, config
        )

        # Session monitor
        session_monitor = AgentSessionMonitor(
            session_manager, queue_service, config, agent_factory, agent_runner
        )

        # CLI client
        queue_root_path = queue_manager.get_queue_root_path()
        cli = CLIClient(
            testcase_root,
            session_id="manual_test",
            queue_root_path=queue_root_path,
        )

        env = {
            "testcase_root": testcase_root,
            "config": config,
            "queue_manager": queue_manager,
            "queue_service": queue_service,
            "agent_factory": agent_factory,
            "session_manager": session_manager,
            "agent_runner": agent_runner,
            "message_handlers": message_handlers,
            "session_monitor": session_monitor,
            "cli": cli,
            "queue_root_path": queue_root_path,
        }

        # Connect CLI
        connected = cli.connect()
        assert connected, "CLI failed to connect"

        # Step 1: Send register_knowledge
        print("\n" + "=" * 80)
        print("SENDING /add — Real Claude API LLM ingestion")
        print("=" * 80)
        print(f"Free text ({len(FREE_TEXT)} chars):")
        print(FREE_TEXT)
        print("-" * 80)
        print("Calling LLM (this may take 30-90 seconds)...")
        t0 = time.time()

        cli._send_control({
            "type": "register_knowledge",
            "message": {"content": FREE_TEXT},
            "timestamp": "manual_test",
        })

        # Process the control message — this calls ingest_knowledge
        # which calls the real Claude API
        service_tick(env)

        elapsed = time.time() - t0
        print(f"Done in {elapsed:.1f}s")

        # Read response
        resp = queue_service.get(config.client_control_queue_id, blocking=False)
        if resp is None:
            print("[FAIL] No response on client_control queue!")
        else:
            print(f"\nResponse: {json.dumps(resp, indent=2, default=str)}")

        # Step 2: Check disk
        print("\n" + "=" * 80)
        print("CHECKING KNOWLEDGE STORE ON DISK")
        print("=" * 80)

        knowledge_store_dir = testcase_root / "_runtime" / "knowledge_store"

        # Pieces
        pieces_dir = knowledge_store_dir / "pieces"
        if pieces_dir.exists():
            piece_files = list(pieces_dir.rglob("*.json"))
            print(f"\nPieces: {len(piece_files)} file(s)")
            for f in piece_files:
                print(f"  {f.relative_to(knowledge_store_dir)}")
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    print(f"    knowledge_type: {data.get('knowledge_type')}")
                    print(f"    info_type:      {data.get('info_type')}")
                    content = data.get("content", "")
                    print(f"    content:        {content[:100]}{'...' if len(content) > 100 else ''}")
                except Exception as e:
                    print(f"    [error reading] {e}")
        else:
            print("[WARN] No pieces directory")

        # Metadata
        metadata_dir = knowledge_store_dir / "metadata"
        if metadata_dir.exists():
            meta_files = list(metadata_dir.rglob("*.json"))
            print(f"\nMetadata: {len(meta_files)} file(s)")
            for f in meta_files:
                print(f"  {f.relative_to(knowledge_store_dir)}")
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    print(f"    {json.dumps(data, indent=4, default=str)}")
                except Exception as e:
                    print(f"    [error reading] {e}")
        else:
            print("[WARN] No metadata directory")

        # Graph
        graph_dir = knowledge_store_dir / "graph"
        if graph_dir.exists():
            graph_files = list(graph_dir.rglob("*.json"))
            print(f"\nGraph: {len(graph_files)} file(s)")
            for f in graph_files:
                print(f"  {f.relative_to(knowledge_store_dir)}")
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    print(f"    {json.dumps(data, indent=4, default=str)}")
                except Exception as e:
                    print(f"    [error reading] {e}")
        else:
            print("[WARN] No graph directory")

        # Ingestion logs
        ingestion_logs_dir = knowledge_store_dir / "ingestion_logs"
        if ingestion_logs_dir.exists():
            log_files = list(ingestion_logs_dir.rglob("*"))
            print(f"\nIngestion logs: {len(log_files)} file(s)")
            for f in log_files:
                if f.is_file():
                    print(f"  {f.relative_to(knowledge_store_dir)}")
        else:
            print("\n[INFO] No ingestion logs directory")

        print("\n" + "=" * 80)
        print("DONE")
        print("=" * 80)

        # Cleanup
        agent_factory.close()
        try:
            cli._queue_service.close()
        except Exception:
            pass
        queue_manager.close()


if __name__ == "__main__":
    main()
