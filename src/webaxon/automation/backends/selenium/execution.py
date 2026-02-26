from os import path
from typing import Mapping, Union

from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from rich_python_utils.common_utils import iter__
from rich_python_utils.common_utils.workflow import Repeat
from rich_python_utils.io_utils.json_io import write_json_objs
from rich_python_utils.io_utils.text_io import write_all_text
from rich_python_utils.path_utils.common import ensure_dir_existence

from rich_python_utils.datetime_utils.common import random_sleep
from webaxon.automation.configs.task_config import FIELD_NAME_TASK_CONFIG_ACTION_INIT_COND, FIELD_NAME_TASK_CONFIG_ACTION_ARGS, FIELD_NAME_TASK_CONFIG_ACTION_TARGET, FIELD_NAME_TASK_CONFIG_ACTION_NAME, FIELD_NAME_TASK_CONFIG_ACTION_REPEAT_COND, FIELD_NAME_TASK_CONFIG_ACTION_REPEAT, FIELD_NAME_TASK_CONFIG_ACTION_SCREENSHOT
from .actions import send_keys_with_random_delay, capture_full_page_screenshot, open_url
from .conditions import check_elements
from .element_selection import find_element
from .types import ElementDict, ElementConditions
from .common import get_element_html, get_body_html, get_element_text, wait_for_page_loading




def _execute_actions(
        driver: WebDriver,
        actions: Mapping,
        elements_dict: ElementDict = None,
        output_path_action_records: str = None,
        **kwargs
):
    if output_path_action_records:
        action_records = []

    for action_index, action in enumerate(actions):
        if output_path_action_records:
            output_path_action_root = ensure_dir_existence(
                path.join(output_path_action_records, f'action_{action_index}')
            )
            action_records_jobj = {'action_index': action_index}

        action_name = action[FIELD_NAME_TASK_CONFIG_ACTION_NAME]
        action_target = action.get(FIELD_NAME_TASK_CONFIG_ACTION_TARGET, None)
        action_args = action.get(FIELD_NAME_TASK_CONFIG_ACTION_ARGS, None)
        action_cond = action.get(FIELD_NAME_TASK_CONFIG_ACTION_INIT_COND, None)
        action_repeat_when = action.get(FIELD_NAME_TASK_CONFIG_ACTION_REPEAT_COND, None)
        action_repeat = action.get(FIELD_NAME_TASK_CONFIG_ACTION_REPEAT, int(not bool(action_repeat_when)))
        action_screenshot = action.get(FIELD_NAME_TASK_CONFIG_ACTION_SCREENSHOT, True)
        repeat = Repeat(
            repeat=action_repeat,
            repeat_cond=lambda: check_elements(driver=driver, conditions=action_repeat_when, elements_dict=elements_dict),
            init_cond=(True if action_cond is None else lambda: check_elements(driver=driver, conditions=action_cond, elements_dict=elements_dict))
        )

        while repeat:

            base_action_records_jobj = action_records_jobj.copy()
            base_action_records_jobj['action_repeat_index'] = repeat.index

            for action_target_index, _action_target in enumerate(iter__(action_target, iter_none=True)):
                element = find_element(driver, _action_target, elements_dict=elements_dict, **kwargs)

                if output_path_action_records:
                    output_path_html_before_action = path.join(output_path_action_root, f'html_before_action-target_{action_target_index}-repeat_{repeat.index}.html')
                    write_all_text(get_body_html(driver, return_dynamic_contents=True), output_path_html_before_action)
                    if action_screenshot:
                        output_path_screenshot_before_action = path.join(output_path_action_root, f'screenshot_before_action-target_{action_target_index}-repeat_{repeat.index}.png')
                        capture_full_page_screenshot(driver, output_path_screenshot_before_action, center_element=element)

                action_result = execute_single_action(driver, element, action_name, action_args)

                if output_path_action_records:
                    _action_records_jobj = base_action_records_jobj.copy()
                    if _action_target is not None:
                        _action_records_jobj['action_target_index'] = action_target_index
                        _action_records_jobj['action_target'] = _action_target
                    if element is not None:
                        _action_records_jobj['action_target_element'] = get_element_html(element)
                    if action_result is not None:
                        _action_records_jobj['action_result'] = action_result
                    action_records.append(_action_records_jobj)

                random_sleep(0.3, 2)

    if output_path_action_records:
        write_json_objs(
            action_records,
            path.join(output_path_action_records, 'action_records.jsonl')
        )


def execute_actions(
        driver: WebDriver,
        actions: Mapping,
        init_cond: Union[bool, ElementConditions] = None,
        repeat: int = 0,
        repeat_when: ElementConditions = None,
        elements_dict: ElementDict = None,
        output_path_action_records: str = None,
        **kwargs
):
    repeat = Repeat(
        repeat=repeat,
        repeat_cond=lambda: check_elements(driver=driver, conditions=repeat_when, elements_dict=elements_dict),
        init_cond=(True if init_cond is None else lambda: check_elements(driver=driver, conditions=init_cond, elements_dict=elements_dict))
    )

    while repeat:
        _execute_actions(
            driver=driver,
            actions=actions,
            elements_dict=elements_dict,
            output_path_action_records=(
                None if output_path_action_records is None
                else path.join(output_path_action_records, f'iteration_{repeat.index}')
            ),
            **kwargs
        )


# Import execute_single_action from actions module for use in _execute_actions
from .actions import execute_single_action
