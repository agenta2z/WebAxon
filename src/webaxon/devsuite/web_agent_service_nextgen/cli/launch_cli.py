"""
Launch Script for Web Agent CLI Client

Entry point for the interactive CLI that connects to a running
web_agent_service_nextgen instance.

Usage:
    python launch_cli.py [workspace_path] [--session-id SESSION_ID] [--queue-root-path PATH]
"""
import sys
import argparse
from pathlib import Path

# Add source paths (same pattern as launch_service.py)
# cli/launch_cli.py -> cli -> web_agent_service_nextgen -> devsuite -> webaxon -> src -> WebAgent -> PythonProjects
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent.parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

rich_python_utils_src = project_root / "SciencePythonUtils" / "src"
agent_foundation_src = project_root / "ScienceModelingTools" / "src"
webagent_src = project_root / "WebAgent" / "src"

for path_item in [rich_python_utils_src, agent_foundation_src, webagent_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

from webaxon.devsuite.web_agent_service_nextgen.cli.client import CLIClient
from webaxon.devsuite.web_agent_service_nextgen.constants import DEFAULT_WORKSPACE_PATH


def main():
    default_workspace = DEFAULT_WORKSPACE_PATH

    parser = argparse.ArgumentParser(
        description="Interactive CLI client for web_agent_service_nextgen"
    )
    parser.add_argument(
        "testcase_root",
        nargs="?",
        type=Path,
        default=default_workspace,
        help=f"Workspace root directory (default: {default_workspace})",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Custom session ID (auto-generated if omitted)",
    )
    parser.add_argument(
        "--queue-root-path",
        type=Path,
        default=None,
        help="Direct path to the service's queue root directory (bypasses auto-discovery)",
    )
    args = parser.parse_args()

    if not args.testcase_root.exists() or not args.testcase_root.is_dir():
        print(f"Error: testcase_root does not exist or is not a directory: {args.testcase_root}")
        sys.exit(1)

    client = CLIClient(args.testcase_root, session_id=args.session_id, queue_root_path=args.queue_root_path)
    client.run()


if __name__ == "__main__":
    main()
