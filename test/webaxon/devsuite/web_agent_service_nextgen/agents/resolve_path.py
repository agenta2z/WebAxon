"""
Path resolution helper for devsuite tests.

This module sets up the Python path to allow imports from the webaxon package.
Import this module at the top of test files before importing webaxon modules.

Usage:
    import resolve_path  # Must be first import
    from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig
"""
import sys
from pathlib import Path

# Configuration
PIVOT_FOLDER_NAME = 'test'  # The folder name we're inside of

# Get absolute path to this file
current_file = Path(__file__).resolve()

# Navigate up to find the pivot folder (test directory)
current_path = current_file.parent
while current_path.name != PIVOT_FOLDER_NAME and current_path.parent != current_path:
    current_path = current_path.parent

if current_path.name != PIVOT_FOLDER_NAME:
    raise RuntimeError(f"Could not find '{PIVOT_FOLDER_NAME}' folder in path hierarchy")

# WebAgent root is parent of test/ directory
webagent_root = current_path.parent

# Add src directory to path for webaxon imports
src_dir = webagent_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Add science packages if they exist (for tests that need them)
projects_root = webagent_root.parent
rich_python_utils_src = projects_root / "SciencePythonUtils" / "src"
agent_foundation_src = projects_root / "ScienceModelingTools" / "src"

for path_item in [rich_python_utils_src, agent_foundation_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

# Verify the setup worked
_webagent_module_path = src_dir / "webaxon"
if not _webagent_module_path.exists():
    raise RuntimeError(f"webaxon module not found at {_webagent_module_path}")
