from typing import Callable, Any, Sequence, Mapping

from attr import attrs, attrib
from .constants import DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_USER_INPUT, DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_ATTACHMENTS
from science_modeling_tools.agents.agent_actor import AgentActor
from science_modeling_tools.agents.prompt_based_agents.prompt_based_action_agent import PromptBasedActionAgent
from science_modeling_tools.agents.prompt_based_agents.prompt_based_agent import PromptBasedAgent


def _create_web_actor_visit_url_base_action(init_url: str) -> PromptBasedAgent:
    """
    Configure a PromptBasedAgent with a base_action to visit an initial URL.

    This sets up the agent to automatically navigate to the specified URL
    before starting the reasoning loop.

    Args:
        agent: The PromptBasedAgent to configure
        init_url: The initial URL to visit before reasoning starts

    Returns:
        The configured agent with base_action set
    """
    # Create a StructuredResponse XML string for visiting the initial URL
    # This will be executed on the first iteration, skipping the reasoner
    return f"""<StructuredResponse>
 <NewTask>true</NewTask>
 <TaskStatus>Ongoing</TaskStatus>
 <InstantResponse>I'll first visit the webpage at {init_url}.</InstantResponse>
 <ImmediateNextActions>
  <Action>
   <Reasoning>Visiting the initial URL {init_url} as the starting point for the task. This will load the webpage content for examination.</Reasoning>
   <Target>{init_url}</Target>
   <Type>Navigation.VisitURL</Type>
  </Action>
 </ImmediateNextActions>
 <PlannedActions>After the webpage loads, I will examine the HTML content and decide the next actions based on the user's request and the available elements on the page.</PlannedActions>
</StructuredResponse>"""


@attrs
class WebActor(AgentActor):
    init_url: str = attrib(default=None)
    base_action_creator: Callable[[str], Any] = attrib(default=_create_web_actor_visit_url_base_action)
    task_input_field_name_user_input: str = attrib(default=DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_USER_INPUT)
    task_input_field_name_attachments: str = attrib(default=DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_ATTACHMENTS)

    def __attrs_post_init__(self):
        if not isinstance(self.actor, PromptBasedActionAgent):
            raise ValueError

        if self.init_url:
            self.actor.base_action = self.base_action_creator(self.init_url)


    def get_actor_input(
            self,
            action_results: Sequence,
            task_input: Any,
            action_type: str,
            action_target: str = None,
            action_args: Mapping = None,
            attachments: Sequence = None
    ):
        return {
            self.task_input_field_name_user_input: action_target,
            self.task_input_field_name_attachments: attachments
        }