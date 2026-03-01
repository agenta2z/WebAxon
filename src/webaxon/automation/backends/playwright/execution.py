"""
Playwright action execution implementations.

This module contains action execution and orchestration functions for the Playwright backend.
"""

import logging
from time import sleep
from typing import Any, List, Mapping, Optional, Sequence, TYPE_CHECKING

from webaxon.automation.backends.exceptions import UnsupportedOperationError
from .shims import PlaywrightElementShim

if TYPE_CHECKING:
    from .playwright_backend import PlaywrightBackend

_logger = logging.getLogger(__name__)


def execute_single_action(
    backend: 'PlaywrightBackend',
    element: Any,
    action_type: str,
    action_args: Optional[Mapping] = None,
    attachments: Optional[Sequence] = None,
    timeout: int = 20,
    additional_wait_time: float = 2.0
) -> Optional[str]:
    """Execute a single action on an element.

    Args:
        backend: The PlaywrightBackend instance
        element: The element to perform the action on
        action_type: Type of action (click, input_text, scroll, etc.)
        action_args: Arguments for the action
        attachments: Optional attachments
        timeout: Timeout for page loading
        additional_wait_time: Additional wait time after action

    Returns:
        Action result (for get_text, get_html) or None
    """
    action_args = dict(action_args) if action_args else {}
    action_type = action_type.lower()

    if action_type == 'click':
        backend.click_element(element, **action_args)
    elif action_type == 'input_text':
        text = action_args.pop('text', '')
        clear = action_args.pop('clear_content', False)
        backend.input_text(element, text, clear_content=clear, **action_args)
    elif action_type == 'scroll':
        direction = action_args.pop('direction', 'Down')
        distance = action_args.pop('distance', 'Large')
        backend.scroll_element(element, direction=direction, distance=distance, **action_args)
    elif action_type == 'get_text':
        return backend.get_element_text(element)
    elif action_type == 'get_html':
        return backend.get_element_html(element)
    elif action_type == 'hover':
        if isinstance(element, PlaywrightElementShim):
            element.hover()
        else:
            element.hover()
    elif action_type == 'focus':
        if isinstance(element, PlaywrightElementShim):
            element.focus()
        else:
            element.focus()
    elif action_type == 'clear':
        if isinstance(element, PlaywrightElementShim):
            element.clear()
        else:
            element.clear()
    elif action_type == 'visit_url':
        # element is the URL string for visit_url action
        url = element if isinstance(element, str) else str(element)
        try_open_in_new_tab = action_args.get('try_open_in_new_tab', False)
        wait_after = action_args.get('wait_after_opening_url', 0)

        _logger.debug(
            f"[execute_single_action] visit_url: "
            f"url={url}, try_open_in_new_tab={try_open_in_new_tab}, "
            f"BEFORE: backend._page.url={backend._page.url}"
        )

        if try_open_in_new_tab:
            # Open URL in a new tab
            new_page = backend._context.new_page()
            # Apply stealth scripts to new page if enabled
            if getattr(backend, '_stealth_enabled', False):
                backend._apply_stealth_scripts(new_page)
            new_page.goto(url)
            _logger.debug(
                f"[execute_single_action] visit_url: "
                f"new_page created, new_page.url={new_page.url}"
            )
            # Switch to the new page and register it with the shim
            backend._page = new_page
            backend._driver_shim._page = new_page
            # CRITICAL: Register the new page so it gets a window handle
            backend._driver_shim._register_page(new_page)
            _logger.debug(
                f"[execute_single_action] visit_url: "
                f"AFTER update: backend._page.url={backend._page.url}, "
                f"shim._page.url={backend._driver_shim._page.url}, "
                f"same_page={backend._page is backend._driver_shim._page}"
            )
        else:
            backend._page.goto(url)

        if wait_after > 0:
            sleep(wait_after)
    else:
        raise UnsupportedOperationError(
            operation=action_type,
            backend_type='playwright',
            message=f"Action type '{action_type}' is not supported",
        )

    backend.wait_for_page_loading(timeout=timeout)
    if additional_wait_time > 0:
        sleep(additional_wait_time)

    return None


def execute_composite_action(
    backend: 'PlaywrightBackend',
    elements: List[Any],
    action_config,  # WebAgentAction from webaxon.automation.schema
    action_args: Optional[Mapping] = None,
    attachments: Optional[Sequence] = None,
    timeout: int = 20,
    additional_wait_time: float = 2.0
) -> None:
    """Execute a composite action by decomposing it into multiple sub-actions.

    This method is the Playwright-compatible implementation of composite action execution.
    It handles composite actions made up of multiple sequential sub-actions.

    Args:
        backend: The PlaywrightBackend instance
        elements: List of resolved elements corresponding to element IDs in action_target
        action_config: WebAgentAction configuration defining the composite action steps
        action_args: Arguments to pass to sub-actions (typically only for input-type actions)
        attachments: Attachments to pass to sub-actions (typically only for input-type actions)
        timeout: Timeout for each sub-action
        additional_wait_time: Additional wait time after each sub-action

    Raises:
        ValueError: If composite_steps references invalid element indices or unsupported composite mode
    """
    # Check composite action mode
    composite_action = action_config.composite_action
    if composite_action is None:
        raise ValueError(
            f"Action '{action_config.name}' is not a composite action (composite_action is None)."
        )

    # Handle both old enum format and new CompositeActionConfig format
    if hasattr(composite_action, 'mode'):
        mode = composite_action.mode
    elif hasattr(composite_action, 'value'):
        mode = composite_action.value
    else:
        mode = str(composite_action)

    if mode != "sequential":
        raise ValueError(
            f"Unsupported composite action mode: {mode}. "
            f"Only 'sequential' is currently supported."
        )

    if not action_config.composite_steps:
        raise ValueError(
            f"Composite action '{action_config.name}' has no composite_steps defined."
        )

    # Execute each step defined in composite_steps
    for step_action_type, element_index in action_config.composite_steps:
        if element_index >= len(elements):
            raise ValueError(
                f"Composite action '{action_config.name}' step references element_index {element_index}, "
                f"but only {len(elements)} elements were provided."
            )

        step_element = elements[element_index]

        # Extract action-specific arguments using prefix (e.g., 'input_text_text')
        step_action_args = _extract_action_specific_args(step_action_type, action_args)

        execute_single_action(
            backend=backend,
            element=step_element,
            action_type=step_action_type,
            action_args=step_action_args if step_action_args else None,
            attachments=attachments,
            timeout=timeout,
            additional_wait_time=additional_wait_time
        )


def _extract_action_specific_args(action_type: str, all_action_args: Optional[Mapping]) -> Mapping:
    """Extract action-specific arguments from a mapping containing args for multiple actions.

    Supports prefixed args format: 'input_text_text' -> 'text' for input_text action

    Args:
        action_type: The action type to extract args for (e.g., 'input_text', 'click')
        all_action_args: Dictionary containing all action args

    Returns:
        Dictionary containing only the args for the specified action type, with prefixes removed
    """
    if not all_action_args:
        return {}

    action_specific_args = {}
    prefix = f"{action_type}_"

    for key, value in all_action_args.items():
        if key.startswith(prefix):
            # Remove prefix to get the actual parameter name
            param_name = key[len(prefix):]
            action_specific_args[param_name] = value

    return action_specific_args


def execute_actions(
    backend: 'PlaywrightBackend',
    actions: Mapping,
    init_cond: Any = None,
    repeat: int = 0,
    repeat_when: Any = None,
    elements_dict: Any = None,
    output_path_action_records: Optional[str] = None,
    **kwargs
) -> None:
    """Execute a sequence of actions with conditions.

    This implementation mirrors Selenium's execute_actions for compatibility.

    Args:
        backend: The PlaywrightBackend instance
        actions: Sequence of action dictionaries with keys:
            - 'action_name': The action type to execute
            - 'action_target': Element target (optional)
            - 'action_args': Arguments for the action (optional)
            - 'init_cond': Initial condition to check before executing (optional)
            - 'repeat': Number of times to repeat the action (optional)
            - 'repeat_when': Condition to check for repeating (optional)
            - 'screenshot': Whether to take screenshots (optional)
        init_cond: Initial condition for the entire sequence (bool or condition dict)
        repeat: Number of times to repeat the entire sequence
        repeat_when: Condition for repeating the entire sequence
        elements_dict: Dictionary of pre-resolved elements
        output_path_action_records: Path to save action records
    """
    from os import path as os_path

    try:
        from rich_python_utils.common_utils import iter__
        from rich_python_utils.common_utils.workflow import Repeat
        from rich_python_utils.datetime_utils.common import random_sleep
        from rich_python_utils.io_utils.json_io import write_json_objs
        from rich_python_utils.io_utils.text_io import write_all_text
        from rich_python_utils.path_utils.common import ensure_dir_existence
    except ImportError as e:
        raise ImportError(
            f"execute_actions requires rich_python_utils package: {e}"
        ) from e

    try:
        from webaxon.automation.configs.task_config import (
            FIELD_NAME_TASK_CONFIG_ACTION_INIT_COND,
            FIELD_NAME_TASK_CONFIG_ACTION_ARGS,
            FIELD_NAME_TASK_CONFIG_ACTION_TARGET,
            FIELD_NAME_TASK_CONFIG_ACTION_NAME,
            FIELD_NAME_TASK_CONFIG_ACTION_REPEAT_COND,
            FIELD_NAME_TASK_CONFIG_ACTION_REPEAT,
            FIELD_NAME_TASK_CONFIG_ACTION_SCREENSHOT,
        )
    except ImportError:
        # Fallback to hardcoded values if config module not available
        FIELD_NAME_TASK_CONFIG_ACTION_NAME = 'action_name'
        FIELD_NAME_TASK_CONFIG_ACTION_TARGET = 'action_target'
        FIELD_NAME_TASK_CONFIG_ACTION_ARGS = 'action_args'
        FIELD_NAME_TASK_CONFIG_ACTION_INIT_COND = 'init_cond'
        FIELD_NAME_TASK_CONFIG_ACTION_REPEAT_COND = 'repeat_when'
        FIELD_NAME_TASK_CONFIG_ACTION_REPEAT = 'repeat'
        FIELD_NAME_TASK_CONFIG_ACTION_SCREENSHOT = 'screenshot'

    def _check_conditions(conditions: Any) -> bool:
        """Check if conditions are met."""
        if conditions is None:
            return True
        if isinstance(conditions, bool):
            return conditions
        if isinstance(conditions, dict):
            # Simple element existence check
            for key, value in conditions.items():
                if key in ('exists', 'element_exists'):
                    try:
                        locator = backend._page.locator(value) if isinstance(value, str) else value
                        return locator.count() > 0
                    except Exception:
                        return False
                elif key in ('visible', 'element_visible'):
                    try:
                        locator = backend._page.locator(value) if isinstance(value, str) else value
                        return locator.is_visible()
                    except Exception:
                        return False
                elif key == 'not_exists':
                    try:
                        locator = backend._page.locator(value) if isinstance(value, str) else value
                        return locator.count() == 0
                    except Exception:
                        return True
            return True
        if callable(conditions):
            return conditions()
        return True

    def _find_element(target: Any) -> Any:
        """Find element from target specification."""
        if target is None:
            return None
        if isinstance(target, str):
            # Try as XPath first, then CSS
            if target.startswith('//') or target.startswith('('):
                return backend.find_element('xpath', target)
            else:
                return backend.find_element('css selector', target)
        if elements_dict and isinstance(target, str) and target in elements_dict:
            return elements_dict[target]
        return target

    def _execute_actions_inner(
        inner_actions: Mapping,
        inner_output_path: Optional[str] = None
    ):
        """Execute the inner action loop."""
        action_records = [] if inner_output_path else None

        for action_index, action in enumerate(inner_actions):
            if inner_output_path:
                output_path_action_root = ensure_dir_existence(
                    os_path.join(inner_output_path, f'action_{action_index}')
                )
                action_records_jobj = {'action_index': action_index}

            action_name = action[FIELD_NAME_TASK_CONFIG_ACTION_NAME]
            action_target = action.get(FIELD_NAME_TASK_CONFIG_ACTION_TARGET, None)
            action_args = action.get(FIELD_NAME_TASK_CONFIG_ACTION_ARGS, None)
            action_cond = action.get(FIELD_NAME_TASK_CONFIG_ACTION_INIT_COND, None)
            action_repeat_when = action.get(FIELD_NAME_TASK_CONFIG_ACTION_REPEAT_COND, None)
            action_repeat = action.get(
                FIELD_NAME_TASK_CONFIG_ACTION_REPEAT,
                int(not bool(action_repeat_when))
            )
            action_screenshot = action.get(FIELD_NAME_TASK_CONFIG_ACTION_SCREENSHOT, True)

            action_repeat_obj = Repeat(
                repeat=action_repeat,
                repeat_cond=lambda: _check_conditions(action_repeat_when),
                init_cond=(True if action_cond is None else lambda: _check_conditions(action_cond))
            )

            while action_repeat_obj:
                if inner_output_path:
                    base_action_records_jobj = action_records_jobj.copy()
                    base_action_records_jobj['action_repeat_index'] = action_repeat_obj.index

                for action_target_index, _action_target in enumerate(
                    iter__(action_target, iter_none=True)
                ):
                    element = _find_element(_action_target)

                    if inner_output_path:
                        # Save HTML before action
                        output_path_html = os_path.join(
                            output_path_action_root,
                            f'html_before_action-target_{action_target_index}-repeat_{action_repeat_obj.index}.html'
                        )
                        write_all_text(backend.get_body_html(return_dynamic_contents=True), output_path_html)

                        # Take screenshot before action
                        if action_screenshot:
                            output_path_screenshot = os_path.join(
                                output_path_action_root,
                                f'screenshot_before_action-target_{action_target_index}-repeat_{action_repeat_obj.index}.png'
                            )
                            backend.capture_full_page_screenshot(output_path_screenshot, center_element=element)

                    # Execute the action
                    action_result = execute_single_action(
                        backend=backend,
                        element=element,
                        action_type=action_name,
                        action_args=action_args,
                        **kwargs
                    )

                    if inner_output_path:
                        _action_records_jobj = base_action_records_jobj.copy()
                        if _action_target is not None:
                            _action_records_jobj['action_target_index'] = action_target_index
                            _action_records_jobj['action_target'] = _action_target
                        if element is not None:
                            _action_records_jobj['action_target_element'] = backend.get_element_html(element)
                        if action_result is not None:
                            _action_records_jobj['action_result'] = action_result
                        action_records.append(_action_records_jobj)

                    random_sleep(0.3, 2)

        if inner_output_path and action_records:
            write_json_objs(
                action_records,
                os_path.join(inner_output_path, 'action_records.jsonl')
            )

    # Main repeat loop
    repeat_obj = Repeat(
        repeat=repeat,
        repeat_cond=lambda: _check_conditions(repeat_when),
        init_cond=(True if init_cond is None else lambda: _check_conditions(init_cond))
    )

    while repeat_obj:
        _execute_actions_inner(
            inner_actions=actions,
            inner_output_path=(
                None if output_path_action_records is None
                else os_path.join(output_path_action_records, f'iteration_{repeat_obj.index}')
            )
        )
