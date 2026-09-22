from typing import Dict, Mapping, Sequence, Union

from selenium.webdriver.remote.webelement import WebElement

ElementDict = Dict[str, Union[str, Sequence[WebElement]]]
ElementCondition = Mapping[str, Union[str, Sequence[str]]]
ElementConditions = Union[ElementCondition, Sequence[ElementCondition]]
