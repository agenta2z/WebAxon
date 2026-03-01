"""
Factory function to create an ActionGraph for GoodTime template selection workflow.

This example demonstrates:
1. Clicking on a specific candidate (Katie Meringolo) from the dashboard
2. Using FindElementInferencer to intelligently select a template based on candidate notes
3. Selecting email template for the availability request
4. Enabling candidate time suggestion option
5. Selecting internal calendar (prefers "Global R&D Interviews" if multiple)
6. Sending the availability request

The workflow assumes you are already on the GoodTime dashboard (navigation and login
should be handled separately). It uses agent-based element finding to match templates
with candidate notes, showcasing how LLM-powered inference can be integrated into
automation workflows.

Prerequisites:
1. Set ANTHROPIC_API_KEY environment variable
2. Install Chrome/Chromium for Selenium WebDriver
3. Be logged into GoodTime and on the dashboard page

Usage:
    from create_goodtime_template_selection_graph import create_goodtime_template_selection_graph

    graph = create_goodtime_template_selection_graph(
        action_executor=action_executor,
        candidate_name="Katie Meringolo"
    )
    graph.execute()
"""

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

from typing import Optional, Union

from agent_foundation.automation.schema import ActionGraph, TargetSpec
from agent_foundation.automation.schema.action_metadata import ActionMetadataRegistry


def create_goodtime_template_selection_graph(
    action_executor,
    candidate_name: Optional[str] = None,
    wait: Optional[Union[float, bool]] = None,
):
    """
    Create an ActionGraph for GoodTime template selection based on candidate notes.

    This workflow assumes you are already on the GoodTime dashboard and:
    1. Clicks on the specified candidate (notes panel opens automatically)
    2. Clicks "Select Template" button
    3. Uses FindElementInferencer to find the best matching template based on notes
    4. Clicks the selected template
    5. Clicks "Continue" to proceed
    6. Selects appropriate email template
    7. Enables "Candidate suggest new times" checkbox (if not already enabled)
    8. Enables "Share itinerary with candidate" checkbox (if not already enabled)
    9. Selects internal calendar (prefers "Global R&D Interviews" if multiple)
    10. Clicks "Request Availability" to send the request

    Args:
        action_executor: The action executor (dict with 'default' WebDriver and
                        'find_element_agent' for LLM-based element finding)
        candidate_name: Name of the candidate to select. If None, selects the first
                        queued candidate on the dashboard. (default: None)
        wait: Wait after each action. float=seconds, True=human confirmation (default: None)

    Returns:
        ActionGraph configured for the template selection workflow
    """

    graph = ActionGraph(
        action_executor=action_executor,
        action_metadata=ActionMetadataRegistry()
    )

    # =========================================================================
    # Step 1: Select Candidate (assumes already on GoodTime dashboard)
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
    # Step 2: Template Selection Based on Notes
    # =========================================================================

    # Click "Select Template" button
    # Button structure: <button><span>Select Template</span></button>
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//button[.//span[text()='Select Template']]"
        ),
        wait=wait,
    )

    # NOTE: Notes panel is automatically opened when clicking on a candidate,
    # so no need to click the Notes button separately.
    # graph.action(
    #     "click",
    #     target=TargetSpec(
    #         strategy="xpath",
    #         value="//button[contains(@class, '_OpenFloatingNotesButton')]"
    #     ),
    #     wait=wait,
    # )

    # =========================================================================
    # Step 3: Use FindElementInferencer to Select Best Matching Template
    # =========================================================================

    # Use agent-based element finding to select best template
    # The find_element_agent will analyze the page and locate the template
    # that best matches the candidate notes visible in the ACTIVITY section
    #
    # Template structure in HTML:
    #   <div class="_avatar_twdin_6">S</div>
    #   <span>S/RS_UAT_Q4FY25_Backend Coding - Code Design P40</span>
    #   <button class="_moreIcon_1ju00_1833"></button>
    #
    # Notes contain: interview type (e.g., "Backend Coding - Code Design") and level (e.g., "P40")
    graph.action(
        "click",
        target=TargetSpec(
            strategy="agent",
            value="""Find the <span> element containing the request-availability template name that matches BOTH the interview type AND the level according to the notes in the ACTIVITY section.
The notes contain TWO key pieces of information to match:
1. Interview type (look for 'Select the Engineering interview types' - e.g., 'Backend Coding - Code Design')
2. Job level (look for 'Level of Job' - e.g., 'P40')

Templates are listed in the 'TEMPLATES' section as <span> elements with names like
'S/RS_UAT_Q4FY25_Backend Coding - Code Design P40'."""
        ),
        wait=wait,
    )

    # =========================================================================
    # Step 4: Confirm and Continue
    # =========================================================================

    # Click "Continue" or "Done" button to proceed with the selected template
    # Button structure: <button class="gui-btn gui-btn-primary ..."><span>Continue</span></button>
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//button[contains(@class, 'gui-btn-primary') and .//span[text()='Continue' or text()='Done']]"
        ),
        wait=wait,
    )

    # =========================================================================
    # Step 5: Select Email Template
    # =========================================================================

    # Click on email template dropdown to open selection
    # Structure: <div data-test="email-template-name" class="_clickable_...">
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//div[@data-test='email-template-name']"
        ),
        wait=wait,
    )

    # Select "GT QUEUES Request Availability - Candidate Schedule" template from dropdown
    # Structure: <div class="Select-option" role="option">GT QUEUES Request Availability...</div>
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//div[@role='option' and contains(., 'Request Availability')]"
        ),
        wait=False,
    )

    # =========================================================================
    # Step 6: Enable "Candidate Suggest New Times" (if not already enabled)
    # =========================================================================

    # Click the checkbox ONLY if not already checked
    # The label has class "_labelChecked" when checked, so we target the label
    # without that class. If checkbox is already checked, this XPath won't match
    # and the action will be skipped gracefully via no_action_if_target_not_found.
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
    # Step 6b: Enable "Share Itinerary with Candidate" (if not already enabled)
    # =========================================================================

    # Click the checkbox ONLY if not already checked
    # Same pattern as allow-candidate-suggest-times: label gets _labelChecked class when checked
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
    # Step 7: Select Internal Calendar
    # =========================================================================

    # Click on internal calendar dropdown to open selection
    # Structure: <div data-test="internal-calendar" class="_animatedDropdownContainer_...">
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//div[@data-test='internal-calendar']"
        ),
        wait=wait,
    )

    # Use agent to select the appropriate calendar from the dropdown
    # If only one calendar, select it; if multiple, prefer "Global R&D Interviews"
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
    # Step 8: Send Availability Request
    # =========================================================================

    # Click "Request Availability" button to send the request
    # Structure: <a class="_buttonTitle_yjkez_24"> Request Availability </a>
    graph.action(
        "click",
        target=TargetSpec(
            strategy="xpath",
            value="//a[contains(@class, '_buttonTitle_') and contains(normalize-space(), 'Request Availability')]"
        ),
        wait=wait,
    )

    return graph


# =========================================================================
# Standalone execution for testing
# =========================================================================

if __name__ == "__main__":
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    _logger = logging.getLogger(__name__)
    
    # Check for API key (needed for FindElementInferencer)
    if not os.environ.get('ANTHROPIC_API_KEY'):
        _logger.error("ANTHROPIC_API_KEY environment variable not set!")
        _logger.error("Please set it: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)
    
    from agent_foundation.common.inferencers.api_inferencers.ag.ag_claude_api_inferencer import AgClaudeApiInferencer as ClaudeApiInferencer
    from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
    from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_format
    
    from webaxon.automation.web_driver import WebDriver
    from webaxon.automation.agents import FindElementInferencer, FindElementInferenceConfig
    
    # Create WebDriver
    _logger.info("Initializing WebDriver...")
    webdriver = WebDriver(headless=False)
    
    # Create reasoner for LLM-based element finding
    _logger.info("Creating Claude API reasoner...")
    reasoner = ClaudeApiInferencer(
        max_retry=3,
        min_retry_wait=1.0,
        max_retry_wait=5.0,
    )
    
    # Create TemplateManager for prompt templates
    templates_path = os.path.join(project_root, "src", "webaxon", "automation", "agents", "prompt_templates")
    prompt_template_manager = TemplateManager(
        templates=templates_path,
        template_formatter=handlebars_format,
    )
    
    # Create FindElementInferencer
    find_element_inferencer = FindElementInferencer(
        base_inferencer=reasoner,
        template_manager=prompt_template_manager,
    )
    
    # Create wrapper for ActionGraph executor
    def find_element_agent(user_input: str, options=None, **_kwargs):
        """Wrapper that adapts ActionGraph call signature to FindElementInferencer."""
        return find_element_inferencer(
            html_source=webdriver,
            description=user_input,
            inference_config=FindElementInferenceConfig(
                inject_unique_index_to_elements=True,
                options=options,
            ),
        )
    
    # Build action executor
    action_executor = {
        'default': webdriver,
        'find_element_agent': find_element_agent,
    }

    # Navigate to GoodTime dashboard (manual setup step)
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

    # Create and execute the graph
    _logger.info("Creating ActionGraph...")
    graph = create_goodtime_template_selection_graph(
        action_executor=action_executor,
        candidate_name=None  # None = first queued, or specify name e.g. "Katie Meringolo"
    )

    _logger.info("Starting ActionGraph execution...")
    try:
        graph.execute()
    except KeyboardInterrupt:
        _logger.info("Execution stopped by user.")
    except Exception as e:
        _logger.error(f"Execution failed: {e}")
    finally:
        _logger.info("Closing browser...")
        webdriver.quit()
