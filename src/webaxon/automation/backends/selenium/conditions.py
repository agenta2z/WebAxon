from typing import Union, Sequence

from selenium.webdriver.chrome.webdriver import WebDriver

from rich_python_utils.common_utils import iter__, iter_
from .element_selection import find_element, find_elements
from .types import ElementDict, ElementConditions


def _check_existence_search_single_element(
        driver: WebDriver,
        exists: Union[str, Sequence[str]] = None,
        not_exists: Union[str, Sequence[str]] = None,
        elements_dict: ElementDict = None
):
    if exists:
        if not all(
                find_element(driver, target=exists_target, elements_dict=elements_dict) is not None
                for exists_target in iter__(exists)
        ):
            return False
    if not_exists:
        if any(
                find_element(driver, target=exists_target, elements_dict=elements_dict) is not None
                for exists_target in iter__(exists)
        ):
            return False
    return True


def _check_existence_search_multiple_elements(
        driver: WebDriver,
        exists: Union[str, Sequence[str]] = None,
        not_exists: Union[str, Sequence[str]] = None,
        explicit_multiple_elements: bool = False,
        elements_dict: ElementDict = None
):
    if exists:
        if not all(
                bool(find_elements(
                    driver=driver,
                    target=exists_target,
                    explicit_multiple_elements=explicit_multiple_elements,
                    elements_dict=elements_dict
                )) for exists_target in iter__(exists)
        ):
            return False
    if not_exists:
        if any(
                bool(find_elements(
                    driver=driver,
                    target=exists_target,
                    explicit_multiple_elements=explicit_multiple_elements,
                    elements_dict=elements_dict
                )) for exists_target in iter__(exists)
        ):
            return False
    return True


def _check_element(
        driver: WebDriver,
        exists: Union[str, Sequence[str]] = None,
        not_exists: Union[str, Sequence[str]] = None,
        elements_dict: ElementDict = None,
        **kwargs
) -> bool:
    if kwargs:
        for condition_name, condition_target in kwargs.items():
            reverse = False
            if condition_name.startswith('not_'):
                condition_name = condition_name[4:]
                reverse = True

            for _condition_target in iter__(condition_target):
                element = find_element(driver, target=_condition_target, elements_dict=elements_dict)
                if element is not None and getattr(element, f'is_{condition_name}')(element) == reverse:
                    return False

    return _check_existence_search_single_element(
        driver=driver,
        exists=exists,
        not_exists=not_exists,
        elements_dict=elements_dict
    )


def _check_elements(
        driver: WebDriver,
        exists: Union[str, Sequence[str]] = None,
        not_exists: Union[str, Sequence[str]] = None,
        explicit_multiple_elements: bool = False,
        elements_dict: ElementDict = None,
        **kwargs
) -> bool:
    if kwargs:
        for condition_name, condition_target in kwargs.items():
            reverse = False
            if condition_name.startswith('not_'):
                condition_name = condition_name[4:]
                reverse = True
            if any(
                    getattr(element, f'is_{condition_name}')()
                    for _condition_target in iter__(condition_target)
                    for element in find_elements(
                        driver=driver,
                        target=_condition_target,
                        explicit_multiple_elements=explicit_multiple_elements,
                        elements_dict=elements_dict
                    )
            ) == reverse:
                return False

    if elements_dict:
        return _check_existence_search_multiple_elements(
            driver=driver,
            exists=exists,
            not_exists=not_exists,
            explicit_multiple_elements=explicit_multiple_elements,
            elements_dict=elements_dict
        )
    else:
        return _check_existence_search_single_element(
            driver=driver,
            exists=exists,
            not_exists=not_exists
        )


def check_element(
        driver: WebDriver,
        conditions: ElementConditions,
        elements_dict: ElementDict = None
) -> bool:
    if not conditions:
        return False

    return any(
        _check_element(driver=driver, elements_dict=elements_dict, **condition)
        for condition in iter_(conditions)
    )


def check_elements(
        driver: WebDriver,
        conditions: ElementConditions,
        elements_dict: ElementDict = None
) -> bool:
    if not conditions:
        return False

    return any(
        _check_elements(driver=driver, elements_dict=elements_dict, **condition)
        for condition in iter_(conditions)
    )
