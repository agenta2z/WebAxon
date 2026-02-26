"""
Factory function to create an ActionGraph for GoodTime template selection with CONTINUOUS monitoring.

This example demonstrates continuous monitoring using `graph.action("monitor", continuous=True)`:
- Monitors the GoodTime dashboard for queued candidates
- When a candidate is detected, opens a NEW tab to process them
- After processing, loops back to monitor for the next candidate
- Only processes one candidate at a time (sequential processing)

Monitor Execution Order:
1. verify_setup() - Check if we're on the dashboard tab
2. If verify fails AND enable_auto_setup=True: auto-switch to dashboard tab
3. Run condition check (element_present for first queued candidate)
4. If condition met: proceed to downstream actions in new tab
5. After actions complete: close tab and loop back to monitor

Architecture:
- Generic Layer (ScienceModelingTools): MonitorNode, MonitorResult, MonitorStatus
- Concrete Layer (WebAgent): MonitorCondition, MonitorConditionType, create_monitor()
- Phase 1 Infrastructure: NextNodesSelector enables self-loop via include_self=True
- ActionGraph handles "monitor" action type with lazy imports from WebAgent

Prerequisites:
1. Set ANTHROPIC_API_KEY environment variable
2. Install Chrome/Chromium for Selenium WebDriver
3. Be logged into GoodTime and on the dashboard page

Usage:
    from create_goodtime_template_selection_graph_with_monitor import create_goodtime_template_selection_graph_with_monitor

    graph = create_goodtime_template_selection_graph_with_monitor(
        action_executor=action_executor,
        dashboard_url="https://eu.goodtime.io/dashboard"
    )
    graph.execute()
"""

from typing import Optional, Union

# =============================================================================
# Path Resolution (must come before package imports)
# =============================================================================
from path_utils import setup_project_paths

setup_project_paths(__file__)

from science_modeling_tools.automation.schema import ActionGraph, TargetSpec
from science_modeling_tools.automation.schema.action_metadata import ActionMetadataRegistry


def create_goodtime_template_selection_graph_with_monitor(
    action_executor,
    dashboard_url: str = "https://eu.goodtime.io/dashboard",
    candidate_name: Optional[str] = None,
    wait: Optional[Union[float, bool]] = None,
):
    """
    Create an ActionGraph that continuously monitors for queued candidates.

    Workflow (loops continuously):
    1. Visit GoodTime dashboard
    2. Monitor for queued candidates (waits for first candidate to appear)
       - Uses "element_present" to detect when a candidate is queued
       - Waits for confirmation time to ensure stable
       - continuous=True: loops back after processing
    3. Process candidate in NEW tab:
       - Click candidate
       - Select template based on notes
       - Configure email options
       - Send availability request
    4. Close tab and loop back to step 2

    Args:
        action_executor: The action executor (dict with 'default' WebDriver and
                        'find_element_agent' for LLM-based element finding)
        dashboard_url: GoodTime dashboard URL (default: "https://eu.goodtime.io/dashboard")
        candidate_name: Name of the candidate to select. If None, selects the first
                        queued candidate on the dashboard. (default: None)
        wait: Wait after each action. float=seconds, True=human confirmation (default: None)

    Returns:
        ActionGraph configured with continuous monitoring
    """
    graph = ActionGraph(
        action_executor=action_executor,
        action_metadata=ActionMetadataRegistry(),
        debug_mode=True  # Enable debug logging to see graph_depth and self_loop_iteration
    )

    # =========================================================================
    # Step 1: Visit GoodTime Dashboard
    # =========================================================================

    # Always wait after initial visit to allow manual setup (login, etc.)
    # This runs BEFORE monitor starts, so won't affect new tab behavior
    graph.action(
        "visit_url",
        target=dashboard_url,
        wait=True,  # Always wait for manual setup, regardless of global wait setting
    )

    # =========================================================================
    # Step 2: Monitor for Queued Candidates (CONTINUOUS MODE)
    # =========================================================================

    # Monitor the dashboard on CURRENT tab for queued candidates
    # - Uses element_present to detect when first queued candidate appears
    # - continuous=True: loops back after processing to handle next candidate
    # - enable_auto_setup=True: auto-switch to dashboard tab if on different tab
    #
    # IMPORTANT: enable_auto_setup MUST be True for Selenium-based monitoring.
    # Selenium's current_window_handle only updates when switch_to.window() is called
    # programmatically - it does NOT detect when users manually switch tabs in the
    # browser UI.
    #
    # XPath for first Queued or Pick Up candidate:
    # (//a[contains(@class, '_Interview_1kmia_9') and (.//span[@class='pillText' and (text()='Queued' or text()='Pick Up')])])[1]
    graph.action(
        "monitor",
        target=TargetSpec(
            strategy="xpath",
            value="(//a[contains(@class, '_Interview_1kmia_9') and (.//span[@class='pillText' and (text()='Queued' or text()='Pick Up')])])[1]"
        ),
        event_condition="element_present",  # Triggers when candidate appears
        event_confirmation_time=3,  # Debounce: wait 3 seconds to confirm
        interval=5,  # Check every 5 seconds
        continuous=True,  # Enable continuous monitoring loop
        enable_auto_setup=True  # Must be True for Selenium
    )

    # =========================================================================
    # Step 3: Visit Dashboard in NEW Tab to Process Candidate
    # =========================================================================

    # This action only executes AFTER the monitor condition is met.
    # It automatically detects the current tab is under monitoring and opens a new one.
    graph.action(
        "visit_url",
        target=dashboard_url
    )

    # =========================================================================
    # Step 4: Select Candidate
    # =========================================================================

    # Build XPath based on candidate selection mode
    if candidate_name:
        # Try specific Queued candidate first by name
        queued_candidate_xpath = (
            f"//a[contains(@class, '_Interview_1kmia_9') and "
            f".//span[@class='_GuestName_1kmia_148' and text()='{candidate_name}'] and "
            f".//span[@class='pillText' and text()='Queued']]"
        )

        # Fallback: Click Pick Up pill (status badge) for same candidate to queue it
        # This clicks the "Pick Up" badge with plus icon to add candidate to queue,
        # NOT the candidate card itself (which would open the detail panel)
        pickup_pill_xpath = (
            f"//a[contains(@class, '_Interview_1kmia_9') and "
            f".//span[@class='_GuestName_1kmia_148' and text()='{candidate_name}']]"
            f"//div[@class='GuiPill queue right-icon' and "
            f".//span[@class='pillText' and text()='Pick Up']]"
        )

        # Click on the candidate with fallback to Pick Up pill
        # If Queued candidate not found, click Pick Up pill to queue it, then retry
        with graph.action(
            "click",
            target=TargetSpec(
                strategy="xpath",
                value=queued_candidate_xpath
            ),
            args={"try_open_in_new_tab": False},
            wait=wait,
        ).target_not_found(
            retry_after_handling=True,  # Retry clicking Queued candidate after queueing
            max_retries=3,
            retry_delay=1.0
        ):
            # Fallback: Click Pick Up pill to queue the candidate
            # After this, the retry will attempt to click the Queued candidate again
            graph.action(
                "click",
                target=TargetSpec(
                    strategy="xpath",
                    value=pickup_pill_xpath
                ),
                args={"try_open_in_new_tab": False},
                wait=wait,
            )
    else:
        # Try first Queued candidate (no specific name)
        first_queued_xpath = (
            "(//a[contains(@class, '_Interview_1kmia_9') and "
            ".//span[@class='pillText' and text()='Queued']])[1]"
        )

        # Fallback: Click first Pick Up pill (status badge) to queue a candidate
        # This clicks the "Pick Up" badge with plus icon, NOT the candidate card
        first_pickup_pill_xpath = (
            "(//div[@class='GuiPill queue right-icon' and "
            ".//span[@class='pillText' and text()='Pick Up']])[1]"
        )

        # Click on the first candidate with fallback to Pick Up pill
        # If no Queued candidates, click Pick Up pill to queue one, then retry
        with graph.action(
            "click",
            target=TargetSpec(
                strategy="xpath",
                value=first_queued_xpath
            ),
            args={"try_open_in_new_tab": False},
            wait=wait,
        ).target_not_found(
            retry_after_handling=True,  # Retry clicking first Queued candidate after queueing
            max_retries=3,
            retry_delay=1.0
        ):
            # Fallback: Click first Pick Up pill to queue a candidate
            # After this, the retry will attempt to click the first Queued candidate again
            graph.action(
                "click",
                target=TargetSpec(
                    strategy="xpath",
                    value=first_pickup_pill_xpath
                ),
                args={"try_open_in_new_tab": False},
                wait=wait,
            )

    # =========================================================================
    # Step 5: Click "Select Template" Button
    # =========================================================================

    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//button[.//span[text()='Select Template']]"
        ),
        wait=wait,
    )

    # =========================================================================
    # Step 6: Use FindElementInferencer to Select Best Matching Template
    # =========================================================================

    # Use agent-based element finding to select best template
    # The find_element_agent will analyze the page and locate the template
    # that best matches the candidate notes visible in the ACTIVITY section
    graph.action(
        "click",
        target=TargetSpec(
            strategy="agent",
            value="""Find the <span> element containing the request-availability template name that matches BOTH the interview type AND the level according to the notes in the ACTIVITY section.
The notes contain TWO key pieces of information to match:
1. Interview type (look for 'Select the Engineering interview types' - e.g., 'Backend Coding - Code Design')
2. Job level (look for 'Level of Job' - e.g., 'P40')

Templates are listed in the 'TEMPLATES' section as <span> elements with names like
'S/RS_UAT_Q4FY25_Backend Coding - Code Design P40'. For this ask, YOU MUST find one best template. DO NOT return 'NOT FOUND'."""
        ),
        wait=wait,
    )

    # =========================================================================
    # Step 7: Click "Continue" Button
    # =========================================================================

    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//button[contains(@class, 'gui-btn-primary') and .//span[text()='Continue' or text()='Done']]"
        ),
        wait=wait,
    )

    # =========================================================================
    # Step 8: Select Email Template
    # =========================================================================

    # Click on email template dropdown to open selection
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//div[@data-test='email-template-name']"
        ),
        wait=wait,
    )

    # Select "GT QUEUES Request Availability - Candidate Schedule" template
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//div[@role='option' and contains(., 'Request Availability')]"
        ),
        wait=False,
    )

    # =========================================================================
    # Step 9: Enable "Candidate Suggest New Times" (if not already enabled)
    # =========================================================================

    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//div[@data-test='allow-candidate-suggest-times-checkbox']//label[not(contains(@class, '_labelChecked'))]"
        ),
        no_action_if_target_not_found=True,
        wait=wait,
    )

    # =========================================================================
    # Step 10: Enable "Share Itinerary with Candidate" (if not already enabled)
    # =========================================================================

    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//div[@data-test='share-itinerary-with-candidate-checkbox']//label[not(contains(@class, '_labelChecked'))]"
        ),
        no_action_if_target_not_found=True,
        wait=wait,
    )

    # =========================================================================
    # Step 11: Select Internal Calendar
    # =========================================================================

    # Click on internal calendar dropdown to open selection
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//div[@data-test='internal-calendar']"
        ),
        wait=wait,
    )

    # Use agent to select the appropriate calendar from the dropdown
    graph.action(
        "click",
        target=TargetSpec(
            strategy="agent",
            value="""Find and click the internal calendar option in the dropdown.
If there is only one calendar option available, select it.
If there are multiple calendar options, select "Global R&D Interviews".
The dropdown options should be visible after clicking the calendar selector."""
        ),
        wait=wait,
    )

    # =========================================================================
    # Step 12: Send Availability Request
    # =========================================================================

    # Click "Request Availability" button to send the request
    # After this action completes, the monitor will re-run to detect the next candidate
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//a[contains(@class, '_buttonTitle_') and contains(normalize-space(), 'Request Availability')]"
        ),
        wait=wait,
    )

    return graph
