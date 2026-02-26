"""
Example: Run ActionGraph with CONTINUOUS element-based monitoring on Google search.

This script demonstrates ActionGraph execution with continuous monitor action.
The monitor waits for external input (user typing) in the search textarea,
then proceeds with the automated actions in a NEW tab (preserving monitored tab).
After actions complete, the monitor RE-RUNS to detect the next value change,
creating an interleaved execution loop that continues until manually stopped.

Usage:
    # Using Selenium (default)
    python run_google_search_action_graph_with_monitor.py

    # Using Playwright with Chromium
    python run_google_search_action_graph_with_monitor.py --backend playwright

    # Using Playwright with Firefox
    python run_google_search_action_graph_with_monitor.py --backend playwright --browser firefox

Workflow (loops continuously):
    1. Shows graph structure for review
    2. Asks for confirmation before proceeding
    3. Opens Google homepage
    4. Waits for you to type something in the search box
    5. After 5 seconds of stable input (debounce), proceeds automatically
    6. Opens Google in a NEW tab (auto-detects current tab is monitored)
    7. Inputs "hello world" and clicks search on the new tab
    8. Monitor re-runs → go back to step 4 (loop continues until Ctrl+C)
"""

import argparse
import logging
import time
import traceback

# Enable debug logging to trace execution flow
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress verbose third-party loggers
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('WDM').setLevel(logging.WARNING)
logging.getLogger('playwright').setLevel(logging.WARNING)

from webaxon.automation.web_driver import WebDriver, WebAutomationDrivers
from create_google_search_action_graph_with_monitor import create_google_search_action_graph


def create_driver(backend: str, browser: str, headless: bool = False) -> WebDriver:
    """
    Create a WebDriver instance with the specified backend.

    Args:
        backend: 'selenium' or 'playwright'
        browser: Browser type ('chrome', 'firefox', 'chromium', 'webkit')
        headless: Whether to run in headless mode

    Returns:
        WebDriver instance
    """
    if backend == 'selenium':
        # Map browser names to WebAutomationDrivers enum
        browser_map = {
            'chrome': WebAutomationDrivers.Chrome,
            'firefox': WebAutomationDrivers.Firefox,
            'edge': WebAutomationDrivers.Edge,
            'undetected_chrome': WebAutomationDrivers.UndetectedChrome,
        }
        driver_type = browser_map.get(browser.lower(), WebAutomationDrivers.Chrome)
        print(f"Using Selenium backend with {driver_type.value}")
        return WebDriver(
            driver_type=driver_type,
            headless=headless
        )

    elif backend == 'playwright':
        from webaxon.automation.backends import PlaywrightBackend

        # Map browser names to Playwright browser types
        browser_map = {
            'chrome': 'chromium',
            'chromium': 'chromium',
            'firefox': 'firefox',
            'webkit': 'webkit',
            'safari': 'webkit',
        }
        browser_type = browser_map.get(browser.lower(), 'chromium')
        print(f"Using Playwright backend with {browser_type}")

        # Create and initialize Playwright backend
        playwright_backend = PlaywrightBackend()
        playwright_backend.initialize(
            browser_type=browser_type,
            headless=headless
        )

        # Create WebDriver with the backend
        return WebDriver(backend=playwright_backend)

    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'selenium' or 'playwright'.")


def run_google_search_with_monitor(backend: str, browser: str, headless: bool):
    """Run ActionGraph with monitor to demonstrate value_changed condition."""
    print(f"\nInitializing browser (backend={backend}, browser={browser})...")
    driver = create_driver(backend, browser, headless)

    try:
        print("Creating ActionGraph with monitor...")
        graph = create_google_search_action_graph(
            action_executor=driver,
            search_query="hello world"
        )

        # Print graph structure for user review
        print("\n" + "=" * 60)
        print("GRAPH STRUCTURE:")
        print("=" * 60)
        graph.print_structure()

        # Ask user if they want to proceed
        print("=" * 60)
        response = input("Do you want to proceed with this example? (y/n): ").strip().lower()
        if response != 'y':
            print("Aborted by user.")
            return

        print("\n" + "=" * 60)
        print("INSTRUCTIONS (CONTINUOUS MONITORING):")
        print("1. The browser will navigate to Google")
        print("2. TYPE SOMETHING in the search box (any text)")
        print("3. Wait 5 seconds (debounce period)")
        print("4. The script will then automatically:")
        print("   - Open Google in a NEW tab (monitored tab preserved)")
        print("   - Input 'hello world' on the new tab")
        print("   - Click the search button")
        print("5. LOOP: Monitor auto-switches back to original tab")
        print("   - Type something NEW in the search box")
        print("   - After 5s debounce, actions execute in another new tab")
        print("   - This continues until you close the browser or Ctrl+C")
        print("=" * 60 + "\n")

        print("Executing ActionGraph with CONTINUOUS monitoring...")
        print("(monitor -> actions -> monitor -> actions -> ... loop)")
        print("Waiting for you to type in the search box...\n")

        print("[DEBUG] Calling graph.execute()...")
        result = graph.execute()
        print(f"[DEBUG] graph.execute() returned: success={result.success}")

        if result.success:
            print("\nSUCCESS: ActionGraph executed successfully!")
            print("Monitor detected value change and automation completed.")
        else:
            print(f"\nFAILED: ActionGraph execution failed: {result.error}")
            # Print full traceback for debugging
            if result.error:
                print("\n--- Full Traceback ---")
                traceback.print_exception(type(result.error), result.error, result.error.__traceback__)

        # Wait 10 seconds before closing to observe the result
        print("\nWaiting 100 seconds before closing browser...")
        time.sleep(100)

    finally:
        driver.quit()
        print("Browser closed.")


def main():
    parser = argparse.ArgumentParser(
        description="Run ActionGraph with monitor example using Selenium or Playwright backend."
    )
    parser.add_argument(
        '--backend', '-b',
        choices=['selenium', 'playwright'],
        default='selenium',
        help="Backend to use: 'selenium' (default) or 'playwright'"
    )
    parser.add_argument(
        '--browser',
        default='chrome',
        help="Browser to use: 'chrome' (default), 'firefox', 'chromium', 'webkit', 'edge'"
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help="Run browser in headless mode"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ActionGraph with Monitor Example")
    print(f"Backend: {args.backend}")
    print(f"Browser: {args.browser}")
    print(f"Headless: {args.headless}")
    print("=" * 60)

    run_google_search_with_monitor(
        backend=args.backend,
        browser=args.browser,
        headless=args.headless
    )


if __name__ == "__main__":
    main()
