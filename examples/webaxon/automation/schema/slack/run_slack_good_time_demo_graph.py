"""
Example: Run ActionGraph on Google search.

This script demonstrates ActionGraph execution with WebDriver.
The ActionGraph handles navigation via visit_url action.

Usage:
    python run_google_search_action_graph.py
"""

import time

from webaxon.automation.web_driver import WebDriver, WebAutomationDrivers
from create_slack_goodtime_demo_graph import create_slack_good_time_demo_graph


def run_google_search_action_graph():
    """Run ActionGraph to visit Google, input text, and click search."""
    # Use headless=False to visually observe the execution
    driver = WebDriver(
        driver_type=WebAutomationDrivers.Chrome,
        headless=False
    )

    try:
        print("Creating ActionGraph...")
        graph = create_slack_good_time_demo_graph(
            action_executor=driver,
            search_query="hello world"
        )

        print("Executing ActionGraph (visit_url -> input_text -> click)...")
        result = graph.execute()

        if result.success:
            print("SUCCESS: ActionGraph executed successfully!")
        else:
            print(f"FAILED: ActionGraph execution failed: {result.error}")

        # Wait 10 seconds before closing to observe the result
        print("Waiting 10 seconds before closing browser...")
        time.sleep(100000)

    finally:
        driver._driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    run_google_search_action_graph()
