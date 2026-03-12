"""Test the final knowledge context format injected into the agent prompt feed.

Exercises RetrievalPipeline + GroupedDictPostProcessor to produce the
Dict[str, str] that gets merged into the agent's prompt feed, then simulates
space-filtered variants by running kb.retrieve(spaces=...) through the same
grouping + formatting pipeline.

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
from agent_foundation.knowledge.retrieval.retrieval_pipeline import RetrievalPipeline
from agent_foundation.knowledge.retrieval.post_processors import GroupedDictPostProcessor
from agent_foundation.knowledge.retrieval.provider import _default_formatter
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


def _make_post_processor(kb: KnowledgeBase) -> GroupedDictPostProcessor:
    """Create a GroupedDictPostProcessor matching the old KnowledgeProvider defaults."""
    return GroupedDictPostProcessor(
        type_formatters={},
        default_formatter=_default_formatter,
        metadata_info_type="user_profile",
        active_entity_id=kb.active_entity_id,
    )


def _make_pipeline(kb: KnowledgeBase) -> RetrievalPipeline:
    """Create a RetrievalPipeline with GroupedDictPostProcessor."""
    return RetrievalPipeline(
        kb=kb,
        post_processor=_make_post_processor(kb),
    )


def format_result_with_pipeline(kb: KnowledgeBase, result):
    """Run a RetrievalResult through the pipeline's post-processor.

    Calls the GroupedDictPostProcessor directly on a pre-fetched result
    (useful for space-filtered variants).
    """
    post_processor = _make_post_processor(kb)
    output = post_processor.process(result, query=QUERY)
    # Normalize StrEnum keys to plain strings
    return {str(k): v for k, v in output.items()}


def run_provider_test(kb, pipeline, test_name, spaces=None):
    """Run a single provider feed test and return structured results."""
    if spaces is None:
        # Real pipeline call (no space filter)
        raw_feed = pipeline.execute(QUERY)
        # Normalize StrEnum keys to plain strings
        feed = {str(k): v for k, v in raw_feed.items()}
    else:
        # Space-filtered: retrieve manually, then format through pipeline post-processor
        result = kb.retrieve(QUERY, spaces=spaces)
        feed = format_result_with_pipeline(kb, result)

    return {
        "test_name": test_name,
        "query": QUERY,
        "spaces_filter": spaces,
        "feed": feed,
        "feed_keys": sorted(feed.keys()),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    kb = create_kb()
    pipeline = _make_pipeline(kb)

    print(f"Knowledge store: {STORE_BASE}")
    print(f"Active entity:   {kb.active_entity_id}")
    print(f"Query:           {QUERY!r}")
    print(f"Output dir:      {OUTPUT_DIR}")
    print()

    tests = [
        ("provider_no_filter", None),
        ("provider_spaces_personal", ["personal"]),
        ("provider_spaces_main", ["main"]),
        ("provider_spaces_personal_and_main", ["personal", "main"]),
    ]

    all_results = []

    for test_name, spaces in tests:
        data = run_provider_test(kb, pipeline, test_name, spaces)
        all_results.append(data)

        # Write individual test output
        out_path = OUTPUT_DIR / f"{test_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Print summary (replace unicode arrows for cp1252 console)
        spaces_str = str(spaces) if spaces else "None"
        print(f"  {test_name:35s}  spaces={spaces_str:25s}  -> feed keys: {data['feed_keys']}")
        for key in data["feed_keys"]:
            text = data["feed"][key]
            preview = text[:120].replace("\n", " | ").replace("\u2192", "->") if text else "(empty)"
            print(f"    {key:20s}: {preview}")
        print()

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
                "feed_keys": d["feed_keys"],
                "feed_lengths": {k: len(v) for k, v in d["feed"].items()},
            }
            for d in all_results
        ],
    }
    summary_path = OUTPUT_DIR / "provider_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Output written to {OUTPUT_DIR}/")
    print(f"  - provider_summary.json")
    for test_name, _ in tests:
        print(f"  - {test_name}.json")

    kb.close()


if __name__ == "__main__":
    main()
