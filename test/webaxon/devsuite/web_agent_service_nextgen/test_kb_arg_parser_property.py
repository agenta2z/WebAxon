"""Property-based tests for kb_arg_parser module.

Uses hypothesis to verify parsing round-trip properties across generated inputs.
"""

import resolve_path  # Setup import paths

import pytest
from hypothesis import given, settings, strategies as st, assume

from webaxon.devsuite.web_agent_service_nextgen.cli.kb_arg_parser import (
    parse_kb_add,
    parse_kb_del,
    parse_kb_get,
    parse_kb_list,
    parse_kb_update,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Non-empty text that survives .strip() — no whitespace-only strings
_nonempty_text = st.text(min_size=1, max_size=500).filter(lambda t: t.strip())

# Alphanumeric + hyphen IDs (no spaces, no --), suitable for piece_id in --id flag
_piece_id = st.text(
    min_size=1,
    max_size=36,
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="-",
    ),
)

# Text that won't be confused with flags: no tokens starting with "--"
_safe_query_text = (
    st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Z"),
            whitelist_characters=" .,!?;:'",
        ),
    )
    .filter(lambda t: t.strip())
    .filter(lambda t: not any(tok.startswith("--") for tok in t.split()))
)

# Flag value strings: no spaces, no leading --, non-empty
_flag_value = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="-_.",
    ),
).filter(lambda t: not t.startswith("--"))


# ---------------------------------------------------------------------------
# Property 1: kb-add argument parsing round-trip
# ---------------------------------------------------------------------------


class TestKbAddParseRoundtrip:
    """Property 1: kb-add argument parsing round-trip.

    **Validates: Requirements 1.1, 6.1**
    """

    @settings(max_examples=100)
    @given(text=_safe_query_text)
    def test_kb_add_parse_roundtrip(self, text: str):
        # Feature: kb-cli-commands, Property 1: kb-add parsing round-trip
        result = parse_kb_add(text)
        # _split_flags joins positional tokens with single spaces
        assert result["text"] == " ".join(text.split())
        assert result["spaces"] is None


# ---------------------------------------------------------------------------
# Property 2: kb-update argument parsing round-trip
# ---------------------------------------------------------------------------


class TestKbUpdateParseRoundtrip:
    """Property 2: kb-update argument parsing round-trip.

    **Validates: Requirements 2.1, 6.2**
    """

    @settings(max_examples=100)
    @given(text=_nonempty_text)
    def test_kb_update_parse_roundtrip(self, text: str):
        # Feature: kb-cli-commands, Property 2: kb-update parsing round-trip
        result = parse_kb_update(text)
        assert result["text"] == text.strip()


# ---------------------------------------------------------------------------
# Property 3: kb-del argument parsing round-trip
# ---------------------------------------------------------------------------


class TestKbDelParseRoundtrip:
    """Property 3: kb-del argument parsing round-trip.

    **Validates: Requirements 3.1, 3.8, 3.9, 6.3**
    """

    @settings(max_examples=100)
    @given(piece_id=_piece_id, hard=st.booleans())
    def test_kb_del_direct_parse_roundtrip(self, piece_id: str, hard: bool):
        # Feature: kb-cli-commands, Property 3: kb-del direct mode parsing round-trip
        args = f"--id {piece_id}" + (" --hard" if hard else "")
        result = parse_kb_del(args)
        assert result["mode"] == "direct"
        assert result["piece_id"] == piece_id
        assert result["hard"] == hard

    @settings(max_examples=100)
    @given(query=_safe_query_text)
    def test_kb_del_query_parse_roundtrip(self, query: str):
        # Feature: kb-cli-commands, Property 3: kb-del query mode parsing round-trip
        assume(not query.strip().startswith("--"))
        result = parse_kb_del(query)
        assert result["mode"] == "query"
        # _split_flags joins positional tokens with single spaces
        expected = " ".join(query.split())
        assert result["query"] == expected


# ---------------------------------------------------------------------------
# Property 4: kb-get argument parsing round-trip
# ---------------------------------------------------------------------------


class TestKbGetParseRoundtrip:
    """Property 4: kb-get argument parsing round-trip.

    **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 6.4**
    """

    @settings(max_examples=100)
    @given(
        query=_safe_query_text,
        domain=st.one_of(st.none(), _flag_value),
        limit=st.one_of(st.none(), st.integers(min_value=1, max_value=1000)),
        entity_id=st.one_of(st.none(), _flag_value),
        tags=st.one_of(st.none(), st.lists(_flag_value, min_size=1, max_size=5)),
    )
    def test_kb_get_parse_roundtrip(
        self,
        query: str,
        domain,
        limit,
        entity_id,
        tags,
    ):
        # Feature: kb-cli-commands, Property 4: kb-get parsing round-trip
        parts = [query]
        if domain is not None:
            parts.append(f"--domain {domain}")
        if limit is not None:
            parts.append(f"--limit {limit}")
        if entity_id is not None:
            parts.append(f"--entity-id {entity_id}")
        if tags is not None:
            parts.append(f"--tags {','.join(tags)}")

        args = " ".join(parts)
        result = parse_kb_get(args)

        expected_query = " ".join(query.split())
        assert result["query"] == expected_query
        assert result["domain"] == domain
        assert result["limit"] == limit
        assert result["entity_id"] == entity_id
        if tags is not None:
            assert result["tags"] == tags
        else:
            assert result["tags"] is None
        assert result["spaces"] is None


# ---------------------------------------------------------------------------
# Property 5: kb-list argument parsing
# ---------------------------------------------------------------------------


class TestKbListParseRoundtrip:
    """Property 5: kb-list argument parsing.

    **Validates: Requirements 5.2, 5.3, 6.5**
    """

    @settings(max_examples=100)
    @given(
        entity_id=st.one_of(st.none(), _flag_value),
        domain=st.one_of(st.none(), _flag_value),
    )
    def test_kb_list_parse_roundtrip(self, entity_id, domain):
        # Feature: kb-cli-commands, Property 5: kb-list parsing round-trip
        parts = []
        if entity_id is not None:
            parts.append(f"--entity-id {entity_id}")
        if domain is not None:
            parts.append(f"--domain {domain}")

        args = " ".join(parts)
        result = parse_kb_list(args)

        assert result["entity_id"] == entity_id
        assert result["domain"] == domain
        assert result["spaces"] is None


# ---------------------------------------------------------------------------
# Strategy for valid space names: alphanumeric, no spaces, no commas,
# no leading "--", non-empty after strip.
# ---------------------------------------------------------------------------

_space_name = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
)


# ---------------------------------------------------------------------------
# Property 13: CLI Space Flag Parsing
# ---------------------------------------------------------------------------


class TestCliSpaceFlagParsing:
    """Property 13: CLI Space Flag Parsing.

    For any valid space string(s), the CLI parsers correctly extract spaces
    from --space and --spaces flags.

    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    """

    # -- parse_kb_add with --space (single) ----------------------------------

    @settings(max_examples=100)
    @given(text=_safe_query_text, space=_space_name)
    def test_kb_add_single_space(self, text: str, space: str):
        """parse_kb_add with --space returns spaces=[space]."""
        args = f"{text} --space {space}"
        result = parse_kb_add(args)
        assert result["spaces"] == [space]
        assert result["text"] == " ".join(text.split())

    # -- parse_kb_add with --spaces (comma-separated) ------------------------

    @settings(max_examples=100)
    @given(
        text=_safe_query_text,
        spaces=st.lists(_space_name, min_size=1, max_size=5),
    )
    def test_kb_add_multiple_spaces(self, text: str, spaces: list):
        """parse_kb_add with --spaces returns all specified spaces."""
        spaces_str = ",".join(spaces)
        args = f"{text} --spaces {spaces_str}"
        result = parse_kb_add(args)
        assert result["spaces"] == spaces
        assert result["text"] == " ".join(text.split())

    # -- parse_kb_get with --space (single) ----------------------------------

    @settings(max_examples=100)
    @given(query=_safe_query_text, space=_space_name)
    def test_kb_get_single_space(self, query: str, space: str):
        """parse_kb_get with --space returns spaces=[space]."""
        args = f"{query} --space {space}"
        result = parse_kb_get(args)
        assert result["spaces"] == [space]
        assert result["query"] == " ".join(query.split())

    # -- parse_kb_get with --spaces (comma-separated) ------------------------

    @settings(max_examples=100)
    @given(
        query=_safe_query_text,
        spaces=st.lists(_space_name, min_size=1, max_size=5),
    )
    def test_kb_get_multiple_spaces(self, query: str, spaces: list):
        """parse_kb_get with --spaces returns all specified spaces."""
        spaces_str = ",".join(spaces)
        args = f"{query} --spaces {spaces_str}"
        result = parse_kb_get(args)
        assert result["spaces"] == spaces
        assert result["query"] == " ".join(query.split())

    # -- parse_kb_list with --space (single) ---------------------------------

    @settings(max_examples=100)
    @given(space=_space_name)
    def test_kb_list_single_space(self, space: str):
        """parse_kb_list with --space returns spaces=[space]."""
        args = f"--space {space}"
        result = parse_kb_list(args)
        assert result["spaces"] == [space]

    # -- parse_kb_list with --spaces (comma-separated) -----------------------

    @settings(max_examples=100)
    @given(spaces=st.lists(_space_name, min_size=1, max_size=5))
    def test_kb_list_multiple_spaces(self, spaces: list):
        """parse_kb_list with --spaces returns all specified spaces."""
        spaces_str = ",".join(spaces)
        args = f"--spaces {spaces_str}"
        result = parse_kb_list(args)
        assert result["spaces"] == spaces

    # -- No space flag returns None ------------------------------------------

    @settings(max_examples=100)
    @given(text=_safe_query_text)
    def test_no_space_flag_returns_none_add(self, text: str):
        """parse_kb_add without --space/--spaces returns spaces=None."""
        result = parse_kb_add(text)
        assert result["spaces"] is None

    @settings(max_examples=100)
    @given(query=_safe_query_text)
    def test_no_space_flag_returns_none_get(self, query: str):
        """parse_kb_get without --space/--spaces returns spaces=None."""
        result = parse_kb_get(query)
        assert result["spaces"] is None

    def test_no_space_flag_returns_none_list(self):
        """parse_kb_list without --space/--spaces returns spaces=None."""
        result = parse_kb_list("")
        assert result["spaces"] is None
