"""Property-based test for Manifest Round-Trip Serialization (Property 3).

**Validates: Requirements 6.6, 6.7**

For any valid ManifestFile instance, serializing to JSON via to_json() and
deserializing back via from_json() SHALL produce an equivalent ManifestFile.
All fields SHALL be preserved including nested TurnEntry and ArtifactEntry objects.
"""

import resolve_path  # noqa: F401 - must be first import

import json

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from rich_python_utils.service_utils.session_management import (
    ArtifactEntry,
    SessionManifest as ManifestFile,
    TurnEntry,
)

# --- Hypothesis strategies ---


@st.composite
def iso_timestamps(draw):
    """Generate ISO 8601 timestamps without milliseconds."""
    year = draw(st.integers(min_value=2020, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"


# Optional timestamps (None or ISO string)
optional_timestamps = st.one_of(st.none(), iso_timestamps())

# Safe text that won't break JSON (printable ASCII for speed)
safe_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-./",
    min_size=1,
    max_size=30,
)

# Artifact entry strategy
artifact_entries = st.builds(
    ArtifactEntry,
    path=safe_text,
    type=safe_text,
    producer=safe_text,
    timestamp=iso_timestamps(),
    step=st.integers(min_value=0, max_value=999),
)

# Turn entry strategy
turn_entries = st.builds(
    TurnEntry,
    turn_number=st.integers(min_value=1, max_value=999),
    start_timestamp=iso_timestamps(),
    log_file=safe_text,
    artifacts=st.lists(artifact_entries, min_size=0, max_size=5),
    end_timestamp=optional_timestamps,
)

# ManifestFile strategy
manifest_files = st.builds(
    ManifestFile,
    session_id=safe_text,
    creation_timestamp=iso_timestamps(),
    session_type=safe_text,
    status=st.sampled_from(["running", "completed", "error"]),
    session_dir=safe_text,
    session_log_file=safe_text,
    turns=st.lists(turn_entries, min_size=0, max_size=10),
    end_timestamp=optional_timestamps,
)


class TestManifestRoundTripProperty:
    """Property 3: Manifest Round-Trip Serialization."""

    @given(manifest=manifest_files)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_json_roundtrip_preserves_all_fields(self, manifest: ManifestFile):
        """Serializing to JSON and back produces an equivalent ManifestFile.

        **Validates: Requirements 6.6, 6.7**
        """
        json_str = manifest.to_json()
        restored = ManifestFile.from_json(json_str)

        assert restored == manifest

    @given(manifest=manifest_files)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_dict_roundtrip_preserves_all_fields(self, manifest: ManifestFile):
        """Serializing to dict and back produces an equivalent ManifestFile.

        **Validates: Requirements 6.6**
        """
        d = manifest.to_dict()
        restored = ManifestFile.from_dict(d)

        assert restored == manifest

    @given(manifest=manifest_files)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_to_json_produces_valid_json_with_sorted_keys(self, manifest: ManifestFile):
        """to_json() produces valid JSON with sorted keys.

        **Validates: Requirements 6.7**
        """
        json_str = manifest.to_json()

        # Must be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

        # Top-level keys must be sorted
        keys = list(parsed.keys())
        assert keys == sorted(keys)

        # Nested turn keys must also be sorted
        for turn in parsed.get("turns", []):
            turn_keys = list(turn.keys())
            assert turn_keys == sorted(turn_keys)

            # Nested artifact keys must also be sorted
            for artifact in turn.get("artifacts", []):
                artifact_keys = list(artifact.keys())
                assert artifact_keys == sorted(artifact_keys)
