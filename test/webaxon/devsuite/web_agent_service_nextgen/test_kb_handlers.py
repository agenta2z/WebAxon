"""Unit tests for KB message handler edge cases.

Tests specific error paths and edge cases for the six kb_* handlers
and the dispatch map registration.
"""

import resolve_path  # Setup import paths  # noqa: F401

import pytest
from unittest.mock import MagicMock, patch

from webaxon.devsuite.web_agent_service_nextgen.communication.message_handlers import (
    MessageHandlers,
)
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig


# ---------------------------------------------------------------------------
# Helpers (reused from property tests)
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
# Test: Missing text in kb_add payload returns error
# Validates: Requirement 1.4
# ---------------------------------------------------------------------------


class TestKbAddMissingText:
    """handle_kb_add sends error when text is missing or empty."""

    def test_missing_text_field(self):
        handlers, agent_factory, queue_service = _make_handlers()
        message = {"type": "kb_add", "message": {}}

        handlers.handle_kb_add(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert "Missing required field: text" in resp["message"]
        assert resp["type"] == "kb_add_response"

    def test_empty_text_field(self):
        handlers, agent_factory, queue_service = _make_handlers()
        message = {"type": "kb_add", "message": {"text": ""}}

        handlers.handle_kb_add(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert "Missing required field: text" in resp["message"]

    def test_none_text_field(self):
        handlers, agent_factory, queue_service = _make_handlers()
        message = {"type": "kb_add", "message": {"text": None}}

        handlers.handle_kb_add(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False


# ---------------------------------------------------------------------------
# Test: IngestionResult with success=False returns error with messages
# Validates: Requirement 1.5
# ---------------------------------------------------------------------------


class TestKbAddIngestionFailure:
    """handle_kb_add sends error when IngestionResult.success is False."""

    def test_ingestion_failure_with_errors(self):
        handlers, agent_factory, queue_service = _make_handlers()

        # Mock the ingester to return a failed result
        ingester = MagicMock()
        result = MagicMock()
        result.success = False
        result.errors = ["error1", "error2"]
        ingester.ingest_text.return_value = result
        agent_factory.get_document_ingester.return_value = ingester
        agent_factory.get_knowledge_base.return_value = MagicMock()

        message = {"type": "kb_add", "message": {"text": "some text"}}
        handlers.handle_kb_add(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert resp["type"] == "kb_add_response"
        assert "error1" in resp["message"]
        assert "error2" in resp["message"]


# ---------------------------------------------------------------------------
# Test: Empty results from update_by_content returns "no matches" response
# Validates: Requirement 2.4
# ---------------------------------------------------------------------------


class TestKbUpdateEmptyResults:
    """handle_kb_update sends 'no matches' when update_by_content returns []."""

    def test_empty_results(self):
        handlers, agent_factory, queue_service = _make_handlers()

        updater = MagicMock()
        updater.update_by_content.return_value = []
        agent_factory.get_knowledge_updater.return_value = updater

        message = {"type": "kb_update", "message": {"text": "update something"}}
        handlers.handle_kb_update(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is True
        assert resp["results"] == []
        assert resp["count"] == 0
        assert "No pieces were updated" in resp["message"]


# ---------------------------------------------------------------------------
# Test: No candidates from delete_by_query returns empty candidates
# Validates: Requirement 3.12
# ---------------------------------------------------------------------------


class TestKbDelNoCandidates:
    """handle_kb_del search phase returns empty candidates when no match."""

    def test_no_candidates(self):
        handlers, agent_factory, queue_service = _make_handlers()

        # When delete_by_query doesn't raise ConfirmationRequiredError,
        # it means no candidates matched
        deleter = MagicMock()
        deleter.delete_by_query.return_value = None
        agent_factory.get_knowledge_deleter.return_value = deleter

        message = {
            "type": "kb_del",
            "message": {"phase": "search", "query": "nonexistent stuff"},
        }
        handlers.handle_kb_del(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is True
        assert resp["phase"] == "candidates"
        assert resp["candidates"] == []
        assert resp["count"] == 0


# ---------------------------------------------------------------------------
# Test: Piece-not-found for direct deletion
# Validates: Requirement 3.12
# ---------------------------------------------------------------------------


class TestKbDelDirectPieceNotFound:
    """handle_kb_del direct phase returns error when piece not found."""

    def test_piece_not_found(self):
        handlers, agent_factory, queue_service = _make_handlers()

        deleter = MagicMock()
        op_result = MagicMock()
        op_result.success = False
        op_result.piece_id = "nonexistent-id"
        op_result.error = "Piece not found"
        deleter.delete_by_id.return_value = op_result
        agent_factory.get_knowledge_deleter.return_value = deleter

        message = {
            "type": "kb_del",
            "message": {"phase": "direct", "piece_id": "nonexistent-id", "hard": False},
        }
        handlers.handle_kb_del(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert resp["phase"] == "done"
        assert resp["results"][0]["piece_id"] == "nonexistent-id"
        assert resp["results"][0]["success"] is False


# ---------------------------------------------------------------------------
# Test: Restore piece-not-found returns error
# Validates: Requirement 7.4
# ---------------------------------------------------------------------------


class TestKbRestorePieceNotFound:
    """handle_kb_restore sends error when piece is not found."""

    def test_piece_not_found(self):
        handlers, agent_factory, queue_service = _make_handlers()

        deleter = MagicMock()
        op_result = MagicMock()
        op_result.success = False
        op_result.piece_id = "missing-id"
        op_result.error = "Piece not found"
        deleter.restore_by_id.return_value = op_result
        agent_factory.get_knowledge_deleter.return_value = deleter

        message = {"type": "kb_restore", "message": {"piece_id": "missing-id"}}
        handlers.handle_kb_restore(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert resp["type"] == "kb_restore_response"
        assert "Piece not found" in resp["message"]


# ---------------------------------------------------------------------------
# Test: Restore already-active piece returns error
# Validates: Requirement 7.4
# ---------------------------------------------------------------------------


class TestKbRestoreAlreadyActive:
    """handle_kb_restore sends error when piece is already active."""

    def test_already_active(self):
        handlers, agent_factory, queue_service = _make_handlers()

        deleter = MagicMock()
        op_result = MagicMock()
        op_result.success = False
        op_result.piece_id = "active-id"
        op_result.error = "Already active"
        deleter.restore_by_id.return_value = op_result
        agent_factory.get_knowledge_deleter.return_value = deleter

        message = {"type": "kb_restore", "message": {"piece_id": "active-id"}}
        handlers.handle_kb_restore(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert "Already active" in resp["message"]


# ---------------------------------------------------------------------------
# Test: Restore superseded piece returns error
# Validates: Requirement 7.4
# ---------------------------------------------------------------------------


class TestKbRestoreSuperseded:
    """handle_kb_restore sends error when piece is superseded."""

    def test_superseded(self):
        handlers, agent_factory, queue_service = _make_handlers()

        deleter = MagicMock()
        op_result = MagicMock()
        op_result.success = False
        op_result.piece_id = "superseded-id"
        op_result.error = "Superseded"
        deleter.restore_by_id.return_value = op_result
        agent_factory.get_knowledge_deleter.return_value = deleter

        message = {"type": "kb_restore", "message": {"piece_id": "superseded-id"}}
        handlers.handle_kb_restore(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert "Superseded" in resp["message"]


# ---------------------------------------------------------------------------
# Test: Dispatch map contains all six new message types
# Validates: Requirement 8.1
# ---------------------------------------------------------------------------


class TestDispatchMapRegistration:
    """dispatch() routes all six kb_* message types to handlers."""

    @pytest.mark.parametrize(
        "msg_type",
        ["kb_add", "kb_update", "kb_del", "kb_get", "kb_list", "kb_restore", "kb_review_spaces"],
    )
    def test_dispatch_calls_handler(self, msg_type):
        handlers, agent_factory, queue_service = _make_handlers()

        # Patch the specific handler method to verify it gets called
        handler_method_name = f"handle_{msg_type}"
        with patch.object(handlers, handler_method_name) as mock_handler:
            message = {"type": msg_type, "message": {}}
            handlers.dispatch(message)
            mock_handler.assert_called_once_with(message)


# ---------------------------------------------------------------------------
# Test: handle_kb_add passes spaces to ingest_text
# Validates: Requirement 10.1
# ---------------------------------------------------------------------------


class TestKbAddSpacesPassthrough:
    """handle_kb_add extracts spaces from payload and passes to ingest_text."""

    def test_spaces_passed_to_ingest_text(self):
        handlers, agent_factory, queue_service = _make_handlers()

        ingester = MagicMock()
        result = MagicMock()
        result.success = True
        result.pieces_created = 1
        result.metadata_created = 0
        result.graph_nodes_created = 0
        result.graph_edges_created = 0
        ingester.ingest_text.return_value = result
        agent_factory.get_document_ingester.return_value = ingester

        mock_kb = MagicMock()
        agent_factory.get_knowledge_base.return_value = mock_kb

        message = {
            "type": "kb_add",
            "message": {"text": "hello world", "spaces": ["personal"]},
        }
        handlers.handle_kb_add(message)

        ingester.ingest_text.assert_called_once_with(
            "hello world", mock_kb, spaces=["personal"]
        )

    def test_no_spaces_passes_none(self):
        handlers, agent_factory, queue_service = _make_handlers()

        ingester = MagicMock()
        result = MagicMock()
        result.success = True
        result.pieces_created = 0
        result.metadata_created = 0
        result.graph_nodes_created = 0
        result.graph_edges_created = 0
        ingester.ingest_text.return_value = result
        agent_factory.get_document_ingester.return_value = ingester

        mock_kb = MagicMock()
        agent_factory.get_knowledge_base.return_value = mock_kb

        message = {"type": "kb_add", "message": {"text": "hello world"}}
        handlers.handle_kb_add(message)

        ingester.ingest_text.assert_called_once_with(
            "hello world", mock_kb, spaces=None
        )

    def test_multiple_spaces_passed(self):
        handlers, agent_factory, queue_service = _make_handlers()

        ingester = MagicMock()
        result = MagicMock()
        result.success = True
        result.pieces_created = 1
        result.metadata_created = 0
        result.graph_nodes_created = 0
        result.graph_edges_created = 0
        ingester.ingest_text.return_value = result
        agent_factory.get_document_ingester.return_value = ingester

        mock_kb = MagicMock()
        agent_factory.get_knowledge_base.return_value = mock_kb

        message = {
            "type": "kb_add",
            "message": {"text": "data", "spaces": ["personal", "main"]},
        }
        handlers.handle_kb_add(message)

        ingester.ingest_text.assert_called_once_with(
            "data", mock_kb, spaces=["personal", "main"]
        )


# ---------------------------------------------------------------------------
# Test: handle_kb_get passes spaces to retrieve
# Validates: Requirement 10.2
# ---------------------------------------------------------------------------


class TestKbGetSpacesPassthrough:
    """handle_kb_get extracts spaces from payload and passes to kb.retrieve."""

    def test_spaces_passed_to_retrieve(self):
        handlers, agent_factory, queue_service = _make_handlers()

        mock_retrieval_result = MagicMock()
        mock_retrieval_result.pieces = []

        mock_kb = MagicMock()
        mock_kb.retrieve.return_value = mock_retrieval_result
        agent_factory.get_knowledge_base.return_value = mock_kb

        message = {
            "type": "kb_get",
            "message": {"query": "test", "spaces": ["personal"]},
        }
        handlers.handle_kb_get(message)

        mock_kb.retrieve.assert_called_once_with(
            "test",
            domain=None,
            top_k=5,
            entity_id=None,
            tags=None,
            spaces=["personal"],
        )

    def test_no_spaces_passes_none(self):
        handlers, agent_factory, queue_service = _make_handlers()

        mock_retrieval_result = MagicMock()
        mock_retrieval_result.pieces = []

        mock_kb = MagicMock()
        mock_kb.retrieve.return_value = mock_retrieval_result
        agent_factory.get_knowledge_base.return_value = mock_kb

        message = {"type": "kb_get", "message": {"query": "test"}}
        handlers.handle_kb_get(message)

        mock_kb.retrieve.assert_called_once_with(
            "test",
            domain=None,
            top_k=5,
            entity_id=None,
            tags=None,
            spaces=None,
        )


# ---------------------------------------------------------------------------
# Test: handle_kb_list passes spaces to list_all
# Validates: Requirement 10.3
# ---------------------------------------------------------------------------


class TestKbListSpacesPassthrough:
    """handle_kb_list extracts spaces from payload and passes to piece_store.list_all."""

    def test_spaces_passed_to_list_all(self):
        handlers, agent_factory, queue_service = _make_handlers()

        mock_kb = MagicMock()
        mock_piece_store = MagicMock()
        mock_piece_store.list_all.return_value = []
        mock_kb.piece_store = mock_piece_store
        agent_factory.get_knowledge_base.return_value = mock_kb

        message = {
            "type": "kb_list",
            "message": {"spaces": ["developmental"]},
        }
        handlers.handle_kb_list(message)

        mock_piece_store.list_all.assert_called_once_with(
            entity_id=None, spaces=["developmental"]
        )

    def test_no_spaces_passes_none(self):
        handlers, agent_factory, queue_service = _make_handlers()

        mock_kb = MagicMock()
        mock_piece_store = MagicMock()
        mock_piece_store.list_all.return_value = []
        mock_kb.piece_store = mock_piece_store
        agent_factory.get_knowledge_base.return_value = mock_kb

        message = {"type": "kb_list", "message": {}}
        handlers.handle_kb_list(message)

        mock_piece_store.list_all.assert_called_once_with(
            entity_id=None, spaces=None
        )


# ---------------------------------------------------------------------------
# Test: handle_kb_review_spaces
# Validates: Requirements 10.6, 10.7, 10.8
# ---------------------------------------------------------------------------


class TestKbReviewSpacesListMode:
    """handle_kb_review_spaces in list mode returns pending suggestions."""

    def test_list_returns_pending_pieces(self):
        handlers, agent_factory, queue_service = _make_handlers()

        piece1 = _make_knowledge_piece("p1", "piece one content")
        piece1.spaces = ["main"]
        piece1.space_suggestion_status = "pending"
        piece1.pending_space_suggestions = ["personal"]
        piece1.space_suggestion_reasons = ["user entity"]
        piece1.summary = "piece one"

        piece2 = _make_knowledge_piece("p2", "piece two content")
        piece2.spaces = ["main"]
        piece2.space_suggestion_status = None
        piece2.pending_space_suggestions = None
        piece2.space_suggestion_reasons = None
        piece2.summary = None

        kb = MagicMock()
        kb.piece_store.list_all.return_value = [piece1, piece2]
        agent_factory.get_knowledge_base.return_value = kb

        message = {"type": "kb_review_spaces", "message": {"mode": "list"}}
        handlers.handle_kb_review_spaces(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is True
        assert resp["count"] == 1
        assert resp["results"][0]["piece_id"] == "p1"
        assert resp["results"][0]["current_spaces"] == ["main"]
        assert resp["results"][0]["suggested_spaces"] == ["personal"]
        assert resp["results"][0]["reasons"] == ["user entity"]

    def test_list_empty_when_no_pending(self):
        handlers, agent_factory, queue_service = _make_handlers()

        piece = _make_knowledge_piece("p1", "content")
        piece.spaces = ["main"]
        piece.space_suggestion_status = None
        piece.pending_space_suggestions = None
        piece.space_suggestion_reasons = None
        piece.summary = None

        kb = MagicMock()
        kb.piece_store.list_all.return_value = [piece]
        agent_factory.get_knowledge_base.return_value = kb

        message = {"type": "kb_review_spaces", "message": {"mode": "list"}}
        handlers.handle_kb_review_spaces(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is True
        assert resp["count"] == 0
        assert resp["results"] == []


class TestKbReviewSpacesApproveMode:
    """handle_kb_review_spaces in approve mode merges suggestions."""

    def test_approve_merges_suggestions(self):
        handlers, agent_factory, queue_service = _make_handlers()

        piece = _make_knowledge_piece("p1", "content")
        piece.spaces = ["main"]
        piece.space = "main"
        piece.pending_space_suggestions = ["personal", "developmental"]
        piece.space_suggestion_reasons = ["user entity", "test reason"]
        piece.space_suggestion_status = "pending"

        kb = MagicMock()
        kb.piece_store.get_by_id.return_value = piece
        agent_factory.get_knowledge_base.return_value = kb

        message = {"type": "kb_review_spaces", "message": {"mode": "approve", "piece_id": "p1"}}
        handlers.handle_kb_review_spaces(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is True
        assert resp["piece_id"] == "p1"
        # Verify piece was updated
        kb.piece_store.update.assert_called_once_with(piece)
        assert piece.spaces == ["main", "personal", "developmental"]
        assert piece.space == "main"
        assert piece.pending_space_suggestions is None
        assert piece.space_suggestion_reasons is None
        assert piece.space_suggestion_status == "approved"

    def test_approve_deduplicates_spaces(self):
        handlers, agent_factory, queue_service = _make_handlers()

        piece = _make_knowledge_piece("p1", "content")
        piece.spaces = ["main", "personal"]
        piece.space = "main"
        piece.pending_space_suggestions = ["personal", "developmental"]
        piece.space_suggestion_reasons = ["reason"]
        piece.space_suggestion_status = "pending"

        kb = MagicMock()
        kb.piece_store.get_by_id.return_value = piece
        agent_factory.get_knowledge_base.return_value = kb

        message = {"type": "kb_review_spaces", "message": {"mode": "approve", "piece_id": "p1"}}
        handlers.handle_kb_review_spaces(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is True
        # "personal" already in spaces, should not be duplicated
        assert piece.spaces == ["main", "personal", "developmental"]

    def test_approve_piece_not_found(self):
        handlers, agent_factory, queue_service = _make_handlers()

        kb = MagicMock()
        kb.piece_store.get_by_id.return_value = None
        agent_factory.get_knowledge_base.return_value = kb

        message = {"type": "kb_review_spaces", "message": {"mode": "approve", "piece_id": "missing"}}
        handlers.handle_kb_review_spaces(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert "not found" in resp["message"].lower()

    def test_approve_missing_piece_id(self):
        handlers, agent_factory, queue_service = _make_handlers()

        message = {"type": "kb_review_spaces", "message": {"mode": "approve"}}
        handlers.handle_kb_review_spaces(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert "piece_id" in resp["message"].lower()


class TestKbReviewSpacesRejectMode:
    """handle_kb_review_spaces in reject mode clears suggestions without changing spaces."""

    def test_reject_clears_suggestions(self):
        handlers, agent_factory, queue_service = _make_handlers()

        piece = _make_knowledge_piece("p1", "content")
        piece.spaces = ["main"]
        piece.space = "main"
        piece.pending_space_suggestions = ["personal"]
        piece.space_suggestion_reasons = ["user entity"]
        piece.space_suggestion_status = "pending"

        kb = MagicMock()
        kb.piece_store.get_by_id.return_value = piece
        agent_factory.get_knowledge_base.return_value = kb

        message = {"type": "kb_review_spaces", "message": {"mode": "reject", "piece_id": "p1"}}
        handlers.handle_kb_review_spaces(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is True
        assert resp["piece_id"] == "p1"
        # Verify spaces unchanged
        assert piece.spaces == ["main"]
        assert piece.pending_space_suggestions is None
        assert piece.space_suggestion_reasons is None
        assert piece.space_suggestion_status == "rejected"
        kb.piece_store.update.assert_called_once_with(piece)

    def test_reject_piece_not_found(self):
        handlers, agent_factory, queue_service = _make_handlers()

        kb = MagicMock()
        kb.piece_store.get_by_id.return_value = None
        agent_factory.get_knowledge_base.return_value = kb

        message = {"type": "kb_review_spaces", "message": {"mode": "reject", "piece_id": "missing"}}
        handlers.handle_kb_review_spaces(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert "not found" in resp["message"].lower()

    def test_reject_missing_piece_id(self):
        handlers, agent_factory, queue_service = _make_handlers()

        message = {"type": "kb_review_spaces", "message": {"mode": "reject"}}
        handlers.handle_kb_review_spaces(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert "piece_id" in resp["message"].lower()


class TestKbReviewSpacesDispatch:
    """dispatch() routes kb_review_spaces to the handler."""

    def test_dispatch_routes_kb_review_spaces(self):
        handlers, agent_factory, queue_service = _make_handlers()

        with patch.object(handlers, "handle_kb_review_spaces") as mock_handler:
            message = {"type": "kb_review_spaces", "message": {}}
            handlers.dispatch(message)
            mock_handler.assert_called_once_with(message)


# ---------------------------------------------------------------------------
# Test: handle_kb_update passes update_instruction
# Validates: Instruction-mode fix (Step 3a)
# ---------------------------------------------------------------------------


class TestKbUpdateInstructionPassthrough:
    """handle_kb_update passes text as update_instruction to update_by_content."""

    def test_kb_update_passes_update_instruction(self):
        handlers, agent_factory, queue_service = _make_handlers()

        updater = MagicMock()
        updater.update_by_content.return_value = []
        agent_factory.get_knowledge_updater.return_value = updater

        message = {
            "type": "kb_update",
            "message": {"text": 'change "shopping" to "price-checking"'},
        }
        handlers.handle_kb_update(message)

        updater.update_by_content.assert_called_once_with(
            'change "shopping" to "price-checking"',
            update_instruction='change "shopping" to "price-checking"',
        )

    def test_kb_update_failure_results_reported(self):
        """When results contain failures, response includes errors list."""
        handlers, agent_factory, queue_service = _make_handlers()

        # Mock a failure result
        fail_result = MagicMock()
        fail_result.success = False
        fail_result.piece_id = "piece-1"
        fail_result.error = "Instruction-mode content generation failed"

        updater = MagicMock()
        updater.update_by_content.return_value = [fail_result]
        agent_factory.get_knowledge_updater.return_value = updater

        message = {"type": "kb_update", "message": {"text": "rewrite this"}}
        handlers.handle_kb_update(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is False
        assert resp["count"] == 0
        assert len(resp["errors"]) == 1
        assert "generation failed" in resp["errors"][0].lower()
        assert "failed" in resp["message"].lower()

    def test_kb_update_mixed_success_and_failure(self):
        """When results contain both successes and failures, response reflects both."""
        handlers, agent_factory, queue_service = _make_handlers()

        success_result = MagicMock()
        success_result.success = True
        success_result.piece_id = "piece-1"
        success_result.old_version = 1
        success_result.new_version = 2
        success_result.details = {"action": "replace"}
        success_result.operation = "update"

        fail_result = MagicMock()
        fail_result.success = False
        fail_result.piece_id = "piece-2"
        fail_result.error = "Content generation failed"

        updater = MagicMock()
        updater.update_by_content.return_value = [success_result, fail_result]
        agent_factory.get_knowledge_updater.return_value = updater

        message = {"type": "kb_update", "message": {"text": "update stuff"}}
        handlers.handle_kb_update(message)

        resp = _sent_response(queue_service)
        assert resp["success"] is True  # At least one succeeded
        assert resp["count"] == 1
        assert len(resp["results"]) == 1
        assert resp["results"][0]["piece_id"] == "piece-1"
        assert len(resp["errors"]) == 1
        assert "generation failed" in resp["errors"][0].lower()
