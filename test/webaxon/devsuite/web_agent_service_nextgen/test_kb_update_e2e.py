"""End-to-end integration test for /kb-update instruction-mode flow.

Simulates:
    /kb-update change the "grocery store shopping procedure" to
             "grocery store price-checking procedure"

Uses the permanent mock knowledge store at ``_mock_knowledge_store/``
(fake user "Alex Johnson" -- no real personal data).  The test performs
the update against the real on-disk piece files, verifies the result,
then **rolls back** the update operation (removes the new piece file,
restores the old piece to its original state) so the test is re-runnable.

Supports two LLM modes:
    - Mock LLM (default under pytest): Deterministic, no API calls.
    - Real LLM (manual testing): Uses Claude API via ClaudeApiInferencer.

Run with real LLM (interactive, human can review piece_id):
    cd WebAxon
    PYTHONPATH="src;../AgentFoundation/src;../RichPythonUtils/src" ^
      python -m test.webaxon.devsuite.web_agent_service_nextgen.test_kb_update_e2e

Or via pytest (mock LLM, non-interactive, -s shows terminal output):
    PYTHONPATH="src;../AgentFoundation/src;../RichPythonUtils/src" ^
      pytest test/webaxon/devsuite/web_agent_service_nextgen/test_kb_update_e2e.py -v -s
"""

import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Callable, Optional

# ── Path setup ────────────────────────────────────────────────────────
_this = Path(__file__).resolve()
_test_dir = _this.parent  # …/web_agent_service_nextgen/
_webaxon_root = _this.parents[4]  # WebAxon/
_projects_root = _webaxon_root.parent  # CoreProjects/

for _src in [
    _webaxon_root / "src",
    _projects_root / "AgentFoundation" / "src",
    _projects_root / "RichPythonUtils" / "src",
]:
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

# ── Imports ───────────────────────────────────────────────────────────
from agent_foundation.knowledge.ingestion.knowledge_updater import (
    KnowledgeUpdater,
    UpdateConfig,
)
from agent_foundation.knowledge.retrieval.stores.pieces.retrieval_adapter import (
    RetrievalKnowledgePieceStore,
)
from rich_python_utils.service_utils.retrieval_service.file_retrieval_service import (
    FileRetrievalService,
)

# ── Constants ─────────────────────────────────────────────────────────
MOCK_STORE_DIR = _test_dir / "_mock_knowledge_store"
PIECES_DIR = MOCK_STORE_DIR / "pieces"
ORIGINAL_PIECE_ID = "grocery-store-shopping-procedure"

USER_INSTRUCTION = (
    'change the "grocery store shopping procedure" to '
    '"grocery store price-checking procedure"'
)

# Only used for mock LLM exact-match assertions
EXPECTED_GENERATED_CONTENT = (
    "Complete grocery store price-checking procedure: "
    "Step 1 - Login first if user is a member to apply member pricing and discounts. "
    "Step 2 - Find right store and location first before further operations. "
    "Step 3 - Must scan items and compare prices across stores to find the best deals."
)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


# ── Pretty-print helpers ─────────────────────────────────────────────

def _header(title: str) -> None:
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def _section(title: str) -> None:
    print(f"\n--- {title} ---")


def _kv(key: str, value, indent: int = 2) -> None:
    prefix = " " * indent
    if isinstance(value, str) and len(value) > 80:
        wrapped = textwrap.fill(
            value, width=68,
            initial_indent="",
            subsequent_indent=prefix + "  ",
        )
        print(f"{prefix}{key}: {wrapped}")
    else:
        print(f"{prefix}{key}: {value}")


def _diff_content(old: str, new: str) -> None:
    """Show before/after content and highlight word-level changes."""
    _section("CONTENT DIFF")
    print()
    print("  BEFORE (v1):")
    for line in textwrap.wrap(old, width=66):
        print(f"    {line}")
    print()
    print("  AFTER  (v2):")
    for line in textwrap.wrap(new, width=66):
        print(f"    {line}")
    print()

    old_words = set(old.lower().split())
    new_words = set(new.lower().split())
    added = sorted(new_words - old_words)
    removed = sorted(old_words - new_words)
    if removed:
        print(f"  - Removed words: {', '.join(removed)}")
    if added:
        print(f"  + Added words:   {', '.join(added)}")


def _is_uuid(s: str) -> bool:
    return bool(_UUID_RE.match(s))


# ── LLM mode selection ───────────────────────────────────────────────

def _select_llm_mode() -> str:
    """Interactive menu: choose mock or real LLM."""
    # Support command-line flags for non-interactive use
    if "--real" in sys.argv:
        return "real"
    if "--mock" in sys.argv:
        return "mock"

    print("\n  Select LLM mode:")
    print("    1. Mock LLM  (no API calls, deterministic)")
    print("    2. Real LLM  (Claude API calls)")
    choice = input("  Enter choice [1/2]: ").strip()
    return "real" if choice == "2" else "mock"


# ── Mock LLM ─────────────────────────────────────────────────────────

def mock_llm_fn(prompt: str) -> str:
    """Two-phase mock LLM (no real API calls).

    Phase 1 (intent):     Classifies as instruction mode, action=replace.
    Phase 2 (generation): Returns the expected updated content.
    """
    if "Determine Input Mode" in prompt:
        return json.dumps({
            "input_mode": "instruction",
            "action": "replace",
            "confidence": 0.95,
            "reasoning": (
                'User says change "shopping procedure" to '
                '"price-checking procedure" -- this is an editing instruction.'
            ),
            "merge_strategy": "append",
            "updated_domain": None,
            "updated_tags": [
                "grocery", "price-checking", "workflow",
                "login", "pricing", "comparison",
            ],
            "clear_tags": False,
            "changes_summary": (
                "Renamed procedure from shopping to price-checking and "
                "updated step 3 to reflect price-comparison workflow."
            ),
        })
    elif "Apply the user's instruction" in prompt:
        return json.dumps({
            "generated_content": EXPECTED_GENERATED_CONTENT,
        })
    else:
        raise RuntimeError(f"Unexpected LLM call: {prompt[:120]}...")


# ── Real LLM ─────────────────────────────────────────────────────────

def _make_real_llm_fn() -> Callable[[str], str]:
    """Create a real LLM function via ClaudeApiInferencer + Claude API."""
    from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import (
        ClaudeApiInferencer,
    )
    from webaxon.devsuite.config import DEFAULT_AGENT_REASONER_ARGS

    inferencer = ClaudeApiInferencer(
        max_retry=3,
        default_inference_args=DEFAULT_AGENT_REASONER_ARGS,
        debug_mode=True,
    )

    def llm_fn(prompt: str) -> str:
        response = inferencer(prompt)
        # ClaudeApiInferencer returns str directly.
        # Guard for ReflectiveInferencer which returns InferencerResponse.
        if hasattr(response, "select_response"):
            return response.select_response().response
        return str(response)

    return llm_fn


# ── Piece ID review ──────────────────────────────────────────────────

PIECE_ID_SUGGESTION_PROMPT = """\
Based on this knowledge piece content, suggest a short, hyphenated,
lowercase piece_id similar in style to "{original_id}".

Content: {content}

Return JSON:
{{
    "suggested_piece_id": "your-suggestion-here"
}}
"""


def _review_piece_id(
    new_piece_id: str,
    new_content: str,
    llm_fn: Callable[[str], str],
    use_real_llm: bool,
) -> Optional[str]:
    """Review the new piece_id. If it's a UUID, suggest a semantic name.

    When use_real_llm=True, the LLM suggests a name and the human
    confirms.  Otherwise, the human is asked directly.

    Returns:
        A new semantic piece_id, or None to keep the current one.
    """
    if not _is_uuid(new_piece_id):
        print(f"  Piece ID '{new_piece_id}' is already semantic. No change needed.")
        return None

    _section("PIECE ID REVIEW")
    print(f"  Current piece_id is a UUID: {new_piece_id}")
    print(f"  The original piece had semantic ID: {ORIGINAL_PIECE_ID}")
    print()

    suggested = None

    if use_real_llm:
        print("  Asking LLM to suggest a semantic piece_id ...")
        try:
            prompt = PIECE_ID_SUGGESTION_PROMPT.format(
                original_id=ORIGINAL_PIECE_ID,
                content=new_content,
            )
            response = llm_fn(prompt)
            parsed = json.loads(KnowledgeUpdater._strip_json_fences(response))
            suggested = parsed.get("suggested_piece_id")
            if suggested:
                print(f"  LLM suggests: {suggested}")
        except Exception as e:
            print(f"  LLM suggestion failed: {e}")

    if suggested:
        confirm = input(f"  Accept '{suggested}'? [Y/n/type custom]: ").strip()
        if confirm.lower() in ("", "y", "yes"):
            return suggested
        elif confirm.lower() in ("n", "no"):
            return None
        else:
            return confirm  # user typed a custom ID
    else:
        custom = input("  Enter a semantic piece_id (or Enter to keep UUID): ").strip()
        return custom if custom else None


def _apply_piece_id_rename(
    pieces_dir: Path,
    old_id: str,
    new_id: str,
) -> None:
    """Rename a piece file on disk and update its doc_id field."""
    old_path = pieces_dir / "_default" / f"{old_id}.json"
    new_path = pieces_dir / "_default" / f"{new_id}.json"

    piece_data = json.loads(old_path.read_text(encoding="utf-8"))
    piece_data["doc_id"] = new_id
    new_path.write_text(
        json.dumps(piece_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    old_path.unlink()
    print(f"  Renamed: {old_id}.json -> {new_id}.json")


# ── Core test ─────────────────────────────────────────────────────────

def _run_e2e_test(mode: str = "mock", interactive: bool = False):
    """Core end-to-end test.

    Args:
        mode: "mock" or "real" LLM.
        interactive: If True, prompt human for piece_id review.
    """
    use_real_llm = (mode == "real")
    assert PIECES_DIR.is_dir(), f"Mock store not found: {PIECES_DIR}"

    # ── 1. Choose LLM function ────────────────────────────────────
    if use_real_llm:
        llm_fn = _make_real_llm_fn()
        llm_label = "REAL (Claude API)"
    else:
        llm_fn = mock_llm_fn
        llm_label = "MOCK (deterministic)"

    # ── 2. Open the permanent mock store ──────────────────────────
    retrieval_svc = FileRetrievalService(base_dir=str(PIECES_DIR))
    store = RetrievalKnowledgePieceStore(retrieval_service=retrieval_svc)

    # Snapshot the original piece file so we can restore it exactly
    original = store.get_by_id(ORIGINAL_PIECE_ID)
    assert original is not None, f"Piece {ORIGINAL_PIECE_ID!r} not in mock store"
    original_content = original.content
    original_json_path = PIECES_DIR / "_default" / f"{ORIGINAL_PIECE_ID}.json"
    original_json_backup = original_json_path.read_text(encoding="utf-8")

    _header("KB-UPDATE END-TO-END TEST")
    _kv("LLM Mode", llm_label)
    _kv("Interactive", str(interactive))

    # ── Show the mock store layout ────────────────────────────────
    _section("MOCK KNOWLEDGE STORE")
    _kv("Location", str(PIECES_DIR))
    piece_files = sorted(PIECES_DIR.rglob("*.json"))
    print(f"  Pieces on disk ({len(piece_files)}):")
    for pf in piece_files:
        print(f"    - {pf.relative_to(PIECES_DIR)}")

    # ── Show the piece before the update ──────────────────────────
    _section("ORIGINAL PIECE (before update)")
    _kv("piece_id", original.piece_id)
    _kv("version", original.version)
    _kv("domain", original.domain)
    _kv("tags", original.tags)
    _kv("is_active", original.is_active)
    _kv("content", original.content)

    # ── Show the simulated user command ───────────────────────────
    _section("USER COMMAND")
    print(f"  /kb-update {USER_INSTRUCTION}")

    # ── 3. Execute the update ─────────────────────────────────────
    updater = KnowledgeUpdater(
        piece_store=store,
        llm_fn=llm_fn,
        config=UpdateConfig(
            similarity_threshold=0.10,
            max_candidates=20,
            max_updates=3,
            preserve_history=True,
        ),
    )

    _section("EXECUTING UPDATE")
    phase_label = "real" if use_real_llm else "mock"
    print(f"  Phase 1: Intent classification  ({phase_label} LLM) ... ", end="", flush=True)

    results = updater.update_by_content(
        USER_INSTRUCTION,
        update_instruction=USER_INSTRUCTION,
    )

    assert len(results) >= 1, (
        f"Expected at least 1 result, got {len(results)}. "
        "BM25 search may not have matched the piece."
    )
    result = results[0]
    print("done")
    print(f"  Phase 2: Content generation     ({phase_label} LLM) ... done")

    new_piece_id = result.piece_id
    renamed_piece_id = None  # track if we rename the piece

    try:
        # ── 4. Show the update result ─────────────────────────────
        _section("UPDATE RESULT")
        _kv("success", result.success)
        _kv("piece_id (new)", result.piece_id)
        _kv("old_version", result.old_version)
        _kv("new_version", result.new_version)
        _kv("action", result.details.get("action"))
        _kv("summary", result.details.get("summary"))

        assert result.success is True, f"Update failed: {result.error}"

        # ── 5. Show the new piece ─────────────────────────────────
        new_piece = store.get_by_id(new_piece_id)
        assert new_piece is not None, "New piece not found in store"

        _section("NEW PIECE (after update)")
        _kv("piece_id", new_piece.piece_id)
        _kv("version", new_piece.version)
        _kv("tags", new_piece.tags)
        _kv("supersedes", new_piece.supersedes)
        _kv("is_active", new_piece.is_active)
        _kv("content", new_piece.content)

        # ── 6. Show the old piece (deactivated) ──────────────────
        old_piece = store.get_by_id(ORIGINAL_PIECE_ID)
        assert old_piece is not None, "Old piece disappeared"

        _section("OLD PIECE (after update)")
        _kv("piece_id", old_piece.piece_id)
        _kv("is_active", old_piece.is_active)
        _kv("content", old_piece.content)

        # ── 7. Content diff ───────────────────────────────────────
        _diff_content(original_content, new_piece.content)

        # ── 8. Piece ID review (interactive only) ─────────────────
        if interactive:
            suggested_id = _review_piece_id(
                new_piece_id, new_piece.content, llm_fn, use_real_llm,
            )
            if suggested_id:
                _apply_piece_id_rename(PIECES_DIR, new_piece_id, suggested_id)
                renamed_piece_id = suggested_id

                # Verify the renamed piece is loadable
                svc_check = FileRetrievalService(base_dir=str(PIECES_DIR))
                store_check = RetrievalKnowledgePieceStore(retrieval_service=svc_check)
                renamed_piece = store_check.get_by_id(suggested_id)
                print(f"  Verified renamed piece loadable: {renamed_piece is not None}")

        # ── 9. Assertions ─────────────────────────────────────────
        _section("ASSERTIONS")

        checks = [
            ("Update succeeded",
             result.success is True),
            ("Instruction text NOT stored as content",
             "change the" not in new_piece.content.lower()),
            ("Content mentions 'price-checking'",
             "price-checking" in new_piece.content.lower()),
            ("Old piece is deactivated (is_active=False)",
             old_piece.is_active is False),
            ("Old piece content unchanged",
             old_piece.content == original_content),
            ("New piece supersedes old piece",
             new_piece.supersedes == ORIGINAL_PIECE_ID),
            ("Version bumped 1 -> 2",
             new_piece.version == 2),
            ("New piece has 'add' history record",
             len(new_piece.history) >= 1
             and new_piece.history[0].operation == "add"),
            ("Old piece has 'delete' history record",
             any(r.operation == "delete" for r in old_piece.history)),
        ]

        # Mock-only: exact content match
        if not use_real_llm:
            checks.append((
                "New content matches expected (mock LLM)",
                new_piece.content == EXPECTED_GENERATED_CONTENT,
            ))

        disk_files = list((PIECES_DIR / "_default").glob("*.json"))
        checks.append((
            f"Disk has {len(disk_files)} files in _default/ (old + new)",
            len(disk_files) >= 2,
        ))

        for label, passed in checks:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {label}")

        for label, passed in checks:
            assert passed, f"ASSERTION FAILED: {label}"

    finally:
        # ── 10. ROLLBACK ──────────────────────────────────────────
        _section("ROLLBACK")

        # a) Remove the new piece file (may have been renamed)
        final_piece_id = renamed_piece_id or new_piece_id
        new_piece_path = PIECES_DIR / "_default" / f"{final_piece_id}.json"
        if new_piece_path.exists():
            new_piece_path.unlink()
            print(f"  Removed new piece file:    _default/{final_piece_id}.json")

        # b) Also remove UUID-named file if rename left it behind
        if renamed_piece_id:
            uuid_path = PIECES_DIR / "_default" / f"{new_piece_id}.json"
            if uuid_path.exists():
                uuid_path.unlink()
                print(f"  Removed UUID piece file:   _default/{new_piece_id}.json")

        # c) Restore the original piece JSON byte-for-byte
        original_json_path.write_text(original_json_backup, encoding="utf-8")
        print(f"  Restored original piece:   _default/{ORIGINAL_PIECE_ID}.json")

        # d) Verify rollback succeeded
        svc2 = FileRetrievalService(base_dir=str(PIECES_DIR))
        store2 = RetrievalKnowledgePieceStore(retrieval_service=svc2)

        restored = store2.get_by_id(ORIGINAL_PIECE_ID)
        gone = store2.get_by_id(new_piece_id)
        renamed_gone = (
            store2.get_by_id(renamed_piece_id) is None
            if renamed_piece_id else True
        )

        restored_ok = (
            restored is not None
            and restored.is_active is True
            and restored.content == original_content
            and restored.version == 1
        )
        gone_ok = gone is None
        renamed_ok = renamed_gone

        disk_after = sorted(
            f.name for f in (PIECES_DIR / "_default").glob("*.json")
        )

        print()
        print(f"  Original piece restored:   {'OK' if restored_ok else 'FAILED'}")
        print(f"  New piece removed:         {'OK' if gone_ok else 'FAILED'}")
        if renamed_piece_id:
            print(f"  Renamed piece removed:     {'OK' if renamed_ok else 'FAILED'}")
        print(f"  Files in _default/:        {disk_after}")

        _header("TEST COMPLETE -- ALL PASSED, ROLLBACK DONE")

        assert restored_ok, "Rollback failed: original piece not properly restored"
        assert gone_ok, "Rollback failed: new piece still exists"
        if renamed_piece_id:
            assert renamed_ok, "Rollback failed: renamed piece still exists"


# ── Pytest entry point ────────────────────────────────────────────────

def test_kb_update_instruction_mode_e2e():
    """Pytest: runs with mock LLM, non-interactive (no human prompts)."""
    _run_e2e_test(mode="mock", interactive=False)


# ── Direct entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    mode = _select_llm_mode()
    interactive = "--non-interactive" not in sys.argv
    _run_e2e_test(mode=mode, interactive=interactive)
