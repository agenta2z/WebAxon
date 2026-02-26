"""Property-based test for Session Directory Naming Uniqueness (Property 1).

**Validates: Requirements 4.1, 4.3**

For any set of session creation requests (including those within the same second),
the resulting session directory names SHALL all be unique. The directory name SHALL
match the pattern {session_id}_{YYYYMMDD_HHMMSS} or {session_id}_{YYYYMMDD_HHMMSS}_{N}
for disambiguated names.
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

# Session IDs: alphanumeric with underscores/hyphens, reasonable length
session_ids = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=15,
)

# Number of sessions to create in a batch (tests same-second collisions)
session_counts = st.integers(min_value=1, max_value=8)

# Directory name pattern: {session_id}_{YYYYMMDD_HHMMSS} or {session_id}_{YYYYMMDD_HHMMSS}_{N}
DIR_NAME_PATTERN = re.compile(
    r"^.+_\d{8}_\d{6}(_\d+)?$"
)


class TestSessionDirNamingProperty:
    """Property 1: Session Directory Naming Uniqueness."""

    @given(session_id=session_ids, count=session_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_same_session_id_produces_unique_dirs(self, session_id, count):
        """Multiple sessions with the same ID within the same second produce unique directories.

        **Validates: Requirements 4.1, 4.3**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            managers = []
            for _ in range(count):
                mgr = SessionLogManager(
                    base_log_dir=tmp_dir,
                    session_id=session_id,
                    session_type="TestAgent",
                )
                managers.append(mgr)

            # All session directories must be unique
            dir_names = [m.session_dir.name for m in managers]
            assert len(dir_names) == len(set(dir_names)), (
                f"Duplicate directory names found: {dir_names}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, count=session_counts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_directory_names_match_expected_pattern(self, session_id, count):
        """All session directory names match the naming pattern.

        **Validates: Requirements 4.1, 4.3**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            managers = []
            for _ in range(count):
                mgr = SessionLogManager(
                    base_log_dir=tmp_dir,
                    session_id=session_id,
                    session_type="TestAgent",
                )
                managers.append(mgr)

            for mgr in managers:
                dir_name = mgr.session_dir.name
                assert DIR_NAME_PATTERN.match(dir_name), (
                    f"Directory name '{dir_name}' does not match expected pattern "
                    f"'{{session_id}}_{{YYYYMMDD_HHMMSS}}' or "
                    f"'{{session_id}}_{{YYYYMMDD_HHMMSS}}_{{N}}'"
                )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_ids_list=st.lists(session_ids, min_size=2, max_size=5, unique=True),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_different_session_ids_produce_unique_dirs(self, session_ids_list):
        """Different session IDs always produce unique directories.

        **Validates: Requirements 4.1**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            managers = []
            for sid in session_ids_list:
                mgr = SessionLogManager(
                    base_log_dir=tmp_dir,
                    session_id=sid,
                    session_type="TestAgent",
                )
                managers.append(mgr)

            dir_names = [m.session_dir.name for m in managers]
            assert len(dir_names) == len(set(dir_names)), (
                f"Duplicate directory names found: {dir_names}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_session_dir_contains_session_id(self, session_id):
        """The session directory name starts with the session_id.

        **Validates: Requirements 4.1**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )
            assert mgr.session_dir.name.startswith(session_id + "_"), (
                f"Directory name '{mgr.session_dir.name}' does not start with "
                f"'{session_id}_'"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_session_dir_and_subdirs_exist(self, session_id):
        """Session directory and artifacts/overflow subdirectories are created.

        **Validates: Requirements 4.1**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )
            assert mgr.session_dir.exists() and mgr.session_dir.is_dir()
            assert mgr.artifacts_dir.exists() and mgr.artifacts_dir.name == "artifacts"
            assert mgr.overflow_dir.exists() and mgr.overflow_dir.name == "overflow"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_disambiguation_suffix_starts_at_2(self, session_id):
        """When collisions occur, the suffix starts at _2 (not _1).

        **Validates: Requirements 4.3**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr1 = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )
            mgr2 = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            name1 = mgr1.session_dir.name
            name2 = mgr2.session_dir.name
            assert name1 != name2

            # The disambiguated name should end with _2 (or higher)
            # Parse the suffix after the timestamp
            # Pattern: {session_id}_{YYYYMMDD}_{HHMMSS}_{N}
            # The timestamp part is always YYYYMMDD_HHMMSS (15 chars)
            # So the suffix is after session_id + _ + timestamp
            for name in [name1, name2]:
                # Check if this name has a disambiguation suffix
                # by seeing if the last segment after _ is a pure digit
                parts = name.split("_")
                # The timestamp is always the last two segments before any suffix
                # e.g., "mysession_20250115_103000" or "mysession_20250115_103000_2"
                last_part = parts[-1]
                if last_part.isdigit() and len(last_part) != 6:
                    # This is a disambiguation suffix (not the HHMMSS part)
                    suffix_num = int(last_part)
                    assert suffix_num >= 2, (
                        f"Disambiguation suffix should start at 2, got {suffix_num}"
                    )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
