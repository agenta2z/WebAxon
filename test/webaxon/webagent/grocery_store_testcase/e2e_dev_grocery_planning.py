from functools import partial
from os import path

from agent_foundation.agents.agent_response import AgentResponseFormat
from agent_foundation.agents.prompt_based_agents.prompt_based_action_agent import PromptBasedActionAgent
from agent_foundation.agents.prompt_based_agents.prompt_based_planning_agent import PromptBasedActionPlanningAgent
from agent_foundation.agents.prompt_based_agents.prompt_based_response_agent import PromptBasedResponseActionAgent
from agent_foundation.agents.prompt_based_agents.prompt_based_summary_agent import PromptBasedSummaryActionAgent
from agent_foundation.common.inferencers.agentic_inferencers.common import ReflectionStyles, ResponseSelectors
from agent_foundation.common.inferencers.agentic_inferencers.reflective_inferencer import ReflectiveInferencer
from agent_foundation.ui.terminal_interactive import TerminalInteractive
from rich_python_utils.io_utils.json_io import write_json
from rich_python_utils.string_utils.formatting.common import KeyValueStringFormat
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
from rich_python_utils.datetime_utils.common import timestamp
from webaxon.automation.web_agent_actors.webpage_make_answer_actor import WebPageMakeAnswerActor, \
    ACTION_TYPE_WEBPAGE_MAKE_ANSWER
from webaxon.automation.web_driver import WebDriver

from agent_foundation.knowledge import KnowledgeBase, KnowledgeDataLoader, KnowledgeProvider
from agent_foundation.knowledge.stores.metadata.keyvalue_adapter import KeyValueMetadataStore
from agent_foundation.knowledge.stores.pieces.retrieval_adapter import RetrievalKnowledgePieceStore
from agent_foundation.knowledge.stores.graph.graph_adapter import GraphServiceEntityGraphStore
from rich_python_utils.service_utils.keyvalue_service.memory_keyvalue_service import MemoryKeyValueService
from rich_python_utils.service_utils.retrieval_service.memory_retrieval_service import MemoryRetrievalService
from rich_python_utils.service_utils.graph_service.memory_graph_service import MemoryGraphService

# Create KnowledgeProvider from knowledge data file
_knowledge_data_file = path.join(path.dirname(__file__), 'knowledge_data.json')
_kb = KnowledgeBase(
    metadata_store=KeyValueMetadataStore(kv_service=MemoryKeyValueService()),
    piece_store=RetrievalKnowledgePieceStore(retrieval_service=MemoryRetrievalService()),
    graph_store=GraphServiceEntityGraphStore(graph_service=MemoryGraphService()),
    active_entity_id="user:[name]"
)
KnowledgeDataLoader.load(_kb, _knowledge_data_file)
knowledge_provider = KnowledgeProvider(_kb)

raw_response_start_delimiter = '<StructuredResponse>'
raw_response_end_delimiter = '</StructuredResponse>'
raw_response_format = AgentResponseFormat.XML

debug_mode = True
always_add_logging_based_logger = False
logger = partial(write_json, file_path=path.join('.', '_logs', f'{timestamp()}.json'), append=True)

prompt_template_manager = TemplateManager(
    templates=path.join('.', 'prompt_templates'),
    template_formatter=handlebars_template_format
)
anchor_action_types = {'Search', 'ElementInteraction.BrowseLink'}

from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import (
    ClaudeApiInferencer
)
reasoner = ClaudeApiInferencer(
    max_retry=3,
    default_inference_args={'connect_timeout': 20, 'response_timeout': 120},
    logger=logger,
    debug_mode=debug_mode
)

# from agent_foundation.common.inferencers.http_request_inferencer import HttpRequestInferencer
#
# reasoner = HttpRequestInferencer(
#     service_url='http://devvm20179.nha0.facebook.com:8087/generate',
#     request_body_prompt_field_name='prompt_or_messages',
#     model_id='claude-4-sonnet-genai',
#     secret_key='mg-api-466441a8622f',
#     max_retry=3,
#     logger=logger,
#     debug_mode=debug_mode
# )

print(reasoner('Hello!'))

reflective_reasoner = ReflectiveInferencer(
    base_inferencer=reasoner,
    max_retry=1,
    reflection_inferencer=reasoner,
    reflection_prompt_formatter=prompt_template_manager.switch(active_template_type='reflection'),
    num_reflections=1,
    reflection_style=ReflectionStyles.Sequential,
    response_selector=ResponseSelectors.LastReflection,
    logger=logger,
    always_add_logging_based_logger=always_add_logging_based_logger,
    debug_mode=debug_mode
)

interactive = TerminalInteractive()

response_agent = PromptBasedResponseActionAgent(
    prompt_formatter=prompt_template_manager.switch(active_template_root_space='response_agent'),
    raw_response_start_delimiter=raw_response_start_delimiter,
    raw_response_end_delimiter=raw_response_end_delimiter,
    raw_response_format=raw_response_format,
    raw_response_parsing_args={'exclude_paths': ['InstantResponse.Response.Answer']},
    use_conversational_user_input=True,
    input_string_formatter=KeyValueStringFormat.XML,
    response_string_formatter=KeyValueStringFormat.XML,
    user_profile=None,
    knowledge_provider=knowledge_provider,
    reasoner=reasoner,
    interactive=interactive,
    logger=logger,
    always_add_logging_based_logger=True,
    debug_mode=debug_mode,
    only_keep_parent_debuggable_ids=True
)
summary_agent = PromptBasedSummaryActionAgent(
    prompt_formatter=prompt_template_manager.switch(active_template_root_space='response_agent'),
    raw_response_start_delimiter=raw_response_start_delimiter,
    raw_response_end_delimiter=raw_response_end_delimiter,
    raw_response_format=raw_response_format,
    use_conversational_user_input=True,
    input_string_formatter=KeyValueStringFormat.XML,
    response_string_formatter=KeyValueStringFormat.XML,
    user_profile=None,
    knowledge_provider=knowledge_provider,
    reasoner=reasoner,
    interactive=interactive,
    logger=logger,
    always_add_logging_based_logger=True,
    debug_mode=debug_mode,
    only_keep_parent_debuggable_ids=True
)

webdriver_actor = WebDriver(headless=False)
master_action_agent = PromptBasedActionAgent(
    prompt_formatter=prompt_template_manager.switch(active_template_root_space='action_agent'),
    anchor_action_types=anchor_action_types,
    raw_response_start_delimiter=raw_response_start_delimiter,
    raw_response_end_delimiter=raw_response_end_delimiter,
    raw_response_format=raw_response_format,
    response_field_task_status_description='PlannedActions',
    use_conversational_user_input=True,
    input_string_formatter=KeyValueStringFormat.XML,
    response_string_formatter=KeyValueStringFormat.XML,
    user_profile=None,
    knowledge_provider=knowledge_provider,
    reasoner=reflective_reasoner,
    interactive=interactive,
    actor={
        'default': webdriver_actor,
        ACTION_TYPE_WEBPAGE_MAKE_ANSWER: WebPageMakeAnswerActor(actor=response_agent)
    },
    summarizer=summary_agent,
    logger=logger,
    always_add_logging_based_logger=always_add_logging_based_logger,
    debug_mode=debug_mode,
    only_keep_parent_debuggable_ids=True
)

planning_agent = PromptBasedActionPlanningAgent(
    prompt_formatter=prompt_template_manager.switch(active_template_root_space='planning_agent'),
    direct_response_start_delimiter='<DirectResponse>',
    direct_response_end_delimiter='</DirectResponse>',
    raw_response_start_delimiter=raw_response_start_delimiter,
    raw_response_end_delimiter=raw_response_end_delimiter,
    raw_response_format=raw_response_format,
    use_conversational_user_input=True,
    input_string_formatter=KeyValueStringFormat.XML,
    response_string_formatter=KeyValueStringFormat.XML,
    user_profile=None,
    knowledge_provider=knowledge_provider,
    reasoner=reflective_reasoner,
    interactive=interactive,
    actor=master_action_agent,
    actor_args_transformation={
        'Request': 'user_input',
        'SolutionRequirement': 'task_requirement'
    },
    logger=logger,
    always_add_logging_based_logger=always_add_logging_based_logger,
    debug_mode=debug_mode,
    only_keep_parent_debuggable_ids=True
)

planning_agent({
    'user_input': \
        'purchase grocery pasta, pasta sauce, garlic bread in order to make pasta'
})
