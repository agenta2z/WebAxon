"""
Runner script for GoodTime Template Selection ActionGraph.

This script demonstrates how to execute the GoodTime template selection workflow
that uses FindElementInferencer for intelligent template matching based on candidate notes.

Prerequisites:
1. Set ANTHROPIC_API_KEY environment variable
2. Install Chrome/Chromium for Selenium WebDriver
3. Have valid GoodTime credentials (browser will use existing session)

Usage:
    python run_goodtime_template_selection_graph.py

The script will:
1. Open Chrome browser
2. Navigate to GoodTime dashboard
3. Click on candidate Katie Meringolo
4. Open template selection
5. View candidate notes
6. Use LLM to select the best matching template
7. Click Continue to proceed
8. Select appropriate email template
9. Enable "Candidate suggest new times" checkbox
10. Select internal calendar (prefers "Global R&D Interviews")
11. Click "Request Availability" to send
"""

import logging
import os
import sys

# Add project root to path for local imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", "..", "..", ".."))
projects_root = os.path.abspath(os.path.join(project_root, ".."))

# Add WebAgent src
sys.path.insert(0, os.path.join(project_root, "src"))

# Add science packages if they exist
for pkg in ["SciencePythonUtils", "ScienceModelingTools"]:
    pkg_src = os.path.join(projects_root, pkg, "src")
    if os.path.exists(pkg_src) and pkg_src not in sys.path:
        sys.path.insert(0, pkg_src)

from create_goodtime_template_selection_graph import (
    create_goodtime_template_selection_graph,
)
from agent_foundation.common.inferencers.api_inferencers.ag.ag_claude_api_inferencer import (
    AgClaudeApiInferencer as ClaudeApiInferencer,
)
from rich_python_utils.string_utils.formatting.handlebars_format import (
    format_template as handlebars_format,
)
from rich_python_utils.string_utils.formatting.template_manager import (
    TemplateManager,
)
from webaxon.automation.agents import FindElementInferenceConfig, FindElementInferencer
from webaxon.automation.backends import BrowserConfig, UndetectedChromeConfig
from webaxon.automation.web_driver import WebDriver

# =============================================================================
# Configuration
# =============================================================================
STEP_WAIT = True  # True = wait for Enter after each step, False = run continuously
CANDIDATE_NAME = (
    None  # None = select first queued, or specify name e.g. "Katie Meringolo"
)

# Browser configuration
# NOTE: UndetectedChrome uses version_main (integer) - extract major version from 144.0.7559.109
CHROME_VERSION_MAIN = 144  # Major version from 144.0.7559.109

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
_logger = logging.getLogger(__name__)


def main():
    """Run the GoodTime template selection ActionGraph."""

    # 1. Create WebDriver with browser configuration
    _logger.info("Initializing WebDriver...")
    config = BrowserConfig(
        headless=False,  # Show browser for demonstration
        undetected_chrome=UndetectedChromeConfig(
            version_main=CHROME_VERSION_MAIN,
        ),
    )
    webdriver = WebDriver(config=config)

    # 2. Create reasoner for LLM-based element finding
    _logger.info("Creating Claude API reasoner...")
    reasoner = ClaudeApiInferencer(
        max_retry=3,
        min_retry_wait=1.0,
        max_retry_wait=5.0,
    )

    # 3. Create TemplateManager for prompt templates
    templates_path = os.path.join(
        project_root, "src", "webaxon", "automation", "agents", "prompt_templates"
    )
    _logger.info(f"Loading prompt templates from: {templates_path}")

    prompt_template_manager = TemplateManager(
        templates=templates_path,
        template_formatter=handlebars_format,
    )

    # 4. Create FindElementInferencer
    _logger.info("Creating FindElementInferencer...")
    find_element_inferencer = FindElementInferencer(
        base_inferencer=reasoner,
        template_manager=prompt_template_manager,
    )

    # Create wrapper that captures webdriver for ActionGraph executor
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

    # 6. Navigate to GoodTime dashboard (manual setup step)
    dashboard_url = "https://eu.goodtime.io/dashboard"
    _logger.info(f"Navigating to GoodTime dashboard: {dashboard_url}")
    webdriver.open_url(dashboard_url)

    # Wait for user to complete manual setup (login, etc.)
    _logger.info("")
    _logger.info("=" * 60)
    _logger.info("MANUAL SETUP REQUIRED")
    _logger.info("=" * 60)
    _logger.info("Please complete any required setup in the browser:")
    _logger.info("  - Log in to GoodTime if needed")
    _logger.info("  - Navigate to the correct view if needed")
    _logger.info("")
    input("Press Enter when ready to proceed with automation...")
    _logger.info("")

    # 7. Create ActionGraph
    _logger.info("Creating ActionGraph...")
    graph = create_goodtime_template_selection_graph(
        action_executor=action_executor,
        candidate_name=CANDIDATE_NAME,
        wait=STEP_WAIT,
    )

    # 8. Execute the graph
    _logger.info("Starting ActionGraph execution...")
    candidate_desc = CANDIDATE_NAME if CANDIDATE_NAME else "first queued candidate"
    _logger.info("The workflow will:")
    _logger.info(f"  1. Click on {candidate_desc}")
    _logger.info("  2. Open template selection")
    _logger.info("  3. View candidate notes")
    _logger.info("  4. Use LLM to select best matching template")
    _logger.info("  5. Click Continue")
    _logger.info("  6. Select email template")
    _logger.info("  7. Enable 'Candidate suggest new times' checkbox")
    _logger.info("  8. Select internal calendar")
    _logger.info("  9. Click 'Request Availability' to send")
    _logger.info("")
    _logger.info("Press Ctrl+C to stop execution.")

    try:
        result = graph.execute()
        _logger.info(
            f"Execution completed. Success: {result.success if hasattr(result, 'success') else 'N/A'}"
        )
    except KeyboardInterrupt:
        _logger.info("Execution stopped by user.")
    except Exception as e:
        _logger.error(f"Execution failed: {e}")
        raise
    finally:
        input("Press Enter to close browser...")
        _logger.info("Closing browser...")
        webdriver.quit()


if __name__ == "__main__":
    main()
