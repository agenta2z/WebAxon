"""
Path resolution helper for browser_utils/chrome tests.

Import this module at the top of test files before importing webaxon modules.
"""
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
for path_item in [
    projects_root / "SciencePythonUtils" / "src",
    projects_root / "ScienceModelingTools" / "src",
]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))
