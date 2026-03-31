"""
Launch Web Agent Service in debug + synchronous mode.

Convenience entry point for IDE debugging (e.g. PyCharm "Run/Debug").
Sets --debug and --synchronous by default so breakpoints work and
console output is verbose.

Usage:
    python launch_service_debug_mode.py [testcase_root] [--profile NAME] [--copy-profile [PATH]]

If testcase_root is omitted, defaults to the _workspace directory.
If --profile is omitted, an interactive chooser is shown at startup.
"""
import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

# Path setup: this file lives at .../WebAxon/src/webaxon/devsuite/web_agent_service_nextgen/
# project_root = WebAxon/
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent.parent

# Add src/ so that 'webaxon' package is importable
src_dir = project_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

rich_python_utils_src = project_root / "SciencePythonUtils" / "src"
agent_foundation_src = project_root / "ScienceModelingTools" / "src"
webagent_src = project_root / "WebAgent" / "src"

for path_item in [rich_python_utils_src, agent_foundation_src, webagent_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

from webaxon.browser_utils.chrome.chrome_version import get_chrome_major_version
from webaxon.browser_utils.chrome.chrome_profiles import (
    get_available_chrome_profiles,
    get_chrome_user_data_dir,
)
from webaxon.devsuite.web_agent_service_nextgen.constants import DEFAULT_WORKSPACE_PATH
from webaxon.devsuite.web_agent_service_nextgen.service import WebAgentService
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig

CHROME_VERSION = get_chrome_major_version()


PERSISTENT_PROFILE_DIR_NAME = "_chrome_profile"


def _get_workspace_profiles(testcase_root: Path) -> list:
    """Scan _chrome_profile/ under workspace for existing persistent profiles."""
    persistent_root = testcase_root / PERSISTENT_PROFILE_DIR_NAME
    if not persistent_root.is_dir():
        return []
    results = []
    for item in sorted(persistent_root.iterdir()):
        if item.is_dir() and (item / "Preferences").exists():
            from webaxon.browser_utils.chrome.chrome_profiles import get_chrome_profile_name
            name = get_chrome_profile_name(str(item))
            results.append({
                "name": f"📂 {name}",
                "profile_dir": item.name,
                "user_data_dir": str(persistent_root),
                "type": "workspace",
            })
    return results


def choose_chrome_profile(
    testcase_root: Path,
) -> Tuple[Optional[str], Optional[str]]:
    """Detect Chrome profiles and prompt the user to choose one.

    Returns:
        (profile_directory, user_data_dir) — profile_directory is None when
        the user picks the temporary-profile option or detection fails.
        For persistent profiles, user_data_dir points to _chrome_profile/.
    """
    user_data_dir = get_chrome_user_data_dir()

    # --- Build the options list ---
    options = []  # Each: {label, on_select -> (profile_dir, user_data_dir)}

    # 1) System Chrome profiles
    chrome_profiles = get_available_chrome_profiles()
    for p in chrome_profiles:
        if p["directory"]:
            options.append({
                "label": p["name"],
                "dir_label": p["directory"],
                "type": "chrome",
                "profile_dir": p["directory"],
                "user_data_dir": user_data_dir,
            })

    # 2) Temporary profile (always present)
    options.append({
        "label": "🆕 New Temporary Profile",
        "dir_label": "(temporary)",
        "type": "temp",
        "profile_dir": None,
        "user_data_dir": None,
    })

    # 3) Existing workspace persistent profiles
    workspace_profiles = _get_workspace_profiles(testcase_root)
    for wp in workspace_profiles:
        options.append({
            "label": wp["name"],
            "dir_label": f"{wp['user_data_dir']}/{wp['profile_dir']}",
            "type": "workspace",
            "profile_dir": wp["profile_dir"],
            "user_data_dir": wp["user_data_dir"],
        })

    # 4) Create new persistent profile
    persistent_root = testcase_root / PERSISTENT_PROFILE_DIR_NAME
    options.append({
        "label": "🆕 New Persistent Profile",
        "dir_label": str(persistent_root),
        "type": "new_persistent",
        "profile_dir": None,
        "user_data_dir": None,
    })

    # --- Display ---
    print("\nAvailable Chrome profiles:")
    for idx, opt in enumerate(options, 1):
        print(f"  {idx}. {opt['label']}  [{opt['dir_label']}]")

    # --- Prompt ---
    while True:
        try:
            choice = input(f"\nSelect a profile [1-{len(options)}]: ").strip()
            if not choice:
                selected = options[0]
                break
            num = int(choice)
            if 1 <= num <= len(options):
                selected = options[num - 1]
                break
            print(f"  Please enter a number between 1 and {len(options)}.")
        except ValueError:
            print(f"  Please enter a number between 1 and {len(options)}.")
        except (EOFError, KeyboardInterrupt):
            print("\nProfile selection cancelled. Using Default.")
            return "Default", user_data_dir

    print(f"Selected: {selected['label']}")

    # --- Handle selection ---
    if selected["type"] == "chrome":
        return selected["profile_dir"], selected["user_data_dir"]

    if selected["type"] == "temp":
        return None, None

    if selected["type"] == "workspace":
        return selected["profile_dir"], selected["user_data_dir"]

    if selected["type"] == "new_persistent":
        name = ""
        try:
            name = input("  Profile name (default: 'Default'): ").strip()
        except (EOFError, KeyboardInterrupt):
            pass
        if not name:
            name = "Default"
        persistent_root.mkdir(parents=True, exist_ok=True)
        return name, str(persistent_root)

    return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Web Agent Service — debug/synchronous mode"
    )
    parser.add_argument(
        "testcase_root",
        nargs="?",
        type=Path,
        default=DEFAULT_WORKSPACE_PATH,
        help=f"Workspace root directory (default: {DEFAULT_WORKSPACE_PATH})",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help='Chrome profile directory name (e.g. "Default", "Profile 1"). '
             "Shows interactive chooser when omitted.",
    )
    copy_group = parser.add_mutually_exclusive_group()
    copy_group.add_argument(
        "--copy-profile",
        nargs="?",
        const=True,
        default=True,
        metavar="PATH",
        help="Copy profile to a temp dir (default) or to PATH for reuse.",
    )
    copy_group.add_argument(
        "--no-copy-profile",
        dest="copy_profile",
        action="store_false",
        help="Use the real Chrome profile directly (may conflict with running Chrome).",
    )
    args = parser.parse_args()

    testcase_root = args.testcase_root
    testcase_root.mkdir(parents=True, exist_ok=True)
    if not testcase_root.is_dir():
        print(f"Error: testcase_root is not a directory: {testcase_root}")
        sys.exit(1)

    # --- Profile selection ---
    if args.profile is not None:
        profile_directory = args.profile
        user_data_dir = get_chrome_user_data_dir()
    else:
        profile_directory, user_data_dir = choose_chrome_profile(testcase_root)

    # --- Build config ---
    config = ServiceConfig.from_env()
    config.debug_mode_service = True
    config.synchronous_agent = True
    config.chrome_version = CHROME_VERSION

    if profile_directory and user_data_dir:
        config.chrome_profile_directory = profile_directory
        config.chrome_user_data_dir = user_data_dir
        # Persistent profile path is its own isolated dir — no copy needed
        persistent_path = str(testcase_root / PERSISTENT_PROFILE_DIR_NAME)
        if user_data_dir == persistent_path:
            config.chrome_copy_profile = False
        else:
            config.chrome_copy_profile = bool(args.copy_profile)

    # --- Banner ---
    print()
    print("=" * 80)
    print("WEB AGENT SERVICE — DEBUG MODE (synchronous)")
    print("=" * 80)
    print(f"Testcase Root: {testcase_root}")
    print(f"Synchronous Agent: {config.synchronous_agent}")
    print(f"New Agent on First Submission: {config.new_agent_on_first_submission}")
    print(f"Chrome Version: {config.chrome_version or 'auto-detect'}")
    if config.chrome_profile_directory:
        print(f"Chrome Profile: {config.chrome_profile_directory}")
        print(f"Chrome User Data Dir: {config.chrome_user_data_dir}")
        print(f"Copy Profile: {config.chrome_copy_profile}")
    print("-" * 80)
    print("Starting service... (Press Ctrl+C to stop)")
    print("=" * 80)
    print()

    try:
        service = WebAgentService(testcase_root, config)
        service.run()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\nService stopped")


if __name__ == "__main__":
    main()
