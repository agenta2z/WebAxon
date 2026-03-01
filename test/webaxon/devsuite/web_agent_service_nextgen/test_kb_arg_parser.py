"""Unit tests for kb_arg_parser edge cases.

Tests error handling for empty inputs, invalid flags, and missing required arguments.
"""

import resolve_path  # Must be first import

import pytest

from webaxon.devsuite.web_agent_service_nextgen.cli.kb_arg_parser import (
    parse_kb_add,
    parse_kb_del,
    parse_kb_get,
    parse_kb_list,
    parse_kb_restore,
    parse_kb_review_spaces,
    parse_kb_update,
)


class TestKbAddEdgeCases:
    """Edge case tests for parse_kb_add.

    Requirements: 1.4, 6.1
    """

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_kb_add("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_kb_add("   ")

    def test_tabs_only_raises(self):
        with pytest.raises(ValueError):
            parse_kb_add("\t\t")

    def test_newlines_only_raises(self):
        with pytest.raises(ValueError):
            parse_kb_add("\n\n")


class TestKbUpdateEdgeCases:
    """Edge case tests for parse_kb_update.

    Requirements: 2.5, 6.2
    """

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_kb_update("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_kb_update("   ")

    def test_tabs_only_raises(self):
        with pytest.raises(ValueError):
            parse_kb_update("\t\t")


class TestKbDelEdgeCases:
    """Edge case tests for parse_kb_del.

    Requirements: 3.11, 6.3
    """

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_kb_del("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_kb_del("   ")

    def test_id_flag_without_value_raises(self):
        with pytest.raises(ValueError):
            parse_kb_del("--id")

    def test_id_flag_with_hard_but_no_id_value_raises(self):
        with pytest.raises(ValueError):
            parse_kb_del("--id --hard")


class TestKbGetEdgeCases:
    """Edge case tests for parse_kb_get.

    Requirements: 4.9, 6.6
    """

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_kb_get("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_kb_get("   ")

    def test_non_integer_limit_raises(self):
        with pytest.raises(ValueError):
            parse_kb_get("some query --limit abc")

    def test_zero_limit_raises(self):
        with pytest.raises(ValueError):
            parse_kb_get("some query --limit 0")

    def test_negative_limit_raises(self):
        with pytest.raises(ValueError):
            parse_kb_get("some query --limit -5")

    def test_float_limit_raises(self):
        with pytest.raises(ValueError):
            parse_kb_get("some query --limit 3.5")

    def test_only_flags_no_query_raises(self):
        with pytest.raises(ValueError):
            parse_kb_get("--domain programming")


class TestKbRestoreEdgeCases:
    """Edge case tests for parse_kb_restore.

    Requirements: 7.5, 6.7
    """

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_kb_restore("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_kb_restore("   ")

    def test_tabs_only_raises(self):
        with pytest.raises(ValueError):
            parse_kb_restore("\t\t")


class TestKbAddSpaceFlags:
    """Tests for --space and --spaces flags in parse_kb_add.

    Requirements: 10.1, 10.4, 10.5
    """

    def test_no_space_flag_returns_none(self):
        result = parse_kb_add("some text to add")
        assert result["text"] == "some text to add"
        assert result["spaces"] is None

    def test_single_space_flag(self):
        result = parse_kb_add("some text --space personal")
        assert result["text"] == "some text"
        assert result["spaces"] == ["personal"]

    def test_multiple_spaces_flag(self):
        result = parse_kb_add("some text --spaces personal,main")
        assert result["text"] == "some text"
        assert result["spaces"] == ["personal", "main"]

    def test_spaces_flag_takes_precedence_over_space(self):
        result = parse_kb_add("some text --space personal --spaces main,developmental")
        assert result["spaces"] == ["main", "developmental"]

    def test_only_space_flag_no_text_raises(self):
        with pytest.raises(ValueError):
            parse_kb_add("--space personal")


class TestKbGetSpaceFlags:
    """Tests for --space and --spaces flags in parse_kb_get.

    Requirements: 10.2
    """

    def test_no_space_flag_returns_none(self):
        result = parse_kb_get("my query")
        assert result["spaces"] is None

    def test_single_space_flag(self):
        result = parse_kb_get("my query --space personal")
        assert result["query"] == "my query"
        assert result["spaces"] == ["personal"]

    def test_multiple_spaces_flag(self):
        result = parse_kb_get("my query --spaces personal,main")
        assert result["query"] == "my query"
        assert result["spaces"] == ["personal", "main"]

    def test_space_with_other_flags(self):
        result = parse_kb_get("my query --domain coding --space personal --limit 5")
        assert result["query"] == "my query"
        assert result["domain"] == "coding"
        assert result["limit"] == 5
        assert result["spaces"] == ["personal"]


class TestKbListSpaceFlags:
    """Tests for --space and --spaces flags in parse_kb_list.

    Requirements: 10.3
    """

    def test_no_space_flag_returns_none(self):
        result = parse_kb_list("")
        assert result["spaces"] is None

    def test_single_space_flag(self):
        result = parse_kb_list("--space personal")
        assert result["spaces"] == ["personal"]

    def test_multiple_spaces_flag(self):
        result = parse_kb_list("--spaces personal,developmental")
        assert result["spaces"] == ["personal", "developmental"]

    def test_space_with_other_flags(self):
        result = parse_kb_list("--entity-id user:123 --space personal")
        assert result["entity_id"] == "user:123"
        assert result["spaces"] == ["personal"]


class TestKbReviewSpaces:
    """Tests for parse_kb_review_spaces.

    Requirements: 10.6, 10.7, 10.8
    """

    def test_no_args_returns_list_mode(self):
        result = parse_kb_review_spaces("")
        assert result["mode"] == "list"
        assert result["piece_id"] is None

    def test_whitespace_only_returns_list_mode(self):
        result = parse_kb_review_spaces("   ")
        assert result["mode"] == "list"
        assert result["piece_id"] is None

    def test_approve_with_piece_id(self):
        result = parse_kb_review_spaces("--approve abc123")
        assert result["mode"] == "approve"
        assert result["piece_id"] == "abc123"

    def test_reject_with_piece_id(self):
        result = parse_kb_review_spaces("--reject abc123")
        assert result["mode"] == "reject"
        assert result["piece_id"] == "abc123"

    def test_approve_without_piece_id_raises(self):
        with pytest.raises(ValueError):
            parse_kb_review_spaces("--approve")

    def test_reject_without_piece_id_raises(self):
        with pytest.raises(ValueError):
            parse_kb_review_spaces("--reject")

    def test_both_approve_and_reject_raises(self):
        with pytest.raises(ValueError):
            parse_kb_review_spaces("--approve abc --reject def")

    def test_approve_with_uuid_style_id(self):
        result = parse_kb_review_spaces("--approve 550e8400-e29b-41d4-a716-446655440000")
        assert result["mode"] == "approve"
        assert result["piece_id"] == "550e8400-e29b-41d4-a716-446655440000"
