"""
Factory function to create an ActionGraph for Google search with CONTINUOUS monitoring.

This example demonstrates continuous monitoring using `graph.action("monitor", continuous=True)`:
- Monitors an element on the CURRENT tab (no new tab created for monitoring)
- Supports debounce via `event_confirmation_time` parameter
- continuous=True: After downstream actions complete, monitor re-runs to detect
  the next condition trigger, creating an interleaved execution loop:

  Monitor → Actions → Monitor → Actions → ... (until manually stopped)

Monitor Execution Order:
1. verify_setup() - Check if we're on the correct (monitored) tab
2. If verify fails AND enable_auto_setup=True: run setup_action to switch tabs
3. If verify fails AND enable_auto_setup=False: return "not met" (paused)
4. Run condition check

Monitor Setup Options:
- enable_verify_setup=True (default): Check we're on correct tab FIRST
- enable_auto_setup=True (required for Selenium): Auto-switch to monitored tab when verify fails

IMPORTANT - Selenium Limitation:
  enable_auto_setup MUST be True for Selenium-based monitoring. Selenium's
  current_window_handle only updates when switch_to.window() is called
  programmatically - it does NOT detect when users manually switch tabs in the
  browser UI. Therefore, we cannot use enable_auto_setup=False to wait for
  user-driven tab switching; the monitor must auto-switch to the monitored tab.

Architecture:
- Generic Layer (ScienceModelingTools): MonitorNode, MonitorResult, MonitorStatus
- Concrete Layer (WebAgent): MonitorCondition, MonitorConditionType, create_monitor()
- Phase 1 Infrastructure: NextNodesSelector enables self-loop via include_self=True
- ActionGraph handles "monitor" action type with lazy imports from WebAgent
"""

from agent_foundation.automation.schema import ActionGraph, TargetSpec
from agent_foundation.automation.schema.action_metadata import ActionMetadataRegistry


def create_google_search_action_graph(
    action_executor,
    search_query: str = "test query",
    url: str = "https://www.google.com"
):
    """
    Create an ActionGraph that demonstrates CONTINUOUS element-based monitoring.

    Workflow (loops continuously):
    1. Visit Google homepage
    2. Monitor the search textarea for value changes (waits for external input)
       - Waits for value to change and remain stable for 5 seconds (debounce)
       - Uses "value_changed" which monitors element.get_attribute("value")
       - continuous=True: loops back to step 2 after actions complete
    3. Visit Google homepage in a NEW tab (auto-detected: current tab is monitored)
    4. Input search query on the new tab
    5. Click search button
    6. → Loop back to step 2: monitor re-runs to detect next value change

    The loop continues until manually stopped (Ctrl+C or browser closed).

    Args:
        action_executor: The action executor (e.g., WebDriver instance)
        search_query: The search query to input
        url: The Google URL to visit (default: https://www.google.com)

    Returns:
        ActionGraph configured with continuous monitoring and action sequence
    """
    graph = ActionGraph(
        action_executor=action_executor,
        action_metadata=ActionMetadataRegistry(),
        debug_mode=True  # Enable debug logging to see graph_depth and self_loop_iteration
    )

    # Action 1: Visit Google homepage
    graph.action(
        "visit_url",
        target=url
    )

    # Action 2: Monitor the search textarea for value changes (CONTINUOUS MODE)
    # - Monitors element on CURRENT tab (no new tab created)
    # - Uses debounce: waits 5 seconds after value change to confirm it's stable
    # - continuous=True: After downstream actions complete, monitor re-runs to
    #   detect the next value change, creating an interleaved execution loop
    # - Execution order: verify_setup() first, then setup_action() if verify fails
    # - enable_verify_setup=True (default): check if on correct tab FIRST
    # - enable_auto_setup=True: auto-switch to monitored tab when verify fails
    #   IMPORTANT: enable_auto_setup MUST be True for Selenium-based monitoring.
    #   Selenium's current_window_handle only updates when switch_to.window() is called
    #   programmatically - it does NOT detect when users manually switch tabs in the
    #   browser UI. So we cannot rely on user-driven tab switching; the monitor must
    #   auto-switch to the monitored tab.
    # NOTE: For textarea/input elements, use "value_changed" (monitors get_attribute("value"))
    #       For regular elements like div/span, use "text_changed" (monitors element.text)
    graph.action(
        "monitor",
        target=TargetSpec(strategy="xpath", value="//textarea[@title='Search']"),
        event_condition="value_changed",  # Triggers when input value changes (for textarea/input)
        event_confirmation_time=5,  # Debounce: wait 5 seconds to confirm change is stable
        interval=2,  # Check every 2 seconds
        continuous=True,  # Enable continuous monitoring loop
        enable_auto_setup=True  # Must be True - see comment above
    )

    # Action 3: Visit Google homepage on a new tab
    # This action only executes AFTER the monitor condition is met.
    # It automatically detects the current tab is under monitoring and opens a new one.
    graph.action(
        "visit_url",
        target=url
    )

    # Action 4: Input text into search textarea
    graph.action(
        "input_text",
        target=TargetSpec(strategy="xpath", value="//textarea[@title='Search']"),
        args={"text": search_query}
    )

    # Action 5: Click the Google Search button
    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//input[@value='Google Search']")
    )

    return graph
