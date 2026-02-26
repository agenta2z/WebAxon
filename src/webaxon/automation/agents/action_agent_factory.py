"""
Default action agent factory for quick setup.

Provides create_action_agent() with bundled default templates for convenient
web automation agent creation without extensive configuration.

Example:
    >>> from webaxon.automation.agents import create_action_agent
    >>> from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
    >>> from webaxon.automation.web_driver import WebDriver
    >>>
    >>> webdriver = WebDriver()
    >>> reasoner = ClaudeApiInferencer(max_retry=3)
    >>> agent = create_action_agent(webdriver=webdriver, reasoner=reasoner)
    >>> result = agent(user_input="Search for Python tutorials")
"""
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Set

from science_modeling_tools.agents.agent_response import AgentResponseFormat
from science_modeling_tools.agents.prompt_based_agents.prompt_based_action_agent import PromptBasedActionAgent
from science_modeling_tools.common.inferencers.inferencer_base import InferencerBase
from rich_python_utils.string_utils.formatting.common import KeyValueStringFormat
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_format
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager

if TYPE_CHECKING:
    from webaxon.automation.web_driver import WebDriver

# Default templates location (bundled with package)
_DEFAULT_TEMPLATES_PATH = Path(__file__).parent / "prompt_templates"

# Default configuration (matching web_agent_service.py patterns)
DEFAULT_RAW_RESPONSE_START_DELIMITER = '<StructuredResponse>'
DEFAULT_RAW_RESPONSE_END_DELIMITER = '</StructuredResponse>'
DEFAULT_RAW_RESPONSE_FORMAT = AgentResponseFormat.XML
DEFAULT_ANCHOR_ACTION_TYPES = {'Search', 'ElementInteraction.BrowseLink'}


def create_action_agent(
    webdriver: "WebDriver",
    reasoner: InferencerBase,
    template_manager: Optional[TemplateManager] = None,
    interactive: Optional[Any] = None,
    logger: Optional[Callable] = None,
    anchor_action_types: Optional[Set[str]] = None,
    debug_mode: bool = True,
    **kwargs
) -> PromptBasedActionAgent:
    """
    Create a PromptBasedActionAgent with sensible defaults.

    Provides a quick way to create an action agent for web automation
    tasks without extensive configuration. Uses bundled default templates.

    Args:
        webdriver: WebDriver instance for web actions
        reasoner: Inferencer for LLM calls (e.g., ClaudeApiInferencer)
        template_manager: Optional custom TemplateManager. If None, uses
                          bundled default templates.
        interactive: Optional interactive handler. If None, agent runs in
                     non-interactive mode (suitable for ActionGraph execution).
        logger: Optional logger function
        anchor_action_types: Action types that anchor state (default: Search, BrowseLink)
        debug_mode: Enable debug mode (default: True)
        **kwargs: Additional kwargs passed to PromptBasedActionAgent

    Returns:
        Configured PromptBasedActionAgent

    Example:
        >>> from webaxon.automation.agents import create_action_agent
        >>> from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
        >>>
        >>> agent = create_action_agent(
        ...     webdriver=WebDriver(),
        ...     reasoner=ClaudeApiInferencer(max_retry=3),
        ... )
        >>> result = agent(user_input="Search for Python tutorials")
    """
    # Use default template manager if not provided
    if template_manager is None:
        template_manager = TemplateManager(
            templates=str(_DEFAULT_TEMPLATES_PATH),
            template_formatter=handlebars_format,
        )

    # Use default anchor action types if not provided
    if anchor_action_types is None:
        anchor_action_types = DEFAULT_ANCHOR_ACTION_TYPES

    return PromptBasedActionAgent(
        prompt_formatter=template_manager.switch(active_template_root_space='action_agent'),
        anchor_action_types=anchor_action_types,
        raw_response_start_delimiter=DEFAULT_RAW_RESPONSE_START_DELIMITER,
        raw_response_end_delimiter=DEFAULT_RAW_RESPONSE_END_DELIMITER,
        raw_response_format=DEFAULT_RAW_RESPONSE_FORMAT,
        response_field_task_status_description='PlannedActions',
        use_conversational_user_input=True,
        input_string_formatter=KeyValueStringFormat.XML,
        response_string_formatter=KeyValueStringFormat.XML,
        reasoner=reasoner,
        interactive=interactive,
        actor={'default': webdriver},
        logger=logger,
        debug_mode=debug_mode,
        **kwargs
    )
