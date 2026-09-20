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

Required Setup:
--------------
This example requires two LLM-based components:
1. `find_element_agent` - For TargetSpec(strategy="agent", ...)
   Uses FindElementInferencer (extends TemplatedInferencerBase)
2. `agent` executor - For graph.action("agent", ...)
   Uses PromptBasedActionAgent (same as web_agent_service.py)

Components:
- webaxon.automation.agents.FindElementInferencer: One-inference agent for element finding
- prompt_templates/: Handlebars templates for agents
  - find_element.hbs: Template for element finding
  - action_agent/: Templates for PromptBasedActionAgent (copied from devsuite)
- run_google_search_with_agents.py: Complete runner script showing setup

Example Usage:
    from agent_foundation.agents.prompt_based_agents.prompt_based_action_agent import PromptBasedActionAgent
    from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
    from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
    from webaxon.automation.web_driver import WebDriver
    from webaxon.automation.agents import FindElementInferencer

    # 1. Create WebDriver
    webdriver = WebDriver(headless=False)

    # 2. Create reasoner and template manager
    reasoner = ClaudeApiInferencer(max_retry=3)
    template_manager = TemplateManager(templates="./prompt_templates/")

    # 3. Create agents
    find_element_agent = FindElementInferencer(
        webdriver=webdriver,
        base_inferencer=reasoner,
        template_manager=template_manager
    )
    action_agent = PromptBasedActionAgent(
        prompt_formatter=template_manager.switch(active_template_root_space='action_agent'),
        reasoner=reasoner,
        actor={'default': webdriver},
        ...  # See run_google_search_with_agents.py for full config
    )

    # 4. Build action executor
    action_executor = {
        'default': webdriver,
        'find_element_agent': find_element_agent,
        'agent': action_agent,
    }

    # 5. Create and execute graph
    graph = create_google_search_action_graph(action_executor=action_executor, search_query="test")
    graph.execute()

See run_google_search_with_agents.py for the complete working example.
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
        action_metadata=ActionMetadataRegistry()
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
    # Here we leverage a 'find_element_agent' to perform element search.
    # The 'static' option means resolving the element once by agent, then convert it to xpath, and we will use xpath since the 2nd iteration.
    # It can also be 'dynamic', indicating using agent every time.
    # Note: strategy="agent" is the user-facing API; internally it uses the "find_element_agent" executor key.
    graph.action(
        "monitor",
        target=TargetSpec(strategy="agent", value="find the search query input box", options=['static']),
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

    # Action 4: Input text into search textarea and perform search,
    # leveraging an agent to complete both text input and clicking the search button.
    graph.action(
        "agent",
        target="input query {{text}} and perform search",
        args={"text": search_query}
    )

    return graph
