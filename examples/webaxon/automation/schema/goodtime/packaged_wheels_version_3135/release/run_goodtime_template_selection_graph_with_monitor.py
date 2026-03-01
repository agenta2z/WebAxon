"""
Runner script for GoodTime Template Selection with Continuous Monitoring.

This script executes the GoodTime template selection workflow with continuous
monitoring that watches for queued candidates and processes them one at a time.

Prerequisites:
1. Install Chrome/Chromium for Selenium WebDriver
2. Have valid GoodTime credentials (browser will use existing session)

Usage:
    python run_goodtime_template_selection_graph_with_monitor.py

The script will:
1. Open Chrome browser
2. Navigate to GoodTime dashboard
3. Monitor for queued candidates (waits until one appears)
4. When a candidate is detected:
   - Open a new tab to process them
   - Click on candidate
   - Select template based on notes
   - Configure email options
   - Send availability request
5. Loop back to step 3 to monitor for the next candidate
6. Press Ctrl+C to stop the monitor loop
"""

import atexit
import fcntl
import os
import signal
import sys
import traceback

# =============================================================================
# Path Resolution (must come before package imports)
# =============================================================================
from path_utils import setup_project_paths

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = setup_project_paths(__file__)

# =============================================================================
# Constants
# =============================================================================
LOGS_FOLDER_NAME = "logs"
LOG_FILE_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
LOCK_FILE_NAME = "goodtime_automation.lock"
CHROME_VERSION_MAIN = 144  # Major version from 144.0.7559.109

# Runtime configuration
STEP_WAIT = True  # True = wait for Enter after each step, False = run continuously
CANDIDATE_NAME = None  # None = select first queued, or specify name e.g. "Katie Meringolo"


# =============================================================================
# Import goodtime_automation_bundle first (for bundle wheel mode)
# This registers rich_python_utils, agent_foundation, webaxon in sys.modules
# =============================================================================
try:
    import goodtime_automation_bundle
    print("✓ Imported goodtime_automation_bundle (modules registered in sys.modules)")
except ImportError:
    # Bundle not installed - will try to import from source or installed packages
    pass


# =============================================================================
# Import packages - fail fast with clear error
# =============================================================================
try:
    from functools import partial
    from rich_python_utils.common_objects.debuggable import Debugger
    from rich_python_utils.datetime_utils.common import current_date_time_string
    from rich_python_utils.io_utils.json_io import write_json
    from rich_python_utils.string_utils.formatting.handlebars_format import (
        format_template as handlebars_format,
    )
    from rich_python_utils.string_utils.formatting.template_manager import (
        TemplateManager,
    )
    from agent_foundation.common.inferencers.api_inferencers.ag.ag_claude_api_inferencer import (
        AgClaudeApiInferencer as ClaudeApiInferencer,
    )
    from webaxon.automation.agents import (
        FindElementInferenceConfig,
        FindElementInferencer,
    )
    from webaxon.automation.backends import BrowserConfig, UndetectedChromeConfig
    from webaxon.automation.web_driver import WebDriver
    from create_goodtime_template_selection_graph_with_monitor import (
        create_goodtime_template_selection_graph_with_monitor,
    )
except ImportError as e:
    print(f"FATAL: Failed to import required packages: {e}")
    print(f"Traceback:\n{traceback.format_exc()}")
    print("\nEnsure packages are installed or source directories exist.")
    if _project_root:
        print(f"Project root found: {_project_root}")
    else:
        print("Project root NOT found - bundle may not be installed.")
    sys.exit(1)


# =============================================================================
# Setup Logger (Debugger + write_json for structured JSONL file logging)
# =============================================================================
_log_file_path = os.path.join(
    _script_dir,
    LOGS_FOLDER_NAME,
    f"goodtime_automation_{current_date_time_string(LOG_FILE_TIMESTAMP_FORMAT)}.jsonl"
)

logger = Debugger(
    logger=partial(write_json, file_path=_log_file_path, append=True),
    always_add_logging_based_logger=True,  # Also console output
    log_name="GoodTimeAutomation",
    debug_mode=True,
    log_time=True
)


# =============================================================================
# Lockfile Management
# =============================================================================
_lockfile_path = os.path.join(_script_dir, LOCK_FILE_NAME)
_lockfile_fd = None


def cleanup_lockfile():
    """Release lock and clean up lockfile on exit."""
    global _lockfile_fd
    if _lockfile_fd:
        try:
            fcntl.flock(_lockfile_fd, fcntl.LOCK_UN)
            _lockfile_fd.close()
            if os.path.exists(_lockfile_path):
                os.remove(_lockfile_path)
        except Exception:
            pass  # Ignore errors during cleanup


def acquire_lock():
    """Acquire exclusive lock or exit if another instance is running."""
    global _lockfile_fd

    try:
        _lockfile_fd = open(_lockfile_path, "w")
        fcntl.flock(_lockfile_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lockfile_fd.write(str(os.getpid()))
        _lockfile_fd.flush()
        logger.log_info(f"Acquired exclusive lock with PID: {os.getpid()}")
        return True
    except IOError:
        logger.log_warning("Another instance is already running (lock held by another process)")
        logger.log_info("Exiting to prevent duplicate instances")
        sys.exit(0)


atexit.register(cleanup_lockfile)


# =============================================================================
# Signal Handlers
# =============================================================================
def signal_handler(signum, frame):
    """Handle signals and log them."""
    signal_name = signal.Signals(signum).name
    logger.log_warning(f"Received signal: {signal_name} ({signum})")

    if signum == signal.SIGTERM:
        cleanup_lockfile()
        sys.exit(1)
    # For SIGHUP and SIGPIPE, just log and continue
    logger.log_info(f"Ignoring {signal_name}, continuing...")


signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGPIPE, signal_handler)


# =============================================================================
# User Interaction
# =============================================================================
def get_user_consent():
    """Ask user for consent before continuing."""
    print("\n" + "=" * 80)
    print("  GoodTime Automation - User Consent Required")
    print("=" * 80)
    print()
    print("This application will:")
    print("  - Open Chrome browser and navigate to GoodTime")
    print("  - Monitor for queued candidates automatically")
    print("  - Process candidates by selecting templates and sending emails")
    print("  - Use AWS Bedrock API to make intelligent decisions")
    print()
    print("Requirements:")
    print("  - You must be logged into GoodTime in your browser")
    print("  - AWS credentials must be configured")
    print("  - Chrome browser must be installed")
    print()
    print("=" * 80)
    sys.stdout.flush()

    while True:
        try:
            response = input("Do you want to continue? (yes/no): ").strip().lower()
            if response in ["yes", "y"]:
                print("\n✓ User consented. Starting automation...\n")
                logger.log_info("User consented to automation")
                return True
            elif response in ["no", "n"]:
                print("\n✗ User declined. Exiting...\n")
                logger.log_info("User declined automation")
                return False
            else:
                print("Please enter 'yes' or 'no'.")
        except EOFError:
            logger.log_error("No stdin available for user input (EOFError)")
            print("\n✗ ERROR: Cannot read user input - terminal not properly connected")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n\n✗ User interrupted (Ctrl+C). Exiting...")
            logger.log_info("User interrupted at consent prompt (Ctrl+C)")
            return False


def check_dependencies():
    """Check all dependencies and display status in terminal."""
    logger.log_info("=" * 70)
    logger.log_info("GoodTime Automation - System Check")
    logger.log_info("=" * 70)
    logger.log_info(f"Python: {sys.version}")

    all_ok = True

    critical_deps = [
        ("webaxon", "webaxon", True),
        ("agent_foundation", "agent_foundation", False),
        ("rich_python_utils", "rich_python_utils", True),
        ("selenium", "selenium", True),
        ("boto3", "boto3", True),
    ]

    optional_deps = [
        ("anthropic", "anthropic"),
        ("beautifulsoup4", "bs4"),
        ("pybars3", "pybars3"),
    ]

    logger.log_info("Critical Packages:")
    for pkg_name, import_name, required in critical_deps:
        try:
            mod = __import__(import_name)
            ver = getattr(mod, "__version__", "unknown")
            logger.log_info(f"  ✓ {pkg_name}: {ver}")
        except ImportError as e:
            if required:
                logger.log_error(f"  ✗ {pkg_name}: MISSING (CRITICAL) - {e}")
                all_ok = False
            else:
                logger.log_warning(f"  ⚠ {pkg_name}: MISSING (optional) - {e}")
        except Exception as e:
            logger.log_warning(f"  ⚠ {pkg_name}: ERROR - {e}")

    logger.log_info("Optional Packages:")
    for pkg_name, import_name in optional_deps:
        try:
            mod = __import__(import_name)
            ver = getattr(mod, "__version__", "unknown")
            logger.log_info(f"  ✓ {pkg_name}: {ver}")
        except ImportError as e:
            logger.log_warning(f"  ⚠ {pkg_name}: MISSING (optional) - {e}")
        except Exception as e:
            logger.log_warning(f"  ⚠ {pkg_name}: ERROR - {e}")

    # Check Chrome
    logger.log_info("Chrome Browser:")
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    found = any(os.path.exists(p) for p in chrome_paths)
    if found:
        logger.log_info("  ✓ Chrome found")
    else:
        logger.log_error("  ✗ Chrome NOT found")
        all_ok = False

    logger.log_info("=" * 70)
    if all_ok:
        logger.log_info("✓ All checks passed!")
    else:
        logger.log_error("✗ Some checks failed - see above")
    logger.log_info("=" * 70)

    return all_ok


# =============================================================================
# Main Function
# =============================================================================
def main():
    """Run the GoodTime template selection ActionGraph with continuous monitoring."""

    # Acquire exclusive lock
    acquire_lock()

    logger.log_info("=" * 80)
    logger.log_info("ENTERING main() function")
    logger.log_info("=" * 80)

    try:
        # Get user consent
        if not get_user_consent():
            logger.log_info("User declined to continue. Exiting...")
            return

        logger.log_info("User consented. Proceeding with automation...")

        # Run dependency checks
        if not check_dependencies():
            logger.log_error("Dependency checks failed, exiting...")
            input("Press Enter to exit...")
            return

        logger.log_info("Dependency checks passed, continuing...")

        # 1. Create WebDriver with browser configuration
        logger.log_info("Initializing WebDriver...")
        config = BrowserConfig(
            headless=False,
            undetected_chrome=UndetectedChromeConfig(
                version_main=CHROME_VERSION_MAIN,
            ),
        )
        webdriver = WebDriver(config=config)

        # 2. Create reasoner for LLM-based element finding
        logger.log_info("Creating Claude API reasoner...")
        reasoner = ClaudeApiInferencer(
            max_retry=3,
            min_retry_wait=1.0,
            max_retry_wait=5.0,
        )

        # 3. Create TemplateManager for prompt templates
        import webaxon.automation.agents.prompt_templates as templates_module
        templates_path = os.path.dirname(templates_module.__file__)
        logger.log_info(f"Loading prompt templates from: {templates_path}")

        prompt_template_manager = TemplateManager(
            templates=templates_path,
            template_formatter=handlebars_format,
        )

        # 4. Create FindElementInferencer
        logger.log_info("Creating FindElementInferencer...")
        find_element_inferencer = FindElementInferencer(
            base_inferencer=reasoner,
            template_manager=prompt_template_manager,
        )

        def find_element_agent(user_input: str, options=None, **kwargs):
            """Wrapper that adapts ActionGraph call signature to FindElementInferencer."""
            return find_element_inferencer(
                html_source=webdriver,
                description=user_input,
                inference_config=FindElementInferenceConfig(
                    inject_unique_index_to_elements=True,
                    options=options,
                ),
            )

        # 5. Build action executor with agents registered
        action_executor = {
            "default": webdriver,
            "find_element_agent": find_element_agent,
        }

        # Wait for user to complete manual setup
        logger.log_info("")
        logger.log_info("=" * 60)
        logger.log_info("MANUAL SETUP REQUIRED")
        logger.log_info("=" * 60)
        logger.log_info("Please complete any required setup:")
        logger.log_info("  - Log in to GoodTime in a browser")
        logger.log_info("  - The script will navigate to the dashboard automatically")
        logger.log_info("")
        logger.log_info("The monitor will:")
        logger.log_info("  1. Watch the dashboard for queued candidates")
        logger.log_info("  2. When a candidate appears, process them in a new tab")
        logger.log_info("  3. Loop back to monitor for the next candidate")
        logger.log_info("")
        logger.log_info("Press Ctrl+C to stop the monitor loop.")
        logger.log_info("")
        input("Press Enter when ready to start monitoring...")
        logger.log_info("")

        # 6. Create ActionGraph
        logger.log_info("Creating ActionGraph with continuous monitoring...")
        candidate_desc = CANDIDATE_NAME if CANDIDATE_NAME else "first queued candidate"
        graph = create_goodtime_template_selection_graph_with_monitor(
            action_executor=action_executor,
            candidate_name=CANDIDATE_NAME,
            wait=STEP_WAIT,
        )

        # 7. Execute the graph
        logger.log_info("Starting ActionGraph execution with continuous monitoring...")
        logger.log_info("The workflow will continuously:")
        logger.log_info(f"  1. Monitor dashboard for queued candidates")
        logger.log_info(f"  2. When detected, process {candidate_desc} in a new tab")
        logger.log_info("  3. Loop back to monitor for next candidate")
        logger.log_info("")
        logger.log_info("Press Ctrl+C to stop the monitor loop.")

        try:
            result = graph.execute()
            logger.log_info(
                f"Execution completed. Success: {result.success if hasattr(result, 'success') else 'N/A'}"
            )
        except KeyboardInterrupt:
            logger.log_info("Monitor stopped by user.")
        except Exception as e:
            logger.log_error(f"Execution failed: {e}")
            logger.log_error(f"Full traceback:\n{traceback.format_exc()}")
            raise
        finally:
            input("Press Enter to close browser...")
            logger.log_info("Closing browser...")
        webdriver.quit()

    except KeyboardInterrupt:
        logger.log_info("Script interrupted by user (Ctrl+C)")
        print("\nScript interrupted by user")
    except Exception as e:
        logger.log_error(f"FATAL ERROR in main(): {e}")
        logger.log_error(traceback.format_exc())
        print(f"\nFATAL ERROR: {e}")
        print(f"Check log file at: {_log_file_path}")
        input("Press Enter to exit...")
        raise


if __name__ == "__main__":
    try:
        logger.log_info("=" * 80)
        logger.log_info("SCRIPT STARTED")
        logger.log_info(f"Log file: {_log_file_path}")
        if _project_root:
            logger.log_info(f"Project root: {_project_root}")
        else:
            logger.log_info("Running in bundle-only mode (no source)")
        logger.log_info("=" * 80)

        main()

        logger.log_info("=" * 80)
        logger.log_info("SCRIPT COMPLETED SUCCESSFULLY")
        logger.log_info("=" * 80)
    except Exception as e:
        logger.log_error("=" * 80)
        logger.log_error(f"SCRIPT FAILED WITH ERROR: {e}")
        logger.log_error(traceback.format_exc())
        logger.log_error("=" * 80)
        print(f"\n\nFATAL ERROR: {e}")
        print(f"\nFull error details have been logged to:")
        print(f"  {_log_file_path}")
        print("\nPlease check the log file for details.")
        input("\nPress Enter to exit...")
        raise
