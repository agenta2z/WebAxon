"""Integration tests: CLI client → web_agent_service_nextgen.

Test 1: Knowledge ingestion via CLI → LLM structuring → file-based KnowledgeBase
Test 2: Agent request → prompt formatting with knowledge → capture at inferencer input
"""
import sys
import resolve_path  # Setup import paths

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

import pytest

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

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Source prompt templates used by the real agents
_WEBAGENT_SRC = Path(__file__).resolve().parent.parent.parent.parent / "src" / "webaxon"
PROMPT_TEMPLATES_SRC = _WEBAGENT_SRC / "devsuite" / "prompt_templates"


# ---------------------------------------------------------------------------
# MockIngestionInferencer — returns pre-built structured JSON for tests
# ---------------------------------------------------------------------------

class MockIngestionInferencer:
    """Mock inferencer for KnowledgeIngestionCLI that returns valid structured JSON.

    Returns a plausible structured response with unique piece_ids per call
    so tests don't need a real API key.
    """

    def __init__(self):
        self._call_count = 0

    def __call__(self, prompt, **kwargs):
        self._call_count += 1
        piece_id = f"test-piece-{self._call_count}"
        return json.dumps({
            "metadata": {
                "user_test_user": {
                    "entity_type": "person",
                    "properties": {"name": "Test User"}
                }
            },
            "pieces": [
                {
                    "piece_id": piece_id,
                    "content": f"Mock ingested knowledge #{self._call_count}",
                    "knowledge_type": "fact",
                    "info_type": "user_profile",
                    "tags": ["test"],
                    "entity_id": None,
                    "embedding_text": f"mock knowledge {self._call_count}"
                }
            ],
            "graph": {
                "nodes": [
                    {"node_id": "user_test_user", "node_type": "person",
                     "label": "Test User", "properties": {}}
                ],
                "edges": []
            }
        })


# ---------------------------------------------------------------------------
# CaptureInferencer — captures the formatted prompt sent to the LLM
# ---------------------------------------------------------------------------

class _CaptureComplete(Exception):
    """Raised by CaptureInferencer to stop agent execution after capture."""


class CaptureInferencer:
    """Mock inferencer that records the prompt and stops the agent."""

    def __init__(self):
        self.captured_inputs = []

    def __call__(self, reasoner_input, reasoner_config=None, **kwargs):
        self.captured_inputs.append(reasoner_input)
        raise _CaptureComplete("Prompt captured — stopping agent")


# ---------------------------------------------------------------------------
# CaptureAgentFactory — injects CaptureInferencer into every agent
# ---------------------------------------------------------------------------

class CaptureAgentFactory(AgentFactory):
    """AgentFactory subclass that builds a minimal planning agent with CaptureInferencer.

    Avoids creating WebDriver (no browser needed — we only capture the prompt).
    """

    def __init__(self, *args, **kwargs):
        self.capture_inferencer = CaptureInferencer()
        super().__init__(*args, **kwargs)

    def create_agent(self, interactive, logger, agent_type='DefaultAgent', template_version=''):
        """Build a minimal PromptBasedActionPlanningAgent without WebDriver."""
        from agent_foundation.agents.agent_response import AgentResponseFormat
        from agent_foundation.agents.prompt_based_agents.prompt_based_planning_agent import (
            PromptBasedActionPlanningAgent,
        )
        from rich_python_utils.string_utils.formatting.common import KeyValueStringFormat

        if template_version:
            self._template_manager.switch(template_version=template_version)

        planning_agent = PromptBasedActionPlanningAgent(
            prompt_formatter=self._template_manager.switch(active_template_root_space='planning_agent'),
            direct_response_start_delimiter='<DirectResponse>',
            direct_response_end_delimiter='</DirectResponse>',
            raw_response_start_delimiter='<StructuredResponse>',
            raw_response_end_delimiter='</StructuredResponse>',
            raw_response_format=AgentResponseFormat.XML,
            use_conversational_user_input=True,
            input_string_formatter=KeyValueStringFormat.XML,
            response_string_formatter=KeyValueStringFormat.XML,
            user_profile=self._user_profile,
            reasoner=self.capture_inferencer,
            interactive=interactive,
            actor={},  # No actors needed — CaptureInferencer stops before actions
            logger=logger,
            always_add_logging_based_logger=False,
            debug_mode=True,
            only_keep_parent_debuggable_ids=True,
            knowledge_provider=self._provider,
        )

        return planning_agent


# ---------------------------------------------------------------------------
# Shared test environment setup
# ---------------------------------------------------------------------------

def setup_cli_test_environment(
    tmpdir,
    use_capture_factory: bool = False,
) -> Dict[str, Any]:
    """Set up all service components + a CLIClient in a temp directory.

    Args:
        tmpdir: Temporary directory path
        use_capture_factory: If True, use CaptureAgentFactory instead of AgentFactory
    """
    testcase_root = Path(tmpdir)

    # Templates — always copy the real .hbs templates so TemplateManager works
    template_dir = testcase_root / "prompt_templates"
    if PROMPT_TEMPLATES_SRC.exists():
        shutil.copytree(str(PROMPT_TEMPLATES_SRC), str(template_dir))
    else:
        template_dir.mkdir(parents=True, exist_ok=True)

    # Config — synchronous agent so everything runs in the test thread
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

    # Agent factory (normal or capture variant)
    # Always use MockIngestionInferencer for tests (no real API key needed)
    mock_ingestion = MockIngestionInferencer()
    FactoryClass = CaptureAgentFactory if use_capture_factory else AgentFactory
    agent_factory = FactoryClass(
        template_manager.get_template_manager(),
        config,
        testcase_root=testcase_root,
        ingestion_inferencer=mock_ingestion,
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

    # CLI client — point it at the queue root so it can connect directly
    queue_root_path = queue_manager.get_queue_root_path()
    cli = CLIClient(
        testcase_root,
        session_id="test_cli_session",
        queue_root_path=queue_root_path,
    )

    return {
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


# ---------------------------------------------------------------------------
# Helper: simulate one iteration of the service main-loop
# ---------------------------------------------------------------------------

def cleanup_env(env: Dict[str, Any]) -> None:
    """Close all services that hold file handles."""
    if env.get("agent_factory"):
        env["agent_factory"].close()
    # Close the CLI's queue service (separate instance from the service's)
    cli: CLIClient = env.get("cli")
    if cli and cli._queue_service:
        try:
            cli._queue_service.close()
        except Exception:
            pass
        cli._queue_service = None
    env["queue_manager"].close()


def service_tick(env: Dict[str, Any]) -> None:
    """Process one control message (if any) and run one monitoring cycle."""
    qs = env["queue_service"]
    config = env["config"]

    # Process control messages
    control_msg = qs.get(config.server_control_queue_id, blocking=False)
    if control_msg:
        env["message_handlers"].dispatch(control_msg)

    # Run monitoring (detects waiting messages, creates agents, etc.)
    env["session_monitor"].run_monitoring_cycle()


# =========================================================================
# Test 1 — Knowledge registration via CLI
# =========================================================================

class TestKnowledgeIngestionViaCLI:
    """CLI sends /add → service calls LLM ingestion → structured knowledge stored."""

    def test_ingest_and_verify(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_cli_test_environment(tmpdir)
            cli: CLIClient = env["cli"]
            qs = env["queue_service"]
            config = env["config"]

            # Connect the CLI to the service queues
            connected = cli.connect()
            assert connected, "CLI failed to connect to service queues"

            # 1) CLI puts register_knowledge with free text
            cli._send_control({
                "type": "register_knowledge",
                "message": {
                    "content": "User prefers organic eggs from local farms",
                },
                "timestamp": "test",
            })

            # 2) Service processes — calls MockIngestionInferencer → structured JSON
            service_tick(env)

            # 3) CLI reads the response
            resp = qs.get(config.client_control_queue_id, blocking=False)
            assert resp is not None, "No response on client_control queue"
            assert resp["type"] == "register_knowledge_response"
            assert resp["success"] is True
            counts = resp.get("counts", {})
            assert counts is not None, "No counts in response"
            print(f"\n  Response: success={resp['success']}, counts={counts}")

            # 4) Verify knowledge files on disk
            knowledge_store_dir = env["testcase_root"] / "_runtime" / "knowledge_store"
            pieces_dir = knowledge_store_dir / "pieces"
            assert pieces_dir.exists(), f"Pieces directory not created: {pieces_dir}"

            piece_files = list(pieces_dir.rglob("*.json"))
            assert len(piece_files) > 0, "No knowledge piece files found on disk"

            # 5) Verify metadata was also created
            metadata_dir = knowledge_store_dir / "metadata"
            assert metadata_dir.exists(), f"Metadata directory not created: {metadata_dir}"

            print(f"[PASS] Knowledge ingestion — {len(piece_files)} piece file(s), metadata on disk")
            print(f"  Store path: {knowledge_store_dir}")

            cleanup_env(env)

    def test_ingest_multiple(self):
        """Ingest several free-text inputs and verify all are stored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_cli_test_environment(tmpdir)
            cli: CLIClient = env["cli"]
            qs = env["queue_service"]
            config = env["config"]
            cli.connect()

            texts = [
                "User is a Safeway Plus member with free delivery on orders over $50",
                "User lives in Bellevue, WA 98004",
                "User prefers organic produce when available",
            ]

            for text in texts:
                cli._send_control({
                    "type": "register_knowledge",
                    "message": {"content": text},
                    "timestamp": "test",
                })
                service_tick(env)
                resp = qs.get(config.client_control_queue_id, blocking=False)
                assert resp is not None and resp["success"] is True

            # Each MockIngestionInferencer call produces 1 piece, so >= 3
            pieces_dir = env["testcase_root"] / "_runtime" / "knowledge_store" / "pieces"
            piece_files = list(pieces_dir.rglob("*.json"))
            assert len(piece_files) >= len(texts), (
                f"Expected >= {len(texts)} piece files, got {len(piece_files)}"
            )

            print(f"\n[PASS] Multiple ingestion — {len(piece_files)} piece file(s)")

            cleanup_env(env)


# =========================================================================
# Test 2 — Agent request capturing inferencer input
# =========================================================================

class TestAgentRequestCapturesInferencerInput:
    """CLI sends a request → agent formats prompt → CaptureInferencer grabs it."""

    def test_capture_inferencer_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_cli_test_environment(
                tmpdir,
                use_capture_factory=True,
            )
            cli: CLIClient = env["cli"]
            cli.connect()
            capture: CaptureInferencer = env["agent_factory"].capture_inferencer

            # Step 1: Register some knowledge so it appears in the prompt
            qs = env["queue_service"]
            config = env["config"]
            cli._send_control({
                "type": "register_knowledge",
                "message": {
                    "content": "User is a Safeway Plus member with free delivery on orders over $50",
                },
                "timestamp": "test",
            })
            service_tick(env)
            # Consume the ack
            qs.get(config.client_control_queue_id, blocking=False)

            # Step 2: Sync session (so service knows our session)
            session_id = cli._session_id
            env["queue_service"].put(
                env["config"].server_control_queue_id,
                {
                    "type": "sync_session_agent",
                    "message": {
                        "session_id": session_id,
                        "agent_type": "DefaultAgent",
                    },
                    "timestamp": "test",
                },
            )
            service_tick(env)  # process sync message

            # Step 3: Put user message on the session-specific input queue
            session_input_queue_id = f"{env['config'].input_queue_id}_{session_id}"
            env["queue_service"].create_queue(session_input_queue_id)
            env["queue_service"].put(session_input_queue_id, {
                "user_input": "what is the organic egg price in safeway right now",
                "session_id": session_id,
            })

            # Step 4: Run monitoring cycle — this triggers lazy agent creation
            # With synchronous_agent=True, the agent runs in-line and
            # CaptureInferencer raises _CaptureComplete which agent_runner
            # catches as an error. That's expected.
            service_tick(env)

            # Step 5: Verify the prompt was captured
            assert len(capture.captured_inputs) >= 1, (
                "CaptureInferencer did not capture any prompts"
            )

            prompt = capture.captured_inputs[0]
            print("\n" + "=" * 80)
            print("CAPTURED INFERENCER INPUT (first iteration)")
            print("=" * 80)
            print(prompt[:3000] if len(prompt) > 3000 else prompt)
            if len(prompt) > 3000:
                print(f"\n... (truncated, total length: {len(prompt)} chars)")
            print("=" * 80)

            # Basic sanity checks on the prompt content
            assert isinstance(prompt, str), "Prompt should be a string"
            assert len(prompt) > 50, "Prompt seems too short"

            print(f"\n[PASS] Inferencer input captured — {len(prompt)} chars")

            cleanup_env(env)


# =========================================================================
# Test 3 — Graph dedup: graph_retrieval_ignore_pieces_already_retrieved
# =========================================================================

class GraphDedupMockIngestionInferencer:
    """Mock inferencer that returns pieces + graph edges with piece_id links.

    Produces:
    - A user-scoped piece (creates the user: namespace for entity detection)
    - A global procedure piece (will be found by BM25 global search)
    - Graph nodes: user node + procedure node
    - Graph edge: user -> procedure with piece_id pointing to the procedure piece

    This setup causes the same piece to appear in both Layer 2 (piece search)
    and Layer 3 (graph traversal), which is the scenario that
    graph_retrieval_ignore_pieces_already_retrieved is designed to handle.
    """

    def __call__(self, prompt, **kwargs):
        return json.dumps({
            "metadata": {
                "user:test-user": {
                    "entity_type": "person",
                    "properties": {"name": "Test User", "role": "tester"}
                }
            },
            "pieces": [
                {
                    "piece_id": "user-profile-fact",
                    "content": "Test User is a QA engineer who validates shopping workflows",
                    "knowledge_type": "fact",
                    "info_type": "user_profile",
                    "tags": ["profile"],
                    "entity_id": "user:test-user",
                    "embedding_text": "test user QA engineer shopping workflows"
                },
                {
                    "piece_id": "proc-test-shopping",
                    "content": "Complete test shopping procedure: Step 1 browse products, Step 2 add to cart, Step 3 checkout",
                    "knowledge_type": "procedure",
                    "info_type": "instructions",
                    "tags": ["shopping", "procedure"],
                    "entity_id": None,
                    "embedding_text": "complete test shopping procedure steps browse add cart checkout"
                }
            ],
            "graph": {
                "nodes": [
                    {
                        "node_id": "user:test-user",
                        "node_type": "person",
                        "label": "Test User",
                        "properties": {}
                    },
                    {
                        "node_id": "procedure:test-shopping",
                        "node_type": "procedure",
                        "label": "Test Shopping Procedure",
                        "properties": {}
                    }
                ],
                "edges": [
                    {
                        "source_id": "user:test-user",
                        "target_id": "procedure:test-shopping",
                        "edge_type": "HAS_SKILL",
                        "properties": {"piece_id": "proc-test-shopping"}
                    }
                ]
            }
        })


# Unique content substring that only appears in the procedure piece content
_PROCEDURE_CONTENT_MARKER = "Complete test shopping procedure"

# The user query — terms must overlap with the procedure piece content for BM25
_DEDUP_TEST_QUERY = "complete the test shopping procedure steps"


class TestGraphDedupPromptCapture:
    """Verify graph_retrieval_ignore_pieces_already_retrieved end-to-end.

    Tests the full pipeline: CLI ingestion -> file stores -> KnowledgeBase
    retrieval (Layer 2 + Layer 3) -> KnowledgeProvider routing -> formatted
    output dict.

    When dedup is ON, a procedure piece found by Layer 2 search should NOT be
    duplicated in the graph edge description. The graph edge structure
    (HAS_SKILL -> procedure:test-shopping) must still appear, but only with
    the node label, not the full piece content.

    When dedup is OFF (default), the same piece content appears both in the
    knowledge pieces section and in the graph edge description.

    NOTE: The planning_agent template does not have {{instructions}} or
    {{user_profile}} placeholders, so knowledge is asserted at the provider
    output level (Dict[str, str]) rather than the rendered prompt string.
    The provider output IS the final formatted knowledge that would be
    injected into templates that support it (e.g., action_agent).
    """

    def _run_dedup_scenario(self, dedup_flag):
        """Run the full CLI -> KB -> provider flow with graph dedup on/off.

        Args:
            dedup_flag: Value for graph_retrieval_ignore_pieces_already_retrieved.
                        False (default behavior) or True (suppress duplicates).

        Returns:
            Tuple of (provider_output_dict, retrieval_result) for assertions.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            env = setup_cli_test_environment(tmpdir, use_capture_factory=True)
            cli: CLIClient = env["cli"]
            cli.connect()

            # Replace the ingestion inferencer with our graph-aware mock
            env["agent_factory"]._ingestion_inferencer = GraphDedupMockIngestionInferencer()

            # Step 1: Register knowledge (pieces + graph edges) via CLI
            qs = env["queue_service"]
            config = env["config"]
            cli._send_control({
                "type": "register_knowledge",
                "message": {
                    "content": "Test shopping procedure with graph links",
                },
                "timestamp": "test",
            })
            service_tick(env)
            resp = qs.get(config.client_control_queue_id, blocking=False)
            assert resp is not None, "No response on client_control queue"
            assert resp["success"] is True, f"Knowledge registration failed: {resp}"
            counts = resp.get("counts", {})
            assert counts.get("pieces", 0) >= 2, (
                f"Expected >= 2 pieces ingested, got {counts}"
            )
            assert counts.get("graph_edges", 0) >= 1, (
                f"Expected >= 1 graph edge ingested, got {counts}"
            )

            # Step 2: Set graph dedup flag on the KnowledgeBase
            kb = env["agent_factory"]._provider.kb
            kb.graph_retrieval_ignore_pieces_already_retrieved = dedup_flag

            # Verify active entity was detected
            assert kb.active_entity_id is not None, (
                "active_entity_id not auto-detected after ingestion"
            )

            # Step 3: Call provider with the test query (same path as agent)
            provider = env["agent_factory"]._provider
            provider_output = provider(_DEDUP_TEST_QUERY)

            # Also get raw retrieval result for detailed graph assertions
            retrieval_result = kb.retrieve(_DEDUP_TEST_QUERY)

            cleanup_env(env)
            return provider_output, retrieval_result

    def test_dedup_off_includes_piece_in_graph_context(self):
        """With dedup OFF, procedure piece content appears in both pieces and graph.

        The instructions group contains: the piece from Layer 2 search AND
        the graph edge with the linked piece content appended.
        """
        provider_output, result = self._run_dedup_scenario(dedup_flag=False)

        print("\n" + "=" * 80)
        print("PROVIDER OUTPUT -- DEDUP OFF")
        print("=" * 80)
        for key, value in provider_output.items():
            safe_value = value.replace("\u2192", "->")
            print(f"\n[{key}] ({len(value)} chars):")
            print(safe_value)
        print("=" * 80)

        # The 'instructions' group should exist and contain the procedure content
        assert "instructions" in provider_output, (
            f"Expected 'instructions' key in provider output, "
            f"got keys: {list(provider_output.keys())}"
        )
        instructions_text = provider_output["instructions"]

        # The procedure content marker must appear at least twice:
        # 1) From Layer 2 piece retrieval
        # 2) From graph edge with linked piece
        occurrences = instructions_text.count(_PROCEDURE_CONTENT_MARKER)
        assert occurrences >= 2, (
            f"Expected '{_PROCEDURE_CONTENT_MARKER}' to appear >= 2 times "
            f"in 'instructions' output (dedup OFF), but found {occurrences}.\n"
            f"Instructions text:\n{instructions_text}"
        )

        # The graph edge type must be in the instructions group (routed there
        # because the linked piece has info_type="instructions")
        assert "HAS_SKILL" in instructions_text, (
            "Graph edge 'HAS_SKILL' not found in instructions output (dedup OFF)"
        )

        # Verify raw retrieval: graph entry should have piece attached
        assert len(result.graph_context) >= 1, "No graph context in retrieval result"
        graph_entry = result.graph_context[0]
        assert graph_entry["piece"] is not None, (
            "Graph entry should have piece attached when dedup is OFF"
        )
        assert graph_entry["piece"].piece_id == "proc-test-shopping", (
            f"Expected linked piece 'proc-test-shopping', "
            f"got '{graph_entry['piece'].piece_id}'"
        )

        print(f"\n[PASS] Dedup OFF — '{_PROCEDURE_CONTENT_MARKER}' appears "
              f"{occurrences} time(s) in instructions, graph piece attached")

    def test_dedup_on_suppresses_duplicate_piece_in_prompt(self):
        """With dedup ON, procedure piece content appears exactly 1 time.

        The instructions group contains the piece from Layer 2 only. The graph
        edge has piece=None and is routed to user_profile (depth-1, no piece).
        """
        provider_output, result = self._run_dedup_scenario(dedup_flag=True)

        print("\n" + "=" * 80)
        print("PROVIDER OUTPUT -- DEDUP ON")
        print("=" * 80)
        for key, value in provider_output.items():
            safe_value = value.replace("\u2192", "->")
            print(f"\n[{key}] ({len(value)} chars):")
            print(safe_value)
        print("=" * 80)

        # The 'instructions' group should exist
        assert "instructions" in provider_output, (
            f"Expected 'instructions' key in provider output, "
            f"got keys: {list(provider_output.keys())}"
        )
        instructions_text = provider_output["instructions"]

        # The procedure content marker should appear exactly once
        # (from Layer 2 piece only; graph edge should NOT re-attach the piece)
        occurrences = instructions_text.count(_PROCEDURE_CONTENT_MARKER)
        assert occurrences == 1, (
            f"Expected '{_PROCEDURE_CONTENT_MARKER}' to appear exactly 1 time "
            f"in 'instructions' output (dedup ON), but found {occurrences}.\n"
            f"Instructions text:\n{instructions_text}"
        )

        # The graph edge should be routed to user_profile (depth-1, no piece)
        # since the linked piece was suppressed
        assert "user_profile" in provider_output, (
            f"Expected 'user_profile' key in provider output (graph edge "
            f"without piece routes to user_profile), "
            f"got keys: {list(provider_output.keys())}"
        )
        user_profile_text = provider_output["user_profile"]

        # HAS_SKILL should appear in user_profile (graph edge still present)
        assert "HAS_SKILL" in user_profile_text, (
            "Graph edge 'HAS_SKILL' not found in user_profile output (dedup ON). "
            "The graph edge structure should be preserved even when piece is suppressed."
        )

        # The graph edge should show the label, not the piece content
        assert "Test Shopping Procedure" in user_profile_text, (
            "Graph edge label 'Test Shopping Procedure' not found in user_profile. "
            "When piece is suppressed, the node label should be shown."
        )

        # The procedure content should NOT appear in user_profile
        assert _PROCEDURE_CONTENT_MARKER not in user_profile_text, (
            f"'{_PROCEDURE_CONTENT_MARKER}' should NOT appear in user_profile "
            f"output (dedup ON) — the piece was suppressed from the graph edge."
        )

        # Verify raw retrieval: graph entry should have piece=None
        assert len(result.graph_context) >= 1, "No graph context in retrieval result"
        graph_entry = result.graph_context[0]
        assert graph_entry["piece"] is None, (
            f"Graph entry should have piece=None when dedup is ON, "
            f"but got piece_id='{graph_entry['piece'].piece_id}'"
        )
        assert graph_entry["relation_type"] == "HAS_SKILL", (
            f"Graph entry relation_type should be 'HAS_SKILL', "
            f"got '{graph_entry['relation_type']}'"
        )
        assert graph_entry["target_node_id"] == "procedure:test-shopping", (
            f"Graph entry target should be 'procedure:test-shopping', "
            f"got '{graph_entry['target_node_id']}'"
        )

        print(f"\n[PASS] Dedup ON — '{_PROCEDURE_CONTENT_MARKER}' appears "
              f"exactly 1 time in instructions, graph edge in user_profile "
              f"with label only, piece=None in raw result")


# =========================================================================
# Entry point
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
