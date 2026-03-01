"""
Web Agent Service - Queue-Based Agent Execution Service

This service runs the grocery planning agent and communicates through
shared on-storage queues. It waits for user input from the input queue,
executes the agent, and puts responses on the response queue.

Architecture:
- Uses StorageBasedQueueService for persistent, multiprocess queues
- Wraps queue service with QueueInteractive for agent integration
- Runs as a standalone service waiting for requests
- Logs all execution to JSON files for debugging

Queue Communication:
- Input Queue: 'user_input' - receives user messages
- Response Queue: 'agent_response' - sends agent responses
- Log Queue: 'agent_logs' - sends log file paths

Usage:
    python web_agent_service.py

    The service will:
    1. Initialize the grocery planning agent
    2. Wait for messages on the 'user_input' queue
    3. Execute the agent for each message
    4. Put responses on the 'agent_response' queue
    5. Put log paths on the 'agent_logs' queue
"""
import copy
from functools import partial
from os import path
from pathlib import Path
from dataclasses import dataclass
from typing import Callable
import time
import threading

from agent_foundation.agents.prompt_based_agents.prompt_based_agent import DEFAULT_AGENT_TURN_IDENTIFYING_STRING
from rich_python_utils.common_objects.debuggable import Debugger
from agent_foundation.agents.agent_response import AgentResponseFormat
from agent_foundation.agents.prompt_based_agents.prompt_based_action_agent import PromptBasedActionAgent
from agent_foundation.agents.prompt_based_agents.prompt_based_planning_agent import PromptBasedActionPlanningAgent
from agent_foundation.agents.prompt_based_agents.prompt_based_response_agent import PromptBasedResponseActionAgent
from agent_foundation.agents.prompt_based_agents.prompt_based_summary_agent import PromptBasedSummaryActionAgent
from agent_foundation.common.inferencers.agentic_inferencers.common import ReflectionStyles, ResponseSelectors
from agent_foundation.common.inferencers.agentic_inferencers.reflective_inferencer import ReflectiveInferencer
from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
from agent_foundation.common.inferencers.mock_inferencers import MockClarificationInferencer
from agent_foundation.ui.queue_interactive import QueueInteractive
from rich_python_utils.io_utils.json_io import write_json
from rich_python_utils.string_utils.formatting.common import KeyValueStringFormat
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
from rich_python_utils.datetime_utils.common import timestamp
from rich_python_utils.service_utils.queue_service.storage_based_queue_service import StorageBasedQueueService
from rich_python_utils.console_utils import hprint_message
from webaxon.devsuite.config import OPTION_BASE_REASONER, OPTION_DEFAULT_PROMPT_VERSION, MOCK_USER_PROFILE, \
    DEFAULT_AGENT_REASONER_ARGS, RESPONSE_AGENT_REASONER_ARGS
from webaxon.automation.web_agent_actors.common import WebActor
from webaxon.automation.web_agent_actors.constants import ACTION_TYPE_INFO_ASK_QUESTION
from webaxon.automation.web_agent_actors.webpage_make_answer_actor import WebPageMakeAnswerActor, \
    ACTION_TYPE_WEBPAGE_MAKE_ANSWER
from webaxon.automation.web_driver import WebDriver

try:
    from agent_foundation.common.inferencers.api_inferencers.ag.ag_claude_api_inferencer import \
        AgClaudeApiInferencer
except ImportError:
    pass

# Import web agent framework utilities from devsuite
from webaxon.devsuite import (
    INPUT_QUEUE_ID,
    RESPONSE_QUEUE_ID,
    CLIENT_CONTROL_QUEUE_ID,
    SERVER_CONTROL_QUEUE_ID,
    AGENT_TYPE_DEFAULT,
    AGENT_TYPE_MOCK_CLARIFICATION,
    OPTION_NEW_AGENT_ON_FIRST_SUBMISSION,
    get_queue_base_path,
    get_log_dir_path
)
from rich_python_utils.service_utils.session_management import SessionInfo
from webaxon.devsuite.common import DebuggerLogTypes
from webaxon.devsuite.config import DEBUG_MODE_SERVICE, DEBUG_MODE_SYNCHRONOUS_AGENT
from webaxon.devsuite.constants import RUNTIME_DIR, FOLDER_NAME_SERVICE_LOGS

# User profile
user_profile = MOCK_USER_PROFILE.get(OPTION_DEFAULT_PROMPT_VERSION, MOCK_USER_PROFILE['default'])

# Agent configuration
raw_response_start_delimiter = '<StructuredResponse>'
raw_response_end_delimiter = '</StructuredResponse>'
raw_response_format = AgentResponseFormat.XML
debug_mode = True
always_add_logging_based_logger = False

# Prompt templates
prompt_template_manager = TemplateManager(
    templates=path.join('.', 'prompt_templates'),
    template_formatter=handlebars_template_format,
    template_version=OPTION_DEFAULT_PROMPT_VERSION
)
anchor_action_types = {'Search', 'ElementInteraction.BrowseLink'}

# Session management configuration
SESSION_IDLE_TIMEOUT = 30 * 60  # 30 minutes in seconds
CLEANUP_CHECK_INTERVAL = 5 * 60  # Check every 5 minutes

# Global debugger for module-level events (will be initialized in run_agent_service())
_global_debugger = None


def _get_or_create_global_debugger(testcase_root: Path = None):
    """Get or create the global debugger for service-level events."""
    global _global_debugger
    if _global_debugger is None:
        # Use project root to create global debugger log directory
        if testcase_root is None:
            testcase_root = Path(__file__).parent
        service_log_dir = testcase_root / RUNTIME_DIR / FOLDER_NAME_SERVICE_LOGS / 'global'
        service_log_dir.mkdir(parents=True, exist_ok=True)

        _global_debugger = Debugger(
            id='web_agent_service_global',
            log_name='WebAgentService',
            logger=[
                print,  # Console output
                partial(write_json, file_path=str(service_log_dir / FOLDER_NAME_SERVICE_LOGS), append=True)
            ],
            debug_mode=DEBUG_MODE_SERVICE,
            log_time=True,
            always_add_logging_based_logger=False
        )
    return _global_debugger


@dataclass
class AgentSessionInfo(SessionInfo):
    """Information about an agent session (service-side).

    Agent is created lazily on first message to allow agent type changes before activation.

    Extends SessionInfo with service-specific fields for agent execution and lifecycle.
    """
    logger: Callable = None
    log_dir_path: Path = None
    interactive: QueueInteractive = None
    agent: PromptBasedActionPlanningAgent = None  # Created on first message (lazy init)
    agent_thread: threading.Thread = None  # Started on first message
    last_agent_status: str = None  # Last known agent status for change detection
    debugger: Debugger = None  # Session-specific debugger for logging


def create_agent(interactive, logger, agent_type=AGENT_TYPE_DEFAULT):
    """
    Create and configure the grocery planning agent.

    Args:
        interactive: Interactive instance for user communication
        logger: Logger function for execution logs
        agent_type: Type of agent to create (AGENT_TYPE_DEFAULT or AGENT_TYPE_MOCK_CLARIFICATION)

    Returns:
        Configured planning agent
    """
    # Create inferencer using the factory function
    if agent_type == AGENT_TYPE_MOCK_CLARIFICATION:
        mock_reasoner = MockClarificationInferencer()
        root_agent = PromptBasedActionAgent(
            prompt_formatter=prompt_template_manager.switch(active_template_root_space='action_agent'),
            anchor_action_types=anchor_action_types,
            raw_response_start_delimiter=raw_response_start_delimiter,
            raw_response_end_delimiter=raw_response_end_delimiter,
            raw_response_format=raw_response_format,
            response_field_task_status_description='PlannedActions',
            use_conversational_user_input=True,
            input_string_formatter=KeyValueStringFormat.XML,
            response_string_formatter=KeyValueStringFormat.XML,
            user_profile=user_profile,
            reasoner=mock_reasoner,
            interactive=interactive,
            actor={},
            logger=logger,
            always_add_logging_based_logger=always_add_logging_based_logger,
            debug_mode=debug_mode,
            only_keep_parent_debuggable_ids=True
        )
    else:
        if OPTION_BASE_REASONER == 'AgClaude':
            reasoner = AgClaudeApiInferencer(
                max_retry=3,
                default_inference_args=DEFAULT_AGENT_REASONER_ARGS,
                logger=logger,
                debug_mode=debug_mode
            )
        else:
            reasoner = ClaudeApiInferencer(
                max_retry=3,
                default_inference_args=DEFAULT_AGENT_REASONER_ARGS,
                logger=logger,
                debug_mode=debug_mode
            )

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

        response_agent = PromptBasedResponseActionAgent(
            prompt_formatter=prompt_template_manager.switch(active_template_root_space='response_agent'),
            raw_response_start_delimiter=raw_response_start_delimiter,
            raw_response_end_delimiter=raw_response_end_delimiter,
            raw_response_format=raw_response_format,
            raw_response_parsing_args={'exclude_paths': ['InstantResponse.Response.Answer']},
            use_conversational_user_input=True,
            input_string_formatter=KeyValueStringFormat.XML,
            response_string_formatter=KeyValueStringFormat.XML,
            user_profile=user_profile,
            reasoner=reasoner,
            reasoner_args=RESPONSE_AGENT_REASONER_ARGS,
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
            user_profile=user_profile,
            reasoner=reasoner,
            interactive=interactive,
            logger=logger,
            always_add_logging_based_logger=True,
            debug_mode=debug_mode,
            only_keep_parent_debuggable_ids=True
        )

        webdriver_actor = WebDriver(headless=False)

        info_ask_question_actor = WebActor(
            actor=PromptBasedActionAgent(
                prompt_formatter=prompt_template_manager.switch(
                    active_template_root_space='action_agent',
                    default_template_name=ACTION_TYPE_INFO_ASK_QUESTION
                ),
                anchor_action_types=anchor_action_types,
                raw_response_start_delimiter=raw_response_start_delimiter,
                raw_response_end_delimiter=raw_response_end_delimiter,
                raw_response_format=raw_response_format,
                response_field_task_status_description='PlannedActions',
                use_conversational_user_input=True,
                input_string_formatter=KeyValueStringFormat.XML,
                response_string_formatter=KeyValueStringFormat.XML,
                user_profile=user_profile,
                reasoner=reasoner,
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
            ),
            target_action_type=ACTION_TYPE_INFO_ASK_QUESTION,
            init_url='https://home.atlassian.com/chat'
        )

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
            user_profile=user_profile,
            reasoner=reasoner,
            interactive=interactive,
            actor={
                'default': webdriver_actor,
                ACTION_TYPE_WEBPAGE_MAKE_ANSWER: WebPageMakeAnswerActor(actor=response_agent),
                ACTION_TYPE_INFO_ASK_QUESTION: info_ask_question_actor
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
            user_profile=user_profile,
            reasoner=reasoner,
            interactive=interactive,
            actor=master_action_agent,
            actor_args_transformation={
                'Request': 'user_input',
                'SolutionRequirement': 'task_requirement',
                'ProblemID': 'task_label'
            },
            logger=logger,
            always_add_logging_based_logger=always_add_logging_based_logger,
            debug_mode=debug_mode,
            only_keep_parent_debuggable_ids=True,
            ensure_consistent_session_metadata_fields=['session_id']  # Ensure session_id stays consistent
        )

        root_agent = planning_agent

    return root_agent


def get_or_create_agent(session_id: str, queue_service, service_log_dir: Path, agents_by_session: dict,
                        agent_type: str = AGENT_TYPE_DEFAULT, create_immediately: bool = False) -> AgentSessionInfo:
    """
    Get existing agent for session or create a new one.

    Args:
        session_id: Session identifier
        queue_service: Queue service instance
        service_log_dir: Root directory for service logs
        agents_by_session: Dictionary tracking all agent sessions
        agent_type: Type of agent to create (AGENT_TYPE_DEFAULT or AGENT_TYPE_MOCK_CLARIFICATION)
        create_immediately: If True, create and start agent immediately. If False, lazy init on first message.

    Returns:
        AgentSessionInfo for the session
    """
    if session_id in agents_by_session:
        # Update last active time
        session_info = agents_by_session[session_id]
        session_info.last_active = time.time()
        session_info.debugger.log_info({
            'action': 'using_existing_session',
            'session_id': session_id
        }, DebuggerLogTypes.SESSION_MANAGEMENT)
        return session_info

    # Create new session (agent created immediately or lazily based on create_immediately flag)
    creation_mode = "immediate" if create_immediately else "lazy init"
    global_debugger = _get_or_create_global_debugger()
    global_debugger.log_info({
        'action': 'creating_new_session',
        'session_id': session_id,
        'agent_type': agent_type,
        'creation_mode': creation_mode
    }, DebuggerLogTypes.SESSION_MANAGEMENT)

    # Create session-specific log directory
    session_log_dir = service_log_dir / session_id
    session_log_dir.mkdir(parents=True, exist_ok=True)

    # Create session-specific debugger log directory (separate from agent logs)
    testcase_root = Path(__file__).parent
    session_debugger_log_dir = testcase_root / RUNTIME_DIR / FOLDER_NAME_SERVICE_LOGS / session_id
    session_debugger_log_dir.mkdir(parents=True, exist_ok=True)

    # Create session-specific debugger for service logging
    session_debugger = Debugger(
        id=f'service_{session_id}',
        log_name=f'WebAgentService_{session_id}',
        logger=[
            print,  # Console output
            partial(write_json, file_path=str(session_debugger_log_dir / FOLDER_NAME_SERVICE_LOGS), append=True)
        ],
        debug_mode=DEBUG_MODE_SERVICE,
        log_time=True,
        always_add_logging_based_logger=False
    )

    # Create session-specific logger (for agents)
    logger = partial(write_json, file_path=session_log_dir, append=True)

    # Create session-specific input queue ID to prevent cross-session message pollution
    # Each session gets its own input queue (e.g., 'user_input_session_1_20251110103004')
    session_input_queue_id = f"{INPUT_QUEUE_ID}_{session_id}"

    # Create the session-specific input queue if it doesn't exist yet
    # create_queue() returns False if queue already exists, True if created
    if queue_service.create_queue(session_input_queue_id):
        session_debugger.log_info({
            'action': 'created_input_queue',
            'queue_id': session_input_queue_id
        }, DebuggerLogTypes.QUEUE_OPERATION)
    else:
        session_debugger.log_info({
            'action': 'reusing_input_queue',
            'queue_id': session_input_queue_id
        }, DebuggerLogTypes.QUEUE_OPERATION)

    # Create session-specific QueueInteractive
    # Each session uses its own input queue but shares the response queue
    interactive = QueueInteractive(
        system_name="GroceryAgent",
        user_name="User",
        input_queue=queue_service,
        response_queue=queue_service,
        input_queue_id=session_input_queue_id,  # Session-specific input queue
        response_queue_id=RESPONSE_QUEUE_ID,  # Shared response queue
        blocking=True,
        timeout=None
    )

    # Store session info WITHOUT creating agent yet (lazy initialization)
    current_time = time.time()
    session_info = AgentSessionInfo(
        session_id=session_id,
        created_at=current_time,
        last_active=current_time,
        session_type=agent_type,
        initialized=False,  # Not created yet
        logger=logger,
        log_dir_path=session_log_dir,
        interactive=interactive,
        agent=None,  # Will be created on first message
        agent_thread=None,  # Will be started on first message
        debugger=session_debugger  # Session-specific debugger
    )

    agents_by_session[session_id] = session_info

    # Send log path immediately so UI can track logs for this session
    # Use standardized message format
    log_path_message = {
        "type": "log_path_available",
        "message": {
            "log_path": str(session_log_dir)
        },
        "timestamp": timestamp()
    }
    queue_service.put(CLIENT_CONTROL_QUEUE_ID, log_path_message)
    session_debugger.log_info({
        'action': 'log_path_sent',
        'queue': CLIENT_CONTROL_QUEUE_ID,
        'log_dir': str(session_log_dir)
    }, DebuggerLogTypes.QUEUE_OPERATION)

    # Create agent immediately if requested
    if create_immediately:
        session_debugger.log_info({
            'action': 'creating_agent_immediately',
            'session_id': session_id
        }, DebuggerLogTypes.AGENT_LIFECYCLE)
        try:
            # Create the agent
            session_info.agent = create_agent(
                session_info.interactive,
                session_info.logger,
                session_info.session_type
            )
            session_debugger.log_info({
                'action': 'agent_created',
                'agent_type': session_info.session_type
            }, DebuggerLogTypes.AGENT_LIFECYCLE)

            # Start the agent thread (will process messages as they arrive)
            session_info.agent_thread = start_agent_thread(session_info, queue_service, session_id)

            # Mark agent as created (locks the agent type)
            session_info.initialized = True
            session_debugger.log_info({
                'action': 'agent_started_and_locked',
                'agent_type': session_info.session_type
            }, DebuggerLogTypes.AGENT_LIFECYCLE)

        except Exception as e:
            error_msg = f"Error creating agent immediately for session {session_id}: {str(e)}"
            session_debugger.log_error({
                'error': error_msg,
                'session_id': session_id
            }, DebuggerLogTypes.ERROR)
            import traceback
            traceback.print_exc()
            # Note: Session still exists but agent creation failed - it will remain in lazy state

    session_debugger.log_info({
        'action': 'session_created_complete',
        'session_id': session_id,
        'agent_type': agent_type,
        'agent_created': session_info.initialized,
        'log_directory': str(session_log_dir),
        'total_active_sessions': len(agents_by_session)
    }, DebuggerLogTypes.SESSION_MANAGEMENT)

    return session_info


def cleanup_session(session_id: str, agents_by_session: dict):
    """
    Clean up resources for a specific session.

    Args:
        session_id: Session identifier to clean up
        agents_by_session: Dictionary tracking all agent sessions
    """
    if session_id not in agents_by_session:
        return

    session_info = agents_by_session[session_id]
    debugger = session_info.debugger

    # Close agent and all its resources (actors, browsers, etc.) if it was created
    if session_info.agent is not None:
        try:
            if hasattr(session_info.agent, 'close'):
                session_info.agent.close()
                debugger.log_info({
                    'action': 'closed_agent_resources',
                    'session_id': session_id
                }, DebuggerLogTypes.SESSION_CLEANUP)
        except Exception as e:
            debugger.log_warning({
                'action': 'error_cleaning_up_agent',
                'session_id': session_id,
                'error': str(e)
            }, DebuggerLogTypes.WARNING)
            import traceback
            traceback.print_exc()
    else:
        debugger.log_info({
            'action': 'no_agent_to_cleanup',
            'session_id': session_id,
            'reason': 'cleaned up before first message'
        }, DebuggerLogTypes.SESSION_CLEANUP)

    # Remove from tracking dict
    del agents_by_session[session_id]
    debugger.log_info({
        'action': 'session_cleaned_up',
        'session_id': session_id,
        'remaining_active_sessions': len(agents_by_session)
    }, DebuggerLogTypes.SESSION_CLEANUP)


def cleanup_idle_sessions(agents_by_session: dict):
    """
    Remove agents that haven't been active for a while.

    Args:
        agents_by_session: Dictionary tracking all agent sessions
    """
    current_time = time.time()
    sessions_to_remove = []

    for session_id, session_info in agents_by_session.items():
        idle_time = current_time - session_info.last_active
        if idle_time > SESSION_IDLE_TIMEOUT:
            sessions_to_remove.append(session_id)
            session_info.debugger.log_info({
                'action': 'marking_idle_session_for_cleanup',
                'session_id': session_id,
                'idle_time_minutes': idle_time / 60
            }, DebuggerLogTypes.SESSION_CLEANUP)

    for session_id in sessions_to_remove:
        cleanup_session(session_id, agents_by_session)

    if sessions_to_remove:
        global_debugger = _get_or_create_global_debugger()
        global_debugger.log_info({
            'action': 'cleaned_up_idle_sessions',
            'num_sessions': len(sessions_to_remove)
        }, DebuggerLogTypes.SESSION_CLEANUP)


def run_agent_in_thread(session_info, queue_service):
    """
    Run an agent in a separate thread so the service can continue listening for other messages.

    The agent will block on its session-specific queue waiting for input.
    When a message arrives, it processes it and sends the response.
    """
    debugger = session_info.debugger
    try:
        # The agent will call interactive.get_input() which blocks on its session-specific queue
        # Note: This is a blocking call that runs the agent in a loop
        result = session_info.agent()
        debugger.log_info({
            'action': 'agent_execution_completed',
            'session_id': session_info.session_id,
            'result': str(result)
        }, DebuggerLogTypes.AGENT_LIFECYCLE)

        # Note: Log path is sent when session is created (in get_or_create_agent),
        # not here, because agents run continuously and may never "complete"

    except Exception as e:
        error_msg = f"Agent execution error in thread: {str(e)}"
        debugger.log_error({
            'error': error_msg,
            'session_id': session_info.session_id
        }, DebuggerLogTypes.ERROR)
        # Agent should have sent error via interactive, but send one just in case
        import traceback
        traceback.print_exc()


def start_agent_thread(session_info, queue_service, session_id: str):
    """
    Start a new agent thread for a session.

    Args:
        session_info: Session information containing the agent
        queue_service: Queue service instance
        session_id: Session identifier for the thread name

    Returns:
        The started thread, or None if DEBUG_MODE_SYNCHRONOUS_AGENT is True
    """
    # In synchronous debug mode, skip thread creation
    if DEBUG_MODE_SYNCHRONOUS_AGENT:
        session_info.debugger.log_info({
            'action': 'skipping_agent_thread_creation',
            'session_id': session_id,
            'reason': 'DEBUG_MODE_SYNCHRONOUS_AGENT enabled - agent will run in main process'
        }, DebuggerLogTypes.AGENT_LIFECYCLE)
        return None

    agent_thread = threading.Thread(
        target=run_agent_in_thread,
        args=(session_info, queue_service),
        name=f"Agent-{session_id}-{session_info.session_type}",
        daemon=True
    )
    agent_thread.start()
    session_info.debugger.log_info({
        'action': 'started_agent_thread',
        'session_id': session_id,
        'agent_type': session_info.session_type,
        'thread_name': agent_thread.name
    }, DebuggerLogTypes.AGENT_LIFECYCLE)
    return agent_thread


def run_agent_service():
    """
    Run the agent service loop.

    Waits for user input from the queue, executes the agent,
    and puts responses back on the queue.
    """
    # Get testcase root directory
    testcase_root = Path(__file__).parent

    # Initialize global debugger for service-level events
    global_debugger = _get_or_create_global_debugger(testcase_root)

    global_debugger.log_info({
        'action': 'service_starting',
        'message': 'WEB AGENT SERVICE - Starting'
    }, DebuggerLogTypes.SERVICE_STARTUP)

    # Create timestamped queue storage path
    queue_base_path = get_queue_base_path(testcase_root)
    queue_root_path = queue_base_path / timestamp()
    queue_root_path.mkdir(parents=True, exist_ok=True)

    # Create shared queue service with archiving enabled for debugging
    queue_service = StorageBasedQueueService(
        root_path=str(queue_root_path),
        archive_popped_items=True,
        archive_dir_name='_archive'
    )
    global_debugger.log_info({
        'action': 'queue_service_initialized',
        'queue_root_path': str(queue_root_path),
        'archiving_enabled': True
    }, DebuggerLogTypes.SERVICE_STARTUP)

    # Create queues
    queue_service.create_queue(RESPONSE_QUEUE_ID)
    queue_service.create_queue(CLIENT_CONTROL_QUEUE_ID)
    queue_service.create_queue(SERVER_CONTROL_QUEUE_ID)
    global_debugger.log_info({
        'action': 'queues_created',
        'queues': [RESPONSE_QUEUE_ID, CLIENT_CONTROL_QUEUE_ID, SERVER_CONTROL_QUEUE_ID]
    }, DebuggerLogTypes.SERVICE_STARTUP)

    # Create service log directory (each session will have its own subdirectory)
    service_log_dir = get_log_dir_path(testcase_root, f'web_agent_service_{timestamp()}')
    service_log_dir.mkdir(parents=True, exist_ok=True)
    global_debugger.log_info({
        'action': 'service_log_directory_created',
        'log_dir': str(service_log_dir)
    }, DebuggerLogTypes.SERVICE_STARTUP)

    # Dictionary to track agent instances per session
    agents_by_session = {}  # {session_id: AgentSessionInfo}

    global_debugger.log_info({
        'action': 'service_ready',
        'message': 'Listening for session control messages',
        'server_control_queue': SERVER_CONTROL_QUEUE_ID,
        'response_queue': RESPONSE_QUEUE_ID,
        'client_control_queue': CLIENT_CONTROL_QUEUE_ID
    }, DebuggerLogTypes.SERVICE_STARTUP)

    # Service loop - listens for session creation messages
    session_count = 0
    session_count = 0
    last_cleanup_time = time.time()

    try:
        while True:
            # Periodic cleanup of idle sessions
            current_time = time.time()
            if current_time - last_cleanup_time > CLEANUP_CHECK_INTERVAL:
                cleanup_idle_sessions(agents_by_session)
                last_cleanup_time = current_time

            # Lazy agent creation: create agent when messages arrive
            # Only run this loop if lazy creation is enabled (OPTION_NEW_AGENT_ON_FIRST_SUBMISSION=True)
            # When immediate creation is enabled, agents are created in get_or_create_agent()
            if OPTION_NEW_AGENT_ON_FIRST_SUBMISSION:
                for session_id, session_info in list(agents_by_session.items()):
                    if not session_info.initialized:
                        session_input_queue_id = f"{INPUT_QUEUE_ID}_{session_id}"

                        # Check if there are messages waiting
                        queue_size = queue_service.size(session_input_queue_id)
                        if queue_size > 0:
                            session_info.debugger.log_info({
                                'action': 'lazy_agent_creation_triggered',
                                'session_id': session_id,
                                'queue_size': queue_size,
                                'agent_type': session_info.session_type
                            }, DebuggerLogTypes.AGENT_LIFECYCLE)
                            try:
                                # Create the agent
                                session_info.agent = create_agent(
                                    session_info.interactive,
                                    session_info.logger,
                                    session_info.session_type
                                )
                                session_info.debugger.log_info({
                                    'action': 'agent_created_lazy',
                                    'agent_type': session_info.session_type
                                }, DebuggerLogTypes.AGENT_LIFECYCLE)

                                # Start the agent thread (will process the waiting messages)
                                session_info.agent_thread = start_agent_thread(session_info, queue_service, session_id)

                                # Mark agent as created (locks the agent type)
                                session_info.initialized = True
                                session_info.debugger.log_info({
                                    'action': 'agent_started_and_locked_lazy',
                                    'agent_type': session_info.session_type
                                }, DebuggerLogTypes.AGENT_LIFECYCLE)

                            except Exception as e:
                                error_msg = f"Error creating agent for session {session_id}: {str(e)}"
                                session_info.debugger.log_error({
                                    'error': error_msg,
                                    'session_id': session_id
                                }, DebuggerLogTypes.ERROR)
                                import traceback
                                traceback.print_exc()

            # Monitor agent status changes: send ack when status actually changes
            for session_id, session_info in list(agents_by_session.items()):
                if session_info.initialized and session_info.agent is not None:
                    agent = session_info.agent
                    current_status = agent.status.value.lower() if hasattr(agent, 'status') else 'unknown'

                    # Check if status has changed
                    if session_info.last_agent_status != current_status:
                        agent_control = agent.control.value.lower() if hasattr(agent, 'control') else 'continue'

                        # Send status change acknowledgment
                        ack_message = {
                            "type": "agent_control_ack",
                            "message": {
                                "session_id": session_id,
                                "control": agent_control,
                                "operation_status": "status_changed",
                                "agent_status": current_status
                            },
                            "timestamp": timestamp()
                        }
                        hprint_message(ack_message,
                                       title=f"[ACK] Agent Status Changed: {session_info.last_agent_status} → {current_status}")
                        queue_service.put(CLIENT_CONTROL_QUEUE_ID, ack_message)

                        session_info.last_agent_status = current_status

            # Listen on session control queue for session lifecycle events
            # Use shorter timeout so we can frequently check for messages
            control_message = queue_service.get(SERVER_CONTROL_QUEUE_ID, blocking=True, timeout=1)

            if control_message is None:
                # Timeout - continue to next iteration for cleanup check (no logging)
                continue

            session_count += 1
            global_debugger.log_info({
                'action': 'control_message_received',
                'message_number': session_count,
                'control_message': control_message
            }, DebuggerLogTypes.CONTROL_MESSAGE)

            # Extract action
            if not isinstance(control_message, dict):
                global_debugger.log_error({
                    'error': 'Invalid control message format',
                    'message': control_message
                }, DebuggerLogTypes.ERROR)
                continue

            action = control_message.get('action')

            # Extract message type from new generic format
            message_type = control_message.get('type')
            if not message_type:
                # Fall back to old 'action' field for backward compatibility
                message_type = control_message.get('action')

            if not message_type:
                global_debugger.log_error({
                    'error': 'Control message missing type field',
                    'message': control_message
                }, DebuggerLogTypes.ERROR)
                continue

            # Handle sync_active_sessions
            if message_type == 'sync_active_sessions':
                # Extract payload from generic message format
                message_payload = control_message.get('message', {})
                active_sessions = message_payload.get('active_sessions', [])
                global_debugger.log_info({
                    'action': 'syncing_active_sessions',
                    'active_sessions': active_sessions
                }, DebuggerLogTypes.SESSION_SYNC)

                # In synchronous debug mode, only allow ONE session
                if DEBUG_MODE_SYNCHRONOUS_AGENT and len(active_sessions) > 1:
                    # Reject all sessions except the first one
                    allowed_session = active_sessions[0]
                    rejected_sessions = active_sessions[1:]

                    global_debugger.log_warning({
                        'action': 'rejecting_multiple_sessions_in_debug_mode',
                        'allowed_session': allowed_session,
                        'rejected_sessions': rejected_sessions,
                        'reason': 'DEBUG_MODE_SYNCHRONOUS_AGENT allows only one session'
                    }, DebuggerLogTypes.SESSION_SYNC)

                    # Send rejection messages for each rejected session
                    for session_id in rejected_sessions:
                        rejection_message = {
                            "type": "agent_status",
                            "message": {
                                "session_id": session_id,
                                "status": "rejected",
                                "error": "DEBUG_MODE_SYNCHRONOUS_AGENT is enabled - only one session allowed for debugging"
                            },
                            "timestamp": timestamp()
                        }
                        queue_service.put(CLIENT_CONTROL_QUEUE_ID, rejection_message)
                        global_debugger.log_info({
                            'action': 'sent_rejection_for_session',
                            'session_id': session_id
                        }, DebuggerLogTypes.SESSION_SYNC)

                    # Update active_sessions to only include the allowed session
                    active_sessions = [allowed_session]

                # Create agents for new sessions (with default agent configuration)
                for session_id in active_sessions:
                    if session_id not in agents_by_session:
                        # Always use default agent for new sessions
                        # Clients can send sync_session_agent to change it later
                        agent_type = AGENT_TYPE_DEFAULT
                        global_debugger.log_info({
                            'action': 'creating_session_from_sync',
                            'session_id': session_id,
                            'agent_type': agent_type
                        }, DebuggerLogTypes.SESSION_SYNC)
                        try:
                            # Create agent for this session with specified agent type
                            # Use config flag to determine creation mode:
                            # - OPTION_NEW_AGENT_ON_FIRST_SUBMISSION=True → create_immediately=False (lazy)
                            # - OPTION_NEW_AGENT_ON_FIRST_SUBMISSION=False → create_immediately=True (immediate)
                            session_info = get_or_create_agent(
                                session_id,
                                queue_service,
                                service_log_dir,
                                agents_by_session,
                                agent_type,
                                create_immediately=not OPTION_NEW_AGENT_ON_FIRST_SUBMISSION
                            )

                            # NOTE: Agent thread started based on OPTION_NEW_AGENT_ON_FIRST_SUBMISSION flag

                            # Send acknowledgment back to client with standardized format
                            ack_message = {
                                "type": "agent_status",
                                "message": {
                                    "session_id": session_id,
                                    "status": "created",
                                    "agent_type": agent_type
                                },
                                "timestamp": timestamp()
                            }
                            queue_service.put(CLIENT_CONTROL_QUEUE_ID, ack_message)
                            global_debugger.log_info({
                                'action': 'sent_session_ack',
                                'session_id': session_id,
                                'ack_message': ack_message
                            }, DebuggerLogTypes.SESSION_SYNC)

                        except Exception as e:
                            error_msg = f"Error creating session {session_id}: {str(e)}"
                            global_debugger.log_error({
                                'error': error_msg,
                                'session_id': session_id
                            }, DebuggerLogTypes.ERROR)

                            # Send error acknowledgment with standardized format
                            error_ack = {
                                "type": "agent_status",
                                "message": {
                                    "session_id": session_id,
                                    "status": "error",
                                    "error": error_msg
                                },
                                "timestamp": timestamp()
                            }
                            queue_service.put(CLIENT_CONTROL_QUEUE_ID, error_ack)

                            import traceback
                            traceback.print_exc()
                    else:
                        # Session already exists - update last_active time
                        agents_by_session[session_id].last_active = time.time()

                # Clean up sessions that are no longer active
                sessions_to_remove = [sid for sid in agents_by_session.keys() if sid not in active_sessions]
                for session_id in sessions_to_remove:
                    global_debugger.log_info({
                        'action': 'removing_inactive_session',
                        'session_id': session_id
                    }, DebuggerLogTypes.SESSION_SYNC)
                    cleanup_session(session_id, agents_by_session)

                global_debugger.log_info({
                    'action': 'session_sync_complete',
                    'active_sessions_count': len(agents_by_session)
                }, DebuggerLogTypes.SESSION_SYNC)

            elif message_type == 'sync_session_agent':
                # Handle per-session agent update (both for new and existing sessions)
                message_payload = control_message.get('message', {})
                session_id = message_payload.get('session_id')
                agent_type = message_payload.get('agent_type')

                if not session_id or not agent_type:
                    print(f"[ERROR] sync_session_agent missing required fields: {control_message}")
                    continue

                print(f"[{timestamp()}] Syncing agent for session {session_id} to {agent_type}")

                if session_id in agents_by_session:
                    try:
                        # Get the session info
                        session_info = agents_by_session[session_id]
                        current_agent_type = session_info.session_type

                        # Check if agent has already been created
                        if session_info.initialized:
                            # Agent already created - cannot change type
                            print(
                                f"[{timestamp()}] Cannot change agent type for session {session_id}: agent already created and running")

                            ack_message = {
                                "type": "agent_status",
                                "message": {
                                    "session_id": session_id,
                                    "status": "agent_locked",
                                    "agent_type": current_agent_type,
                                    "error": "Cannot change agent type after first message"
                                },
                                "timestamp": timestamp()
                            }
                            queue_service.put(CLIENT_CONTROL_QUEUE_ID, ack_message)

                        elif current_agent_type == agent_type:
                            # Already the requested type (and not created yet)
                            print(f"[{timestamp()}] Agent type for session {session_id} is already {agent_type}")

                            ack_message = {
                                "type": "agent_status",
                                "message": {
                                    "session_id": session_id,
                                    "status": "agent_unchanged",
                                    "agent_type": agent_type
                                },
                                "timestamp": timestamp()
                            }
                            queue_service.put(CLIENT_CONTROL_QUEUE_ID, ack_message)
                        else:
                            # Agent not created yet - just update the type
                            print(
                                f"[{timestamp()}] Updating agent type for session {session_id} from {current_agent_type} to {agent_type}")
                            session_info.session_type = agent_type

                            # Send acknowledgment that type was updated
                            ack_message = {
                                "type": "agent_status",
                                "message": {
                                    "session_id": session_id,
                                    "status": "agent_type_updated",
                                    "agent_type": agent_type
                                },
                                "timestamp": timestamp()
                            }
                            queue_service.put(CLIENT_CONTROL_QUEUE_ID, ack_message)
                            print(
                                f"[{timestamp()}] Agent type updated to {agent_type} (will be created on first message)")

                    except Exception as e:
                        error_msg = f"Error updating agent for session {session_id}: {str(e)}"
                        print(f"\n[ERROR] {error_msg}")

                        # Send error acknowledgment with standardized format
                        error_ack = {
                            "type": "agent_status",
                            "message": {
                                "session_id": session_id,
                                "status": "error",
                                "error": error_msg
                            },
                            "timestamp": timestamp()
                        }
                        queue_service.put(CLIENT_CONTROL_QUEUE_ID, error_ack)

                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[WARNING] Session {session_id} not found for agent update")

            elif message_type == 'agent_control':
                # Handle agent workflow control commands (stop, pause, continue, step)
                message_payload = control_message.get('message', {})
                session_id = message_payload.get('session_id')
                control = message_payload.get('control')

                if not session_id or not control:
                    print(f"[ERROR] agent_control missing required fields: {control_message}")
                    continue

                print(f"[{timestamp()}] Agent control command for session {session_id}: {control}")

                if session_id in agents_by_session:
                    try:
                        session_info = agents_by_session[session_id]
                        agent = session_info.agent

                        if agent is None:
                            # Agent not created yet
                            print(
                                f"[{timestamp()}] Cannot control agent for session {session_id}: agent not created yet")

                            ack_message = {
                                "type": "agent_control_ack",
                                "message": {
                                    "session_id": session_id,
                                    "control": "continue",  # Default control before agent starts
                                    "operation_status": "error",
                                    "agent_status": "not_started",
                                    "error": "Agent not created yet"
                                },
                                "timestamp": timestamp()
                            }
                            hprint_message(ack_message, title=f"[ACK] Agent Control Error: Agent Not Created")
                            queue_service.put(CLIENT_CONTROL_QUEUE_ID, ack_message)
                        else:
                            # Apply control command to agent
                            if control == 'stop':
                                agent.stop()
                            elif control == 'pause':
                                agent.pause()
                            elif control == 'continue':
                                agent.resume()
                            elif control == 'step':
                                agent.step_by_step()
                            else:
                                print(f"[WARNING] Unknown control command: {control}, ignoring")
                                continue

                            # Get current agent control and status, then send acknowledgment
                            agent_control = agent.control.value.lower() if hasattr(agent, 'control') else 'continue'
                            agent_status = agent.status.value.lower() if hasattr(agent, 'status') else 'unknown'

                            ack_message = {
                                "type": "agent_control_ack",
                                "message": {
                                    "session_id": session_id,
                                    "control": agent_control,
                                    "operation_status": "success",
                                    "agent_status": agent_status
                                },
                                "timestamp": timestamp()
                            }
                            hprint_message(ack_message,
                                           title=f"[ACK] Agent Control Applied: {control} (Control={agent_control}, Status={agent_status})")
                            queue_service.put(CLIENT_CONTROL_QUEUE_ID, ack_message)

                            # Store current status for change detection
                            session_info.last_agent_status = agent_status

                    except Exception as e:
                        error_msg = f"Error applying control command for session {session_id}: {str(e)}"
                        print(f"\n[ERROR] {error_msg}")

                        # Send error acknowledgment
                        agent_control = (
                            agent.control.value.lower() if (agent and hasattr(agent, 'control')) else "unknown")
                        agent_status = (
                            agent.status.value.lower() if (agent and hasattr(agent, 'status')) else "unknown")
                        error_ack = {
                            "type": "agent_control_ack",
                            "message": {
                                "session_id": session_id,
                                "control": agent_control,
                                "operation_status": "error",
                                "agent_status": agent_status,
                                "error": error_msg
                            },
                            "timestamp": timestamp()
                        }
                        hprint_message(error_ack, title=f"[ACK] Agent Control Exception Error")
                        queue_service.put(CLIENT_CONTROL_QUEUE_ID, error_ack)

                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[WARNING] Session {session_id} not found for agent control")

                    # Send error acknowledgment
                    ack_message = {
                        "type": "agent_control_ack",
                        "message": {
                            "session_id": session_id,
                            "control": "unknown",
                            "operation_status": "error",
                            "agent_status": "unknown",
                            "error": "Session not found"
                        },
                        "timestamp": timestamp()
                    }
                    hprint_message(ack_message, title=f"[ACK] Agent Control Error: Session Not Found")
                    queue_service.put(CLIENT_CONTROL_QUEUE_ID, ack_message)

            else:
                global_debugger.log_warning({
                    'warning': 'Unknown message type',
                    'message_type': message_type
                }, DebuggerLogTypes.WARNING)

            global_debugger.log_info({
                'action': 'control_message_processed',
                'message_number': session_count
            }, DebuggerLogTypes.CONTROL_MESSAGE)

            # Synchronous agent execution in debug mode
            # When DEBUG_MODE_SYNCHRONOUS_AGENT is True, the agent runs in the main process
            # instead of a separate thread. This allows breakpoints to work properly during debugging.
            # Note: In this mode, the agent will block the service loop while running, so control
            # messages will only be processed when the agent is idle/waiting for input.
            if DEBUG_MODE_SYNCHRONOUS_AGENT:
                for session_id, session_info in list(agents_by_session.items()):
                    if session_info.agent is not None and session_info.agent_thread is None:
                        # Agent exists but no thread - run synchronously in main process
                        # This will block here, processing messages as they arrive
                        # The agent runs in an infinite loop until stopped
                        session_info.debugger.log_info({
                            'action': 'starting_agent_synchronously_in_main_process',
                            'session_id': session_id,
                            'note': 'Service loop will be blocked while agent runs. Use for debugging only.'
                        }, DebuggerLogTypes.AGENT_LIFECYCLE)

                        try:
                            # Run the agent in the main process
                            # This blocks indefinitely as the agent processes messages
                            result = session_info.agent()
                            session_info.debugger.log_info({
                                'action': 'agent_synchronous_execution_completed',
                                'session_id': session_info.session_id,
                                'result': str(result)
                            }, DebuggerLogTypes.AGENT_LIFECYCLE)

                        except Exception as e:
                            error_msg = f"Error in synchronous agent execution: {str(e)}"
                            session_info.debugger.log_error({
                                'error': error_msg,
                                'session_id': session_info.session_id
                            }, DebuggerLogTypes.ERROR)
                            import traceback
                            traceback.print_exc()

    except KeyboardInterrupt:
        global_debugger.log_info({
            'action': 'service_interrupted',
            'reason': 'user_interrupt'
        }, DebuggerLogTypes.SERVICE_SHUTDOWN)
    finally:
        global_debugger.log_info({
            'action': 'cleaning_up',
            'active_sessions': len(agents_by_session)
        }, DebuggerLogTypes.SERVICE_SHUTDOWN)

        # Clean up all agent sessions
        for session_id in list(agents_by_session.keys()):
            cleanup_session(session_id, agents_by_session)

        queue_service.close()
        global_debugger.log_info({
            'action': 'service_stopped'
        }, DebuggerLogTypes.SERVICE_SHUTDOWN)


if __name__ == '__main__':
    run_agent_service()
