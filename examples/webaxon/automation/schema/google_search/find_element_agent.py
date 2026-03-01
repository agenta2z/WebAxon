"""
Factory function to create element finder callable.

Creates a closure that resolves natural language element descriptions
to __id__ attribute values using LLM inference.

Interface (called by monitor.py _resolve_agent_target):
    result = find_agent(user_input="...", options=['static'])
    element_id = result.output if hasattr(result, 'output') else result

Example:
    >>> from find_element_agent import create_find_element_callable
    >>> from agent_foundation.common.inferencers.templated_inferencer import TemplatedInferencer
    >>>
    >>> find_element = create_find_element_callable(
    ...     webdriver=webdriver,
    ...     inferencer=templated_inferencer,
    ... )
    >>> element_id = find_element(user_input="the search input box")
    >>> print(element_id)  # "42"
"""

import re
from typing import Any, List, Optional, TYPE_CHECKING

from webaxon.html_utils.sanitization import (
    clean_html,
    DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP_WITH_INCREMENTAL_ID,
)

if TYPE_CHECKING:
    from agent_foundation.common.inferencers.templated_inferencer import TemplatedInferencer


def create_find_element_callable(
    webdriver: Any,
    inferencer: 'TemplatedInferencer',
    max_html_length: int = 50000
):
    """
    Factory function that creates a callable for finding elements via LLM.

    The returned closure:
    1. Gets sanitized HTML from current page (with __id__ attributes)
    2. Asks LLM to find element matching the description
    3. Parses and returns the __id__ value

    Args:
        webdriver: WebDriver instance (must have page_source property)
        inferencer: TemplatedInferencer with "find_element" template
        max_html_length: Max HTML chars to send to LLM (default 50000)

    Returns:
        Callable that takes (user_input: str, options: List[str]) and returns element __id__

    Example:
        >>> find_element = create_find_element_callable(webdriver, inferencer)
        >>> element_id = find_element(user_input="the search input box")
        >>> print(element_id)  # "42"
    """

    def _get_sanitized_html() -> str:
        """Get sanitized HTML from current page with __id__ attributes."""
        raw_html = webdriver.page_source
        sanitized = clean_html(
            raw_html,
            attributes_to_keep=DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP_WITH_INCREMENTAL_ID
        )
        if len(sanitized) > max_html_length:
            sanitized = sanitized[:max_html_length] + "\n... [truncated]"
        return sanitized

    def _parse_element_id(response: Any) -> str:
        """
        Parse element __id__ from LLM response.

        Returns:
            The __id__ value extracted from the response

        Raises:
            ValueError: If NOT_FOUND returned or no numeric ID found
        """
        text = str(response).strip()

        # Check for explicit not found
        if "NOT_FOUND" in text.upper():
            raise ValueError("Element not found for the given description")

        # Extract numeric ID (the __id__ value)
        match = re.search(r'\d+', text)
        if match:
            return match.group()

        # If response is already just a number
        if text.isdigit():
            return text

        raise ValueError(f"Could not parse element ID from LLM response: {text}")

    def find_element(
        user_input: str,
        options: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        Find element matching description and return its __id__.

        This function is called by monitor.py _resolve_agent_target() when
        TargetSpec has strategy="agent".

        Args:
            user_input: Natural language description of the element
                        (e.g., "the search input box", "submit button")
            options: Optional hints for element finding (e.g., ['static'] for cacheable)
            **kwargs: Additional arguments (ignored, for interface compatibility)

        Returns:
            The __id__ attribute value of the matching element (as string)

        Raises:
            ValueError: If element not found or response cannot be parsed
        """
        html = _get_sanitized_html()

        response = inferencer(
            "find_element",
            feed={"html": html, "description": user_input, "options": options or []}
        )

        return _parse_element_id(response)

    return find_element
