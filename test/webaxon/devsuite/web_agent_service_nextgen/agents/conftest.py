"""Conftest for web_agent_service_nextgen agents tests.

Adds the test directory to sys.path so that `import resolve_path` works
when running tests via `python -m pytest` from the workspace root.
"""
import sys
from pathlib import Path

# Add this directory to sys.path so resolve_path.py can be imported
_this_dir = str(Path(__file__).resolve().parent)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
