"""
Example: Run ActionGraph on local Google search HTML.

This script demonstrates ActionGraph execution with WebDriver.
Run directly to manually verify the ActionGraph works correctly.

Usage:
    python run_google_search_action_graph.py
"""

import time
from pathlib import Path

from webaxon.automation.web_driver import WebDriver, WebAutomationDrivers
from create_google_search_action_graph import create_google_search_action_graph


def run_google_search_action_graph():
    """Run ActionGraph to input text and click search on local Google HTML."""
    html_path = Path(__file__).parent / "google_search.html"
    file_url = f"file:///{html_path.as_posix()}"

    # Use headless=False to visually observe the execution
    driver = WebDriver(
        driver_type=WebAutomationDrivers.Chrome,
        headless=False
    )

    try:
        print(f"Navigating to: {file_url}")
        driver.driver.get(file_url)

        print("Creating ActionGraph...")
        graph = create_google_search_action_graph(
            action_executor=driver,
            search_query="hello world"
        )

        print("Executing ActionGraph...")
        result = graph.execute()

        if result.success:
            print("SUCCESS: ActionGraph executed successfully!")
        else:
            print(f"FAILED: ActionGraph execution failed: {result.error}")

        # Wait 10 seconds before closing to observe the result
        print("Waiting 10 seconds before closing browser...")
        time.sleep(10)

    finally:
        driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    run_google_search_action_graph()
