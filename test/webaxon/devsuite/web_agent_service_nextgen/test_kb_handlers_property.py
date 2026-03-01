"""Property-based tests for KB message handlers.

Uses hypothesis to verify handler delegation and serialization properties
across generated inputs.
"""

import resolve_path  # Setup import paths  # noqa: F401

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck
from unittest.mock import MagicMock, patch

from webaxon.devsuite.web_agent_service_nextgen.communication.message_handlers import (
    MessageHandlers,
)
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

_nonempty_text = st.text(min_size=1, max_size=300).filter(lambda t: t.strip())

_piece_id = st.text(
    min_size=1,
    max_size=36,
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="-",
    ),
)

_nonneg_int = st.integers(min_value=0, max_value=1000)

_domain = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("Ll",)),
)

_tag = st.text(
    min_size=1,
    max_size=20,
    alphabet=st.characters(whitelist_categories=("Ll",)),
)

_knowledge_type = st.sampled_from(["fact", "instruction", "preference", "procedure", "note"])

_score = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

_action = st.sampled_from(["replace", "merge", "append", "no_change"])

_version = st.integers(min_value=1, max_value=100)


# ---------------------------------------------------------------------------
# Helper: create a MessageHandlers instance with mocked dependencies
# ---------------------------------------------------------------------------


def _make_handlers():
    """Create a MessageHandlers with fully mocked dependencies."""
    session_manager = MagicMock()
    agent_factory = MagicMock()
    queue_service = MagicMock()
    config = MagicMock(spec=ServiceConfig)
    config.client_control_queue_id = "test-queue"
    debugger = MagicMock()

    handlers = MessageHandlers(
        session_manager=session_manager,
        agent_factory=agent_factory,
        queue_service=queue_service,
        config=config,
        debugger=debugger,
    )
    return handlers, agent_factory, queue_service


def _sent_response(queue_service):
    """Extract the response dict sent via queue_service.put()."""
    queue_service.put.assert_called_once()
    return queue_service.put.call_args[0][1]


def _make_knowledge_piece(piece_id, content, domain="general", tags=None,
                          knowledge_type="fact", is_active=True):
    """Create a MagicMock that looks like a KnowledgePiece."""
    piece = MagicMock()
    piece.piece_id = piece_id
    piece.content = content
    piece.domain = domain
    piece.tags = tags or []
    piece.knowledge_type = knowledge_type
    piece.is_active = is_active
    return piece


# ---------------------------------------------------------------------------
# Property 6: kb-add handler delegates and serializes correctly
# ---------------------------------------------------------------------------


class TestKbAddHandlerProperty:
    """Property 6: kb-add handler delegates and serializes correctly.

    **Validates: Requirements 1.2, 1.3, 1.6, 1.8**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        text=_nonempty_text,
        pieces_created=_nonneg_int,
        metadata_created=_nonneg_int,
        graph_nodes_created=_nonneg_int,
        graph_edges_created=_nonneg_int,
    )
    def test_kb_add_handler_delegates_and_serializes(
        self, text, pieces_created, metadata_created,
        graph_nodes_created, graph_edges_created,
    ):
        # Feature: kb-cli-commands, Property 6: kb-add handler delegates and serializes correctly
        handlers, agent_factory, queue_service = _make_handlers()

        # Mock IngestionResult
        ingestion_result = MagicMock()
        ingestion_result.success = True
        ingestion_result.pieces_created = pieces_created
        ingestion_result.metadata_created = metadata_created
        ingestion_result.graph_nodes_created = graph_nodes_created
        ingestion_result.graph_edges_created = graph_edges_created

        mock_ingester = MagicMock()
        mock_ingester.ingest_text.return_value = ingestion_result
        agent_factory.get_document_ingester.return_value = mock_ingester

        mock_kb = MagicMock()
        agent_factory.get_knowledge_base.return_value = mock_kb

        message = {"type": "kb_add", "message": {"text": text}}
        handlers.handle_kb_add(message)

        # Verify delegation
        mock_ingester.ingest_text.assert_called_once_with(text, mock_kb, spaces=None)

        # Verify response serialization
        response = _sent_response(queue_service)
        assert response["type"] == "kb_add_response"
        assert response["success"] is True
        assert response["counts"]["pieces_created"] == pieces_created
        assert response["counts"]["metadata_created"] == metadata_created
        assert response["counts"]["graph_nodes_created"] == graph_nodes_created
        assert response["counts"]["graph_edges_created"] == graph_edges_created


# ---------------------------------------------------------------------------
# Property 7: kb-update handler delegates and serializes correctly
# ---------------------------------------------------------------------------


class TestKbUpdateHandlerProperty:
    """Property 7: kb-update handler delegates and serializes correctly.

    **Validates: Requirements 2.2, 2.3, 2.6, 2.8**
    """

    @settings(max_examples=100)
    @given(
        text=_nonempty_text,
        results_data=st.lists(
            st.tuples(_piece_id, _version, _version, _action),
            min_size=1,
            max_size=5,
        ),
    )
    def test_kb_update_handler_delegates_and_serializes(self, text, results_data):
        # Feature: kb-cli-commands, Property 7: kb-update handler delegates and serializes correctly
        handlers, agent_factory, queue_service = _make_handlers()

        # Build mock OperationResult list
        mock_results = []
        for pid, old_v, new_v, action in results_data:
            r = MagicMock()
            r.piece_id = pid
            r.old_version = old_v
            r.new_version = new_v
            r.operation = "update"
            r.details = {"action": action}
            mock_results.append(r)

        mock_updater = MagicMock()
        mock_updater.update_by_content.return_value = mock_results
        agent_factory.get_knowledge_updater.return_value = mock_updater

        message = {"type": "kb_update", "message": {"text": text}}
        handlers.handle_kb_update(message)

        # Verify delegation
        mock_updater.update_by_content.assert_called_once_with(text)

        # Verify response serialization
        response = _sent_response(queue_service)
        assert response["type"] == "kb_update_response"
        assert response["success"] is True
        assert len(response["results"]) == len(results_data)

        for i, (pid, old_v, new_v, action) in enumerate(results_data):
            r = response["results"][i]
            assert r["piece_id"] == pid
            assert r["old_version"] == old_v
            assert r["new_version"] == new_v
            assert r["action"] == action


# ---------------------------------------------------------------------------
# Property 8: kb-del search-phase handler serializes candidates correctly
# ---------------------------------------------------------------------------


class TestKbDelSearchPhaseProperty:
    """Property 8: kb-del search-phase handler serializes candidates correctly.

    **Validates: Requirements 3.2, 3.3**
    """

    @settings(max_examples=100)
    @given(
        query=_nonempty_text,
        candidates_data=st.lists(
            st.tuples(_piece_id, _nonempty_text, _score),
            min_size=0,
            max_size=5,
        ),
    )
    def test_kb_del_search_phase_serializes_candidates(self, query, candidates_data):
        # Feature: kb-cli-commands, Property 8: kb-del search-phase handler serializes candidates correctly
        from agent_foundation.knowledge.ingestion.knowledge_deleter import (
            ConfirmationRequiredError,
        )

        handlers, agent_factory, queue_service = _make_handlers()

        # Build candidate (KnowledgePiece, float) tuples
        candidate_tuples = []
        for pid, content, score in candidates_data:
            piece = _make_knowledge_piece(pid, content)
            candidate_tuples.append((piece, score))

        mock_deleter = MagicMock()
        if candidate_tuples:
            err = ConfirmationRequiredError(candidates=candidate_tuples)
            mock_deleter.delete_by_query.side_effect = err
        else:
            # No candidates — delete_by_query returns without raising
            mock_deleter.delete_by_query.return_value = []
        agent_factory.get_knowledge_deleter.return_value = mock_deleter

        message = {"type": "kb_del", "message": {"phase": "search", "query": query}}
        handlers.handle_kb_del(message)

        response = _sent_response(queue_service)
        assert response["type"] == "kb_del_response"
        assert response["success"] is True
        assert response["phase"] == "candidates"
        assert len(response["candidates"]) == len(candidates_data)

        for i, (pid, content, score) in enumerate(candidates_data):
            c = response["candidates"][i]
            assert c["piece_id"] == pid
            assert c["score"] == score
            # Content preview should be truncated version of content
            if len(content) <= 200:
                assert c["content_preview"] == content
            else:
                assert c["content_preview"] == content[:200] + "..."


# ---------------------------------------------------------------------------
# Property 9: kb-del confirm/direct handler delegates correctly
# ---------------------------------------------------------------------------


class TestKbDelConfirmDirectProperty:
    """Property 9: kb-del confirm/direct handler delegates correctly.

    **Validates: Requirements 3.5, 3.6, 3.7, 3.10**
    """

    @settings(max_examples=100)
    @given(
        piece_ids=st.lists(_piece_id, min_size=1, max_size=5),
        query=_nonempty_text,
    )
    def test_kb_del_confirm_phase_delegates(self, piece_ids, query):
        # Feature: kb-cli-commands, Property 9: kb-del confirm-phase delegates correctly
        handlers, agent_factory, queue_service = _make_handlers()

        mock_results = []
        for pid in piece_ids:
            r = MagicMock()
            r.piece_id = pid
            r.success = True
            r.error = None
            mock_results.append(r)

        mock_deleter = MagicMock()
        mock_deleter.delete_by_query.return_value = mock_results
        agent_factory.get_knowledge_deleter.return_value = mock_deleter

        message = {
            "type": "kb_del",
            "message": {
                "phase": "confirm",
                "query": query,
                "piece_ids": piece_ids,
            },
        }
        handlers.handle_kb_del(message)

        # Verify delegation with piece_ids
        mock_deleter.delete_by_query.assert_called_once_with(
            query, piece_ids=piece_ids
        )

        response = _sent_response(queue_service)
        assert response["type"] == "kb_del_response"
        assert response["success"] is True
        assert response["phase"] == "done"
        assert len(response["results"]) == len(piece_ids)

    @settings(max_examples=100)
    @given(
        piece_id=_piece_id,
        hard=st.booleans(),
    )
    def test_kb_del_direct_phase_delegates(self, piece_id, hard):
        # Feature: kb-cli-commands, Property 9: kb-del direct-phase delegates correctly
        from agent_foundation.knowledge.retrieval.models.enums import DeleteMode

        handlers, agent_factory, queue_service = _make_handlers()

        mock_result = MagicMock()
        mock_result.piece_id = piece_id
        mock_result.success = True
        mock_result.error = None

        mock_deleter = MagicMock()
        mock_deleter.delete_by_id.return_value = mock_result
        agent_factory.get_knowledge_deleter.return_value = mock_deleter

        message = {
            "type": "kb_del",
            "message": {
                "phase": "direct",
                "piece_id": piece_id,
                "hard": hard,
            },
        }
        handlers.handle_kb_del(message)

        expected_mode = DeleteMode.HARD if hard else DeleteMode.SOFT
        mock_deleter.delete_by_id.assert_called_once_with(piece_id, expected_mode)

        response = _sent_response(queue_service)
        assert response["type"] == "kb_del_response"
        assert response["phase"] == "done"
        expected_mode_str = "hard" if hard else "soft"
        assert response["mode"] == expected_mode_str


# ---------------------------------------------------------------------------
# Property 10: kb-get handler serializes results correctly
# ---------------------------------------------------------------------------


class TestKbGetHandlerProperty:
    """Property 10: kb-get handler serializes results correctly.

    **Validates: Requirements 4.6, 4.7**
    """

    @settings(max_examples=100)
    @given(
        pieces_data=st.lists(
            st.tuples(
                _piece_id,
                _nonempty_text,
                _domain,
                st.lists(_tag, min_size=0, max_size=3),
                _knowledge_type,
                _score,
            ),
            min_size=0,
            max_size=5,
        ),
    )
    def test_kb_get_handler_serializes_results(self, pieces_data):
        # Feature: kb-cli-commands, Property 10: kb-get handler serializes results correctly
        handlers, agent_factory, queue_service = _make_handlers()

        # Build (KnowledgePiece, float) tuples for RetrievalResult.pieces
        piece_tuples = []
        for pid, content, domain, tags, ktype, score in pieces_data:
            piece = _make_knowledge_piece(pid, content, domain, tags, ktype)
            piece_tuples.append((piece, score))

        mock_retrieval_result = MagicMock()
        mock_retrieval_result.pieces = piece_tuples

        mock_kb = MagicMock()
        mock_kb.retrieve.return_value = mock_retrieval_result
        agent_factory.get_knowledge_base.return_value = mock_kb

        message = {"type": "kb_get", "message": {"query": "test query"}}
        handlers.handle_kb_get(message)

        response = _sent_response(queue_service)
        assert response["type"] == "kb_get_response"
        assert response["success"] is True
        assert len(response["results"]) == len(pieces_data)

        for i, (pid, content, domain, tags, ktype, score) in enumerate(pieces_data):
            r = response["results"][i]
            assert r["piece_id"] == pid
            assert r["domain"] == domain
            assert r["tags"] == tags
            assert r["knowledge_type"] == ktype
            assert r["score"] == score
            # Content should be truncated to 200 chars
            if len(content) <= 200:
                assert r["content"] == content
            else:
                assert r["content"] == content[:200] + "..."


# ---------------------------------------------------------------------------
# Property 11: kb-list handler serializes results correctly
# ---------------------------------------------------------------------------


class TestKbListHandlerProperty:
    """Property 11: kb-list handler serializes results correctly.

    **Validates: Requirements 5.4, 5.5**
    """

    @settings(max_examples=100)
    @given(
        pieces_data=st.lists(
            st.tuples(
                _piece_id,
                _nonempty_text,
                _domain,
                st.lists(_tag, min_size=0, max_size=3),
                _knowledge_type,
                st.booleans(),  # is_active
            ),
            min_size=0,
            max_size=5,
        ),
        filter_domain=st.one_of(st.none(), _domain),
    )
    def test_kb_list_handler_serializes_results(self, pieces_data, filter_domain):
        # Feature: kb-cli-commands, Property 11: kb-list handler serializes results correctly
        handlers, agent_factory, queue_service = _make_handlers()

        # Build mock pieces
        mock_pieces = []
        for pid, content, domain, tags, ktype, is_active in pieces_data:
            piece = _make_knowledge_piece(pid, content, domain, tags, ktype, is_active)
            mock_pieces.append(piece)

        mock_kb = MagicMock()
        mock_piece_store = MagicMock()
        mock_piece_store.list_all.return_value = mock_pieces
        mock_kb.piece_store = mock_piece_store
        agent_factory.get_knowledge_base.return_value = mock_kb

        payload = {}
        if filter_domain is not None:
            payload["domain"] = filter_domain

        message = {"type": "kb_list", "message": payload}
        handlers.handle_kb_list(message)

        response = _sent_response(queue_service)
        assert response["type"] == "kb_list_response"
        assert response["success"] is True

        # Compute expected pieces after domain filtering
        if filter_domain is not None:
            expected = [
                (pid, content, domain, tags, ktype, is_active)
                for pid, content, domain, tags, ktype, is_active in pieces_data
                if domain == filter_domain
            ]
        else:
            expected = list(pieces_data)

        assert len(response["results"]) == len(expected)

        for i, (pid, content, domain, tags, ktype, is_active) in enumerate(expected):
            r = response["results"][i]
            assert r["piece_id"] == pid
            assert r["domain"] == domain
            assert r["tags"] == tags
            assert r["knowledge_type"] == ktype
            assert r["is_active"] == is_active
            # Content should be truncated to 200 chars
            if len(content) <= 200:
                assert r["content"] == content
            else:
                assert r["content"] == content[:200] + "..."


# ---------------------------------------------------------------------------
# Property 16: Handler exception produces error response
# ---------------------------------------------------------------------------


class TestHandlerExceptionProperty:
    """Property 16: Handler exception produces error response.

    **Validates: Requirements 8.2**
    """

    @settings(max_examples=100)
    @given(
        msg_type=st.sampled_from([
            "kb_add", "kb_update", "kb_del", "kb_get", "kb_list", "kb_restore",
        ]),
        error_text=_nonempty_text,
    )
    def test_handler_exception_produces_error_response(self, msg_type, error_text):
        # Feature: kb-cli-commands, Property 16: Handler exception produces error response
        handlers, agent_factory, queue_service = _make_handlers()

        # Make the underlying operation raise an exception
        exc = RuntimeError(error_text)

        if msg_type == "kb_add":
            agent_factory.get_document_ingester.side_effect = exc
        elif msg_type == "kb_update":
            agent_factory.get_knowledge_updater.side_effect = exc
        elif msg_type == "kb_del":
            agent_factory.get_knowledge_deleter.side_effect = exc
        elif msg_type == "kb_get":
            agent_factory.get_knowledge_base.side_effect = exc
        elif msg_type == "kb_list":
            agent_factory.get_knowledge_base.side_effect = exc
        elif msg_type == "kb_restore":
            agent_factory.get_knowledge_deleter.side_effect = exc

        # Build a minimal valid message for each type
        payloads = {
            "kb_add": {"text": "some text"},
            "kb_update": {"text": "some text"},
            "kb_del": {"phase": "search", "query": "some query"},
            "kb_get": {"query": "some query"},
            "kb_list": {},
            "kb_restore": {"piece_id": "some-id"},
        }

        message = {"type": msg_type, "message": payloads[msg_type]}

        # dispatch() catches exceptions and sends error response
        handlers.dispatch(message)

        response = _sent_response(queue_service)
        assert response["type"] == f"{msg_type}_response"
        assert error_text in response["error"]
