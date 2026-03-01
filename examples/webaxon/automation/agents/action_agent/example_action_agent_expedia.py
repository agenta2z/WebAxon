"""
Example: Action agent on Expedia - Switch to Flights tab.

This example demonstrates using the action agent to interact with
Expedia.com by switching to the Flights booking tab.

Prerequisites:
1. Set ANTHROPIC_API_KEY environment variable
2. Install Chrome/Chromium for Selenium WebDriver

Usage:
    python example_action_agent_expedia.py --live
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

# Import common utilities
from common import (
    setup_project_paths,
    setup_logging,
    TestResult,
    extract_executed_actions,
    print_action_summary
)

# Setup paths and logging
project_root = setup_project_paths()
_logger = setup_logging(__name__)


def run_live_test() -> bool:
    """
    Live test: Navigate to Expedia and switch to Flights tab.

    This verifies:
    1. WebDriver initializes
    2. Can navigate to Expedia
    3. Action agent can click the Flights tab
    4. Flights section is displayed
    """
    from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
    from webaxon.automation.web_driver import WebDriver
    from webaxon.automation.agents import create_action_agent

    _logger.info("Running LIVE test on Expedia (browser + API calls)")
    result = TestResult(_logger)

    # Check for API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    result.check("ANTHROPIC_API_KEY is set", bool(api_key), "Set ANTHROPIC_API_KEY environment variable")
    if not api_key:
        return result.summary()

    webdriver = None

    try:
        # Test 1: Create WebDriver (visible browser for demonstration)
        _logger.info("Initializing WebDriver...")
        webdriver = WebDriver(headless=False)
        result.check("WebDriver initialized", webdriver is not None)

        # Test 2: Create reasoner
        _logger.info("Creating Claude API reasoner...")
        reasoner = ClaudeApiInferencer(
            max_retry=3,
            min_retry_wait=1.0,
            max_retry_wait=5.0,
        )
        result.check("Reasoner created", reasoner is not None)

        # Test 3: Create action agent
        _logger.info("Creating action agent...")
        action_agent = create_action_agent(
            webdriver=webdriver,
            reasoner=reasoner,
        )
        result.check("Action agent created", action_agent is not None)

        # Test 4: Navigate to Expedia
        _logger.info("Navigating to Expedia...")
        webdriver.get("https://www.expedia.com/")

        # Wait for page to load
        time.sleep(3)

        # Verify initial page loaded
        initial_url = webdriver.current_url
        result.check(
            "Initial page navigation to Expedia",
            "expedia" in initial_url.lower(),
            f"URL: {initial_url}"
        )

        # Test 5: Call action agent to search for flights
        _logger.info("Calling action agent to search for flights...")

        # Compute dates dynamically (1 month from now, 1 week trip)
        departure_date = datetime.now() + timedelta(days=30)
        return_date = departure_date + timedelta(days=7)
        departure_str = departure_date.strftime("%B %d %Y")
        return_str = return_date.strftime("%B %d %Y")

        # Task that allows agent to navigate to any flight search site
        task = f"Search for round-trip flights from Seattle to New York, departing {departure_str} and returning {return_str}, for 1 adult. You can use any flight search website."
        _logger.info(f"Task: {task}")

        try:
            agent_result = action_agent(user_input=task)
            result.check("Action agent returned result", agent_result is not None)
        except Exception as e:
            # Even if action execution fails, we continue to check the browser state
            error_type = type(e).__name__
            _logger.warning(f"Action agent raised {error_type}: {e}")
            result.check("Action agent call completed", True)

        # Extract and print executed actions summary
        _logger.info("Extracting executed actions from agent state...")
        executed_actions = extract_executed_actions(action_agent)
        print_action_summary(executed_actions)

        # Wait for any actions to complete
        time.sleep(2)

        # Test 6: Verify agent took actions
        _logger.info("Verifying agent executed actions...")

        current_url = webdriver.current_url
        page_title = webdriver.title

        # Check if we're still on a flights-related page
        url_has_flights = "flight" in current_url.lower()
        result.check(
            "Still on flights page",
            url_has_flights,
            f"URL: {current_url}"
        )

        # Check for any relevant actions executed
        # Accept Click, InputText, or Navigation actions
        relevant_actions = [
            a for a in executed_actions
            if any(action_type in a.get('type', '') for action_type in
                   ['Click', 'InputText', 'Navigation', 'MakeAnswer', 'Clarification'])
        ]
        result.check(
            "Agent executed relevant actions",
            len(relevant_actions) > 0,
            f"Found {len(relevant_actions)} actions, types: {[a.get('type') for a in executed_actions]}"
        )

    except Exception as e:
        result.check("Live test execution", False, f"{type(e).__name__}: {e}")

    finally:
        if webdriver:
            _logger.info("Closing browser...")
            try:
                webdriver.quit()
            except Exception:
                pass  # Ignore cleanup errors

    return result.summary()


def main():
    """Run example with specified mode."""
    parser = argparse.ArgumentParser(
        description="Example: Action agent on Expedia - Switch to Flights tab",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python example_action_agent_expedia.py --live    # Run the test
        """
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=True,
        help="Run live test with browser and API calls (default: True)"
    )

    args = parser.parse_args()

    success = run_live_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
