"""
Playwright element selection implementations.

This module contains element finding and resolution functions for the Playwright backend.
"""

import logging
from typing import Any, List, Mapping, Optional, Tuple, TYPE_CHECKING

from webaxon.automation.backends.exceptions import ElementNotFoundError
from webaxon.automation.schema import TargetStrategy
from webaxon.html_utils.element_identification import ATTR_NAME_INCREMENTAL_ID
from .shims import PlaywrightElementShim

if TYPE_CHECKING:
    from .playwright_backend import PlaywrightBackend

_logger = logging.getLogger(__name__)


def find_element_by_xpath(
    backend: 'PlaywrightBackend',
    tag_name: Optional[str] = '*',
    attributes: Optional[Mapping[str, Any]] = None,
    text: Optional[str] = None,
    immediate_text: Optional[str] = None
) -> Any:
    """Find element using XPath with tag, attributes, and text filters.

    Args:
        backend: The PlaywrightBackend instance
        tag_name: HTML tag name to match
        attributes: Dictionary of attributes to match
        text: Text content to match
        immediate_text: Immediate text content to match

    Returns:
        PlaywrightElementShim wrapping the found element

    Raises:
        ElementNotFoundError: If element is not found
    """
    from webaxon.html_utils.element_identification import get_xpath
    xpath = get_xpath(
        tag_name=tag_name,
        attributes=attributes,
        text=text,
        immediate_text=immediate_text,
    )
    try:
        locator = backend._page.locator(f"xpath={xpath}").first
        locator.wait_for(timeout=1000)
        return PlaywrightElementShim(locator, backend._page)
    except Exception as e:
        raise ElementNotFoundError(
            strategy='xpath',
            target=f"tag={tag_name}, attributes={attributes}, text={text}",
            message=str(e),
        ) from e


def find_elements_by_xpath(
    backend: 'PlaywrightBackend',
    tag_name: Optional[str] = '*',
    attributes: Optional[Mapping[str, Any]] = None,
    text: Optional[str] = None,
    immediate_text: Optional[str] = None
) -> List[Any]:
    """Find elements using XPath with tag, attributes, and text filters.

    Args:
        backend: The PlaywrightBackend instance
        tag_name: HTML tag name to match
        attributes: Dictionary of attributes to match
        text: Text content to match
        immediate_text: Immediate text content to match

    Returns:
        List of PlaywrightElementShim wrapping the found elements
    """
    from webaxon.html_utils.element_identification import get_xpath
    xpath = get_xpath(
        tag_name=tag_name,
        attributes=attributes,
        text=text,
        immediate_text=immediate_text,
    )
    locators = backend._page.locator(f"xpath={xpath}")
    count = locators.count()
    return [
        PlaywrightElementShim(locators.nth(i), backend._page)
        for i in range(count)
    ]


def resolve_action_target(
    backend: 'PlaywrightBackend',
    strategy: str,
    action_target: str
) -> Any:
    """Resolve element using explicit strategy.

    Args:
        backend: The PlaywrightBackend instance
        strategy: The target resolution strategy (e.g., 'xpath', 'id', '__id__')
        action_target: The target value to resolve

    Returns:
        The resolved element

    Raises:
        ElementNotFoundError: If element is not found
        NotImplementedError: If strategy is not supported
    """
    _logger.debug(f"[resolve_action_target] strategy={strategy}, action_target={action_target}")

    # Normalize strategy
    if hasattr(strategy, 'value'):
        strategy = strategy.value
        _logger.debug(f"[resolve_action_target] Normalized strategy to: {strategy}")

    try:
        if strategy == TargetStrategy.FRAMEWORK_ID.value:  # '__id__'
            _logger.debug(f"[resolve_action_target] Using FRAMEWORK_ID strategy")
            return find_element_by_unique_index(backend, action_target)
        elif strategy == TargetStrategy.ID.value:  # 'id'
            _logger.debug(f"[resolve_action_target] Using ID strategy")
            return backend.find_element('id', action_target)
        elif strategy == TargetStrategy.XPATH.value:  # 'xpath'
            _logger.debug(f"[resolve_action_target] Using XPATH strategy")
            return backend.find_element('xpath', action_target)
        elif strategy in (TargetStrategy.CSS.value, 'css_selector'):  # 'css'
            return backend.find_element('css selector', action_target)
        elif strategy == TargetStrategy.TEXT.value:  # 'text'
            locator = backend._page.locator(f"text={action_target}").first
            return PlaywrightElementShim(locator, backend._page)
        elif strategy == TargetStrategy.SOURCE.value:  # 'source'
            return find_element_by_html(backend, action_target, always_return_single_element=True)
        elif strategy == TargetStrategy.LITERAL.value:  # 'literal'
            return action_target
        elif strategy == TargetStrategy.DESCRIPTION.value:  # 'description'
            raise NotImplementedError(
                "Description-based element resolution is not yet implemented"
            )
        elif strategy == 'name':
            return backend.find_element('name', action_target)
        elif strategy in ('tag', 'tag_name'):
            return backend.find_element('tag_name', action_target)
        elif strategy in ('class', 'class_name'):
            return backend.find_element('class_name', action_target)
        elif strategy == 'link_text':
            return backend.find_element('link_text', action_target)
        elif strategy == 'partial_link_text':
            return backend.find_element('partial_link_text', action_target)
        else:
            raise NotImplementedError(f"Unsupported strategy: {strategy}")
    except Exception as e:
        if isinstance(e, (ElementNotFoundError, NotImplementedError)):
            raise
        raise ElementNotFoundError(
            strategy=strategy,
            target=action_target,
            message=str(e),
        ) from e


def add_unique_index_to_elements(
    backend: 'PlaywrightBackend',
    index_name: Optional[str] = None
) -> None:
    """Inject unique ID attributes to all elements on the page.

    Args:
        backend: The PlaywrightBackend instance
        index_name: Name of the attribute to use for the unique index
    """
    if index_name is None:
        index_name = ATTR_NAME_INCREMENTAL_ID

    script = f"""
    let elements = document.getElementsByTagName('*');
    for (let i = 0; i < elements.length; i++) {{
        elements[i].setAttribute('{index_name}', i);
    }}
    """
    backend._page.evaluate(script)


def find_element_by_unique_index(
    backend: 'PlaywrightBackend',
    index_value: str,
    index_name: Optional[str] = None
) -> Any:
    """Find element by framework-assigned unique index.

    Args:
        backend: The PlaywrightBackend instance
        index_value: The unique index value to find
        index_name: Name of the attribute containing the unique index

    Returns:
        PlaywrightElementShim wrapping the found element

    Raises:
        ElementNotFoundError: If element is not found
    """
    if index_name is None:
        index_name = ATTR_NAME_INCREMENTAL_ID

    try:
        locator = backend._page.locator(f"[{index_name}='{index_value}']").first
        locator.wait_for(timeout=1000)
        return PlaywrightElementShim(locator, backend._page)
    except Exception as e:
        raise ElementNotFoundError(
            strategy='framework_id',
            target=index_value,
            message=str(e),
        ) from e


def find_element_by_html(
    backend: 'PlaywrightBackend',
    target_element_html: str,
    identifying_attributes: Tuple[str, ...] = ('id', 'aria-label', 'class'),
    always_return_single_element: bool = False
) -> Optional[Any]:
    """Find element by HTML snippet.

    Args:
        backend: The PlaywrightBackend instance
        target_element_html: HTML snippet to match
        identifying_attributes: Attributes to use for identification
        always_return_single_element: If True, always return a single element

    Returns:
        PlaywrightElementShim if single element found, list if multiple, None if not found
    """
    from webaxon.html_utils.common import get_tag_text_and_attributes_from_element

    tag_name, text, attributes = get_tag_text_and_attributes_from_element(target_element_html)

    # Build selector from tag and attributes
    selector = tag_name or '*'
    for attr in identifying_attributes:
        if attr in attributes:
            value = attributes[attr]
            if isinstance(value, list):
                value = ' '.join(value)
            selector += f"[{attr}='{value}']"

    locators = backend._page.locator(selector)
    count = locators.count()

    if count == 0:
        return None
    elif count == 1 or always_return_single_element:
        return PlaywrightElementShim(locators.first, backend._page)
    else:
        return [
            PlaywrightElementShim(locators.nth(i), backend._page)
            for i in range(count)
        ]
