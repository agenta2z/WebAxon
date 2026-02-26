import sys
from pathlib import Path

PIVOT_FOLDER_NAME = 'agent_debugger_nextgen'
SRC_FOLDER_NAME = 'src'

# Sibling projects that may be needed (relative to parent of project root)
SIBLING_PROJECTS = [
    'ScienceModelingTools',
    'SciencePythonUtils',
]

def resolve_path():
    """Resolve and add required paths to sys.path.

    Returns:
        Path: The testcase_root (webaxon/devsuite folder)
    """
    current = Path(__file__).resolve()
    while current != current.parent:  # Stop at filesystem root
        if current.name == PIVOT_FOLDER_NAME:
            # current is agent_debugger_nextgen folder
            # testcase_root is the parent (webaxon/devsuite)
            testcase_root = current.parent

            # Find project root (WebAgent) by going up to find 'src' folder
            project_root = testcase_root
            while project_root != project_root.parent:
                if (project_root / SRC_FOLDER_NAME).is_dir():
                    break
                project_root = project_root.parent

            # Add this project's src
            src_path = project_root / SRC_FOLDER_NAME
            if src_path.is_dir() and str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            # Add sibling projects' src directories
            # Go up to parent of project root (e.g., PythonProjects)
            projects_root = project_root.parent
            for sibling in SIBLING_PROJECTS:
                sibling_src = projects_root / sibling / SRC_FOLDER_NAME
                if sibling_src.is_dir() and str(sibling_src) not in sys.path:
                    sys.path.insert(0, str(sibling_src))

            return testcase_root
        current = current.parent
    else:
        raise FileNotFoundError(f"Could not find '{PIVOT_FOLDER_NAME}' directory in path hierarchy")
