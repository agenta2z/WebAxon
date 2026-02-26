from functools import partial
from os import path

from science_modeling_tools.agents.agent_response import AgentResponseFormat
from science_modeling_tools.agents.prompt_based_agents.prompt_based_action_agent import PromptBasedActionAgent
from science_modeling_tools.agents.prompt_based_agents.prompt_based_response_agent import PromptBasedResponseActionAgent
from science_modeling_tools.common.inferencers.agentic_inferencers.common import ReflectionStyles, ResponseSelectors
from science_modeling_tools.common.inferencers.agentic_inferencers.reflective_inferencer import ReflectiveInferencer
from science_modeling_tools.common.inferencers.api_inferencers.claude_api_inferencer import (
    ClaudeApiInferencer
)
from science_modeling_tools.ui.terminal_interactive import TerminalInteractive
from rich_python_utils.io_utils.json_io import write_json
from rich_python_utils.string_utils.formatting.common import KeyValueStringFormat
from rich_python_utils.string_utils.formatting.handlebars_format import format_template
from rich_python_utils.datetime_utils.common import timestamp
from webaxon.automation.web_agent_actors.constants import DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_TASK_REQUIREMENT
from webaxon.automation.web_agent_actors.webpage_make_answer_actor import WebPageMakeAnswerActor, \
    ACTION_TYPE_WEBPAGE_MAKE_ANSWER
from webaxon.automation.web_driver import WebDriver

user_profile = {
    'Name': {
        'FirstName': 'Emma',
        'LastName': 'Chen'
    },
    'PhoneNumber': '215-925-9368',
    'Location': 'Seattle, Washington, USA',
    'ZipCode': '98121'
}

raw_response_start_delimiter = '<StructuredResponse>'
raw_response_end_delimiter = '</StructuredResponse>'
raw_response_format = AgentResponseFormat.XML

debug_mode = True
logger = partial(write_json, file_path=path.join('.', '_logs', f'{timestamp()}.json'), append=True)
reasoner = ClaudeApiInferencer(
    max_retry=3,
    default_inference_args={'connect_timeout': 20, 'response_timeout': 120},
    logger=logger,
    debug_mode=debug_mode
)

reflective_reasoner = ReflectiveInferencer(
    base_inferencer=reasoner,
    max_retry=1,
    reflection_inferencer=reasoner,
    reflection_prompt_formatter=format_template,
    num_reflections=1,
    reflection_style=ReflectionStyles.Sequential,
    response_selector=ResponseSelectors.LastReflection,
    logger=logger,
    debug_mode=debug_mode
)

interactive = TerminalInteractive()

response_agent_prompt_template = path.join('.', 'response_agent_prompt_template')
response_agent = PromptBasedResponseActionAgent(
    default_prompt_template=response_agent_prompt_template,
    prompt_formatter=format_template,
    raw_response_start_delimiter=raw_response_start_delimiter,
    raw_response_end_delimiter=raw_response_end_delimiter,
    raw_response_format=raw_response_format,
    raw_response_parsing_args={'exclude_paths': ['InstantResponse.Response.Answer']},
    use_conversational_user_input=True,
    input_string_formatter=KeyValueStringFormat.XML,
    response_string_formatter=KeyValueStringFormat.XML,
    user_profile=user_profile,
    reasoner=reasoner,
    interactive=interactive,
    logger=logger,
    debug_mode=debug_mode
)

action_agent_prompt_template = path.join('.', 'action_agent_prompt_template')
webdriver_actor = WebDriver(headless=False)
master_action_agent = PromptBasedActionAgent(
    default_prompt_template=action_agent_prompt_template,
    prompt_formatter=format_template,
    raw_response_start_delimiter=raw_response_start_delimiter,
    raw_response_end_delimiter=raw_response_end_delimiter,
    raw_response_format=raw_response_format,
    response_field_task_status_description='PlannedActions',
    use_conversational_user_input=True,
    input_string_formatter=KeyValueStringFormat.XML,
    response_string_formatter=KeyValueStringFormat.XML,
    user_profile=user_profile,
    reasoner=reflective_reasoner,
    interactive=interactive,
    actor={
        'default': webdriver_actor,
        ACTION_TYPE_WEBPAGE_MAKE_ANSWER: WebPageMakeAnswerActor(actor=response_agent)
    },
    logger=logger,
    debug_mode=debug_mode
)

master_action_agent(
    {
        DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_TASK_REQUIREMENT:  # 'task_requirement'
            'Specific and exact customization instructions needed for ordering, including exact ingredients, quantities, and modifications',

        'user_input': """Place online order through Starbucks app/website for the selected customized drink

You can use these exact ordering instructions at your local Seattle Starbucks:
    Ask for a Sweet Cream Cold Brew as your base
    Request these specific modifications:
        2 pumps of vanilla syrup
        4 pumps of mocha syrup in the drink
        2 pumps of mocha syrup in the foam
        Cookie crumble topping"""
    }
)
