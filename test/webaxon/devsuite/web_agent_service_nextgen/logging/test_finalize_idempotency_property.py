"""Property-based test for Finalize Idempotency (Property 11).

**Validates: Requirement 6.5**

For any session, calling `finalize()` multiple times with any combination of
status values SHALL produce the same manifest state as calling it once. The first
call sets the end_timestamp and status; subsequent calls are no-ops.
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

status_values = st.sampled_from(["completed", "error", "cancelled", "timeout"])

turn_counts = st.integers(min_value=0, max_value=5)

# Lists of status values for multiple finalize calls
finalize_call_statuses = st.lists(status_values, min_size=2, max_size=6)


class TestFinalizeIdempotencyProperty:
    """Property 11: Finalize Idempotency."""

    @given(
        session_id=session_ids,
        first_status=status_values,
        subsequent_statuses=finalize_call_statuses,
        num_turns=turn_counts,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_multiple_finalize_calls_produce_same_manifest_as_single_call(
        self, session_id, first_status, subsequent_statuses, num_turns,
    ):
        """Calling finalize() multiple times SHALL produce the same manifest as once.

        **Validates: Requirement 6.5**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            # --- Session A: finalize once ---
            mgr_a = SessionLogManager(
                base_log_dir=tmp_dir / "a",
                session_id=session_id,
                session_type="TestAgent",
            )
            for t in range(1, num_turns + 1):
                mgr_a.start_turn(t)

            mgr_a.finalize(first_status)
            manifest_a = mgr_a.get_manifest()

            # --- Session B: finalize multiple times ---
            mgr_b = SessionLogManager(
                base_log_dir=tmp_dir / "b",
                session_id=session_id,
                session_type="TestAgent",
            )
            for t in range(1, num_turns + 1):
                mgr_b.start_turn(t)

            mgr_b.finalize(first_status)
            for status in subsequent_statuses:
                mgr_b.finalize(status)
            manifest_b = mgr_b.get_manifest()

            # Compare key fields (session_dir will differ, so compare selectively)
            assert manifest_a["status"] == manifest_b["status"], (
                f"Status mismatch: {manifest_a['status']} vs {manifest_b['status']}"
            )
            assert manifest_a["end_timestamp"] is not None
            assert manifest_b["end_timestamp"] is not None
            assert manifest_a["status"] == first_status
            assert manifest_b["status"] == first_status
            assert len(manifest_a["turns"]) == len(manifest_b["turns"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        first_status=status_values,
        second_status=status_values,
        num_turns=turn_counts,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_second_finalize_does_not_change_status(
        self, session_id, first_status, second_status, num_turns,
    ):
        """The second finalize() call SHALL NOT change the status.

        **Validates: Requirement 6.5**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )
            for t in range(1, num_turns + 1):
                mgr.start_turn(t)

            mgr.finalize(first_status)
            manifest_after_first = mgr.get_manifest()

            mgr.finalize(second_status)
            manifest_after_second = mgr.get_manifest()

            assert manifest_after_first["status"] == first_status
            assert manifest_after_second["status"] == first_status
            assert manifest_after_first["end_timestamp"] == manifest_after_second["end_timestamp"]
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        first_status=status_values,
        num_turns=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_finalize_sets_end_timestamp_on_last_turn(
        self, session_id, first_status, num_turns,
    ):
        """Finalize SHALL set end_timestamp on the last turn if not already set.

        **Validates: Requirement 6.5**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )
            for t in range(1, num_turns + 1):
                mgr.start_turn(t)

            # Before finalize, last turn should have no end_timestamp
            assert mgr._manifest.turns[-1].end_timestamp is None

            mgr.finalize(first_status)

            # After finalize, last turn should have end_timestamp set
            assert mgr._manifest.turns[-1].end_timestamp is not None
            assert mgr._manifest.turns[-1].end_timestamp == mgr._manifest.end_timestamp
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        first_status=status_values,
        second_status=status_values,
        num_turns=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_second_finalize_does_not_change_last_turn_end_timestamp(
        self, session_id, first_status, second_status, num_turns,
    ):
        """Second finalize() SHALL NOT change the last turn's end_timestamp.

        **Validates: Requirement 6.5**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )
            for t in range(1, num_turns + 1):
                mgr.start_turn(t)

            mgr.finalize(first_status)
            last_turn_ts_after_first = mgr._manifest.turns[-1].end_timestamp

            mgr.finalize(second_status)
            last_turn_ts_after_second = mgr._manifest.turns[-1].end_timestamp

            assert last_turn_ts_after_first == last_turn_ts_after_second
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        status=status_values,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_finalize_with_no_turns_is_safe(
        self, session_id, status,
    ):
        """Finalize SHALL work correctly even with zero turns.

        **Validates: Requirement 6.5**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            # No turns started — finalize should still work
            mgr.finalize(status)
            manifest = mgr.get_manifest()

            assert manifest["status"] == status
            assert manifest["end_timestamp"] is not None
            assert len(manifest["turns"]) == 0

            # Second call should be no-op
            mgr.finalize("different_status")
            manifest2 = mgr.get_manifest()
            assert manifest2["status"] == status
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
