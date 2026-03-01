# test_cli_service_integration.py

Integration tests that verify the full pipeline from CLI client through the web_agent_service_nextgen service core to the knowledge retrieval and agent prompt construction layers.

## Overview

This test module exercises three progressively deeper integration scenarios:

| Test Class | What It Tests | Key Assertion Level |
|---|---|---|
| `TestKnowledgeIngestionViaCLI` | CLI `/add` -> LLM structuring -> file-based KnowledgeBase storage | Files on disk |
| `TestAgentRequestCapturesInferencerInput` | CLI request -> agent prompt formatting -> inferencer input capture | Rendered prompt string |
| `TestGraphDedupPromptCapture` | Graph dedup feature through full retrieval + provider pipeline | KnowledgeProvider output dict |

All tests run **without** a real LLM API key or a browser. Mock inferencers supply structured JSON in place of LLM calls, and `CaptureInferencer` intercepts prompts before they would reach a real model.

---

## Test Infrastructure

### Paths

```
_WEBAGENT_SRC    = <repo>/src/webagent
PROMPT_TEMPLATES_SRC = <repo>/src/webagent/devsuite/prompt_templates
```

Real `.hbs` prompt templates are copied into each test's temp directory so `TemplateManager` works identically to production.

### MockIngestionInferencer

**Purpose**: Replaces the real LLM call during knowledge ingestion. When the service processes a `register_knowledge` control message, the ingestion pipeline calls an inferencer to convert free-text user input into structured JSON (metadata, pieces, graph). This mock returns valid structured JSON immediately.

**Behavior**:
- Maintains a `_call_count` counter; each call produces a piece with a unique `piece_id` (`test-piece-1`, `test-piece-2`, ...).
- Returns metadata for a `user_test_user` entity (type `person`).
- Returns one knowledge piece per call (type `fact`, info_type `user_profile`).
- Returns a single graph node (`user_test_user`) with no edges.
- No `entity_id` on the piece (global piece, not scoped to a specific entity).

**Note**: The entity_id format here is `user_test_user` (no colon). This means `_detect_and_set_active_entity_id()` will NOT set `active_entity_id` (it requires the `user:` prefix), so Layer 3 graph traversal is skipped in Tests 1 and 2. This is intentional — those tests don't need graph features.

### CaptureInferencer

**Purpose**: Intercepts the fully formatted prompt that would be sent to the LLM reasoner during agent execution.

**Behavior**:
- Appends the `reasoner_input` string to `self.captured_inputs`.
- Immediately raises `_CaptureComplete` to halt the agent (no LLM call, no browser actions).
- The captured string is the complete prompt after template rendering and knowledge injection.

### CaptureAgentFactory

**Purpose**: A subclass of `AgentFactory` that builds a minimal `PromptBasedActionPlanningAgent` wired to `CaptureInferencer` instead of a real LLM.

**Key differences from production `AgentFactory.create_agent()`**:
- Uses `CaptureInferencer` as the reasoner (no API key needed).
- Sets `actor={}` (no WebDriver / browser needed).
- Always uses `planning_agent` template space.
- Passes through `knowledge_provider` so knowledge is included in the prompt feed.

### setup_cli_test_environment()

**Purpose**: Creates a complete, self-contained service environment in a temp directory.

**Components created**:
1. **Template directory** — copies real `.hbs` templates from source.
2. **ServiceConfig** — `synchronous_agent=True` so agent runs in the test thread.
3. **QueueManager + QueueService** — file-based message queues for CLI <-> service communication.
4. **TemplateManagerWrapper** — manages prompt templates with handlebars formatting.
5. **AgentFactory** (or `CaptureAgentFactory`) — with `MockIngestionInferencer` by default.
6. **SessionManager** — tracks active sessions.
7. **AgentRunner** — executes agents (synchronously in tests).
8. **MessageHandlers** — dispatches control messages (e.g., `register_knowledge`, `sync_session_agent`).
9. **SessionMonitor** — detects waiting messages and triggers agent creation.
10. **CLIClient** — connected to the queue root path for sending control/user messages.

**Parameters**:
- `tmpdir`: Path to a temporary directory (unique per test).
- `use_capture_factory`: When `True`, uses `CaptureAgentFactory` instead of `AgentFactory`.

**Returns**: A dictionary with all components, keyed by name.

### service_tick()

**Purpose**: Simulates one iteration of the service main loop.

**Steps**:
1. Reads one control message from `server_control_queue_id` (non-blocking).
2. If found, dispatches it via `MessageHandlers.dispatch()`.
3. Runs one `SessionMonitor.run_monitoring_cycle()` — detects waiting user messages, creates/triggers agents.

### cleanup_env()

**Purpose**: Closes file handles held by the agent factory (knowledge stores) and queue services.

---

## Test 1: TestKnowledgeIngestionViaCLI

### Purpose

Verifies that free-text knowledge sent via the CLI is processed through the ingestion pipeline and persisted to the file-based KnowledgeBase on disk.

### Data Flow

```
CLIClient._send_control()         # puts register_knowledge message on server_control queue
  -> QueueService
    -> MessageHandlers.dispatch()  # routes to knowledge registration handler
      -> MockIngestionInferencer() # returns structured JSON (metadata + pieces + graph)
        -> KnowledgeBase           # FileMetadataStore + FilePieceStore + FileGraphStore
          -> disk files            # _runtime/knowledge_store/{metadata,pieces,graph}/
```

### test_ingest_and_verify

**Steps**:
1. Set up environment with default `AgentFactory` (no capture needed).
2. Connect CLI to service queues.
3. Send a `register_knowledge` control message with free-text content: `"User prefers organic eggs from local farms"`.
4. Call `service_tick()` — service processes the message, calls `MockIngestionInferencer`, stores the result.
5. Read the response from `client_control_queue_id`.
6. Verify the response is successful and contains counts.
7. Verify knowledge files exist on disk under `_runtime/knowledge_store/pieces/` and `_runtime/knowledge_store/metadata/`.

**Expected Results**:
- Response `type == "register_knowledge_response"` with `success == True`.
- At least 1 piece file (`.json`) exists under `pieces/`.
- `metadata/` directory exists.

### test_ingest_multiple

**Steps**:
1. Set up environment.
2. Send 3 separate `register_knowledge` messages with different texts.
3. Call `service_tick()` after each, consuming responses.
4. Verify at least 3 piece files on disk.

**Expected Results**:
- All 3 registrations succeed.
- At least 3 piece files on disk (each `MockIngestionInferencer` call creates one unique piece).

---

## Test 2: TestAgentRequestCapturesInferencerInput

### Purpose

Verifies that when a user sends a request through the CLI, the service creates an agent, formats a prompt with knowledge, and the prompt reaches the inferencer. Uses `CaptureInferencer` to intercept and inspect the rendered prompt.

### Data Flow

```
register_knowledge (setup knowledge first)
  -> KnowledgeBase stores data

sync_session_agent (tell service about our session)
  -> SessionManager creates session entry

user message on session input queue
  -> SessionMonitor detects waiting message
    -> AgentFactory.create_agent() -> PromptBasedActionPlanningAgent
      -> Agent.__call__()
        -> knowledge_provider(user_input) -> Dict[str, str]
        -> _construct_reasoner_input()
          -> _merge_into_feed() (knowledge merged into template feed)
          -> prompt_formatter(template_key, feed=feed) -> rendered prompt
        -> CaptureInferencer(prompt) -> captures and raises _CaptureComplete
```

### test_capture_inferencer_prompt

**Steps**:
1. Set up environment with `use_capture_factory=True`.
2. Register knowledge: `"User is a Safeway Plus member with free delivery on orders over $50"`.
3. Sync session via `sync_session_agent` control message.
4. Put a user message on the session-specific input queue: `"what is the organic egg price in safeway right now"`.
5. Call `service_tick()` — triggers agent creation and execution.
6. Verify `CaptureInferencer` captured at least one prompt.
7. Print the captured prompt (truncated to 3000 chars) for manual inspection.
8. Assert the prompt is a non-trivial string (length > 50).

**Expected Results**:
- `capture.captured_inputs` has at least 1 entry.
- The prompt is a string longer than 50 characters.
- The prompt content (printed to stdout) shows the planning agent template with the user's conversation injected.

**Note on knowledge visibility**: The `planning_agent` template (`default.hbs`) only has `{{{conversation}}}` as a placeholder — it does NOT have `{{instructions}}`, `{{user_profile}}`, or `{{context}}` placeholders. Therefore, knowledge from the KnowledgeProvider IS merged into the template feed dict but is NOT rendered in the final prompt string. This is expected behavior for the planning agent. The `action_agent` and `response_agent` templates DO include these placeholders.

---

## Test 3: TestGraphDedupPromptCapture

### Purpose

End-to-end verification of the `graph_retrieval_ignore_pieces_already_retrieved` feature on `KnowledgeBase`. This feature prevents the same knowledge piece from appearing twice in the formatted output — once from Layer 2 (BM25 piece search) and once from Layer 3 (graph traversal with linked `piece_id`).

### The Duplication Problem

When `KnowledgeBase.retrieve()` runs:
- **Layer 2** (piece search): BM25 finds piece `proc-test-shopping` by matching query terms against piece content/embedding_text.
- **Layer 3** (graph traversal): Walking from `user:test-user`, the edge `HAS_SKILL` has `properties.piece_id = "proc-test-shopping"`, so the piece is looked up and attached to the graph entry.

Without dedup, the same procedure content (`"Complete test shopping procedure: Step 1 browse products, Step 2 add to cart, Step 3 checkout"`) appears in both the pieces section and the graph edge description of the formatted output.

### GraphDedupMockIngestionInferencer

A specialized mock that produces data designed to trigger the duplication scenario:

| Data | Details |
|---|---|
| **Metadata** | `user:test-user` (person, name="Test User", role="tester") |
| **Piece 1** | `user-profile-fact` — entity_id=`"user:test-user"`, info_type=`"user_profile"` |
| **Piece 2** | `proc-test-shopping` — entity_id=`null` (global), info_type=`"instructions"` |
| **Graph node 1** | `user:test-user` (person) |
| **Graph node 2** | `procedure:test-shopping` (procedure, label="Test Shopping Procedure") |
| **Graph edge** | `user:test-user` -> `procedure:test-shopping`, type=`HAS_SKILL`, properties=`{piece_id: "proc-test-shopping"}` |

**Critical design decisions**:
- Entity ID uses `"user:test-user"` (with colon) so `_detect_and_set_active_entity_id()` recognizes the `user:` namespace and sets `active_entity_id`. Without this, Layer 3 graph traversal would be skipped entirely.
- `proc-test-shopping` has `entity_id=null` (global piece) so it is found by BM25 global search.
- The query `"complete the test shopping procedure steps"` shares BM25 tokens (`complete`, `test`, `shopping`, `procedure`, `steps`) with the piece's `embedding_text`.

### Constants

```python
_PROCEDURE_CONTENT_MARKER = "Complete test shopping procedure"
_DEDUP_TEST_QUERY = "complete the test shopping procedure steps"
```

### _run_dedup_scenario() Helper

Runs the complete pipeline and returns the KnowledgeProvider output and raw retrieval result.

**Steps**:
1. Set up environment with `CaptureAgentFactory`.
2. Replace ingestion inferencer with `GraphDedupMockIngestionInferencer`.
3. Register knowledge via CLI -> `service_tick()`.
4. Assert ingestion counts: >= 2 pieces, >= 1 graph edge.
5. Set `kb.graph_retrieval_ignore_pieces_already_retrieved = dedup_flag`.
6. Verify `active_entity_id` was auto-detected.
7. Call `provider(_DEDUP_TEST_QUERY)` — this runs the full retrieval + routing + formatting pipeline.
8. Also call `kb.retrieve(_DEDUP_TEST_QUERY)` for raw result inspection.
9. Return `(provider_output, retrieval_result)`.

**Why assert on provider output instead of rendered prompt**: As noted in Test 2, the `planning_agent` template has no knowledge placeholders. The provider output dict IS the final formatted knowledge — the handlebars rendering step is just string substitution that doesn't affect the knowledge content. Testing at the provider level exercises the entire data pipeline except the final template render.

### test_dedup_off_includes_piece_in_graph_context

**Scenario**: `dedup_flag=False` (default behavior, no deduplication)

**Expected data flow**:
```
Layer 2: BM25 finds proc-test-shopping -> result.pieces
Layer 3: HAS_SKILL edge has piece_id="proc-test-shopping" -> piece looked up -> attached to graph entry
Provider routing:
  - proc-test-shopping piece (info_type="instructions") -> "instructions" group
  - graph entry with linked piece (piece.info_type="instructions") -> "instructions" group
Formatter:
  - Piece content rendered in pieces section
  - Graph line: "HAS_SKILL -> procedure:test-shopping (Complete test shopping procedure: ...)"
```

**Assertions**:
1. `"instructions"` key exists in provider output.
2. `_PROCEDURE_CONTENT_MARKER` appears **>= 2 times** in the `instructions` text (once from piece, once from graph edge).
3. `"HAS_SKILL"` appears in the `instructions` text (graph edge present).
4. Raw `result.graph_context[0]["piece"]` is not None (piece attached).
5. Linked piece_id is `"proc-test-shopping"`.

### test_dedup_on_suppresses_duplicate_piece_in_prompt

**Scenario**: `dedup_flag=True` (deduplication enabled)

**Expected data flow**:
```
Layer 2: BM25 finds proc-test-shopping -> result.pieces
         already_retrieved = {"proc-test-shopping": "instructions"}
Layer 3: HAS_SKILL edge has piece_id="proc-test-shopping"
         _should_skip_graph_piece() returns True -> piece NOT attached (entry["piece"] = None)
Provider routing:
  - proc-test-shopping piece (info_type="instructions") -> "instructions" group
  - graph entry WITHOUT piece (depth-1, from user entity) -> "user_profile" group
Formatter:
  - "instructions": piece content rendered once
  - "user_profile": "HAS_SKILL -> procedure:test-shopping (Test Shopping Procedure)" (label only, no piece content)
```

**Assertions**:
1. `"instructions"` key exists in provider output.
2. `_PROCEDURE_CONTENT_MARKER` appears **exactly 1 time** in `instructions` text (only from piece, not from graph).
3. `"user_profile"` key exists in provider output (graph edge routed there because no linked piece + depth-1).
4. `"HAS_SKILL"` appears in `user_profile` text (graph structure preserved).
5. `"Test Shopping Procedure"` appears in `user_profile` text (node label used as fallback).
6. `_PROCEDURE_CONTENT_MARKER` does NOT appear in `user_profile` text (piece content suppressed).
7. Raw `result.graph_context[0]["piece"]` is None (piece was suppressed).
8. Graph edge still has correct `relation_type` and `target_node_id`.

---

## How to Run

From the `WebAgent` project root:

```bash
# Run all tests in this file
pytest test/devsuite/web_agent_service_nextgen/test_cli_service_integration.py -v -s

# Run only a specific test class
pytest test/devsuite/web_agent_service_nextgen/test_cli_service_integration.py::TestKnowledgeIngestionViaCLI -v -s
pytest test/devsuite/web_agent_service_nextgen/test_cli_service_integration.py::TestAgentRequestCapturesInferencerInput -v -s
pytest test/devsuite/web_agent_service_nextgen/test_cli_service_integration.py::TestGraphDedupPromptCapture -v -s
```

The `-s` flag disables stdout capture so you can see the printed prompt and provider output for manual inspection.

**Important**: Do NOT `cd` into the test directory before running — the `logging/` and `monitoring/` subdirectories there would shadow Python's built-in `logging` module and cause `ImportError`. Always run from the project root.

---

## Dependencies

- `agent_foundation` — KnowledgeBase, KnowledgeProvider, formatters, agent classes
- `rich_python_utils` — Handlebars template formatting
- `rank-bm25` — BM25 search engine used by `FileRetrievalService`
- `pytest` — test runner
- `pybars3` — Handlebars template rendering (used by prompt templates)

No real LLM API key or browser is required.
