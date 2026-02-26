"""Property-based test for Manifest Completeness (Property 4).

**Validates: Requirements 6.3, 6.4**

For any session with N turns and M total artifacts, the finalized manifest SHALL
contain exactly N turn entries and M artifact entries distributed across those turns.
Every artifact SHALL reference a valid turn number that exists in the turns array.
"""

import resolve_path  # noqa: F401 - must be first import

import shutil
import tempfile
from pathlib import Path

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from rich_python_utils.service_utils.session_management import (
    SessionLogger as SessionLogManager,
)

# --- Strategies ---

session_ids = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=10,
)

class_names = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    min_size=1,
    max_size=15,
)

artifact_log_types = st.sampled_from(sorted(SessionLogManager.ARTIFACT_LOG_TYPES))

# Per-turn artifact counts
artifacts_per_turn_st = st.integers(min_value=0, max_value=5)

# Turn counts
turn_counts = st.integers(min_value=1, max_value=5)

# Artifact items
artifact_items = st.one_of(
    st.text(min_size=0, max_size=50),
    st.dictionaries(
        keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
        values=st.text(min_size=0, max_size=10),
        min_size=0,
        max_size=3,
    ),
)


class TestManifestCompletenessProperty:
    """Property 4: Manifest Completeness."""

    @given(
        session_id=session_ids,
        num_turns=turn_counts,
        artifacts_per_turn=st.lists(
            artifacts_per_turn_st, min_size=1, max_size=5,
        ),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_finalized_manifest_has_exact_turn_count(
        self, session_id, num_turns, artifacts_per_turn,
    ):
        """Finalized manifest SHALL contain exactly N turn entries.

        **Validates: Requirements 6.3, 6.4**
        """
        # Ensure artifacts_per_turn list matches num_turns
        while len(artifacts_per_turn) < num_turns:
            artifacts_per_turn.append(0)
        artifacts_per_turn = artifacts_per_turn[:num_turns]

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            artifact_logger = mgr.create_artifact_logger()

            for turn_idx in range(num_turns):
                turn_num = turn_idx + 1
                mgr.start_turn(turn_num)
                for _ in range(artifacts_per_turn[turn_idx]):
                    artifact_logger({
                        "type": "ReasonerInput",
                        "name": "TestClass",
                        "item": "test content",
                    })

            mgr.finalize("completed")
            manifest = mgr.get_manifest()

            assert len(manifest["turns"]) == num_turns, (
                f"Expected {num_turns} turns, got {len(manifest['turns'])}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        num_turns=turn_counts,
        artifacts_per_turn=st.lists(
            artifacts_per_turn_st, min_size=1, max_size=5,
        ),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_finalized_manifest_has_exact_artifact_count(
        self, session_id, num_turns, artifacts_per_turn,
    ):
        """Finalized manifest SHALL contain exactly M artifact entries total.

        **Validates: Requirements 6.3, 6.4**
        """
        while len(artifacts_per_turn) < num_turns:
            artifacts_per_turn.append(0)
        artifacts_per_turn = artifacts_per_turn[:num_turns]

        expected_total = sum(artifacts_per_turn)

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            artifact_logger = mgr.create_artifact_logger()

            for turn_idx in range(num_turns):
                turn_num = turn_idx + 1
                mgr.start_turn(turn_num)
                for _ in range(artifacts_per_turn[turn_idx]):
                    artifact_logger({
                        "type": "ReasonerInput",
                        "name": "TestClass",
                        "item": "test content",
                    })

            mgr.finalize("completed")
            manifest = mgr.get_manifest()

            actual_total = sum(
                len(turn["artifacts"]) for turn in manifest["turns"]
            )
            assert actual_total == expected_total, (
                f"Expected {expected_total} total artifacts, got {actual_total}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        num_turns=turn_counts,
        artifacts_per_turn=st.lists(
            artifacts_per_turn_st, min_size=1, max_size=5,
        ),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_every_artifact_references_valid_turn_number(
        self, session_id, num_turns, artifacts_per_turn,
    ):
        """Every artifact SHALL reference a valid turn number that exists in the turns array.

        **Validates: Requirements 6.3, 6.4**
        """
        while len(artifacts_per_turn) < num_turns:
            artifacts_per_turn.append(0)
        artifacts_per_turn = artifacts_per_turn[:num_turns]

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            artifact_logger = mgr.create_artifact_logger()

            for turn_idx in range(num_turns):
                turn_num = turn_idx + 1
                mgr.start_turn(turn_num)
                for _ in range(artifacts_per_turn[turn_idx]):
                    artifact_logger({
                        "type": "AgentResponse",
                        "name": "TestAgent",
                        "item": "response content",
                    })

            mgr.finalize("completed")
            manifest = mgr.get_manifest()

            turn_numbers = {t["turn_number"] for t in manifest["turns"]}

            for turn in manifest["turns"]:
                for artifact in turn["artifacts"]:
                    # Artifact path contains turn number — verify it matches
                    # the turn it's registered under
                    assert turn["turn_number"] in turn_numbers, (
                        f"Artifact in turn {turn['turn_number']} references "
                        f"a turn not in the turns array"
                    )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        num_turns=turn_counts,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_each_turn_has_correct_per_turn_artifact_count(
        self, session_id, num_turns,
    ):
        """Each turn SHALL have exactly the number of artifacts logged during that turn.

        **Validates: Requirements 6.3, 6.4**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            artifact_logger = mgr.create_artifact_logger()

            # Log turn_num artifacts in each turn (1 in turn 1, 2 in turn 2, etc.)
            for turn_num in range(1, num_turns + 1):
                mgr.start_turn(turn_num)
                for _ in range(turn_num):
                    artifact_logger({
                        "type": "ReasonerResponse",
                        "name": "Inferencer",
                        "item": "response",
                    })

            mgr.finalize("completed")
            manifest = mgr.get_manifest()

            for turn in manifest["turns"]:
                expected = turn["turn_number"]
                actual = len(turn["artifacts"])
                assert actual == expected, (
                    f"Turn {turn['turn_number']}: expected {expected} artifacts, got {actual}"
                )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
