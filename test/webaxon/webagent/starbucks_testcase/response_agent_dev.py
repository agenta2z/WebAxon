from functools import partial

from science_modeling_tools.agents.prompt_based_agents.prompt_based_action_agent import PromptBasedActionAgent
from science_modeling_tools.common.inferencers.api_inferencers.claude_api_inferencer import (
    ClaudeApiInferencer
)
from science_modeling_tools.ui.terminal_interactive import TerminalInteractive
from rich_python_utils.io_utils.json_io import write_json
from rich_python_utils.datetime_utils.common import timestamp
from webaxon.automation.web_driver import WebDriver
from rich_python_utils.string_utils.formatting.handlebars_format import format_template
from os import path

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

reasoner = ClaudeApiInferencer()
interactive = TerminalInteractive()
actor = WebDriver(headless=False)
logger = partial(write_json, file_path=path.join('.', '_logs', f'{timestamp()}.json'), append=True)

response_agent_prompt_template =  path.join('.', 'response_agent_prompt_template')
response_agent = PromptBasedActionAgent(
    default_prompt_template=response_agent_prompt_template,
    prompt_formatter=format_template,
    raw_response_start_delimiter=raw_response_start_delimiter,
    raw_response_end_delimiter=raw_response_end_delimiter,
    use_conversational_user_input=True,
    user_profile=user_profile,
    reasoner=reasoner,
    interactive=interactive,
    logger=logger
)

prompt_template = path.join('.', 'response_agent_prompt_template')
agent = PromptBasedActionAgent(
    default_prompt_template=prompt_template,
    prompt_formatter=format_template,
    raw_response_start_delimiter=raw_response_start_delimiter,
    raw_response_end_delimiter=raw_response_end_delimiter,
    response_field_task_status_description='PlannedActions',
    use_conversational_user_input=True,
    user_profile=user_profile,
    reasoner=reasoner,
    interactive=interactive,
    actor=actor,
    logger=logger
)

agent.start()
