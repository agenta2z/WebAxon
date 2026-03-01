"""
Launch Web Agent Service in debug + synchronous mode.

Convenience entry point for IDE debugging (e.g. PyCharm "Run/Debug").
Sets --debug and --synchronous by default so breakpoints work and
console output is verbose.

Usage:
    python launch_service_debug_mode.py [testcase_root]

If testcase_root is omitted, defaults to the parent directory (devsuite/).
"""
import sys
from pathlib import Path

# Reuse the same path setup from launch_service.py
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

rich_python_utils_src = project_root / "SciencePythonUtils" / "src"
agent_foundation_src = project_root / "ScienceModelingTools" / "src"
webagent_src = project_root / "WebAgent" / "src"

for path_item in [rich_python_utils_src, agent_foundation_src, webagent_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

from webaxon.browser_utils.chrome.chrome_version import get_chrome_major_version
from webaxon.devsuite.web_agent_service_nextgen.constants import DEFAULT_WORKSPACE_PATH
from webaxon.devsuite.web_agent_service_nextgen.service import WebAgentService
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig

# Pin ChromeDriver to match the locally installed Chrome major version.
# Set to None to auto-detect, or override with a specific version (e.g. 145).
CHROME_VERSION = get_chrome_major_version()


def main():
    if len(sys.argv) > 1:
        testcase_root = Path(sys.argv[1]).resolve()
    else:
        testcase_root = DEFAULT_WORKSPACE_PATH

    testcase_root.mkdir(parents=True, exist_ok=True)
    if not testcase_root.is_dir():
        print(f"Error: testcase_root is not a directory: {testcase_root}")
        sys.exit(1)

    config = ServiceConfig.from_env()
    config.debug_mode_service = True
    config.synchronous_agent = True
    config.chrome_version = CHROME_VERSION

    print("=" * 80)
    print("WEB AGENT SERVICE — DEBUG MODE (synchronous)")
    print("=" * 80)
    print(f"Testcase Root: {testcase_root}")
    print(f"Synchronous Agent: {config.synchronous_agent}")
    print(f"New Agent on First Submission: {config.new_agent_on_first_submission}")
    print(f"Chrome Version: {config.chrome_version or 'auto-detect'}")
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
