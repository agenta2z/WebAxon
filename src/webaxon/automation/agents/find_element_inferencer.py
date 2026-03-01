"""
FindElementInferencer - One-inference agent for finding HTML elements via LLM.

This inferencer extends TemplatedInferencer to add:
1. Pre-processing: HTML extraction and sanitization with __id__ injection
2. Post-processing: Parse element ID from LLM response and map back to element

Supports two modes via `inject_unique_index_to_elements` in inference_config (when WebDriver provided):
- True (default): Inject __id__ into live browser DOM, return __id__ for direct lookup
- False: Inject __id__ only in extracted HTML, return xpath for element location

Example with webdriver (injects __id__ into live DOM):
    >>> from webaxon.automation.agents import FindElementInferencer, FindElementInferenceConfig
    >>> from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
    >>> from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
    >>>
    >>> inferencer = FindElementInferencer(
    ...     base_inferencer=ClaudeApiInferencer(max_retry=3),
    ...     template_manager=TemplateManager(templates="path/to/templates/")
    ... )
    >>>
    >>> # Returns __id__ that exists in live browser DOM
    >>> element_id = inferencer(html_source=driver, description="the search input box")
    >>> print(element_id)  # "42"

Example with HTML string:
    >>> # Returns xpath since __id__ only exists in extracted HTML
    >>> xpath = inferencer(html_source="<html>...</html>", description="submit button")
    >>> print(xpath)  # "//button[@type='submit']"
"""

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from attr import attrs, attrib, Factory
from bs4 import BeautifulSoup

from agent_foundation.common.inferencers.templated_inferencer import TemplatedInferencer

if TYPE_CHECKING:
    from webaxon.automation.web_driver import WebDriver
from webaxon.html_utils.sanitization import (
    clean_html,
    DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP_WITH_INCREMENTAL_ID,
)
from webaxon.html_utils.element_identification import (
    ATTR_NAME_INCREMENTAL_ID,
    add_unique_index_to_html,
    elements_to_xpath,
)
from webaxon.automation.backends.selenium.element_selection import add_unique_index_to_elements


@attrs
class FindElementInferenceConfig:
    """
    Configuration for FindElementInferencer inference.

    Attributes:
        inject_unique_index_to_elements: Only applies when WebDriver is provided.
            - True (default): Inject __id__ into live browser DOM via JavaScript,
              then return the __id__ for direct element lookup.
            - False: Only inject __id__ into extracted HTML string (browser DOM
              unchanged), then map back to element via xpath.
        options: Optional hints for element finding passed to LLM template.
            Examples: ['static'] for cacheable elements, ['visible'] for visible only.
    """
    inject_unique_index_to_elements: bool = attrib(default=True)
    options: Optional[List[str]] = attrib(default=None)


def _parse_element_id(response: Any) -> str:
    """
    Parse element __id__ from LLM response.

    Expects response in format: <TargetElementID>42</TargetElementID>
    Extracts from the LAST matching tag if multiple are present.
    Falls back to extracting any numeric ID if tags not found.

    Args:
        response: LLM response text

    Returns:
        The __id__ value extracted from the response

    Raises:
        ValueError: If NOT_FOUND returned or no numeric ID found
    """
    text = str(response).strip()

    # Try to extract from <TargetElementID> tags (take the last match)
    tag_matches = re.findall(r'<TargetElementID>\s*(.+?)\s*</TargetElementID>', text, re.IGNORECASE)
    if tag_matches:
        content = tag_matches[-1].strip()  # Take the last match
        # Check for explicit not found
        if content.upper() == "NOT_FOUND":
            raise ValueError("Element not found for the given description")
        # Return the content if it's numeric
        if content.isdigit():
            return content
        # Try to extract numeric ID from content
        num_match = re.search(r'\d+', content)
        if num_match:
            return num_match.group()

    # Fallback: Check for explicit not found anywhere in response
    if "NOT_FOUND" in text.upper():
        raise ValueError("Element not found for the given description")

    # Fallback: Extract numeric ID (the __id__ value)
    match = re.search(r'\d+', text)
    if match:
        return match.group()

    # If response is already just a number
    if text.isdigit():
        return text

    raise ValueError(f"Could not parse element ID from LLM response: {text}")


@attrs
class FindElementInferencer(TemplatedInferencer):
    """
    One-inference agent for finding HTML elements via LLM.

    Extends TemplatedInferencer to add:
    - Pre-processing: HTML extraction and sanitization with __id__ injection
    - Post-processing: Parse element ID and map back to element (via __id__ or xpath)

    The inferencer is callable - use it like a function:
        element_id = inferencer(driver, description="the search input box")
        xpath = inferencer("<html>...</html>", description="submit button")

    Attributes:
        base_inferencer: Any InferencerBase subclass for LLM calls (inherited)
        template_manager: TemplateManager with "find_element" template (inherited)
        max_html_length: Maximum HTML characters to send to LLM (None = no limit)
        default_template_key: Template key to use (default "find_element")

    Example:
        >>> inferencer = FindElementInferencer(
        ...     base_inferencer=ClaudeApiInferencer(max_retry=3),
        ...     template_manager=TemplateManager(templates="path/to/templates/")
        ... )
        >>> # With webdriver - returns __id__
        >>> element_id = inferencer(html_source=driver, description="submit button")
        >>> # With HTML string - returns xpath
        >>> xpath = inferencer(html_source="<html>...</html>", description="submit button")
        >>> # With custom config
        >>> config = FindElementInferenceConfig(inject_unique_index_to_elements=False)
        >>> xpath = inferencer(html_source=driver, description="button", inference_config=config)
    """
    max_html_length: int = attrib(default=None)
    default_template_key: str = attrib(default="find_element")

    def __call__(
        self,
        template_key: str = None,
        feed: Optional[Dict[str, Any]] = None,
        inference_config: Optional[FindElementInferenceConfig] = None,
        active_template_type: Optional[str] = None,
        active_template_root_space: Optional[str] = None,
        *,
        html_source: Union[str, "WebDriver"] = None,
        description: str = None,
        **kwargs
    ) -> str:
        """
        Find element matching description and return its locator.

        This method follows the base TemplatedInferencer signature while adding
        domain-specific keyword-only parameters for element finding.

        Args:
            template_key: Template key (default: self.default_template_key).
            feed: Feed dict for template. If html_source/description provided,
                  they override feed values.
            inference_config: FindElementInferenceConfig with:
                - inject_unique_index_to_elements: Whether to inject __id__ into live DOM
                - options: Hints for element finding (e.g., ['static'])
            active_template_type: Override template type for this call.
            active_template_root_space: Override template root space for this call.
            html_source: (keyword-only) Either an HTML string or a WebDriver instance.
                - If string: Treated as raw HTML to search in
                - If WebDriver: Extracts HTML from current page
            description: (keyword-only) Natural language description of the element
                         (e.g., "the search input box", "submit button")
            **kwargs: Additional arguments passed to base inferencer

        Returns:
            When WebDriver provided with inject_unique_index_to_elements=True:
                The __id__ attribute value (str) for use with find_element_by_unique_index()
            When WebDriver provided with inject_unique_index_to_elements=False:
                XPath string to locate the element
            When HTML string provided:
                XPath string to locate the element

        Raises:
            ValueError: If element not found or response cannot be parsed
        """
        # Extract html_source/description from feed if not provided directly
        feed = feed or {}
        if html_source is None:
            html_source = feed.get("html_source") or feed.get("html")
        if description is None:
            description = feed.get("description")

        if html_source is None:
            raise ValueError("html_source is required (via keyword arg or feed)")
        if description is None:
            raise ValueError("description is required (via keyword arg or feed)")

        # Use default config if not provided
        config = inference_config or FindElementInferenceConfig()
        options = config.options

        if isinstance(html_source, str):
            # HTML string provided - always use xpath mapping
            return self._find_with_xpath_mapping(html_source, description, options, **kwargs)
        else:
            # WebDriver provided
            if config.inject_unique_index_to_elements:
                return self._find_with_dom_injection(html_source, description, options, **kwargs)
            else:
                return self._find_with_xpath_mapping(html_source.page_source, description, options, **kwargs)

    def _find_with_dom_injection(
        self,
        webdriver: "WebDriver",
        description: str,
        options: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        Find element by injecting __id__ into live browser DOM.

        This approach modifies the actual browser DOM to add __id__ attributes,
        allowing direct element lookup via find_element_by_unique_index().

        Args:
            webdriver: WebDriver instance
            description: Element description
            options: Optional hints
            **kwargs: Additional inferencer args

        Returns:
            The __id__ attribute value for direct lookup
        """
        # Inject __id__ into live browser DOM
        add_unique_index_to_elements(webdriver._backend._driver, index_name=ATTR_NAME_INCREMENTAL_ID)

        # Get and sanitize HTML (now has __id__ in both DOM and extracted HTML)
        raw_html = webdriver.page_source
        sanitized = clean_html(
            raw_html,
            attributes_to_keep=DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP_WITH_INCREMENTAL_ID
        )
        if self.max_html_length is not None and len(sanitized) > self.max_html_length:
            sanitized = sanitized[:self.max_html_length] + "\n... [truncated]"

        # Call LLM to find element
        response = super().__call__(
            self.default_template_key,
            feed={"html": sanitized, "description": description, "options": options or []},
            **kwargs
        )

        # Return __id__ directly (exists in live DOM)
        return _parse_element_id(response)

    def _find_with_xpath_mapping(
        self,
        html: str,
        description: str,
        options: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        Find element by injecting __id__ only in extracted HTML, return xpath.

        This approach does NOT modify the browser DOM. Instead:
        1. Add __id__ to extracted HTML string only
        2. Find element via LLM
        3. Map __id__ back to xpath using elements_to_xpath()

        Args:
            html: Raw HTML string
            description: Element description
            options: Optional hints
            **kwargs: Additional inferencer args

        Returns:
            XPath string to locate the element
        """
        # Add __id__ to extracted HTML only (not in browser DOM)
        html_with_ids = add_unique_index_to_html(html, index_name=ATTR_NAME_INCREMENTAL_ID)

        # Sanitize the HTML (preserves __id__)
        sanitized = clean_html(
            html_with_ids,
            attributes_to_keep=DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP_WITH_INCREMENTAL_ID
        )
        if self.max_html_length is not None and len(sanitized) > self.max_html_length:
            sanitized = sanitized[:self.max_html_length] + "\n... [truncated]"

        # Call LLM to find element
        response = super().__call__(
            self.default_template_key,
            feed={"html": sanitized, "description": description, "options": options or []},
            **kwargs
        )

        # Parse the __id__ from LLM response
        element_id = _parse_element_id(response)

        # Find the element in BeautifulSoup by __id__
        soup = BeautifulSoup(html_with_ids, 'html.parser')
        element = soup.find(attrs={ATTR_NAME_INCREMENTAL_ID: element_id})

        if element is None:
            raise ValueError(f"Element with __id__={element_id} not found in HTML")

        # Generate xpath for the element (excluding __id__ since it doesn't exist in live DOM)
        xpath = elements_to_xpath(
            elements=element,
            html_context=html_with_ids,
            exclude_attrs=(ATTR_NAME_INCREMENTAL_ID,)
        )

        return xpath

    def infer(
        self,
        template_key: str = None,
        feed: Optional[Dict[str, Any]] = None,
        inference_config: Optional[FindElementInferenceConfig] = None,
        active_template_type: Optional[str] = None,
        active_template_root_space: Optional[str] = None,
        *,
        html_source: Union[str, "WebDriver"] = None,
        description: str = None,
        **kwargs
    ) -> str:
        """
        Alias for __call__.

        Args:
            template_key: Template key (default: self.default_template_key).
            feed: Feed dict for template.
            inference_config: FindElementInferenceConfig with inference options.
            active_template_type: Override template type for this call.
            active_template_root_space: Override template root space for this call.
            html_source: (keyword-only) Either an HTML string or a WebDriver instance
            description: (keyword-only) Natural language description of the element
            **kwargs: Additional arguments passed to base inferencer

        Returns:
            Element locator (__id__ or xpath depending on mode)
        """
        return self.__call__(
            template_key=template_key,
            feed=feed,
            inference_config=inference_config,
            active_template_type=active_template_type,
            active_template_root_space=active_template_root_space,
            html_source=html_source,
            description=description,
            **kwargs
        )
