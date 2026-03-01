"""Agent creation factory for web agent service.

This module provides centralized agent creation with support for different
agent types and template version switching.
"""
import logging
from functools import partial
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional

from agent_foundation.agents.agent_response import AgentResponseFormat
from agent_foundation.knowledge import KnowledgeBase, KnowledgeDataLoader, KnowledgeProvider
from agent_foundation.knowledge.stores.metadata.keyvalue_adapter import KeyValueMetadataStore
from agent_foundation.knowledge.stores.pieces.retrieval_adapter import RetrievalKnowledgePieceStore
from agent_foundation.knowledge.stores.graph.graph_adapter import GraphServiceEntityGraphStore
from rich_python_utils.service_utils.keyvalue_service.file_keyvalue_service import FileKeyValueService
from rich_python_utils.service_utils.retrieval_service.file_retrieval_service import FileRetrievalService
from rich_python_utils.service_utils.graph_service.file_graph_service import FileGraphService
from agent_foundation.agents.prompt_based_agents.prompt_based_action_agent import PromptBasedActionAgent
from agent_foundation.agents.prompt_based_agents.prompt_based_planning_agent import PromptBasedActionPlanningAgent
from agent_foundation.agents.prompt_based_agents.prompt_based_response_agent import PromptBasedResponseActionAgent
from agent_foundation.agents.prompt_based_agents.prompt_based_summary_agent import PromptBasedSummaryActionAgent
from agent_foundation.common.inferencers.agentic_inferencers.common import ReflectionStyles, ResponseSelectors
from agent_foundation.common.inferencers.agentic_inferencers.reflective_inferencer import ReflectiveInferencer
from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
from agent_foundation.common.inferencers.mock_inferencers import MockClarificationInferencer
from agent_foundation.ui.input_modes import (
    InputModeConfig, ChoiceOption, single_choice, multiple_choices,
)
from agent_foundation.ui.queue_interactive import QueueInteractive
from rich_python_utils.string_utils.formatting.common import KeyValueStringFormat
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
from webaxon.devsuite.config import OPTION_BASE_REASONER, OPTION_DEFAULT_PROMPT_VERSION, MOCK_USER_PROFILE, \
    DEFAULT_AGENT_REASONER_ARGS, RESPONSE_AGENT_REASONER_ARGS
from webaxon.automation.web_agent_actors.common import WebActor
from webaxon.automation.web_agent_actors.constants import ACTION_TYPE_INFO_ASK_QUESTION
from webaxon.automation.web_agent_actors.webpage_make_answer_actor import WebPageMakeAnswerActor, \
    ACTION_TYPE_WEBPAGE_MAKE_ANSWER
from webaxon.automation.backends.config import BrowserConfig, UndetectedChromeConfig
from webaxon.automation.web_driver import WebDriver

try:
    from agent_foundation.common.inferencers.api_inferencers.ag.ag_claude_api_inferencer import \
        AgClaudeApiInferencer
except ImportError:
    AgClaudeApiInferencer = None

from .config import ServiceConfig


class AgentFactory:
    """Factory for creating different agent types.
    
    This class centralizes agent creation logic and provides:
    - Support for multiple agent types (default, mock)
    - Template version switching per agent
    - Consistent agent configuration
    - User profile and response format management
    
    The factory ensures all agents are properly configured with the
    necessary dependencies (reasoner, interactive, logger, etc.).
    """
    
    def __init__(
        self,
        template_manager: TemplateManager,
        config: ServiceConfig,
        testcase_root: Path,
        ingestion_inferencer: Any = None,
    ):
        """Initialize the agent factory.

        Args:
            template_manager: Template manager for prompt templates
            config: Service configuration
            testcase_root: Root directory for the testcase (used for file-based stores)
            ingestion_inferencer: Optional pre-built inferencer for knowledge
                ingestion.  If None a ClaudeApiInferencer is created lazily
                on the first ``ingest_knowledge`` call.
        """
        self._template_manager = template_manager
        self._config = config
        self._testcase_root = testcase_root
        self._ingestion_inferencer = ingestion_inferencer
        self._provider = self._create_knowledge_provider()
        self._user_profile = self._load_user_profile()
        self._response_format_config = self._load_response_format_config()
    
    def create_agent(
        self,
        interactive: QueueInteractive,
        logger: Callable,
        agent_type: str = 'DefaultAgent',
        template_version: str = ""
    ) -> PromptBasedActionPlanningAgent:
        """Create agent based on type and template version.
        
        This method:
        1. Switches template version if provided
        2. Validates agent type
        3. Creates agent based on type
        4. Returns configured agent
        
        Args:
            interactive: QueueInteractive instance for agent communication
            logger: Logger function for agent execution
            agent_type: Type of agent to create ('DefaultAgent' or 'MockClarificationAgent')
            template_version: Template version to use (empty string for default)
            
        Returns:
            Configured agent instance
            
        Raises:
            ValueError: If agent_type is not supported
        """
        # Switch template version if provided
        # NOTE: switch() returns a new TemplateManager copy — must reassign
        if template_version:
            self._template_manager = self._template_manager.switch(template_version=template_version)
        
        # Validate agent type
        if agent_type not in self.get_available_types():
            raise ValueError(
                f"Unknown agent type: {agent_type}. "
                f"Available types: {', '.join(self.get_available_types())}"
            )
        
        # Create agent based on type
        if agent_type == 'MockClarificationAgent':
            return self._create_mock_agent(interactive, logger)
        else:  # DefaultAgent
            return self._create_default_agent(interactive, logger)
    
    def _create_default_agent(
        self,
        interactive: QueueInteractive,
        logger: Callable
    ) -> PromptBasedActionPlanningAgent:
        """Create default planning agent with full capabilities.
        
        This creates a full-featured planning agent with:
        - Claude API reasoner (with optional reflection)
        - Response agent for direct responses
        - Summary agent for summarization
        - WebDriver actor for web automation
        - Master action agent coordinating all actions
        - Planning agent orchestrating the workflow
        
        Args:
            interactive: QueueInteractive instance for agent communication
            logger: Logger function for agent execution
            
        Returns:
            Configured planning agent
        """
        # Agent configuration
        raw_response_start_delimiter = '<StructuredResponse>'
        raw_response_end_delimiter = '</StructuredResponse>'
        raw_response_format = AgentResponseFormat.XML
        debug_mode = True
        always_add_logging_based_logger = False
        anchor_action_types = {'Search', 'ElementInteraction.BrowseLink'}
        
        # Create base reasoner
        if OPTION_BASE_REASONER == 'AgClaude' and AgClaudeApiInferencer is not None:
            reasoner = AgClaudeApiInferencer(
                max_retry=3,
                default_inference_args=DEFAULT_AGENT_REASONER_ARGS,
                logger=logger,
                debug_mode=debug_mode,
                id='reasoner'
            )
        else:
            reasoner = ClaudeApiInferencer(
                max_retry=3,
                default_inference_args=DEFAULT_AGENT_REASONER_ARGS,
                logger=logger,
                debug_mode=debug_mode,
                id='reasoner'
            )
        
        # Create reflective reasoner wrapper
        reflective_reasoner = ReflectiveInferencer(
            base_inferencer=reasoner,
            max_retry=1,
            reflection_inferencer=reasoner,
            reflection_prompt_formatter=self._template_manager.switch(active_template_type='reflection'),
            num_reflections=1,
            reflection_style=ReflectionStyles.Sequential,
            response_selector=ResponseSelectors.LastReflection,
            logger=logger,
            always_add_logging_based_logger=always_add_logging_based_logger,
            debug_mode=debug_mode,
            id='reflective_reasoner'
        )
        
        # Create response agent
        response_agent = PromptBasedResponseActionAgent(
            prompt_formatter=self._template_manager.switch(active_template_root_space='response_agent'),
            raw_response_start_delimiter=raw_response_start_delimiter,
            raw_response_end_delimiter=raw_response_end_delimiter,
            raw_response_format=raw_response_format,
            raw_response_parsing_args={'exclude_paths': ['InstantResponse.Response.Answer']},
            use_conversational_user_input=True,
            input_string_formatter=KeyValueStringFormat.XML,
            response_string_formatter=KeyValueStringFormat.XML,
            user_profile=self._user_profile,
            reasoner=reasoner,
            reasoner_args=RESPONSE_AGENT_REASONER_ARGS,
            interactive=interactive,
            logger=logger,
            always_add_logging_based_logger=True,
            debug_mode=debug_mode,
            only_keep_parent_debuggable_ids=True,
            knowledge_provider=self._provider,
            id='response_agent'
        )
        
        # Create summary agent
        summary_agent = PromptBasedSummaryActionAgent(
            prompt_formatter=self._template_manager.switch(active_template_root_space='response_agent'),
            raw_response_start_delimiter=raw_response_start_delimiter,
            raw_response_end_delimiter=raw_response_end_delimiter,
            raw_response_format=raw_response_format,
            use_conversational_user_input=True,
            input_string_formatter=KeyValueStringFormat.XML,
            response_string_formatter=KeyValueStringFormat.XML,
            user_profile=self._user_profile,
            reasoner=reasoner,
            interactive=interactive,
            logger=logger,
            always_add_logging_based_logger=True,
            debug_mode=debug_mode,
            only_keep_parent_debuggable_ids=True,
            knowledge_provider=self._provider,
            id='summary_agent'
        )
        
        # Create WebDriver actor
        browser_config = None
        if self._config.chrome_version:
            browser_config = BrowserConfig(
                headless=False,
                undetected_chrome=UndetectedChromeConfig(
                    version_main=self._config.chrome_version
                ),
            )
        webdriver_actor = WebDriver(
            headless=False,
            id='webdriver',
            logger=logger,
            debug_mode=debug_mode,
            always_add_logging_based_logger=always_add_logging_based_logger,
            config=browser_config,
        )
        
        # Create info ask question actor
        info_ask_question_actor = WebActor(
            actor=PromptBasedActionAgent(
                prompt_formatter=self._template_manager.switch(
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
                user_profile=self._user_profile,
                reasoner=reasoner,
                interactive=interactive,
                actor={
                    'default': webdriver_actor,
                    ACTION_TYPE_WEBPAGE_MAKE_ANSWER: WebPageMakeAnswerActor(actor=response_agent, id='make_answer_actor')
                },
                summarizer=summary_agent,
                logger=logger,
                always_add_logging_based_logger=always_add_logging_based_logger,
                debug_mode=debug_mode,
                only_keep_parent_debuggable_ids=True,
                knowledge_provider=self._provider,
                id='info_ask_question_agent'
            ),
            target_action_type=ACTION_TYPE_INFO_ASK_QUESTION,
            init_url='https://home.atlassian.com/chat'
        )
        
        # Create master action agent
        master_action_agent = PromptBasedActionAgent(
            prompt_formatter=self._template_manager.switch(active_template_root_space='action_agent'),
            anchor_action_types=anchor_action_types,
            raw_response_start_delimiter=raw_response_start_delimiter,
            raw_response_end_delimiter=raw_response_end_delimiter,
            raw_response_format=raw_response_format,
            response_field_task_status_description='PlannedActions',
            use_conversational_user_input=True,
            input_string_formatter=KeyValueStringFormat.XML,
            response_string_formatter=KeyValueStringFormat.XML,
            user_profile=self._user_profile,
            reasoner=reasoner,
            interactive=interactive,
            actor={
                'default': webdriver_actor,
                ACTION_TYPE_WEBPAGE_MAKE_ANSWER: WebPageMakeAnswerActor(actor=response_agent, id='make_answer_actor'),
                ACTION_TYPE_INFO_ASK_QUESTION: info_ask_question_actor
            },
            summarizer=summary_agent,
            user_input_mode_mapping=self._get_user_input_mode_mapping(),
            logger=logger,
            always_add_logging_based_logger=always_add_logging_based_logger,
            debug_mode=debug_mode,
            only_keep_parent_debuggable_ids=True,
            knowledge_provider=self._provider,
            id='action_agent'
        )
        
        # Create planning agent
        planning_agent = PromptBasedActionPlanningAgent(
            prompt_formatter=self._template_manager.switch(active_template_root_space='planning_agent'),
            direct_response_start_delimiter='<DirectResponse>',
            direct_response_end_delimiter='</DirectResponse>',
            raw_response_start_delimiter=raw_response_start_delimiter,
            raw_response_end_delimiter=raw_response_end_delimiter,
            raw_response_format=raw_response_format,
            use_conversational_user_input=True,
            input_string_formatter=KeyValueStringFormat.XML,
            response_string_formatter=KeyValueStringFormat.XML,
            user_profile=self._user_profile,
            reasoner=reasoner,
            interactive=interactive,
            actor=master_action_agent,
            actor_args_transformation={
                'Request': 'user_input',
                'SolutionRequirement': 'task_requirement',
                'ProblemID': 'task_label'
            },
            user_input_mode_mapping=self._get_user_input_mode_mapping(),
            logger=logger,
            always_add_logging_based_logger=always_add_logging_based_logger,
            debug_mode=debug_mode,
            only_keep_parent_debuggable_ids=True,
            ensure_consistent_session_metadata_fields=['session_id'],  # Ensure session_id stays consistent
            knowledge_provider=self._provider,
            id='planning_agent'
        )
        
        return planning_agent
    
    def _create_mock_agent(
        self,
        interactive: QueueInteractive,
        logger: Callable
    ) -> PromptBasedActionAgent:
        """Create mock clarification agent for testing.
        
        This creates a simplified agent for testing that uses a mock
        reasoner instead of calling the actual Claude API.
        
        Args:
            interactive: QueueInteractive instance for agent communication
            logger: Logger function for agent execution
            
        Returns:
            Configured mock agent
        """
        # Agent configuration
        raw_response_start_delimiter = '<StructuredResponse>'
        raw_response_end_delimiter = '</StructuredResponse>'
        raw_response_format = AgentResponseFormat.XML
        debug_mode = True
        always_add_logging_based_logger = False
        anchor_action_types = {'Search', 'ElementInteraction.BrowseLink'}
        
        # Create mock reasoner
        mock_reasoner = MockClarificationInferencer()
        
        # Create simple action agent with mock reasoner
        root_agent = PromptBasedActionAgent(
            prompt_formatter=self._template_manager.switch(active_template_root_space='action_agent'),
            anchor_action_types=anchor_action_types,
            raw_response_start_delimiter=raw_response_start_delimiter,
            raw_response_end_delimiter=raw_response_end_delimiter,
            raw_response_format=raw_response_format,
            response_field_task_status_description='PlannedActions',
            use_conversational_user_input=True,
            input_string_formatter=KeyValueStringFormat.XML,
            response_string_formatter=KeyValueStringFormat.XML,
            user_profile=self._user_profile,
            reasoner=mock_reasoner,
            interactive=interactive,
            actor={},
            logger=logger,
            always_add_logging_based_logger=always_add_logging_based_logger,
            debug_mode=debug_mode,
            only_keep_parent_debuggable_ids=True
        )
        
        return root_agent
    
    # -- UserInputsRequired input mode builders ---------------------------------

    @staticmethod
    def _build_auth_input_mode(action) -> InputModeConfig:
        """Build PREDEFINED SINGLE_CHOICE for Authentication based on AllowRelayInfo."""
        allow_relay = False
        if action.args:
            allow_relay = str(action.args.get('AllowRelayInfo', 'False')).lower() in ('true', '1', 'yes')

        options = [
            ChoiceOption(
                label="I have completed the authentication myself",
                value="completed",
                needs_user_copilot=True,
            ),
        ]
        if allow_relay:
            options.append(ChoiceOption(
                label="Enter password or passcode",
                value="",
                follow_up_prompt="[Enter password/passcode]: ",
                needs_user_copilot=False,
            ))

        return single_choice(options, allow_custom=True)

    @staticmethod
    def _build_options_input_mode(action) -> InputModeConfig:
        """Build DYNAMIC input mode from Options in action.args.

        Supports two formats:
        1. Simple pipe-delimited: <Options>A|B|C</Options>
           - args['Options'] is a str -> split on '|', label=value
        2. Full XML structure: <Options><Option>...</Option></Options>
           - args['Options'] is a dict -> read Option list with Content/Value/FollowUpPrompt

        Also reads:
        - <AllowMultiple>True</AllowMultiple> -> MULTIPLE_CHOICES vs SINGLE_CHOICE
        - <AllowFreeText>False</AllowFreeText> -> disables "Other (type your own)" option

        Falls back to FREE_TEXT when no Options provided.
        """
        if not action.args:
            return InputModeConfig()

        options_raw = action.args.get('Options', '')
        allow_multiple = str(action.args.get('AllowMultiple', 'False')).lower() in ('true', '1', 'yes')
        allow_free_text = str(action.args.get('AllowFreeText', 'True')).lower() not in ('false', '0', 'no')
        needs_user_copilot = str(action.args.get('NeedsUserCopilot', 'False')).lower() in ('true', '1', 'yes')

        choice_options = []

        if isinstance(options_raw, str) and options_raw.strip():
            # Simple format: "A|B|C" -> label=value for each
            for label in options_raw.split('|'):
                label = label.strip()
                if label:
                    choice_options.append(ChoiceOption(
                        label=label, value=label,
                        needs_user_copilot=needs_user_copilot
                    ))

        elif isinstance(options_raw, dict):
            # Full XML format: {'Option': [{Content, Value, FollowUpPrompt}, ...]}
            option_items = options_raw.get('Option', [])
            # Handle single Option (parser returns dict instead of list)
            if isinstance(option_items, dict):
                option_items = [option_items]
            for item in option_items:
                content = item.get('Content', '')
                value = item.get('Value', content)  # defaults to Content if omitted
                follow_up = item.get('FollowUpPrompt', '')
                if content:
                    choice_options.append(ChoiceOption(
                        label=content, value=value, follow_up_prompt=follow_up,
                        needs_user_copilot=needs_user_copilot
                    ))

        if choice_options:
            if allow_multiple:
                return multiple_choices(choice_options, allow_custom=allow_free_text)
            return single_choice(choice_options, allow_custom=allow_free_text)

        return InputModeConfig()  # FREE_TEXT fallback

    def _get_user_input_mode_mapping(self) -> dict:
        """Get mapping from UserInputsRequired subtypes to input mode builders."""
        return {
            'Authentication': self._build_auth_input_mode,
            'MissingInformation': self._build_options_input_mode,
            'Clarification': self._build_options_input_mode,
        }

    def get_available_types(self) -> List[str]:
        """Get list of available agent types.

        Returns:
            List of supported agent type names
        """
        return ['DefaultAgent', 'MockClarificationAgent']
    
    def _create_knowledge_provider(self) -> Optional[KnowledgeProvider]:
        """Create a KnowledgeProvider with file-based persistent stores.

        Always creates the provider so that knowledge can be registered at runtime
        (e.g. via CLI) even without a seed file.  If config has a knowledge_data_file,
        the stores are seeded from it on first run only (when piece store is empty).

        Returns:
            KnowledgeProvider instance.
        """
        from webaxon.devsuite.web_agent_service_nextgen.constants import KNOWLEDGE_STORE_DIR
        store_base = self._testcase_root / KNOWLEDGE_STORE_DIR

        logger = logging.getLogger(__name__)
        logger.info("Creating file-based KnowledgeProvider at %s", store_base)

        kb = KnowledgeBase(
            metadata_store=KeyValueMetadataStore(
                kv_service=FileKeyValueService(base_dir=str(store_base / "metadata"))
            ),
            piece_store=RetrievalKnowledgePieceStore(
                retrieval_service=FileRetrievalService(base_dir=str(store_base / "pieces"))
            ),
            graph_store=GraphServiceEntityGraphStore(
                graph_service=FileGraphService(base_dir=str(store_base / "graph"))
            ),
            active_entity_id=None,  # Will be auto-detected from ingested data
            graph_retrieval_ignore_pieces_already_retrieved=True,
        )

        # Auto-detect active_entity_id from existing data on disk
        self._detect_and_set_active_entity_id(kb)

        # Seed from knowledge_data_file only if stores are empty (first run)
        if self._config.knowledge_data_file:
            if kb.piece_store.retrieval_service.size() == 0:
                logger.info("Seeding knowledge from %s", self._config.knowledge_data_file)
                KnowledgeDataLoader.load(kb, self._config.knowledge_data_file)
            else:
                logger.info("Knowledge store already populated, skipping seed")

        return KnowledgeProvider(kb)

    @staticmethod
    def _detect_and_set_active_entity_id(kb: KnowledgeBase) -> None:
        """Auto-detect active_entity_id from ingested data on disk.

        Scans the piece store namespaces for user entities (prefixed with
        'user:') and sets the first one found as the active entity. This
        avoids hardcoding the entity_id, which depends on LLM-generated
        formatting (e.g., 'user:tony-chen' vs 'user:tony_chen').
        """
        logger = logging.getLogger(__name__)
        retrieval_service = kb.piece_store.retrieval_service
        try:
            namespaces = retrieval_service.namespaces()
        except Exception:
            namespaces = []
        user_namespaces = [ns for ns in namespaces if ns.startswith("user:")]
        if user_namespaces:
            kb.active_entity_id = user_namespaces[0]
            logger.info("Auto-detected active_entity_id: %s", kb.active_entity_id)
        else:
            logger.info("No user entity found in knowledge store yet")

    def ensure_knowledge_provider(self) -> None:
        """Ensure the knowledge provider exists, creating it lazily if needed."""
        if self._provider is None:
            self._provider = self._create_knowledge_provider()
            self._user_profile = self._load_user_profile()

    def ingest_knowledge(self, user_text: str) -> dict:
        """Ingest free-text knowledge via LLM structuring.

        Uses KnowledgeIngestionCLI to send the free text to the LLM, which
        decomposes it into structured metadata, knowledge pieces (with proper
        knowledge_type and info_type), and graph relationships, then loads
        everything into the KnowledgeBase.

        Args:
            user_text: Free-form user input text to structurize and ingest.

        Returns:
            Dict with counts from KnowledgeDataLoader.load(), e.g.
            {"metadata": 1, "pieces": 3, "graph_nodes": 4, "graph_edges": 5}

        Raises:
            ValueError: If LLM fails to produce valid structured JSON.
        """
        from agent_foundation.knowledge.ingestion_cli import KnowledgeIngestionCLI

        self.ensure_knowledge_provider()

        # Create a lightweight inferencer for knowledge structuring (reused across calls)
        if self._ingestion_inferencer is None:
            self._ingestion_inferencer = ClaudeApiInferencer(
                max_retry=3,
                default_inference_args=DEFAULT_AGENT_REASONER_ARGS,
                logger=logging.getLogger(__name__).info,
                debug_mode=True,
            )

        cli = KnowledgeIngestionCLI(
            inferencer=self._ingestion_inferencer,
            max_retries=3,
            raw_files_store_path=str(
                self._testcase_root / "_runtime" / "knowledge_store" / "ingestion_logs"
            ),
        )

        counts = cli.ingest(user_text, self._provider.kb)

        # Re-detect active_entity_id after ingestion (LLM may create new entities)
        self._detect_and_set_active_entity_id(self._provider.kb)

        return counts

    def _ensure_ingestion_inferencer(self) -> None:
        """Lazily create the ClaudeApiInferencer if not already set.

        Follows the same pattern as ingest_knowledge().
        """
        if self._ingestion_inferencer is None:
            self._ingestion_inferencer = ClaudeApiInferencer(
                max_retry=3,
                default_inference_args=DEFAULT_AGENT_REASONER_ARGS,
                logger=logging.getLogger(__name__).info,
                debug_mode=True,
            )

    def _make_llm_fn(self) -> Callable[[str], str]:
        """Create an LLM callable from the ingestion inferencer.

        Handles InferencerResponse duck-typing via select_response().
        KnowledgeUpdater expects Callable[[str], str] and calls
        json.loads(response) directly, so the wrapper MUST extract the string.
        """
        self._ensure_ingestion_inferencer()

        def llm_fn(prompt: str) -> str:
            response = self._ingestion_inferencer(prompt)
            if hasattr(response, "select_response"):
                return response.select_response().response
            return str(response)

        return llm_fn

    def get_document_ingester(self):
        """Return a DocumentIngester with the LLM inferencer."""
        from agent_foundation.knowledge.ingestion.document_ingester import DocumentIngester

        self.ensure_knowledge_provider()
        return DocumentIngester(inferencer=self._make_llm_fn())

    def get_knowledge_updater(self):
        """Return a KnowledgeUpdater with piece_store and LLM function."""
        from agent_foundation.knowledge.ingestion.knowledge_updater import KnowledgeUpdater

        self.ensure_knowledge_provider()
        return KnowledgeUpdater(
            piece_store=self._provider.kb.piece_store,
            llm_fn=self._make_llm_fn(),
        )

    def get_knowledge_deleter(self):
        """Return a KnowledgeDeleter with piece_store."""
        from agent_foundation.knowledge.ingestion.knowledge_deleter import KnowledgeDeleter

        self.ensure_knowledge_provider()
        return KnowledgeDeleter(piece_store=self._provider.kb.piece_store)

    def get_knowledge_base(self):
        """Return the KB instance, ensuring provider is initialized."""
        self.ensure_knowledge_provider()
        return self._provider.kb

    def _load_user_profile(self) -> Optional[Dict[str, Any]]:
        """Load user profile configuration.
        
        Returns None if a KnowledgeProvider is active (the provider supplies
        user_profile via dict merge in additional_reasoner_input_feed).
        Falls back to MOCK_USER_PROFILE if no provider is configured.
        
        Returns:
            User profile dictionary for the configured prompt version, or None
            if a KnowledgeProvider is active.
        """
        if self._provider:
            return None
        return MOCK_USER_PROFILE.get(OPTION_DEFAULT_PROMPT_VERSION, MOCK_USER_PROFILE['default'])
    
    def close(self):
        """Close the KnowledgeProvider if it exists. Called during service shutdown."""
        if self._provider:
            self._provider.close()

    def _load_response_format_config(self) -> Dict[str, Any]:
        """Load response format configuration.
        
        Returns:
            Response format configuration dictionary
        """
        return {
            'raw_response_start_delimiter': '<StructuredResponse>',
            'raw_response_end_delimiter': '</StructuredResponse>',
            'raw_response_format': AgentResponseFormat.XML
        }

