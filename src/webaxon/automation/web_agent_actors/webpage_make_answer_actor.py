from typing import Any, Mapping, Sequence, Dict

from attr import attrs, attrib

from science_modeling_tools.agents.agent_actor import AgentActor
from rich_python_utils.common_utils import last_
from webaxon.automation.web_agent_actors.constants import (
    DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_TASK_INPUT,
    DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_USER_INPUT
)
from webaxon.automation.web_driver import WebDriverActionResult
from webaxon.html_utils.element_identification import ATTR_NAME_INCREMENTAL_ID
from webaxon.html_utils.sanitization import clean_html, DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE, \
    DEFAULT_HTML_CLEAN_TAGS_TO_KEEP_WITH_EXTRA_CONTENTS, \
    DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP_WITH_INCREMENTAL_ID

ACTION_TYPE_WEBPAGE_MAKE_ANSWER = 'Webpage.MakeAnswer'
DEFAULT_WEBPAGE_MAKE_ANSWER_ACTION_ARGS_FIELD_NAME_USER_INPUT = 'Query'


@attrs
class WebPageMakeAnswerActor(AgentActor):
    target_action_type: str = attrib(default=ACTION_TYPE_WEBPAGE_MAKE_ANSWER)
    task_input_field_name_task_input: str = attrib(default=DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_TASK_INPUT)
    task_input_field_name_user_input: str = attrib(default=DEFAULT_WEB_AGENT_TASK_INPUT_FIELD_NAME_USER_INPUT)
    action_args_field_name_user_input: str = attrib(
        default=DEFAULT_WEBPAGE_MAKE_ANSWER_ACTION_ARGS_FIELD_NAME_USER_INPUT
    )

    def get_actor_input(
            self,
            action_results: Sequence,
            task_input: Any,
            action_type: str,
            action_target: str = None,
            action_args: Mapping = None,
            attachments: Sequence = None
    ):
        # region STEP1: gets the last WebDriverActionResult from `action_results`

        # This special action assumes the `action_results` should contain at least one WebDriverActionResult,
        # and we assume the last WebDriverActionResult contains webpage source where we can make answers to user requests
        last_web_driver_action_result: WebDriverActionResult = last_(
            action_results,
            cond=lambda x: isinstance(x, WebDriverActionResult)
        )

        if last_web_driver_action_result is None:
            raise ValueError(f"'action_results' must contain at least one WebDriverActionResult; got {action_results}")
        # endregion

        # region STEP2: gets cleaned webpage source with media contents
        cleaned_webpage_source_with_media_contents: str = clean_html(
            last_web_driver_action_result.body_html_after_last_action,
            tags_to_always_remove=DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP_WITH_EXTRA_CONTENTS,
            attributes_to_keep=DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP_WITH_INCREMENTAL_ID,
            keep_elements_with_immediate_text=True,
            keep_only_incremental_change=last_web_driver_action_result.is_cleaned_body_html_only_incremental_change,
            html_content_to_compare=last_web_driver_action_result.body_html_before_last_action,
            consider_text_for_comparison=False,
            keep_all_text_in_hierarchy_for_incremental_change=True,
            ignore_attrs_for_comparison=(ATTR_NAME_INCREMENTAL_ID,)
        )
        # endregion

        # region STEP3: create actor input
        user_input = action_args[self.action_args_field_name_user_input]

        actor_input = {
            self.task_input_field_name_task_input: cleaned_webpage_source_with_media_contents,
            self.task_input_field_name_user_input: user_input
        }

        if isinstance(task_input, Dict):
            for key, value in task_input.items():
                if key not in actor_input:
                    actor_input[key] = value

        return actor_input

        # endregion
