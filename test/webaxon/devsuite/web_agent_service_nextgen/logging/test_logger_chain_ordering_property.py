"""Property-based test for Logger Chain Ordering (Property 13).

**Validates: Design constraint (turn-aware logger before artifact logger)**

For any log entry processed through the logger chain, the turn-aware logger
SHALL execute before the artifact logger. This ensures that when an AgentState
entry triggers a new turn, the artifact logger uses the updated turn number
and reset step counter.

The correct ordering is:
1. Turn-aware logger (detects turn boundary, calls start_turn(), resets step counter)
2. Artifact logger (uses updated _current_turn_number and fresh _turn_step_counter)
3. Any additional backend loggers
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
    max_size=20,
)

# Artifact-worthy log types (excluding AgentState since it triggers turns)
non_turn_artifact_types = st.sampled_from([
    "ReasonerInput",
    "ReasonerResponse",
    "AgentResponse",
    "AgentActionResults",
    "AgentActionError",
    "Screenshot",
    "HtmlSnapshot",
    "AgentNextActions",
])

# Number of non-AgentState artifacts per turn
artifacts_per_turn = st.integers(min_value=1, max_value=5)

# Number of turns
turn_counts = st.integers(min_value=2, max_value=6)


class TestLoggerChainOrderingProperty:
    """Property 13: Logger Chain Ordering.

    The turn-aware logger MUST run before the artifact logger so that when
    an AgentState entry triggers a new turn, the artifact logger uses the
    updated turn number and reset step counter.
    """

    @given(
        session_id=session_ids,
        producer=class_names,
        artifact_type=non_turn_artifact_types,
        num_turns=turn_counts,
        num_artifacts=artifacts_per_turn,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_correct_ordering_artifacts_use_new_turn_number(
        self, session_id, class_name, artifact_type, num_turns, num_artifacts
    ):
        """When turn-aware logger runs FIRST, artifacts land under the correct new turn.

        **Validates: Design constraint (turn-aware logger before artifact logger)**

        Simulates the correct logger chain ordering:
        1. Turn-aware logger processes AgentState -> increments turn, resets step
        2. Artifact logger processes subsequent entries -> uses new turn number
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            turn_logger = mgr.create_turn_aware_logger()
            artifact_logger = mgr.create_artifact_logger()

            for turn_idx in range(num_turns):
                # CORRECT ORDER: turn-aware logger first, then artifact logger
                agent_state_entry = {
                    "type": "AgentState",
                    "name": class_name,
                    "item": f"Turn {turn_idx + 1} state",
                }
                turn_logger(agent_state_entry)
                artifact_logger(agent_state_entry)

                # Now log some non-AgentState artifacts in this turn
                for art_idx in range(num_artifacts):
                    entry = {
                        "type": artifact_type,
                        "name": class_name,
                        "item": f"artifact {art_idx}",
                    }
                    turn_logger(entry)
                    artifact_logger(entry)

            # Verify: each turn should have artifacts under the correct turn number
            manifest = mgr._manifest
            assert len(manifest.turns) == num_turns

            for i, turn_entry in enumerate(manifest.turns):
                expected_turn = i + 1
                assert turn_entry.turn_number == expected_turn

                # Each turn gets: 1 AgentState artifact + num_artifacts non-AgentState
                expected_artifact_count = 1 + num_artifacts
                assert len(turn_entry.artifacts) == expected_artifact_count, (
                    f"Turn {expected_turn}: expected {expected_artifact_count} artifacts, "
                    f"got {len(turn_entry.artifacts)}"
                )

                # Step counter should be sequential starting from 1
                steps = [a.step for a in turn_entry.artifacts]
                assert steps == list(range(1, expected_artifact_count + 1)), (
                    f"Turn {expected_turn}: steps {steps} should be "
                    f"{list(range(1, expected_artifact_count + 1))}"
                )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        producer=class_names,
        artifact_type=non_turn_artifact_types,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_wrong_ordering_artifacts_use_stale_turn_number(
        self, session_id, class_name, artifact_type
    ):
        """When artifact logger runs FIRST (wrong order), artifacts land under stale turn.

        **Validates: Design constraint (turn-aware logger before artifact logger)**

        Simulates the WRONG logger chain ordering to demonstrate the bug:
        1. Artifact logger processes AgentState -> uses OLD turn number and stale step
        2. Turn-aware logger processes AgentState -> increments turn, resets step
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            turn_logger = mgr.create_turn_aware_logger()
            artifact_logger = mgr.create_artifact_logger()

            # First turn (correct — no prior state to be stale about)
            agent_state_1 = {
                "type": "AgentState",
                "name": class_name,
                "item": "Turn 1 state",
            }
            turn_logger(agent_state_1)
            artifact_logger(agent_state_1)

            # Log an artifact in turn 1
            entry_1 = {
                "type": artifact_type,
                "name": class_name,
                "item": "artifact in turn 1",
            }
            turn_logger(entry_1)
            artifact_logger(entry_1)

            # Second turn — WRONG ORDER: artifact logger before turn-aware logger
            agent_state_2 = {
                "type": "AgentState",
                "name": class_name,
                "item": "Turn 2 state",
            }

            # Record state before wrong-order processing
            turn_before = mgr._current_turn_number
            step_before = mgr._turn_step_counter

            # WRONG: artifact logger runs first (still sees turn 1)
            artifact_logger(agent_state_2)

            # The artifact was registered under the OLD turn number
            turn_1_artifacts = mgr._manifest.turns[0].artifacts
            # Turn 1 now has 3 artifacts: AgentState(1), artifact_type(1), AgentState(2-stale)
            stale_artifact = turn_1_artifacts[-1]
            assert stale_artifact.type == "AgentState", (
                "The stale AgentState artifact should be in turn 1 (wrong turn)"
            )

            # Step counter was NOT reset — it continued from the old turn
            assert stale_artifact.step == step_before + 1, (
                f"Step should be {step_before + 1} (stale counter), got {stale_artifact.step}"
            )

            # NOW the turn-aware logger runs (correct order would have been first)
            turn_logger(agent_state_2)

            # Turn 2 now exists but the AgentState artifact is stuck in turn 1
            assert len(mgr._manifest.turns) == 2
            assert mgr._current_turn_number == 2
            assert mgr._turn_step_counter == 0  # Reset by start_turn

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        producer=class_names,
        num_turns=turn_counts,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_step_counter_resets_on_new_turn_with_correct_ordering(
        self, session_id, class_name, num_turns
    ):
        """With correct ordering, step counter resets to 0 at each new turn.

        **Validates: Design constraint (turn-aware logger before artifact logger)**

        The turn-aware logger calls start_turn() which resets _turn_step_counter
        to 0. The artifact logger then increments from 1 for the first artifact
        in the new turn.
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            turn_logger = mgr.create_turn_aware_logger()
            artifact_logger = mgr.create_artifact_logger()

            for turn_idx in range(num_turns):
                # Correct order: turn-aware first
                agent_state = {
                    "type": "AgentState",
                    "name": class_name,
                    "item": f"Turn {turn_idx + 1}",
                }
                turn_logger(agent_state)

                # After turn-aware logger processes AgentState, step counter is 0
                assert mgr._turn_step_counter == 0, (
                    f"After turn-aware logger, step counter should be 0, "
                    f"got {mgr._turn_step_counter}"
                )

                # Artifact logger processes the same AgentState entry
                artifact_logger(agent_state)

                # Step counter should now be 1 (first artifact in this turn)
                assert mgr._turn_step_counter == 1, (
                    f"After first artifact, step counter should be 1, "
                    f"got {mgr._turn_step_counter}"
                )

                # Verify the artifact is registered under the correct turn
                current_turn_entry = mgr._manifest.turns[-1]
                assert current_turn_entry.turn_number == turn_idx + 1
                assert len(current_turn_entry.artifacts) >= 1
                assert current_turn_entry.artifacts[-1].step == 1

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        producer=class_names,
        artifact_type=non_turn_artifact_types,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_turn_number_propagates_to_artifact_filenames(
        self, session_id, class_name, artifact_type
    ):
        """With correct ordering, artifact filenames contain the new turn number.

        **Validates: Design constraint (turn-aware logger before artifact logger)**

        When the turn-aware logger runs first, the artifact logger creates files
        with the updated turn number in the filename.
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            turn_logger = mgr.create_turn_aware_logger()
            artifact_logger = mgr.create_artifact_logger()

            # Start turn 1
            turn_logger({"type": "AgentState", "name": class_name, "item": "state1"})
            artifact_logger({"type": "AgentState", "name": class_name, "item": "state1"})

            # Start turn 2 (correct order)
            turn_logger({"type": "AgentState", "name": class_name, "item": "state2"})

            # Log an artifact — should use turn 2
            entry = {"type": artifact_type, "name": class_name, "item": "data"}
            artifact_logger(entry)

            # Find the artifact file for this entry
            artifact_files = sorted(mgr.artifacts_dir.iterdir())
            # Last artifact file should be for turn 2
            last_file = artifact_files[-1]
            assert last_file.name.startswith("turn_002_"), (
                f"Artifact filename '{last_file.name}' should start with 'turn_002_' "
                f"(turn 2), indicating correct ordering"
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
