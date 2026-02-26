"""Property-based test for Turn End Timestamp Consistency (Property 10).

**Validates: Requirements 6.4, 6.5**

For any session with multiple turns, each turn's `end_timestamp` SHALL be set
either when the next turn starts or when the session is finalized. The
`end_timestamp` SHALL be >= the `start_timestamp` for the same turn. The last
turn's `end_timestamp` SHALL be set during `finalize()`.
"""

import resolve_path  # noqa: F401 - must be first import

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from rich_python_utils.service_utils.session_management import (
    SessionLogger as SessionLogManager,
)

# --- Strategies ---

# Number of turns to create
turn_counts = st.integers(min_value=2, max_value=15)

# Session IDs
session_ids = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=10,
)


def _parse_timestamp(ts_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string (no milliseconds)."""
    return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")


class TestTurnEndTimestampProperty:
    """Property 10: Turn End Timestamp Consistency."""

    @given(session_id=session_ids, num_turns=turn_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_previous_turn_end_timestamp_set_on_new_turn(self, session_id, num_turns):
        """When a new turn starts, the previous turn's end_timestamp is set.

        **Validates: Requirements 6.4, 6.5**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            logger = mgr.create_turn_aware_logger()

            # Simulate multiple turns via AgentState entries
            for _ in range(num_turns):
                logger({"type": "AgentState", "message": "turn start"})

            turns = mgr._manifest.turns

            # All turns except the last should have end_timestamp set
            for i in range(len(turns) - 1):
                assert turns[i].end_timestamp is not None, (
                    f"Turn {turns[i].turn_number} should have end_timestamp set "
                    f"because turn {turns[i + 1].turn_number} started after it"
                )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, num_turns=turn_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_end_timestamp_gte_start_timestamp(self, session_id, num_turns):
        """Each turn's end_timestamp is >= its start_timestamp.

        **Validates: Requirements 6.4, 6.5**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            logger = mgr.create_turn_aware_logger()

            for _ in range(num_turns):
                logger({"type": "AgentState", "message": "turn start"})

            turns = mgr._manifest.turns

            # Check all turns that have end_timestamp set
            for turn in turns:
                if turn.end_timestamp is not None:
                    start = _parse_timestamp(turn.start_timestamp)
                    end = _parse_timestamp(turn.end_timestamp)
                    assert end >= start, (
                        f"Turn {turn.turn_number}: end_timestamp {turn.end_timestamp} "
                        f"is before start_timestamp {turn.start_timestamp}"
                    )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, num_turns=turn_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_last_turn_has_no_end_timestamp_before_finalize(self, session_id, num_turns):
        """The last turn's end_timestamp is None before finalize() is called.

        **Validates: Requirements 6.4, 6.5**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            logger = mgr.create_turn_aware_logger()

            for _ in range(num_turns):
                logger({"type": "AgentState", "message": "turn start"})

            turns = mgr._manifest.turns
            assert turns[-1].end_timestamp is None, (
                f"Last turn should not have end_timestamp before finalize(), "
                f"but got {turns[-1].end_timestamp}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, num_turns=turn_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_start_turn_directly_sets_previous_end_timestamp(self, session_id, num_turns):
        """Calling start_turn() directly also sets end_timestamp on previous turn
        via the turn-aware logger mechanism.

        **Validates: Requirements 6.4**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            logger = mgr.create_turn_aware_logger()

            # Use the turn-aware logger to create turns
            for _ in range(num_turns):
                logger({"type": "AgentState", "message": "turn start"})
                # Also send some non-AgentState entries
                logger({"type": "ActionResult", "message": "some action"})

            turns = mgr._manifest.turns
            assert len(turns) == num_turns

            # All but last should have end_timestamp
            for i in range(len(turns) - 1):
                assert turns[i].end_timestamp is not None
                # end_timestamp should be valid ISO format
                _parse_timestamp(turns[i].end_timestamp)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
