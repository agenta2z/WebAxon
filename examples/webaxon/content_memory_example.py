"""
Example: Using ContentMemory with WebDriver

This example demonstrates how to use the content memorization feature
to track elements across multiple scroll actions.
"""

from webagent.automation.web_driver import WebDriver, WebAutomationDrivers

def main():
    print("=" * 80)
    print("ContentMemory Example: Tracking Elements Across Scrolls")
    print("=" * 80)

    # Create WebDriver with content memory enabled
    driver = WebDriver(
        driver_type=WebAutomationDrivers.UndetectedChrome,
        headless=False,  # Show browser for demo
        enable_content_memory=True  # Enable content memorization
    )

    try:
        # Navigate to a long page
        print("\n[1] Opening webpage...")
        driver.open_url('https://news.ycombinator.com/')

        # Add incremental IDs to elements
        print("[2] Adding element IDs...")
        driver.add_unique_index_to_elements()

        # Get initial HTML (without memory)
        initial_html = driver.get_body_html(return_dynamic_contents=True)
        print(f"[3] Initial page has ~{len(initial_html)} characters")

        # Method 1: Use execute_action_with_memory wrapper
        print("\n[4] Scrolling with memory (Method 1: Wrapper)...")
        result = driver.execute_action_with_memory(
            action_func=lambda: driver.execute_single_action(
                element=driver.find_element_by_xpath(tag_name='body'),
                action_type='scroll',
                action_args={'direction': 'Down', 'distance': 'Full'}
            ),
            action_context='scroll_down'
        )

        # Analyze results
        print(f"\n   Results after scroll #1:")
        print(f"   - New elements appeared: {len(result['new_elements'])}")
        print(f"   - Elements disappeared: {len(result['removed_elements'])}")
        print(f"   - Elements stayed visible: {result['merge_result'].persistent_count}")

        # Get cumulative HTML (all elements seen so far)
        cumulative_html = result['cumulative_html']
        visible_html = result['visible_html']
        print(f"   - Cumulative HTML size: {len(cumulative_html)} characters")
        print(f"   - Visible-only HTML size: {len(visible_html)} characters")

        # Get statistics
        stats = result['statistics']
        print(f"\n   Memory statistics:")
        print(f"   - Total elements tracked: {stats['total_elements']}")
        print(f"   - Currently visible: {stats['visible_elements']}")
        print(f"   - Removed from view: {stats['removed_elements']}")
        print(f"   - Snapshots taken: {stats['snapshots_taken']}")

        # Scroll again
        print("\n[5] Scrolling again...")
        result2 = driver.execute_action_with_memory(
            action_func=lambda: driver.execute_single_action(
                element=driver.find_element_by_xpath(tag_name='body'),
                action_type='scroll',
                action_args={'direction': 'Down', 'distance': 'Full'}
            ),
            action_context='scroll_down_2'
        )

        print(f"\n   Results after scroll #2:")
        print(f"   - New elements appeared: {len(result2['new_elements'])}")
        print(f"   - Elements disappeared: {len(result2['removed_elements'])}")

        # Get updated statistics
        stats2 = driver.content_memory.get_statistics()
        print(f"\n   Updated statistics:")
        print(f"   - Total elements tracked: {stats2['total_elements']}")
        print(f"   - Currently visible: {stats2['visible_elements']}")
        print(f"   - Removed from view: {stats2['removed_elements']}")

        # The cumulative HTML now contains elements from both scrolls
        final_cumulative = driver.content_memory.get_cumulative_html()
        print(f"\n   Final cumulative HTML: {len(final_cumulative)} characters")
        print(f"   (vs initial: {len(initial_html)} characters)")

        # Access specific elements
        print("\n[6] Accessing tracked elements...")
        all_elements = driver.content_memory.get_all_elements()
        print(f"   Total elements in memory: {len(all_elements)}")

        # Show sample elements
        print("\n   Sample elements (first 3):")
        for i, (elem_id, elem_data) in enumerate(list(all_elements.items())[:3]):
            print(f"   - ID: {elem_id}")
            print(f"     Tag: {elem_data.tag}")
            print(f"     Visibility: {elem_data.visibility_state.value}")
            print(f"     View count: {elem_data.view_count}")
            print(f"     Text preview: {elem_data.text[:50]}...")

        # Save cumulative HTML to file
        print("\n[7] Saving cumulative HTML...")
        with open('cumulative_content.html', 'w', encoding='utf-8') as f:
            f.write(final_cumulative)
        print("   Saved to: cumulative_content.html")

        print("\n" + "=" * 80)
        print("Example completed successfully!")
        print("=" * 80)

    finally:
        # Clean up
        driver.quit()


if __name__ == '__main__':
    main()
