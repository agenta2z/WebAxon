from collections.abc import MutableMapping
from typing import Mapping, Union

from rich_python_utils.io_utils.json_io import read_json
from webaxon.automation.configs.task_config import FIELD_NAME_TASK_CONFIG_ELEMENTS, FIELD_NAME_TASK_CONFIG_TASKS
from webaxon.automation.backends.selenium.types import ElementDict
from webaxon.automation.web_driver import WebDriver


class TaskRuntime(MutableMapping):
    def __init__(self, task_config: Union[str, Mapping]):
        task_config: Mapping = read_json(task_config)
        self.tasks: Mapping = task_config[FIELD_NAME_TASK_CONFIG_TASKS]
        self.elements: ElementDict = task_config[FIELD_NAME_TASK_CONFIG_ELEMENTS].copy()

    def get_task_config(self, task_name: str) -> Mapping:
        return self.tasks.get(task_name, None)

    def execute_task(
            self,
            task_name: str,
            driver: WebDriver,
            output_path_action_records: str = None
    ):
        task_config = self.get_task_config(task_name)
        if task_config:
            driver.execute_actions(
                elements_dict=self.elements,
                output_path_action_records=output_path_action_records,
                **task_config
            )

    # region exposing `elements` for `Mapping`
    def __getitem__(self, key):
        return self.elements[key]

    def __setitem__(self, key, value):
        self.elements[key] = value

    def __delitem__(self, key):
        del self.elements[key]

    def __iter__(self):
        return iter(self.elements)

    def __len__(self):
        return len(self.elements)

    def __contains__(self, key):
        return key in self.elements

    # endregion
