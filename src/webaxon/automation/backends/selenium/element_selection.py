from enum import Enum
from typing import Optional, Mapping, Any, Sequence, Tuple

from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from rich_python_utils.common_utils import promote_keys, get_relevant_named_args
from webaxon.html_utils.element_identification import get_xpath, ATTR_NAME_INCREMENTAL_ID
from webaxon.html_utils.common import is_html_string, get_tag_text_and_attributes_from_element
from .types import ElementDict


def find_element_by_xpath(
        driver,
        tag_name: Optional[str] = '*',
        attributes: Mapping[str, Any] = None,
        text: str = None,
        immediate_text: str = None
):
    xpath = get_xpath(
        tag_name=tag_name,
        attributes=attributes,
        text=text,
        immediate_text=immediate_text
    )
    return driver.find_element(By.XPATH, xpath)


def find_elements_by_xpath(
        driver,
        tag_name: Optional[str] = '*',
        attributes: Mapping[str, Any] = None,
        text: str = None,
        immediate_text: str = None
):
    xpath = get_xpath(
        tag_name=tag_name,
        attributes=attributes,
        text=text,
        immediate_text=immediate_text
    )
    return driver.find_elements(By.XPATH, xpath)


def add_unique_index_to_elements(driver, index_name=None):
    """
    Adds a unique index to each HTML element on the current page loaded in Selenium WebDriver.

    Args:
        driver (webdriver): A Selenium WebDriver instance with a page already loaded.
        index_name (str): The attribute name to use for the index. Defaults to ATTR_NAME_INCREMENTAL_ID ('__id__').
    """
    if index_name is None:
        index_name = ATTR_NAME_INCREMENTAL_ID

    # JavaScript to add a unique index to each element
    script = f"""
    let elements = document.getElementsByTagName('*');
    for (let i = 0; i < elements.length; i++) {{
        elements[i].setAttribute('{index_name}', i);
    }}
    """
    driver.execute_script(script)


def find_element_by_unique_index(driver, index_value: str, index_name: str = None) -> WebElement:
    """
    Find an element by its unique index attribute (e.g., __id__).

    This is the primary method for locating elements that have been indexed
    using add_unique_index_to_elements().

    Args:
        driver: A Selenium WebDriver instance.
        index_value: The value of the index attribute to search for (e.g., "42").
        index_name: The attribute name to search by. Defaults to ATTR_NAME_INCREMENTAL_ID ('__id__').

    Returns:
        The WebElement with the matching index attribute.

    Raises:
        NoSuchElementException: If no element with the given index is found.

    Example:
        >>> add_unique_index_to_elements(driver)  # Inject __id__ attributes
        >>> element = find_element_by_unique_index(driver, "42")  # Find element with __id__="42"
    """
    if index_name is None:
        index_name = ATTR_NAME_INCREMENTAL_ID

    return driver.find_element(By.XPATH, f"//*[@{index_name}='{index_value}']")


def find_element_by_html(driver, target_element_html: str, identifying_attributes=('id', 'aria-label', 'class'), always_return_single_element: bool = False):
    """
    Finds an element by an HTML snippet, using a combination of tag name, text content, and attributes.
    The function first tries to find elements by tag name and text. If multiple elements are found,
    it progressively filters these elements by their attributes until one unique element remains or
    no elements match the criteria.

    This approach is useful when an element's identification requires more than a simple selector,
    and when precision is needed to single out an element among many with similar attributes.

    Args:
        driver: A Selenium WebDriver instance used to interact with the web page.
        target_element_html: A string representing an HTML snippet of the target element.

    Returns:
        The first web element that uniquely matches the generated criteria or None if no such element is found.
    """
    tag_name, text, attributes = get_tag_text_and_attributes_from_element(target_element_html)
    elements = find_elements_by_xpath(driver=driver, tag_name=tag_name, text=text)

    if len(elements) == 1:
        return elements[0]
    elif not elements:
        elements = find_elements_by_xpath(driver=driver, tag_name=tag_name)
        if len(elements) == 1:
            return elements[0]
        elif not elements:
            return None

    attributes = promote_keys(attributes, keys_to_promote=identifying_attributes)

    for attr, target_attr_values in attributes.items():
        if isinstance(target_attr_values, str):
            target_attr_values = target_attr_values.split()
        elem_attr_values = []
        for elem in elements:
            values = elem.get_attribute(attr)
            if values is not None:
                elem_attr_values.append((elem, values.split()))

        if len(elem_attr_values) == 1:
            return elem_attr_values[0][0]
        elif len(elem_attr_values) == 0:
            return None

        _elem_attr_values = elem_attr_values
        for single_target_attr_value in target_attr_values:
            _elem_attr_values = [
                (elem, attr_values) for elem, attr_values in _elem_attr_values
                if single_target_attr_value in attr_values
            ]
            if len(_elem_attr_values) == 1:
                return _elem_attr_values[0][0]
            elif len(_elem_attr_values) == 0:
                if attr in identifying_attributes:
                    return None
                else:
                    break
        if _elem_attr_values:
            elem_attr_values = _elem_attr_values

        elements = [elem for elem, attr_values in elem_attr_values]

    if always_return_single_element:
        return elements[0]
    else:
        return elements


class TargetTypes(Enum):
    ID = "id"
    XPATH = "xpath"
    HTML = "html"


def get_find_elements_target_type(target: str) -> Tuple[TargetTypes, str]:
    target_type_set = False
    target_type = TargetTypes.ID

    for target_type in TargetTypes:
        if target.startswith(f'{target_type.value}:'):
            target = target[(len(target_type.value) + 1):]
            target_type_set = True
            break

    if not target_type_set:
        if is_html_string(target):
            target_type = TargetTypes.HTML
        elif target[0] == '/':
            target_type = TargetTypes.XPATH
        else:
            target_type = TargetTypes.ID

    return target_type, target


def _find_element(driver, target: str, **kwargs) -> WebElement:
    target_type, target = get_find_elements_target_type(target)

    if target_type == TargetTypes.XPATH:
        return driver.find_element(By.XPATH, target)
    elif target_type == TargetTypes.ID:
        return driver.find_element(By.ID, target)
    else:
        return find_element_by_html(
            driver=driver,
            target_element_html=target,
            always_return_single_element=True,
            **get_relevant_named_args(
                find_element_by_html,
                exclusion=['target_element_html', 'always_return_single_element'],
                **kwargs
            )
        )


def _find_elements(driver, target: str, explicit_multiple_elements: bool = False, **kwargs) -> Sequence[WebElement]:
    if explicit_multiple_elements and target[0] != '*':
        element = _find_element(driver, target, **kwargs)
        if element is not None:
            return [element]
    else:
        target_type, target = get_find_elements_target_type(target)

        if target_type == TargetTypes.XPATH:
            return driver.find_elements(By.XPATH, target)
        elif target_type == TargetTypes.ID:
            return driver.find_elements(By.ID, target)
        else:
            elements = find_element_by_html(
                driver=driver,
                target_element_html=target,
                **get_relevant_named_args(
                    find_element_by_html, **kwargs
                )
            )

            if isinstance(elements, WebElement):
                return [elements]
            else:
                return elements


def find_element(
        driver: WebDriver,
        target: str,
        elements_dict: ElementDict = None,
        **kwargs
) -> Optional[WebElement]:
    if target:
        if target in elements_dict:
            target_key = target
            target = elements_dict[target]
            if isinstance(target, str):
                element = _find_element(driver, target, **kwargs)
                if element is not None:
                    elements_dict[target_key] = [element]
            else:
                element = target[0]
        else:
            element = _find_element(driver, target, **kwargs)
        return element


def find_elements(
        driver: WebDriver,
        target: str,
        explicit_multiple_elements: bool = False,
        elements_dict: ElementDict = None,
        **kwargs
) -> Optional[Sequence[WebElement]]:
    if target:
        if target in elements_dict:
            target_key = target
            target = elements_dict[target]
            if isinstance(target, str):
                elements = _find_elements(
                    driver=driver,
                    target=target,
                    explicit_multiple_elements=explicit_multiple_elements,
                    **kwargs
                )
                if elements is not None:
                    elements_dict[target_key] = elements
            else:
                elements = target
        else:
            elements = _find_elements(driver, target, **kwargs)
        return elements
