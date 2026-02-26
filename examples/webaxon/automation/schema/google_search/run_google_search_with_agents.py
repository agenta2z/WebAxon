"""
Runner script for Google Search ActionGraph with PromptBasedActionAgent.

This script demonstrates how to set up and execute the Google search example
using PromptBasedActionAgent for task execution (same infrastructure as web_agent_service.py).

Components:
- FindElementInferencer: One-inference agent for LLM-based element finding (extends TemplatedInferencer)
- create_action_agent: Factory function for creating action agents with default templates

Prerequisites:
1. Set ANTHROPIC_API_KEY environment variable
2. Install Chrome/Chromium for Selenium WebDriver

Usage:
    python run_google_search_with_agents.py

The script will:
1. Open Chrome browser
2. Navigate to Google
3. Monitor the search input for value changes
4. When value changes, execute the search task using PromptBasedActionAgent
"""

import logging
import os
import sys

# Add parent directories to path for local imports
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from science_modeling_tools.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_format

from webaxon.automation.web_driver import WebDriver
from webaxon.automation.agents import FindElementInferencer, FindElementInferenceConfig, create_action_agent

from create_google_search_action_graph_with_monitor_and_agent import create_google_search_action_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_logger = logging.getLogger(__name__)


def main():
    """Run the Google search ActionGraph with PromptBasedActionAgent."""

    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        _logger.error("ANTHROPIC_API_KEY environment variable not set!")
        _logger.error("Please set it: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    # 1. Create WebDriver
    _logger.info("Initializing WebDriver...")
    webdriver = WebDriver(
        headless=False,  # Show browser for demonstration
    )

    # 2. Create reasoner (shared by action agent)
    _logger.info("Creating Claude API reasoner...")
    reasoner = ClaudeApiInferencer(
        max_retry=3,
        min_retry_wait=1.0,
        max_retry_wait=5.0,
    )

    # 3. Create TemplateManager for action_agent templates
    templates_path = os.path.join(script_dir, "prompt_templates")
    _logger.info(f"Loading prompt templates from: {templates_path}")

    prompt_template_manager = TemplateManager(
        templates=templates_path,
        template_formatter=handlebars_format,
    )

    # 4. Create agents
    _logger.info("Creating agents...")

    # Find element inferencer (extends TemplatedInferencer)
    # Note: webdriver is passed at call time, not construction time
    find_element_inferencer = FindElementInferencer(
        base_inferencer=reasoner,
        template_manager=prompt_template_manager,
    )

    # Create wrapper that captures webdriver for ActionGraph executor
    # ActionGraph calls: find_element_agent(user_input="...", options=['static'])
    # FindElementInferencer expects: inferencer(html_source, description="...", inference_config=...)
    def find_element_agent(user_input: str, options=None, **kwargs):
        """Wrapper that adapts ActionGraph call signature to FindElementInferencer."""
        return find_element_inferencer(
            html_source=webdriver,
            description=user_input,
            inference_config=FindElementInferenceConfig(
                inject_unique_index_to_elements=True,  # Inject __id__ into live DOM
                options=options,
            ),
            **kwargs
        )

    # Action agent using the new factory from webaxon.automation.agents
    # Uses bundled default templates, or custom template_manager if provided
    action_agent = create_action_agent(
        webdriver=webdriver,
        reasoner=reasoner,
        template_manager=prompt_template_manager,  # Optional: omit to use bundled defaults
    )

    # 5. Build action executor with both agents registered
    # 'default' → webdriver handles standard actions (click, input, etc.)
    # 'find_element_agent' → called when TargetSpec strategy="agent"
    # 'agent' → called for action type="agent"
    action_executor = {
        'default': webdriver,
        'find_element_agent': find_element_agent,
        'agent': action_agent,
    }

    # 6. Create ActionGraph with configured executor
    _logger.info("Creating ActionGraph...")
    graph = create_google_search_action_graph(
        action_executor=action_executor,
        search_query="anthropic claude AI"
    )

    # 7. Execute the graph
    _logger.info("Starting ActionGraph execution...")
    _logger.info("The monitor will wait for you to type in the search box.")
    _logger.info("After value changes and stabilizes (5 seconds), it will execute the search.")
    _logger.info("Press Ctrl+C to stop the continuous monitoring loop.")

    try:
        graph.execute()
    except KeyboardInterrupt:
        _logger.info("Execution stopped by user.")
    finally:
        _logger.info("Closing browser...")
        webdriver.quit()


if __name__ == "__main__":
    main()
