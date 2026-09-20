"""Pytest config for FindElementInferencer characterization tests.

- Inserts WebAxon/src + sibling package srcs onto sys.path so `webaxon.*`,
  `agent_foundation.*`, `rich_python_utils.*` resolve when running pytest from
  CoreProjects root.
- Registers the `integration` marker locally (not in any project-wide pytest.ini).
- Exposes a `webaxon_root` fixture pointing at WebAxon/ for tests that need
  bundled fixtures (e.g. the google_search.html corpus).
"""
import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
_WEBAXON_ROOT = _THIS_DIR.parents[4]   # WebAxon/test/webaxon/automation/agents/find_element_inferencer/ -> WebAxon/
_CORE_ROOT = _WEBAXON_ROOT.parent      # CoreProjects/

for src in (
    _WEBAXON_ROOT / "src",
    _CORE_ROOT / "AgentFoundation" / "src",
    _CORE_ROOT / "RichPythonUtils" / "src",
):
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: real-LLM integration tests (require ANTHROPIC_API_KEY; cost real money)",
    )


@pytest.fixture(scope="session")
def webaxon_root() -> Path:
    return _WEBAXON_ROOT
