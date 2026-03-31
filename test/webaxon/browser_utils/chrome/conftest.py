"""Conftest for browser_utils/chrome tests.

Adds the test directory to sys.path so that `import resolve_path` works
when running tests via `python -m pytest` from the workspace root.
"""
import sys
from pathlib import Path

_this_dir = str(Path(__file__).resolve().parent)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
