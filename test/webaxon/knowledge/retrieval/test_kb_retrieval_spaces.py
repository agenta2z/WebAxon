"""Manual retrieval test for knowledge space filtering.

Instantiates KnowledgeBase against the existing file-based knowledge store
and runs queries with different space filters to verify space-aware retrieval.

Results are written as JSON files to an output/ directory alongside this script.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Resolve paths relative to the monorepo root (CoreProjects/)
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]  # WebAxon/test/webaxon/knowledge/retrieval -> CoreProjects

sys.path.insert(0, str(REPO_ROOT / "AgentFoundation" / "src"))
sys.path.insert(0, str(REPO_ROOT / "RichPythonUtils" / "src"))
sys.path.insert(0, str(REPO_ROOT / "SciencePythonUtils" / "src"))

from agent_foundation.knowledge import KnowledgeBase
from agent_foundation.knowledge.stores.metadata.keyvalue_adapter import KeyValueMetadataStore
from agent_foundation.knowledge.stores.pieces.retrieval_adapter import RetrievalKnowledgePieceStore
from agent_foundation.knowledge.stores.graph.graph_adapter import GraphServiceEntityGraphStore
from rich_python_utils.service_utils.keyvalue_service.file_keyvalue_service import FileKeyValueService
from rich_python_utils.service_utils.retrieval_service.file_retrieval_service import FileRetrievalService
from rich_python_utils.service_utils.graph_service.file_graph_service import FileGraphService

STORE_BASE = (
    REPO_ROOT
    / "WebAxon"
    / "src"
    / "webaxon"
    / "devsuite"
    / "web_agent_service_nextgen"
    / "_workspace"
    / "_knowledge_store"
)

OUTPUT_DIR = SCRIPT_DIR / "output"

QUERY = "what is organic egg prices on safeway right now"


def create_kb() -> KnowledgeBase:
    return KnowledgeBase(
        metadata_store=KeyValueMetadataStore(
            kv_service=FileKeyValueService(base_dir=str(STORE_BASE / "metadata"))
        ),
        piece_store=RetrievalKnowledgePieceStore(
            retrieval_service=FileRetrievalService(base_dir=str(STORE_BASE / "pieces"))
        ),
        graph_store=GraphServiceEntityGraphStore(
            graph_service=FileGraphService(base_dir=str(STORE_BASE / "graph"))
        ),
        active_entity_id="user:tony-chen",
        graph_retrieval_ignore_pieces_already_retrieved=True,
    )


def result_to_dict(result):
    """Serialize a RetrievalResult to a JSON-safe dict."""
    def piece_to_dict(piece, score):
        return {
            "piece_id": piece.piece_id,
            "score": round(score, 4),
            "space": piece.space,
            "spaces": piece.spaces,
            "content": piece.content,
            "knowledge_type": piece.knowledge_type.value if piece.knowledge_type else None,
            "info_type": piece.info_type,
            "tags": list(piece.tags),
            "entity_id": piece.entity_id,
            "embedding_text": piece.embedding_text,
            "domain": piece.domain,
            "created_at": piece.created_at,
            "updated_at": piece.updated_at,
        }

    def metadata_to_dict(m):
        if m is None:
            return None
        return {
            "entity_id": m.entity_id,
            "entity_type": m.entity_type,
            "properties": dict(m.properties),
            "spaces": m.spaces,
            "created_at": m.created_at,
            "updated_at": m.updated_at,
        }

    def graph_ctx_to_dict(ctx):
        out = {
            "relation_type": ctx.get("relation_type"),
            "target_node_id": ctx.get("target_node_id"),
            "target_label": ctx.get("target_label"),
            "depth": ctx.get("depth"),
        }
        piece = ctx.get("piece")
        if piece is not None:
            out["linked_piece"] = {
                "piece_id": piece.piece_id,
                "space": piece.space,
                "spaces": piece.spaces,
                "content": piece.content[:120],
            }
        else:
            out["linked_piece"] = None
        return out

    return {
        "metadata": metadata_to_dict(result.metadata),
        "global_metadata": metadata_to_dict(result.global_metadata),
        "pieces": [piece_to_dict(p, s) for p, s in result.pieces],
        "graph_context": [graph_ctx_to_dict(c) for c in result.graph_context],
    }


def run_test(kb, test_name, spaces, query=QUERY, top_k=10):
    """Run a single retrieval test and return structured results."""
    result = kb.retrieve(query, top_k=top_k, spaces=spaces)
    return {
        "test_name": test_name,
        "query": query,
        "spaces_filter": spaces,
        "active_entity_id": kb.active_entity_id,
        "result": result_to_dict(result),
        "piece_count": len(result.pieces),
        "graph_context_count": len(result.graph_context),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    kb = create_kb()
    print(f"Knowledge store: {STORE_BASE}")
    print(f"Active entity:   {kb.active_entity_id}")
    print(f"Query:           {QUERY!r}")
    print(f"Output dir:      {OUTPUT_DIR}")
    print()

    tests = [
        ("test_1_no_filter", None),
        ("test_2_personal", ["personal"]),
        ("test_3_main", ["main"]),
        ("test_4_developmental", ["developmental"]),
        ("test_5_personal_and_main", ["personal", "main"]),
    ]

    all_results = []

    for test_name, spaces in tests:
        data = run_test(kb, test_name, spaces)
        all_results.append(data)

        # Write individual test output
        out_path = OUTPUT_DIR / f"{test_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Print summary line
        piece_ids = [p["piece_id"] for p in data["result"]["pieces"]]
        spaces_str = str(spaces) if spaces else "None"
        print(f"  {test_name:30s}  spaces={spaces_str:30s}  -> {data['piece_count']} pieces: {piece_ids}")

    # Write combined summary
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "query": QUERY,
        "active_entity_id": kb.active_entity_id,
        "knowledge_store_path": str(STORE_BASE),
        "tests": [
            {
                "test_name": d["test_name"],
                "spaces_filter": d["spaces_filter"],
                "piece_count": d["piece_count"],
                "piece_ids": [p["piece_id"] for p in d["result"]["pieces"]],
                "graph_context_count": d["graph_context_count"],
            }
            for d in all_results
        ],
    }
    summary_path = OUTPUT_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nOutput written to {OUTPUT_DIR}/")
    print(f"  - summary.json")
    for test_name, _ in tests:
        print(f"  - {test_name}.json")

    kb.close()


if __name__ == "__main__":
    main()
