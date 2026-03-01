"""Property-based test for LogCollector JSONL-Only Loading.

This module contains a property-based test using hypothesis to verify
that the LogCollector only reads .jsonl files from a session directory,
excluding manifest.json and other non-log files.

**Feature: session-logging-improvements, Property 12: LogCollector JSONL-Only Loading**
**Validates: Requirement 2.4**
"""
import sys
import json
import os
import tempfile
from pathlib import Path

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != 'test' and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
_workspace_root = _project_root.parent
_rich_python_utils_src = _workspace_root / "SciencePythonUtils" / "src"
_agent_foundation_src = _workspace_root / "ScienceModelingTools" / "src"
if _rich_python_utils_src.exists() and str(_rich_python_utils_src) not in sys.path:
    sys.path.insert(0, str(_rich_python_utils_src))
if _agent_foundation_src.exists() and str(_agent_foundation_src) not in sys.path:
    sys.path.insert(0, str(_agent_foundation_src))

from hypothesis import given, strategies as st, settings
from agent_foundation.ui.dash_interactive.utils.log_collector import LogCollector


def _make_log_entry(node_id: str, parent_ids=None, log_type: str = 'Info'):
    """Create a minimal valid JSONL log entry."""
    entry = {
        'id': node_id,
        'parent_ids': parent_ids or [],
        'type': log_type,
        'name': 'TestComponent',
        'level': 20,
        'time': '2025-01-15T10:30:00',
        'item': f'Log message for {node_id}'
    }
    return entry


# Strategy for generating a list of unique node IDs for JSONL log entries
node_id_strategy = st.text(
    alphabet=st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789_'),
    min_size=3,
    max_size=20
).filter(lambda s: s and not s.startswith('_'))

# Strategy for number of JSONL files (1-5 turn files + session file)
num_jsonl_files_strategy = st.integers(min_value=1, max_value=5)

# Strategy for number of log entries per file
entries_per_file_strategy = st.integers(min_value=1, max_value=5)

# Strategy for non-JSONL filenames that should be excluded
non_jsonl_filename_strategy = st.sampled_from([
    'manifest.json',
    'config.json',
    'metadata.json',
    'notes.txt',
    'README.md',
    'data.csv',
])


# **Feature: session-logging-improvements, Property 12: LogCollector JSONL-Only Loading**
# **Validates: Requirement 2.4**
@settings(max_examples=50, deadline=None)
@given(
    num_jsonl_files=num_jsonl_files_strategy,
    entries_per_file=entries_per_file_strategy,
    non_jsonl_files=st.lists(non_jsonl_filename_strategy, min_size=1, max_size=3, unique=True),
)
def test_log_collector_reads_only_jsonl_files(num_jsonl_files, entries_per_file, non_jsonl_files):
    """Property: For any session directory containing both .jsonl log files and
    non-JSONL files (like manifest.json), the LogCollector SHALL only read .jsonl files.
    The manifest file SHALL NOT produce any nodes in the execution graph.

    **Validates: Requirement 2.4**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Track all node IDs we put into JSONL files
        expected_node_ids = set()
        # Track node IDs we put into non-JSONL files (should NOT appear)
        excluded_node_ids = set()

        # Create JSONL log files with valid log entries
        for i in range(num_jsonl_files):
            if i == 0:
                filename = 'session.jsonl'
            else:
                filename = f'turn_{i:03d}_20250115_103000.jsonl'

            filepath = Path(tmpdir) / filename
            with open(filepath, 'w') as f:
                for j in range(entries_per_file):
                    node_id = f'jsonl_file{i}_entry{j}'
                    entry = _make_log_entry(node_id)
                    f.write(json.dumps(entry) + '\n')
                    expected_node_ids.add(node_id)

        # Create non-JSONL files with data that would produce nodes if read
        for non_jsonl_name in non_jsonl_files:
            filepath = Path(tmpdir) / non_jsonl_name
            if non_jsonl_name.endswith('.json'):
                # Write a JSON object that looks like a manifest or config
                manifest_data = {
                    'id': f'non_jsonl_{non_jsonl_name}',
                    'parent_ids': [],
                    'type': 'Manifest',
                    'name': 'ManifestFile',
                    'level': 20,
                    'time': '2025-01-15T10:30:00',
                    'session_id': 'test_session',
                    'item': 'This should not appear as a node'
                }
                with open(filepath, 'w') as f:
                    json.dump(manifest_data, f)
                excluded_node_ids.add(f'non_jsonl_{non_jsonl_name}')
            else:
                # Write plain text that is not JSON
                with open(filepath, 'w') as f:
                    f.write('This is not a JSON file\n')

        # Load using the JSONL-only pattern (as used by handle_log_path_message)
        collector = LogCollector.from_json_logs(tmpdir, json_file_pattern='*.jsonl')

        # Property: All JSONL node IDs should be present
        actual_node_ids = set(collector.get_all_node_ids())
        assert expected_node_ids == actual_node_ids, (
            f"Expected nodes from JSONL files: {expected_node_ids}, "
            f"but got: {actual_node_ids}. "
            f"Missing: {expected_node_ids - actual_node_ids}, "
            f"Extra: {actual_node_ids - expected_node_ids}"
        )

        # Property: No excluded node IDs should be present
        leaked_ids = excluded_node_ids & actual_node_ids
        assert len(leaked_ids) == 0, (
            f"Non-JSONL file nodes leaked into the graph: {leaked_ids}"
        )

        # Property: Total log count matches expected
        expected_total = num_jsonl_files * entries_per_file
        assert len(collector.logs) == expected_total, (
            f"Expected {expected_total} log entries, got {len(collector.logs)}"
        )


def test_log_collector_jsonl_only_example():
    """Example-based test: a session directory with JSONL logs and manifest.json.

    Verifies that manifest.json is excluded and only .jsonl files are loaded.

    **Validates: Requirement 2.4**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create session.jsonl
        session_file = Path(tmpdir) / 'session.jsonl'
        with open(session_file, 'w') as f:
            f.write(json.dumps(_make_log_entry('session_start', log_type='SessionStart')) + '\n')

        # Create turn files
        turn1_file = Path(tmpdir) / 'turn_001_20250115_103000.jsonl'
        with open(turn1_file, 'w') as f:
            f.write(json.dumps(_make_log_entry('turn1_entry1', ['session_start'], 'AgentState')) + '\n')
            f.write(json.dumps(_make_log_entry('turn1_entry2', ['turn1_entry1'], 'AgentResponse')) + '\n')

        turn2_file = Path(tmpdir) / 'turn_002_20250115_103200.jsonl'
        with open(turn2_file, 'w') as f:
            f.write(json.dumps(_make_log_entry('turn2_entry1', ['session_start'], 'AgentState')) + '\n')

        # Create manifest.json (should be excluded)
        manifest_file = Path(tmpdir) / 'manifest.json'
        with open(manifest_file, 'w') as f:
            json.dump({
                'id': 'manifest_node',
                'parent_ids': [],
                'type': 'Manifest',
                'name': 'ManifestFile',
                'level': 20,
                'time': '2025-01-15T10:30:00',
                'session_id': 'test',
                'status': 'completed',
                'item': 'manifest data'
            }, f)

        collector = LogCollector.from_json_logs(tmpdir, json_file_pattern='*.jsonl')

        # Should have exactly 4 log entries from the 3 JSONL files
        assert len(collector.logs) == 4, f"Expected 4 logs, got {len(collector.logs)}"

        # Should have the correct node IDs
        node_ids = set(collector.get_all_node_ids())
        expected = {'session_start', 'turn1_entry1', 'turn1_entry2', 'turn2_entry1'}
        assert node_ids == expected, f"Expected {expected}, got {node_ids}"

        # manifest_node should NOT be present
        assert 'manifest_node' not in node_ids, "manifest.json node leaked into graph"


def test_wildcard_pattern_would_include_manifest():
    """Regression test: using pattern='*' WOULD include manifest.json.

    This demonstrates the bug that the fix addresses.

    **Validates: Requirement 2.4**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a JSONL log file
        log_file = Path(tmpdir) / 'session.jsonl'
        with open(log_file, 'w') as f:
            f.write(json.dumps(_make_log_entry('real_node')) + '\n')

        # Create manifest.json with a structure that would create a phantom node
        manifest_file = Path(tmpdir) / 'manifest.json'
        with open(manifest_file, 'w') as f:
            json.dump({
                'id': 'phantom_manifest_node',
                'parent_ids': [],
                'type': 'Manifest',
                'name': 'ManifestFile',
                'level': 20,
                'time': '2025-01-15T10:30:00',
                'item': 'should not appear'
            }, f)

        # With '*' pattern, manifest.json IS included (the old buggy behavior)
        collector_wildcard = LogCollector.from_json_logs(tmpdir, json_file_pattern='*')
        wildcard_ids = set(collector_wildcard.get_all_node_ids())

        # With '*.jsonl' pattern, manifest.json is excluded (the fix)
        collector_jsonl = LogCollector.from_json_logs(tmpdir, json_file_pattern='*.jsonl')
        jsonl_ids = set(collector_jsonl.get_all_node_ids())

        # The wildcard collector picks up the phantom node
        assert 'phantom_manifest_node' in wildcard_ids, (
            "Expected wildcard pattern to include manifest node"
        )

        # The JSONL collector does NOT pick up the phantom node
        assert 'phantom_manifest_node' not in jsonl_ids, (
            "JSONL pattern should exclude manifest node"
        )

        # Both should include the real node
        assert 'real_node' in wildcard_ids
        assert 'real_node' in jsonl_ids


if __name__ == '__main__':
    print("Running property-based tests for LogCollector JSONL-Only Loading...")
    print("=" * 70)
    print()

    print("1. Running example-based test...")
    print("-" * 70)
    test_log_collector_jsonl_only_example()
    print("✓ Example-based test passed")
    print()

    print("2. Running regression test...")
    print("-" * 70)
    test_wildcard_pattern_would_include_manifest()
    print("✓ Regression test passed")
    print()

    print("3. Running property-based test with 50 random examples...")
    print("-" * 70)
    test_log_collector_reads_only_jsonl_files()
    print("✓ Property test passed")
    print()

    print("=" * 70)
    print("All tests passed! ✓")
