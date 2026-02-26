"""Property-based test for Artifact Persistence and Registration (Property 7).

**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

For any artifact captured during a session turn, the artifact file SHALL exist
within the session's `artifacts/` directory, be registered in the manifest with
the correct turn number and step, and the agent SHALL have received the artifact
directory path. The artifact filename SHALL follow the pattern
`turn_{NNN}_{SSS}_{ClassName}_{LogType}_{timestamp}.{ext}` where NNN is the
three-digit turn number and SSS is the three-digit step counter.
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

# Artifact log types that the SessionLogManager recognizes
artifact_log_types = st.sampled_from(sorted(SessionLogManager.ARTIFACT_LOG_TYPES))

# Items that can be logged as artifacts
text_items = st.text(min_size=0, max_size=100)
dict_items = st.dictionaries(
    keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
    values=st.text(min_size=0, max_size=20),
    min_size=0,
    max_size=5,
)
list_items = st.lists(st.text(min_size=0, max_size=20), min_size=0, max_size=5)
artifact_items = st.one_of(text_items, dict_items, list_items)

# Number of artifacts per turn
artifacts_per_turn = st.integers(min_value=1, max_value=8)

# Number of turns
turn_counts = st.integers(min_value=1, max_value=5)

# Artifact filename pattern: turn_{NNN}_{SSS}_{ClassName}_{LogType}_{timestamp}.{ext}
ARTIFACT_FILE_PATTERN = re.compile(
    r"^turn_(\d{3})_(\d{3})_([A-Za-z]+)_([A-Za-z]+)_(\d{8}_\d{6})\.(txt|json|html|png)$"
)


class TestArtifactPersistenceProperty:
    """Property 7: Artifact Persistence and Registration."""

    @given(
        session_id=session_ids,
        producer=class_names,
        log_type=artifact_log_types,
        item=artifact_items,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_artifact_file_exists_in_artifacts_directory(
        self, session_id, class_name, log_type, item
    ):
        """Artifact files SHALL exist within the session's artifacts/ directory.

        **Validates: Requirements 5.1, 5.2**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            # Start a turn so artifacts have a turn to register against
            mgr.start_turn(1)

            # Create artifact logger and log an entry
            artifact_logger = mgr.create_artifact_logger()
            artifact_logger({"type": log_type, "name": class_name, "item": item})

            # Verify at least one artifact file exists in artifacts/
            artifact_files = list(mgr.artifacts_dir.iterdir())
            assert len(artifact_files) == 1, (
                f"Expected 1 artifact file, found {len(artifact_files)}"
            )

            # Verify the file is inside the artifacts directory
            assert artifact_files[0].parent == mgr.artifacts_dir
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        producer=class_names,
        log_type=artifact_log_types,
        item=artifact_items,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_artifact_filename_follows_naming_pattern(
        self, session_id, class_name, log_type, item
    ):
        """Artifact filenames SHALL follow turn_{NNN}_{SSS}_{ClassName}_{LogType}_{timestamp}.{ext}.

        **Validates: Requirements 5.2, 5.3**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            mgr.start_turn(1)
            artifact_logger = mgr.create_artifact_logger()
            artifact_logger({"type": log_type, "name": class_name, "item": item})

            artifact_files = list(mgr.artifacts_dir.iterdir())
            assert len(artifact_files) == 1

            filename = artifact_files[0].name
            match = ARTIFACT_FILE_PATTERN.match(filename)
            assert match is not None, (
                f"Artifact filename '{filename}' does not match expected pattern"
            )

            # Verify turn number is 001 (we started turn 1)
            assert match.group(1) == "001"
            # Verify step is 001 (first artifact in this turn)
            assert match.group(2) == "001"
            # Verify class name matches
            assert match.group(3) == class_name
            # Verify log type matches
            assert match.group(4) == log_type
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        producer=class_names,
        log_type=artifact_log_types,
        item=artifact_items,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_artifact_registered_in_manifest_with_correct_turn_and_step(
        self, session_id, class_name, log_type, item
    ):
        """Artifacts SHALL be registered in the manifest with correct turn number and step.

        **Validates: Requirements 5.3**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            mgr.start_turn(1)
            artifact_logger = mgr.create_artifact_logger()
            artifact_logger({"type": log_type, "name": class_name, "item": item})

            # Check manifest has the artifact registered
            assert len(mgr._manifest.turns) == 1
            turn_entry = mgr._manifest.turns[0]
            assert len(turn_entry.artifacts) == 1

            artifact_entry = turn_entry.artifacts[0]
            assert artifact_entry.type == log_type
            assert artifact_entry.producer == class_name
            assert artifact_entry.step == 1
            assert artifact_entry.path.startswith("artifacts/")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        num_turns=turn_counts,
        num_artifacts=artifacts_per_turn,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_step_counter_resets_per_turn(self, session_id, num_turns, num_artifacts):
        """Step counter SHALL reset to 0 at the start of each turn.

        **Validates: Requirements 5.2, 5.3**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            artifact_logger = mgr.create_artifact_logger()

            for turn in range(1, num_turns + 1):
                mgr.start_turn(turn)
                for _ in range(num_artifacts):
                    artifact_logger({
                        "type": "ReasonerInput",
                        "name": "TestClass",
                        "item": "test content",
                    })

            # Verify each turn has the correct number of artifacts
            for turn_entry in mgr._manifest.turns:
                assert len(turn_entry.artifacts) == num_artifacts

                # Verify steps are 1-indexed and sequential within each turn
                steps = [a.step for a in turn_entry.artifacts]
                assert steps == list(range(1, num_artifacts + 1)), (
                    f"Steps {steps} don't match expected {list(range(1, num_artifacts + 1))}"
                )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_artifacts_directory_path_is_accessible(self, session_id):
        """The agent SHALL have received the artifact directory path.

        **Validates: Requirements 5.4**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            # The artifacts_dir property provides the path to the agent
            artifacts_dir = mgr.artifacts_dir
            assert artifacts_dir.exists()
            assert artifacts_dir.is_dir()
            assert artifacts_dir.name == "artifacts"
            assert artifacts_dir.parent == mgr.session_dir
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        log_type=artifact_log_types,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_extension_inference_rules(self, session_id, log_type):
        """Extension SHALL be inferred correctly based on log type and content.

        **Validates: Requirements 5.2**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            # Test extension inference for text content
            ext_text = mgr._infer_extension("some text", log_type)
            if log_type == "Screenshot":
                assert ext_text == ".png"
            elif log_type == "HtmlSnapshot":
                assert ext_text == ".html"
            elif log_type in ("AgentActionResults", "AgentNextActions"):
                assert ext_text == ".json"
            else:
                assert ext_text == ".txt"

            # Test extension inference for dict content
            ext_dict = mgr._infer_extension({"key": "value"}, log_type)
            if log_type == "Screenshot":
                assert ext_dict == ".png"
            elif log_type == "HtmlSnapshot":
                assert ext_dict == ".html"
            else:
                assert ext_dict == ".json"

            # Test extension inference for list content
            ext_list = mgr._infer_extension(["item1", "item2"], log_type)
            if log_type == "Screenshot":
                assert ext_list == ".png"
            elif log_type == "HtmlSnapshot":
                assert ext_list == ".html"
            else:
                assert ext_list == ".json"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        session_id=session_ids,
        producer=class_names,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_non_artifact_log_types_are_ignored(self, session_id, class_name):
        """Log entries with types not in ARTIFACT_LOG_TYPES SHALL be ignored.

        **Validates: Requirements 5.2**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mgr = SessionLogManager(
                base_log_dir=tmp_dir,
                session_id=session_id,
                session_type="TestAgent",
            )

            mgr.start_turn(1)
            artifact_logger = mgr.create_artifact_logger()

            # Log a non-artifact type
            artifact_logger({
                "type": "SomeOtherType",
                "name": class_name,
                "item": "should be ignored",
            })

            # No artifact files should be created
            artifact_files = list(mgr.artifacts_dir.iterdir())
            assert len(artifact_files) == 0

            # No artifacts in manifest
            assert len(mgr._manifest.turns[0].artifacts) == 0
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
