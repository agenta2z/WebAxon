"""
Path resolution utilities for GoodTime automation scripts.

This module provides common path resolution logic that works in both:
- Source mode: Running from the source directory with packages in sibling folders
- Bundle mode: Running with goodtime_automation_bundle wheel installed

Usage:
    from path_utils import setup_project_paths

    project_root = setup_project_paths()
    # Now all packages are importable
"""

import os
import sys

# =============================================================================
# Constants
# =============================================================================
PROJECT_ROOT_MARKER = "WebAgent"  # Folder name to search for when finding project root
PROJECTS_ROOT_PACKAGES = ["SciencePythonUtils", "ScienceModelingTools"]  # Sibling packages


# =============================================================================
# Try bundle import first (for installed wheel mode)
# =============================================================================
try:
    import goodtime_automation_bundle  # noqa: F401 - registers modules in sys.modules
    _BUNDLE_MODE = True
except ImportError:
    _BUNDLE_MODE = False


# =============================================================================
# Path Resolution Functions
# =============================================================================
def find_project_root(start_path: str, marker_name: str = PROJECT_ROOT_MARKER) -> str:
    """
    Find the project root by searching upward from the start path.

    Args:
        start_path: Path to start searching from.
        marker_name: Name of the project directory to find.

    Returns:
        Path to the project root, or None if not found.
    """
    current = os.path.abspath(start_path)

    for _ in range(20):  # Limit search depth
        if os.path.basename(current) == marker_name:
            return current

        parent = os.path.dirname(current)
        if parent == current:  # Reached filesystem root
            break

        current = parent

    return None


def setup_project_paths(caller_file: str = None) -> str:
    """
    Set up sys.path for importing project packages.

    This function:
    1. Tries to import goodtime_automation_bundle (for bundle mode)
    2. If not in bundle mode, finds the project root and adds source paths

    Args:
        caller_file: The __file__ of the calling script. If None, uses this module's location.

    Returns:
        The project root path if found, None if running in bundle-only mode.
    """
    if caller_file is None:
        caller_file = __file__

    script_dir = os.path.dirname(os.path.abspath(caller_file))
    project_root = find_project_root(script_dir, PROJECT_ROOT_MARKER)

    if project_root:
        projects_root = os.path.dirname(project_root)

        # Add WebAgent src
        webagent_src = os.path.join(project_root, "src")
        if os.path.exists(webagent_src) and webagent_src not in sys.path:
            sys.path.insert(0, webagent_src)

        # Add sibling packages if they exist
        for pkg in PROJECTS_ROOT_PACKAGES:
            pkg_src = os.path.join(projects_root, pkg, "src")
            if os.path.exists(pkg_src) and pkg_src not in sys.path:
                sys.path.insert(0, pkg_src)

    return project_root


def is_bundle_mode() -> bool:
    """Check if running in bundle mode (wheel installed)."""
    return _BUNDLE_MODE
