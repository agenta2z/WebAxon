"""Property-based test for Turn File Ordering Consistency (Property 2).

**Validates: Requirements 2.1, 3.4**

For any sequence of turn starts, the resulting turn log files SHALL be named
with monotonically increasing turn numbers. The turn number in the filename
SHALL match the turn number in the manifest entry. Turn files SHALL have the
`.jsonl` extension.
"""

import resolve_path  # noqa: F401 - must be first import

import re
import shutil
import tempfile
from pathlib import Path

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from rich_python_utils.service_utils.session_management import (
    SessionLogger as SessionLogManager,
)

# --- Strategies ---

# Number of turns to create in a session
turn_counts = st.integers(min_value=1, max_value=15)

# Session IDs
session_ids = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=10,
)

# Turn file naming pattern: turn_{NNN}_{YYYYMMDD_HHMMSS}.jsonl
TURN_FILE_PATTERN = re.compile(r"^turn_(\d{3})_\d{8}_\d{6}\.jsonl$")


class TestTurnFileOrderingProperty:
    """Property 2: Turn File Ordering Consistency."""

    @given(session_id=session_ids, num_turns=turn_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_turn_numbers_are_monotonically_increasing(self, session_id, num_turns):
        """Turn file names contain monotonically increasing turn numbers.

        **Validates: Requirements 2.1, 3.4**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            for i in range(1, num_turns + 1):
                mgr.start_turn(i)

            # Extract turn numbers from filenames
            turn_numbers = []
            for turn_entry in mgr._manifest.turns:
                match = TURN_FILE_PATTERN.match(turn_entry.log_file)
                assert match is not None, (
                    f"Turn file '{turn_entry.log_file}' does not match expected pattern"
                )
                turn_numbers.append(int(match.group(1)))

            # Verify monotonically increasing
            for i in range(1, len(turn_numbers)):
                assert turn_numbers[i] > turn_numbers[i - 1], (
                    f"Turn numbers not monotonically increasing: {turn_numbers}"
                )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, num_turns=turn_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_filename_turn_number_matches_manifest_entry(self, session_id, num_turns):
        """The turn number in the filename matches the turn number in the manifest entry.

        **Validates: Requirements 2.1, 3.4**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            for i in range(1, num_turns + 1):
                mgr.start_turn(i)

            for turn_entry in mgr._manifest.turns:
                match = TURN_FILE_PATTERN.match(turn_entry.log_file)
                assert match is not None
                filename_turn_number = int(match.group(1))
                assert filename_turn_number == turn_entry.turn_number, (
                    f"Filename turn number {filename_turn_number} does not match "
                    f"manifest turn number {turn_entry.turn_number}"
                )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, num_turns=turn_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_all_turn_files_have_jsonl_extension(self, session_id, num_turns):
        """All turn log files have the .jsonl extension.

        **Validates: Requirements 3.4**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            for i in range(1, num_turns + 1):
                mgr.start_turn(i)

            for turn_entry in mgr._manifest.turns:
                assert turn_entry.log_file.endswith(".jsonl"), (
                    f"Turn file '{turn_entry.log_file}' does not have .jsonl extension"
                )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, num_turns=turn_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_turn_aware_logger_produces_ordered_turns(self, session_id, num_turns):
        """The turn-aware logger creates turns with monotonically increasing numbers.

        **Validates: Requirements 2.1, 3.4**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            logger = mgr.create_turn_aware_logger()

            # Simulate agent turns by sending AgentState entries
            for _ in range(num_turns):
                logger({"type": "AgentState", "message": "turn start"})

            # Verify turn numbers are monotonically increasing
            turn_numbers = [t.turn_number for t in mgr._manifest.turns]
            for i in range(1, len(turn_numbers)):
                assert turn_numbers[i] > turn_numbers[i - 1], (
                    f"Turn numbers not monotonically increasing: {turn_numbers}"
                )

            # Verify filename matches manifest
            for turn_entry in mgr._manifest.turns:
                match = TURN_FILE_PATTERN.match(turn_entry.log_file)
                assert match is not None
                assert int(match.group(1)) == turn_entry.turn_number
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
