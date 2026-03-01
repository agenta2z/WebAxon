"""Unit tests for kb_formatters edge cases.

Tests truncation boundaries, empty results lists, and content shorter than max_len.
Requirements: 4.10, 5.7, 5.8
"""

import resolve_path  # Must be first import

import pytest

from webaxon.devsuite.web_agent_service_nextgen.cli.kb_formatters import (
    format_delete_candidates,
    format_delete_results,
    format_list_results,
    format_search_results,
    format_update_results,
    truncate_content,
)


class TestTruncateContent:
    """Tests for truncate_content boundary behavior.

    Requirements: 4.10, 5.7
    """

    def test_content_shorter_than_max_len_not_truncated(self):
        content = "short"
        result = truncate_content(content, max_len=200)
        assert result == "short"

    def test_content_exactly_at_max_len_not_truncated(self):
        content = "a" * 200
        result = truncate_content(content, max_len=200)
        assert result == content
        assert "..." not in result

    def test_content_one_over_max_len_is_truncated(self):
        content = "a" * 201
        result = truncate_content(content, max_len=200)
        assert result == "a" * 200 + "..."
        assert len(result) == 203

    def test_empty_content_not_truncated(self):
        result = truncate_content("", max_len=200)
        assert result == ""

    def test_custom_max_len_boundary(self):
        content = "abcde"
        assert truncate_content(content, max_len=5) == "abcde"
        assert truncate_content(content + "f", max_len=5) == "abcde..."


class TestEmptyResultsLists:
    """Tests for empty results list handling across all formatters.

    Requirements: 4.10, 5.7, 5.8
    """

    def test_format_search_results_empty(self):
        result = format_search_results([])
        assert result == "No results found"

    def test_format_list_results_empty(self):
        result = format_list_results([])
        assert result == "No knowledge pieces found."

    def test_format_update_results_empty(self):
        result = format_update_results([])
        assert result == "No matching pieces found"

    def test_format_delete_candidates_empty(self):
        result = format_delete_candidates([])
        assert result == "No matching pieces found"

    def test_format_delete_results_empty(self):
        result = format_delete_results([])
        assert result == "No pieces deleted"
