"""Unit tests for trajectory screenshot logging via Debuggable logger.

Verifies that WebDriver._log_trajectory_screenshot() calls self.log_info()
with the correct log_type and payload, enabling turn-aware routing through
SessionLogger.
"""

# Path resolution - must be first
import sys
from pathlib import Path

PIVOT_FOLDER_NAME = 'test'
current_file = Path(__file__).resolve()
current_path = current_file.parent
while current_path.name != PIVOT_FOLDER_NAME and current_path.parent != current_path:
    current_path = current_path.parent

if current_path.name != PIVOT_FOLDER_NAME:
    raise RuntimeError(f"Could not find '{PIVOT_FOLDER_NAME}' folder in path hierarchy")

webagent_root = current_path.parent
src_dir = webagent_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

projects_root = webagent_root.parent
for path_item in [projects_root / "RichPythonUtils" / "src", projects_root / "AgentFoundation" / "src"]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

import inspect
import os
import re
import tempfile
import pytest
from unittest.mock import MagicMock, patch, call

from webaxon.automation.web_driver import WebDriver


def _create_stub_webdriver():
    """Create a minimal WebDriver stub with trajectory capture fields."""
    driver = WebDriver.__new__(WebDriver)
    driver._backend = MagicMock()
    driver._driver_type = 'chrome'
    driver._state = None
    driver.state_setting_max_retry = 3
    driver.state_setting_retry_wait = 0.2
    driver._action_configs = {}
    driver._window_infos = {}
    driver._monitor_tabs = set()
    driver._id = "test-webdriver"
    driver._log_level = 0
    driver._capture_trajectory = False
    driver._trajectory_dir = None
    driver._trajectory_step_counter = 0
    # Debuggable requires a logger dict
    driver.logger = {}
    return driver


# =============================================================================
# Unit tests: _log_trajectory_screenshot method
# =============================================================================

class TestLogTrajectoryScreenshot:
    """Tests for WebDriver._log_trajectory_screenshot()."""

    def test_calls_log_info_with_correct_log_type(self):
        """_log_trajectory_screenshot calls self.log_info with log_type='TrajectoryScreenshot'."""
        driver = _create_stub_webdriver()

        with patch.object(driver, 'log_info') as mock_log_info:
            driver._log_trajectory_screenshot(
                "/tmp/screenshots/0_screenshot.png", step=0, phase="before"
            )

        mock_log_info.assert_called_once()
        _, kwargs = mock_log_info.call_args
        assert kwargs["log_type"] == "TrajectoryScreenshot"

    def test_log_payload_contains_path_and_step(self):
        """The logged payload includes path, step, phase, and artifact_type."""
        driver = _create_stub_webdriver()

        with patch.object(driver, 'log_info') as mock_log_info:
            driver._log_trajectory_screenshot(
                "/tmp/screenshots/3_screenshot.png", step=3, phase="after"
            )

        args, kwargs = mock_log_info.call_args
        payload = args[0]
        assert payload["path"] == "/tmp/screenshots/3_screenshot.png"
        assert payload["step"] == 3
        assert payload["phase"] == "after"
        assert payload["artifact_type"] == "Screenshot"
        assert "timestamp" in payload

    def test_before_phase_default(self):
        """Phase defaults to 'before' when not specified."""
        driver = _create_stub_webdriver()

        with patch.object(driver, 'log_info') as mock_log_info:
            driver._log_trajectory_screenshot(
                "/tmp/screenshots/0_screenshot.png", step=0
            )

        payload = mock_log_info.call_args[0][0]
        assert payload["phase"] == "before"

    def test_timestamp_is_iso_format(self):
        """The logged timestamp is in ISO format."""
        driver = _create_stub_webdriver()

        with patch.object(driver, 'log_info') as mock_log_info:
            driver._log_trajectory_screenshot("/tmp/0.png", step=0)

        payload = mock_log_info.call_args[0][0]
        ts = payload["timestamp"]
        # ISO format: YYYY-MM-DDTHH:MM:SS.ffffff
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)

    def test_different_steps_produce_different_payloads(self):
        """Multiple calls with different steps produce distinct payloads."""
        driver = _create_stub_webdriver()

        payloads = []
        with patch.object(driver, 'log_info') as mock_log_info:
            driver._log_trajectory_screenshot("/tmp/0.png", step=0, phase="before")
            driver._log_trajectory_screenshot("/tmp/1.png", step=1, phase="after")

        assert mock_log_info.call_count == 2
        p0 = mock_log_info.call_args_list[0][0][0]
        p1 = mock_log_info.call_args_list[1][0][0]
        assert p0["step"] == 0
        assert p1["step"] == 1
        assert p0["phase"] == "before"
        assert p1["phase"] == "after"


# =============================================================================
# Logger routing: verify log_info is called with correct structure
# =============================================================================

class TestSessionLoggerRouting:
    """Tests that the log entry has the right structure for SessionLogger routing.

    Note: Full end-to-end routing through Debuggable.log() → SessionLogger.__call__()
    requires a fully-initialized Debuggable (many attrs fields). That path is
    covered by the e2e test suite. Here we verify the contract between
    _log_trajectory_screenshot and log_info.
    """

    def test_log_info_called_with_dict_payload(self):
        """log_info receives a dict (not a string), which Debuggable.log()
        passes as log_data['item'] to callable loggers."""
        driver = _create_stub_webdriver()

        with patch.object(driver, 'log_info') as mock_log_info:
            driver._log_trajectory_screenshot("/tmp/1.png", step=1, phase="before")

        payload = mock_log_info.call_args[0][0]
        assert isinstance(payload, dict)
        assert payload["artifact_type"] == "Screenshot"
        assert payload["path"] == "/tmp/1.png"
        assert payload["step"] == 1
        assert payload["phase"] == "before"

    def test_log_type_matches_artifact_convention(self):
        """log_type='TrajectoryScreenshot' — distinct from agent state log types
        so SessionLogger doesn't trigger turn advancement on screenshot logs."""
        driver = _create_stub_webdriver()

        with patch.object(driver, 'log_info') as mock_log_info:
            driver._log_trajectory_screenshot("/tmp/0.png", step=0)

        _, kwargs = mock_log_info.call_args
        log_type = kwargs["log_type"]
        assert log_type == "TrajectoryScreenshot"
        # Must NOT be 'AgentState' (which triggers turn advancement in SessionLogger)
        assert log_type != "AgentState"


# =============================================================================
# Source-code verification: __call__ method wires _log_trajectory_screenshot
# =============================================================================

class TestCallMethodWiring:
    """Verify that WebDriver.__call__ calls _log_trajectory_screenshot
    in the trajectory capture blocks. This avoids the complexity of mocking
    the entire __call__ pipeline."""

    def test_call_source_contains_before_screenshot_log(self):
        """__call__ source contains _log_trajectory_screenshot call for before-action."""
        source = inspect.getsource(WebDriver.__call__)
        # Find the before-action trajectory block
        assert "self._log_trajectory_screenshot(" in source
        # Specifically check phase="before" appears
        assert 'phase="before"' in source

    def test_call_source_contains_after_screenshot_log(self):
        """__call__ source contains _log_trajectory_screenshot call for after-action."""
        source = inspect.getsource(WebDriver.__call__)
        assert 'phase="after"' in source

    def test_log_calls_inside_try_blocks(self):
        """_log_trajectory_screenshot calls are inside try/except blocks,
        so logging failures don't crash the action pipeline."""
        source = inspect.getsource(WebDriver.__call__)

        # Both _log_trajectory_screenshot calls should be in try blocks
        # Find all occurrences
        log_positions = [
            m.start() for m in re.finditer(
                r"self\._log_trajectory_screenshot\(", source
            )
        ]
        assert len(log_positions) == 2, (
            f"Expected 2 _log_trajectory_screenshot calls, found {len(log_positions)}"
        )

        # Each should be preceded by a try: (within the same block)
        for pos in log_positions:
            # Look backward from the log call for 'try:'
            preceding = source[:pos]
            last_try = preceding.rfind("try:")
            last_except = preceding.rfind("except")
            assert last_try > last_except, (
                "_log_trajectory_screenshot should be inside a try block"
            )

    def test_log_calls_after_capture_screenshot(self):
        """_log_trajectory_screenshot is called after capture_screenshot (not before),
        ensuring the screenshot file exists when the path is logged."""
        source = inspect.getsource(WebDriver.__call__)

        # For each _log_trajectory_screenshot call, capture_screenshot should appear before it
        lines = source.split("\n")
        capture_lines = []
        log_lines = []
        for i, line in enumerate(lines):
            if "self.capture_screenshot(" in line:
                capture_lines.append(i)
            if "self._log_trajectory_screenshot(" in line:
                log_lines.append(i)

        assert len(capture_lines) >= 2
        assert len(log_lines) == 2

        # Each log call should come after its corresponding capture call
        assert log_lines[0] > capture_lines[0], "before-log should follow before-capture"
        assert log_lines[1] > capture_lines[1], "after-log should follow after-capture"
