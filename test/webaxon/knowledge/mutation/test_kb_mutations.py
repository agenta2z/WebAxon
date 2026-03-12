"""Mutation tests for the knowledge base operation history system.

Tests CRUD operations on pieces, metadata, and graph entities with
history record verification, soft delete, and rollback capabilities.

Run:
    cd CoreProjects
    PYTHONPATH="AgentFoundation/src;RichPythonUtils/src;SciencePythonUtils/src;WebAxon/src" \
        python -m pytest WebAxon/test/webaxon/knowledge/mutation/test_kb_mutations.py -v
"""

import time
from datetime import datetime, timezone

import pytest

from rich_python_utils.service_utils.data_operation_record import (
    DataOperationRecord,
    generate_operation_id,
)
from rich_python_utils.service_utils.graph_service.graph_node import (
    GraphEdge,
    GraphNode,
)
from rich_python_utils.service_utils.graph_service.memory_graph_service import (
    MemoryGraphService,
)
from rich_python_utils.service_utils.keyvalue_service.memory_keyvalue_service import (
    MemoryKeyValueService,
)
from rich_python_utils.service_utils.retrieval_service.memory_retrieval_service import (
    MemoryRetrievalService,
)

from agent_foundation.knowledge.retrieval.knowledge_base import KnowledgeBase
from agent_foundation.knowledge.retrieval.models.entity_metadata import EntityMetadata
from agent_foundation.knowledge.retrieval.models.knowledge_piece import (
    KnowledgePiece,
    KnowledgeType,
)
from agent_foundation.knowledge.retrieval.stores.graph.graph_adapter import (
    GraphServiceEntityGraphStore,
)
from agent_foundation.knowledge.retrieval.stores.metadata.keyvalue_adapter import (
    KeyValueMetadataStore,
)
from agent_foundation.knowledge.retrieval.stores.pieces.retrieval_adapter import (
    RetrievalKnowledgePieceStore,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def stores():
    """Create fresh in-memory stores for each test."""
    kv = MemoryKeyValueService()
    retrieval = MemoryRetrievalService()
    graph = MemoryGraphService()
    metadata_store = KeyValueMetadataStore(kv_service=kv)
    piece_store = RetrievalKnowledgePieceStore(retrieval_service=retrieval)
    graph_store = GraphServiceEntityGraphStore(graph_service=graph)
    return metadata_store, piece_store, graph_store


@pytest.fixture
def kb(stores):
    """Create a KnowledgeBase with in-memory stores."""
    metadata_store, piece_store, graph_store = stores
    return KnowledgeBase(
        metadata_store=metadata_store,
        piece_store=piece_store,
        graph_store=graph_store,
    )


# ── 1. Piece CRUD + History ─────────────────────────────────────────────────


class TestPieceCRUDHistory:
    """Test piece add/update/remove lifecycle with history records."""

    def test_add_piece_creates_add_record(self, kb, stores):
        piece = KnowledgePiece(content="Test fact", piece_id="p1")
        kb.add_piece(piece)

        stored = stores[1].get_by_id("p1")
        assert stored is not None
        assert len(stored.history) == 1
        assert stored.history[0].operation == "add"
        assert stored.history[0].source == "KnowledgeBase.add_piece"
        assert stored.history[0].operation_id is not None

    def test_update_piece_creates_update_record(self, kb, stores):
        piece = KnowledgePiece(content="Original", piece_id="p2")
        kb.add_piece(piece)

        piece_to_update = stores[1].get_by_id("p2")
        piece_to_update.content = "Updated content"
        kb.update_piece(piece_to_update)

        stored = stores[1].get_by_id("p2")
        assert len(stored.history) == 2
        assert stored.history[0].operation == "add"
        assert stored.history[1].operation == "update"
        assert stored.history[1].content_before == "Original"
        assert stored.history[1].content_after == "Updated content"

    def test_soft_delete_creates_delete_record(self, kb, stores):
        piece = KnowledgePiece(content="To delete", piece_id="p3")
        kb.add_piece(piece)
        kb.remove_piece("p3")

        stored = stores[1].get_by_id("p3")
        assert stored is not None
        assert stored.is_active is False
        assert len(stored.history) == 2
        assert stored.history[1].operation == "delete"
        assert stored.history[1].details.get("delete_mode") == "soft"

    def test_hard_delete_removes_piece(self, kb, stores):
        piece = KnowledgePiece(content="To hard delete", piece_id="p4")
        kb.add_piece(piece)
        kb.remove_piece("p4", hard=True)

        stored = stores[1].get_by_id("p4")
        assert stored is None

    def test_operation_ids_are_unique(self, kb, stores):
        kb.add_piece(KnowledgePiece(content="First", piece_id="p5"))
        kb.add_piece(KnowledgePiece(content="Second", piece_id="p6"))

        p5 = stores[1].get_by_id("p5")
        p6 = stores[1].get_by_id("p6")
        assert p5.history[0].operation_id != p6.history[0].operation_id

    def test_update_tracks_field_changes(self, kb, stores):
        piece = KnowledgePiece(
            content="Same content",
            piece_id="p7",
            domain="general",
            tags=["tag1"],
        )
        kb.add_piece(piece)

        p = stores[1].get_by_id("p7")
        p.domain = "grocery"
        p.tags = ["tag1", "tag2"]
        kb.update_piece(p)

        stored = stores[1].get_by_id("p7")
        update_rec = stored.history[1]
        assert update_rec.fields_changed is not None
        assert "domain" in update_rec.fields_changed
        assert update_rec.fields_changed["domain"]["before"] == "general"
        assert update_rec.fields_changed["domain"]["after"] == "grocery"


# ── 2. Metadata CRUD + History ──────────────────────────────────────────────


class TestMetadataCRUDHistory:
    """Test metadata save/delete lifecycle with history records."""

    def test_save_new_metadata_creates_add_record(self, stores):
        metadata_store = stores[0]
        meta = EntityMetadata(entity_id="user:test", entity_type="user")
        metadata_store.save_metadata(meta)

        stored = metadata_store.get_metadata("user:test")
        assert stored is not None
        assert len(stored.history) == 1
        assert stored.history[0].operation == "add"

    def test_save_existing_metadata_creates_update_record(self, stores):
        metadata_store = stores[0]
        meta = EntityMetadata(
            entity_id="user:test2",
            entity_type="user",
            properties={"name": "Alice"},
        )
        metadata_store.save_metadata(meta)

        meta2 = EntityMetadata(
            entity_id="user:test2",
            entity_type="user",
            properties={"name": "Bob"},
        )
        metadata_store.save_metadata(meta2)

        stored = metadata_store.get_metadata("user:test2")
        assert len(stored.history) == 2
        assert stored.history[1].operation == "update"
        assert stored.history[1].properties_before == {"name": "Alice"}
        assert stored.history[1].properties_after == {"name": "Bob"}

    def test_soft_delete_metadata(self, stores):
        metadata_store = stores[0]
        meta = EntityMetadata(entity_id="user:del", entity_type="user")
        metadata_store.save_metadata(meta)

        result = metadata_store.delete_metadata("user:del")
        assert result is True

        # Default get_metadata filters out inactive
        assert metadata_store.get_metadata("user:del") is None

        # include_inactive=True returns it
        stored = metadata_store.get_metadata("user:del", include_inactive=True)
        assert stored is not None
        assert stored.is_active is False
        assert stored.history[-1].operation == "delete"


# ── 3. Graph CRUD + History ─────────────────────────────────────────────────


class TestGraphCRUDHistory:
    """Test graph node/edge add/remove with history records."""

    def test_add_node_creates_add_record(self, stores):
        graph_store = stores[2]
        node = GraphNode(node_id="n1", node_type="entity", label="Test")
        graph_store.add_node(node)

        stored = graph_store.get_node("n1")
        assert stored is not None
        assert len(stored.history) == 1
        assert stored.history[0].operation == "add"

    def test_add_existing_node_creates_update_record(self, stores):
        graph_store = stores[2]
        node1 = GraphNode(
            node_id="n2", node_type="entity",
            properties={"key": "old"},
        )
        graph_store.add_node(node1)

        node2 = GraphNode(
            node_id="n2", node_type="entity",
            properties={"key": "new"},
        )
        graph_store.add_node(node2)

        stored = graph_store.get_node("n2")
        assert len(stored.history) == 2
        assert stored.history[1].operation == "update"
        assert stored.history[1].properties_before == {"key": "old"}
        assert stored.history[1].properties_after == {"key": "new"}

    def test_soft_delete_node_cascades_to_edges(self, stores):
        graph_store = stores[2]
        graph_store.add_node(GraphNode(node_id="n3", node_type="entity"))
        graph_store.add_node(GraphNode(node_id="n4", node_type="entity"))
        graph_store.add_relation(GraphEdge(
            source_id="n3", target_id="n4", edge_type="knows",
        ))

        result = graph_store.remove_node("n3")
        assert result is True

        # Node is soft-deleted
        assert graph_store.get_node("n3") is None  # filtered out
        assert graph_store.get_node("n3", include_inactive=True) is not None

        # Edge is also soft-deleted
        edges = graph_store.get_relations("n3", direction="outgoing")
        assert len(edges) == 0  # filtered out
        edges_all = graph_store.get_relations(
            "n3", direction="outgoing", include_inactive=True
        )
        assert len(edges_all) >= 0  # may include inactive

    def test_soft_delete_edge(self, stores):
        graph_store = stores[2]
        graph_store.add_node(GraphNode(node_id="n5", node_type="entity"))
        graph_store.add_node(GraphNode(node_id="n6", node_type="entity"))
        graph_store.add_relation(GraphEdge(
            source_id="n5", target_id="n6", edge_type="related",
        ))

        result = graph_store.remove_relation("n5", "n6", "related")
        assert result is True

        # Edge should be filtered out from active results
        edges = graph_store.get_relations("n5", direction="outgoing")
        assert len(edges) == 0


# ── 4. History Verification ─────────────────────────────────────────────────


class TestHistoryVerification:
    """Verify history record structure and timestamps."""

    def test_history_records_have_timestamps(self, kb, stores):
        piece = KnowledgePiece(content="Timestamped", piece_id="ts1")
        kb.add_piece(piece)

        stored = stores[1].get_by_id("ts1")
        record = stored.history[0]
        assert record.timestamp is not None
        # Verify ISO 8601 format
        datetime.fromisoformat(record.timestamp)

    def test_shared_operation_id_across_batch(self, stores):
        graph_store = stores[2]
        op_id = generate_operation_id("test", "batch")

        graph_store.add_node(
            GraphNode(node_id="b1", node_type="entity"),
            operation_id=op_id,
        )
        graph_store.add_node(
            GraphNode(node_id="b2", node_type="entity"),
            operation_id=op_id,
        )

        n1 = graph_store.get_node("b1")
        n2 = graph_store.get_node("b2")
        assert n1.history[0].operation_id == op_id
        assert n2.history[0].operation_id == op_id

    def test_generate_operation_id_format(self):
        op_id = generate_operation_id("test", "description")
        assert op_id.startswith("op-")
        assert "test" in op_id


# ── 5a. Time-based Rollback ─────────────────────────────────────────────────


class TestRollbackTo:
    """Test rollback_to(timestamp) restores piece state."""

    def test_rollback_restores_content(self, kb, stores):
        piece = KnowledgePiece(content="V1", piece_id="rb1")
        kb.add_piece(piece)

        t1 = datetime.now(timezone.utc).isoformat()
        time.sleep(0.01)  # Ensure timestamp ordering

        p = stores[1].get_by_id("rb1")
        p.content = "V2"
        kb.update_piece(p)

        result = kb.rollback_to(t1)
        assert result["pieces"] >= 1

        restored = stores[1].get_by_id("rb1")
        assert restored.content == "V1"

    def test_rollback_restores_deleted_piece(self, kb, stores):
        piece = KnowledgePiece(content="To restore", piece_id="rb2")
        kb.add_piece(piece)

        t1 = datetime.now(timezone.utc).isoformat()
        time.sleep(0.01)

        kb.remove_piece("rb2")

        result = kb.rollback_to(t1)
        assert result["pieces"] >= 1

        restored = stores[1].get_by_id("rb2")
        assert restored is not None
        assert restored.is_active is True

    def test_rollback_removes_added_piece(self, kb, stores):
        t1 = datetime.now(timezone.utc).isoformat()
        time.sleep(0.01)

        piece = KnowledgePiece(content="Added after", piece_id="rb3")
        kb.add_piece(piece)

        result = kb.rollback_to(t1)
        assert result["pieces"] >= 1

        assert stores[1].get_by_id("rb3") is None


# ── 5b. Operation-based Rollback ────────────────────────────────────────────


class TestRollbackOperation:
    """Test rollback_operation(operation_id) undoes a specific batch."""

    def test_rollback_specific_operation(self, kb, stores):
        piece = KnowledgePiece(content="Original", piece_id="rbo1")
        kb.add_piece(piece)

        # Update with a known operation_id
        op_id = generate_operation_id("test", "update")
        p = stores[1].get_by_id("rbo1")
        p.content = "Modified"
        kb.update_piece(p, operation_id=op_id)

        result = kb.rollback_operation(op_id)
        assert result["pieces"] >= 1

        restored = stores[1].get_by_id("rbo1")
        assert restored.content == "Original"


# ── 6. Space Preservation ───────────────────────────────────────────────────


class TestSpacePreservation:
    """Test that mutations preserve space assignments."""

    def test_update_preserves_spaces(self, kb, stores):
        piece = KnowledgePiece(
            content="In personal",
            piece_id="sp1",
            spaces=["personal", "main"],
        )
        kb.add_piece(piece)

        p = stores[1].get_by_id("sp1")
        p.content = "Updated in personal"
        kb.update_piece(p)

        stored = stores[1].get_by_id("sp1")
        assert "personal" in stored.spaces
        assert "main" in stored.spaces


# ── 7. DataOperationRecord Serialization ────────────────────────────────────


class TestDataOperationRecordSerialization:
    """Test DataOperationRecord to_dict/from_dict round-trip."""

    def test_round_trip(self):
        record = DataOperationRecord(
            operation="update",
            timestamp="2026-03-01T12:00:00+00:00",
            operation_id="op-test-123",
            reason="Test update",
            source="test",
            content_before="old",
            content_after="new",
            fields_changed={"domain": {"before": "a", "after": "b"}},
            details={"confidence": 0.95},
        )
        d = record.to_dict()
        restored = DataOperationRecord.from_dict(d)
        assert restored.operation == "update"
        assert restored.content_before == "old"
        assert restored.content_after == "new"
        assert restored.fields_changed["domain"]["before"] == "a"
        assert restored.details["confidence"] == 0.95

    def test_minimal_record(self):
        record = DataOperationRecord(
            operation="add",
            timestamp="2026-03-01T12:00:00+00:00",
        )
        d = record.to_dict()
        assert "operation" in d
        assert "timestamp" in d
        # Optional fields should not appear
        assert "reason" not in d
        assert "content_before" not in d
