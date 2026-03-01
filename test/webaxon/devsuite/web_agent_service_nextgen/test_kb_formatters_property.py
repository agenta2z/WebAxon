"""Property-based tests for kb_formatters module.

Uses hypothesis to verify formatting properties across generated inputs.
"""

import resolve_path  # Setup import paths

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck

from webaxon.devsuite.web_agent_service_nextgen.cli.kb_formatters import (
    format_search_results,
    format_list_results,
    format_ingestion_result,
    format_update_results,
    format_delete_candidates,
    truncate_content,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Piece IDs: at least 8 chars so truncation to first 8 is testable
_piece_id = st.text(
    min_size=8,
    max_size=36,
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="-",
    ),
)

# Domain strings
_domain = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"),
)

# Knowledge type strings
_knowledge_type = st.sampled_from(["fact", "skill", "preference", "procedure", "concept"])

# Content strings (non-empty, printable, no filter needed — from_regex guarantees non-empty)
_content = st.from_regex(r"[A-Za-z0-9 .,!?;:']{1,300}", fullmatch=True)

# Score floats
_score = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Non-negative integers for counts
_count = st.integers(min_value=0, max_value=10000)

# Version integers
_version = st.integers(min_value=0, max_value=1000)


# ---------------------------------------------------------------------------
# Strategy builders for result dicts
# ---------------------------------------------------------------------------

_piece_result = st.fixed_dictionaries({
    "piece_id": _piece_id,
    "domain": _domain,
    "knowledge_type": _knowledge_type,
    "content": _content,
    "score": _score,
})

_list_result = st.fixed_dictionaries({
    "piece_id": _piece_id,
    "domain": _domain,
    "knowledge_type": _knowledge_type,
    "content": _content,
    "is_active": st.booleans(),
})

_update_result = st.fixed_dictionaries({
    "piece_id": _piece_id,
    "old_version": _version,
    "new_version": _version,
    "action": st.sampled_from(["replace", "merge", "append", "no_change"]),
})

_delete_candidate = st.fixed_dictionaries({
    "piece_id": _piece_id,
    "content_preview": _content,
    "score": _score,
})


# ---------------------------------------------------------------------------
# Property 12: Piece formatting contains required fields
# ---------------------------------------------------------------------------


class TestPieceFormattingContainsRequiredFields:
    """Property 12: Piece formatting contains required fields.

    For any list of piece result dicts with piece_id, domain, knowledge_type,
    and content, the formatted output string should contain the first 8
    characters of each piece_id and a truncated version of each content string.

    **Validates: Requirements 4.10, 5.7**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(results=st.lists(_piece_result, min_size=1, max_size=10))
    def test_format_search_results_contains_piece_ids_and_content(self, results):
        # Feature: kb-cli-commands, Property 12: Piece formatting (search)
        output = format_search_results(results)
        for r in results:
            pid_prefix = r["piece_id"][:8]
            assert pid_prefix in output, (
                f"Expected piece_id prefix '{pid_prefix}' in output"
            )
            truncated = truncate_content(r["content"])
            assert truncated in output, (
                f"Expected truncated content '{truncated}' in output"
            )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(results=st.lists(_list_result, min_size=1, max_size=10))
    def test_format_list_results_contains_piece_ids_and_content(self, results):
        # Feature: kb-cli-commands, Property 12: Piece formatting (list)
        output = format_list_results(results)
        for r in results:
            pid_prefix = r["piece_id"][:8]
            assert pid_prefix in output, (
                f"Expected piece_id prefix '{pid_prefix}' in output"
            )
            truncated = truncate_content(r["content"])
            assert truncated in output, (
                f"Expected truncated content '{truncated}' in output"
            )


# ---------------------------------------------------------------------------
# Property 13: Ingestion count formatting
# ---------------------------------------------------------------------------


class TestIngestionCountFormatting:
    """Property 13: Ingestion count formatting.

    For any dict with non-negative integer values for pieces_created,
    metadata_created, graph_nodes_created, and graph_edges_created, the
    formatted output string should contain each count value.

    **Validates: Requirements 1.6**
    """

    @settings(max_examples=100)
    @given(
        pieces_created=_count,
        metadata_created=_count,
        graph_nodes_created=_count,
        graph_edges_created=_count,
    )
    def test_ingestion_counts_appear_in_output(
        self, pieces_created, metadata_created, graph_nodes_created, graph_edges_created
    ):
        # Feature: kb-cli-commands, Property 13: Ingestion count formatting
        counts = {
            "pieces_created": pieces_created,
            "metadata_created": metadata_created,
            "graph_nodes_created": graph_nodes_created,
            "graph_edges_created": graph_edges_created,
        }
        output = format_ingestion_result(counts)
        assert str(pieces_created) in output, (
            f"Expected pieces_created={pieces_created} in output"
        )
        assert str(metadata_created) in output, (
            f"Expected metadata_created={metadata_created} in output"
        )
        assert str(graph_nodes_created) in output, (
            f"Expected graph_nodes_created={graph_nodes_created} in output"
        )
        assert str(graph_edges_created) in output, (
            f"Expected graph_edges_created={graph_edges_created} in output"
        )


# ---------------------------------------------------------------------------
# Property 14: Update result formatting
# ---------------------------------------------------------------------------


class TestUpdateResultFormatting:
    """Property 14: Update result formatting.

    For any list of update result dicts with piece_id, old_version, and
    new_version, the formatted output string should contain the first 8
    characters of each piece_id and both version numbers.

    **Validates: Requirements 2.6**
    """

    @settings(max_examples=100)
    @given(results=st.lists(_update_result, min_size=1, max_size=10))
    def test_update_results_contain_ids_and_versions(self, results):
        # Feature: kb-cli-commands, Property 14: Update result formatting
        output = format_update_results(results)
        for r in results:
            pid_prefix = r["piece_id"][:8]
            assert pid_prefix in output, (
                f"Expected piece_id prefix '{pid_prefix}' in output"
            )
            assert str(r["old_version"]) in output, (
                f"Expected old_version={r['old_version']} in output"
            )
            assert str(r["new_version"]) in output, (
                f"Expected new_version={r['new_version']} in output"
            )


# ---------------------------------------------------------------------------
# Property 15: Delete candidate formatting
# ---------------------------------------------------------------------------


class TestDeleteCandidateFormatting:
    """Property 15: Delete candidate formatting.

    For any list of candidate dicts with piece_id, content_preview, and score,
    the formatted output string should contain a numbered list where each entry
    includes the first 8 characters of the piece_id and a content preview.

    **Validates: Requirements 3.4**
    """

    @settings(max_examples=100)
    @given(candidates=st.lists(_delete_candidate, min_size=1, max_size=10))
    def test_delete_candidates_numbered_with_ids_and_preview(self, candidates):
        # Feature: kb-cli-commands, Property 15: Delete candidate formatting
        output = format_delete_candidates(candidates)
        for i, c in enumerate(candidates, 1):
            # Check numbering
            assert f"{i}." in output, (
                f"Expected numbered entry '{i}.' in output"
            )
            # Check piece_id prefix
            pid_prefix = c["piece_id"][:8]
            assert pid_prefix in output, (
                f"Expected piece_id prefix '{pid_prefix}' in output"
            )
            # Check content preview is present
            assert c["content_preview"] in output, (
                f"Expected content_preview in output"
            )
