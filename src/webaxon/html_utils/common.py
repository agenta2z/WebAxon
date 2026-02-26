import functools
import re
from copy import deepcopy
from enum import StrEnum
from typing import Tuple, Optional, Mapping, Union, Iterable, List
from urllib.parse import urlparse

import bs4
from bs4 import BeautifulSoup, NavigableString, Tag

from rich_python_utils.common_utils import dedup_chain
from rich_python_utils.string_utils import string_check, dedup_string_list
from rich_python_utils.string_utils.regex import contains_whole_word
from types import MappingProxyType


class ElementInteractionTypes(StrEnum):
    """String-based enum for classifying a link's relationship to the current domain."""
    NO_INTERACTION = "no_interaction"
    SAME_PAGE_ANCHOR_LINK = "same_page_anchor_link"
    SAME_DOMAIN_LINK = "same_domain_link"
    EXTERNAL_DOMAIN_LINK = "external_domain_link"
    SAME_PAGE_INTERACTABLE = "same_page_interactable"
    UNKNOWN_INTERACTABLE = "unknown_interactable"


HTML_STYLE_STRING_REGEX = re.compile(r'^<([a-zA-Z][a-zA-Z0-9]*)[^>]*>.*?</\1>$', re.DOTALL)
HTML_COMMON_NON_INTERACTABLE_TAGS = ('div', 'span', 'p')
HTML_COMMON_LIST_LIKE_ATTRIBUTES = ('class', 'rel')
DEFAULT_HTML_INTERACTIVE_ATTRIBUTES_AND_VALUES = MappingProxyType({
    'role': {
        'button': ElementInteractionTypes.SAME_PAGE_INTERACTABLE,
        'link': ElementInteractionTypes.UNKNOWN_INTERACTABLE
    },
    'jsname': None,
    'data-jsname': None
})


def is_html_string(s: str) -> bool:
    """Check if a string is representing an HTML element (enclosed by a matched pair of HTML tags).

    This function uses a regular expression to determine if a given string
    is enclosed by a matching pair of HTML tags.

    Args:
        s: The input string to check.

    Returns:
        True if the string is enclosed by a matching HTML tag, False otherwise.

    Examples:
        >>> is_html_string("<p>This is a paragraph.</p>")
        True
        >>> is_html_string("<div><p>This is a paragraph.</p></div>")
        True
        >>> is_html_string("<span>Some text</span>")
        True
        >>> is_html_string("<a href='example.com'>Link</a>")
        True
        >>> is_html_string("<p>Nested <span>text</span></p>")
        True
        >>> is_html_string("<div>\\n<p>Text on\\nmultiple lines</p>\\n</div>")
        True
        >>> is_html_string("<div>\\n<p>Text on\\nmultiple lines</p>\\n</span>")
        False
        >>> is_html_string("Just a plain text")
        False
    """
    match = HTML_STYLE_STRING_REGEX.fullmatch(s)
    return match is not None


def parse_html_string(html_string: str):
    """
    Parses an HTML string as an HTML element object (BeautifulSoup).

    Args:
        html_string (str): An HTML string representing an HTML element.

    Returns: The parsed HTML element object.

    Examples:
        >>> html_string = '<div><p>Hello World</p></div>'
        >>> element = parse_html_string(html_string)
        >>> print(element.name)
        div
    """
    soup = BeautifulSoup(html_string, 'html.parser')
    return soup.find()


def copy_html_element_name_and_attrs(element, copy_children: bool = True, recursively_copy_children: bool = True):
    """
    Creates a copy of an HTML element, copying its name and attributes. Optionally, recursively copies its children.

    Args:
        element: The HTML element or text node to copy.
        copy_children (bool, optional): If True, also copies the element's children.
        recursively_copy_children (bool, optional): If True, recursively copies the element's children.
            If False, includes references to the original children without copying, and the original element will lose its children. Defaults to True.
            Only effective if 'copy_children' is True.

    Returns: A copy of the input element with the specified properties.

    Examples:
        >>> from bs4 import BeautifulSoup, NavigableString
        >>> html = '<div id="container"><p class="text">Hello <b>World</b></p></div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> original_element = soup.find('div')

        # Example 1: Recursively copy the element and its children
        >>> copied_element = copy_html_element_name_and_attrs(original_element)
        >>> print(copied_element)
        <div id="container"><p class="text">Hello <b>World</b></p></div>

        # Modifying the copied element does not affect the original
        >>> copied_element['id'] = 'new-container'
        >>> copied_element.p['class'] = 'new-text'
        >>> copied_element.p.b.string.replace_with('Universe')
        'World'
        >>> print(copied_element)
        <div id="new-container"><p class="new-text">Hello <b>Universe</b></p></div>
        >>> print(original_element)
        <div id="container"><p class="text">Hello <b>World</b></p></div>

        # Example 2: Copy only the element's name and attributes, not its children
        >>> copied_element = copy_html_element_name_and_attrs(original_element, recursively_copy_children=False)
        >>> print(copied_element)
        <div id="container"><p class="text">Hello <b>World</b></p></div>

        # The original element lose its children when they are not recursively copied
        >>> print(original_element)
        <div id="container"></div>
    """
    if element is not None:
        new_element = type(element)(
            name=element.name,
            attrs=element.attrs
        )
        if copy_children:
            if recursively_copy_children:
                for child in list(element.children):
                    if isinstance(child, NavigableString):
                        child = NavigableString(child)
                    else:
                        child = copy_html_element_name_and_attrs(child)
                    if child is not None:
                        new_element.append(child)
            else:
                for child in list(element.children):
                    if child is not None:
                        new_element.append(child)

        return new_element


def support_input_html(func):
    """Decorator that ensures the element argument is a BeautifulSoup element.

    If the element is a string, it will be parsed using `parse_html_string` to convert to an HTML element object (BeautifulSoup).
    This decorator only converts the first argument of the decorated function.
    """

    @functools.wraps(func)
    def wrapper(element, *args, **kwargs):
        if isinstance(element, str):
            element = parse_html_string(element)
        return func(element, *args, **kwargs)

    return wrapper


def support_input_html2(func):
    """Decorator that ensures two element arguments are BeautifulSoup elements.

    If the element is a string, it will be parsed using `parse_html_string` to convert to an HTML element object (BeautifulSoup).
    This decorator converts the first two arguments of the decorated function.
    """

    @functools.wraps(func)
    def wrapper(element1, element2, *args, **kwargs):
        if isinstance(element1, str):
            element1 = parse_html_string(element1)
        if isinstance(element2, str):
            element2 = parse_html_string(element2)
        return func(element1, element2, *args, **kwargs)

    return wrapper


def parse_onclick_for_url(onclick_value: str) -> str:
    """
    Attempts to extract a URL from an onclick string if it explicitly navigates somewhere.
    Looks for common patterns like window.open('...') or location.href='...'.
    Returns the URL string if found, otherwise an empty string.
    """
    # Common simple regex patterns to detect a URL in JS calls:
    patterns = [
        r"window\.open\s*\(\s*'([^']+)'",  # window.open('URL')
        r"window\.open\s*\(\s*\"([^\"]+)\"",  # window.open("URL")
        r"location\.href\s*=\s*'([^']+)'",  # location.href='URL'
        r"location\.href\s*=\s*\"([^\"]+)\"",  # location.href="URL"
        r"window\.location\s*=\s*'([^']+)'",  # window.location='URL'
        r"window\.location\s*=\s*\"([^\"]+)\""  # window.location="URL"
    ]
    for pattern in patterns:
        match = re.search(pattern, onclick_value)
        if match:
            return match.group(1)
    return ""


def classify_url_domain(url: str, current_domain: str) -> ElementInteractionTypes:
    """
    Given a URL string (from href or onclick), classify it as:
      - SAME_PAGE_ANCHOR (if just '#something')
      - SAME_DOMAIN
      - EXTERNAL_DOMAIN
    """
    if not url:
        return ElementInteractionTypes.NO_INTERACTION

    # If it's purely an anchor link: e.g. "#section"
    if url.startswith('#'):
        return ElementInteractionTypes.SAME_PAGE_ANCHOR_LINK

    parsed = urlparse(url)
    if not parsed.netloc:
        # No netloc => relative URL => same domain
        return ElementInteractionTypes.SAME_DOMAIN_LINK

    # Compare netloc to the current domain
    if parsed.netloc == current_domain:
        return ElementInteractionTypes.SAME_DOMAIN_LINK
    else:
        return ElementInteractionTypes.EXTERNAL_DOMAIN_LINK


def get_element_interaction_type(
        element,
        current_domain: str,
        interactive_attrs_and_values: Mapping[
            str,
            Union[Iterable, Mapping[str, ElementInteractionTypes], None]
        ] = DEFAULT_HTML_INTERACTIVE_ATTRIBUTES_AND_VALUES,
        element_get_attr_method_name='get',
        element_has_attr_method_name='has_attr'
) -> ElementInteractionTypes:
    """
    Classifies how an element interacts with the current page/domain. Possible outcomes:

    - NO_INTERACTION: No navigational or interactive indication.
    - SAME_PAGE_ANCHOR_LINK: If href='#something'.
    - SAME_DOMAIN_LINK: If the element points to a URL on the same domain (including relative URLs).
    - EXTERNAL_DOMAIN_LINK: If the element points to a different domain.
    - SAME_PAGE_INTERACTABLE: If it's clearly an in-page interactive element (e.g. role="button").
    - UNKNOWN_INTERACTABLE: If there's an 'onclick' we can't parse for a URL, or if the element has
      attributes (e.g. 'jsname', 'data-jsname', or role="link" with no href) that suggest interactivity
      but do not yield a definitive link.

    The function checks, in order:
      1) If the element has an 'href', classify that link.
      2) If there's an 'onclick' that we can parse for a URL (like window.open(...) or location.href='...'),
         classify that.
      3) Otherwise, check each key in `interactive_attrs_and_values`:
         - If the element has that attribute:
           * If the dictionary value is a **dict** of specific mappings:
               e.g. 'role': {'button': SAME_PAGE_INTERACTABLE, 'link': UNKNOWN_INTERACTABLE}
             then if element[role] == 'button', return SAME_PAGE_INTERACTABLE, etc.
           * If the dictionary value is an **iterable** or single string, we check if
             element[attr_key] is in those values; if so, we typically return UNKNOWN_INTERACTABLE
             (unless you add your own logic).
           * If the dictionary value is **None**, the mere presence of that attribute indicates
             UNKNOWN_INTERACTABLE.
      4) Fallback: NO_INTERACTION if nothing else applies.

    Args:
        element:
            The HTML element to check (e.g., <a>, <button>, <div>, etc.).
            We assume it is bs4.element.Tag element by default
            (see also the default values of `element_get_attr_method_name` and `element_has_attr_method_name`).
        current_domain (str):
            The domain (netloc) of the current page (e.g., "example.com").
        interactive_attrs_and_values (Mapping[str, Union[Iterable, Mapping[str, ElementInteractionTypes], None]], optional):
            A mapping that defines how certain attributes or attribute-value pairs indicate interactivity.
            Defaults to DEFAULT_HTML_INTERACTIVE_ATTRIBUTES_AND_VALUES.
        element_get_attr_method_name (str): The method name for getting attribute value from the element.
        element_has_attr_method_name (str): The method name for checking if an attribute exists in the element.

    Returns:
        ElementInteractionTypes: The determined classification.

    Examples:
        >>> from bs4 import BeautifulSoup
        >>> html = '<a href="https://example.com/path">Click</a>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> link_elem = soup.find('a')
        >>> get_element_interaction_type(link_elem, "example.com")
        <ElementInteractionTypes.SAME_DOMAIN_LINK: 'same_domain_link'>

        >>> html = '<a href="https://example.com/about">About</a>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> link = soup.find("a")
        >>> get_element_interaction_type(link, "example.com")
        <ElementInteractionTypes.SAME_DOMAIN_LINK: 'same_domain_link'>

        >>> html = '<a href="#section1">Section 1</a>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> link = soup.find("a")
        >>> get_element_interaction_type(link, "example.com")
        <ElementInteractionTypes.SAME_PAGE_ANCHOR_LINK: 'same_page_anchor_link'>

        >>> html = '<div onclick="window.open(\\'https://external.org\\')">External</div>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> div_elem = soup.find('div')
        >>> get_element_interaction_type(div_elem, "example.com")
        <ElementInteractionTypes.EXTERNAL_DOMAIN_LINK: 'external_domain_link'>

        >>> html = '<a href="https://external.org">External Site</a>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> link = soup.find("a")
        >>> get_element_interaction_type(link, "example.com")
        <ElementInteractionTypes.EXTERNAL_DOMAIN_LINK: 'external_domain_link'>

        >>> html = '<span role="button">Fake Button</span>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> span_elem = soup.find('span')
        >>> get_element_interaction_type(span_elem, "example.com")
        <ElementInteractionTypes.SAME_PAGE_INTERACTABLE: 'same_page_interactable'>

        >>> html = '<span jsname="xyz">Clickable??</span>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> span_elem = soup.find('span')
        >>> get_element_interaction_type(span_elem, "example.com")
        <ElementInteractionTypes.UNKNOWN_INTERACTABLE: 'unknown_interactable'>

        >>> html = '<button jsname="LgbsSe" type="button">Next</button>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> btn = soup.find('button')
        >>> get_element_interaction_type(btn, "accounts.google.com")
        <ElementInteractionTypes.SAME_PAGE_INTERACTABLE: 'same_page_interactable'>

        >>> html = '<a>Missing href</a>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> link = soup.find("a")
        >>> get_element_interaction_type(link, "example.com")
        <ElementInteractionTypes.NO_INTERACTION: 'no_interaction'>
    """
    element_get_attr_method = getattr(element, element_get_attr_method_name)
    element_has_attr_method = getattr(element, element_has_attr_method_name)

    # 1) Check for href
    href = element_get_attr_method("href")
    if href:
        return classify_url_domain(href, current_domain)

    # 2) Check for onclick with a parseable URL
    # was `onclick_value = element_get_attr_method("onclick", "")`, not sure why
    onclick_value = element_get_attr_method("onclick")
    if onclick_value:
        onclick_url = parse_onclick_for_url(onclick_value)
        if onclick_url:
            return classify_url_domain(onclick_url, current_domain)
        # If no parseable URL, we continue to check attributes below

    # 3) Single pass over interactive_attrs_and_values
    for attr_key, value_map in interactive_attrs_and_values.items():
        if element_has_attr_method(attr_key):
            # The element actually has this attribute
            # NOTE: Use single-arg call for Selenium compatibility (get_attribute takes 1 arg)
            elem_val = element_get_attr_method(attr_key) or ""

            if value_map is None:
                # attr_key presence alone (e.g., jsname, data-jsname).
                # For <button> elements without onclick, jsname is an internal JS
                # event binding (not a navigation indicator) — treat as same-page.
                tag = getattr(element, 'name', None) or getattr(element, 'tag_name', '')
                if tag.lower() == 'button' and not onclick_value:
                    return ElementInteractionTypes.SAME_PAGE_INTERACTABLE
                return ElementInteractionTypes.UNKNOWN_INTERACTABLE
            elif isinstance(value_map, ElementInteractionTypes):
                # If `value_map` is `ElementInteractionTypes`, then return itself
                return value_map
            elif isinstance(value_map, dict):
                # If the dict maps specific attribute values to an ElementInteractionTypes
                # e.g. 'role': {'button': SAME_PAGE_INTERACTABLE, 'link': UNKNOWN_INTERACTABLE}
                elem_val_lower = elem_val.lower()
                if elem_val_lower in value_map:
                    return value_map[elem_val_lower]
                # If it doesn't match any known keys, we keep going
                # (Possibility: you could default to UNKNOWN_INTERACTABLE here if you want.)

            else:
                # value_map is either a single string or an iterable of strings
                # If single string, convert it to a list
                if isinstance(value_map, str):
                    value_map = [value_map]

                # Check if the element's value is in that list (case-insensitive)
                if elem_val.lower() in {x.lower() for x in value_map}:
                    return ElementInteractionTypes.UNKNOWN_INTERACTABLE
                # Or if you want partial matching, you'd add more logic
    # 4) If none of the above matched, we say NO_INTERACTION
    return ElementInteractionTypes.NO_INTERACTION


@support_input_html
def get_text_and_attributes_from_element(
        element,
        immediate_text_only: bool = False,
        strip_texts_before_concatenation: bool = False
) -> Tuple[Optional[str], Mapping[str, str]]:
    """
    Extracts the combined text content and attributes from an HTML element.
    This function takes either an HTML string or an HTML elmeent object (BeautifulSoup).

    Args:
        element: A string containing the HTML snippet of a single element or an HTML element object (BeautifulSoup).
        immediate_text_only (bool, optional): If True, extracts only the immediate text (excluding text from child elements). Defaults to False.
        strip_texts_before_concatenation (bool): If True, strings from element and its children will be stripped before being concatenated. Defaults to False.

    Returns:
        tuple: Returns a tuple containing:
            - text (str): All text content combined from the element and its descendants, stripped of leading/trailing whitespace.
            - attributes (dict): A dictionary of all attributes of the element.

    Examples:
        >>> html_snippet = '<div class="example" id="test"><p>Hello</p><p>World</p></div>'
        >>> get_text_and_attributes_from_element(html_snippet)
        ('HelloWorld', {'class': ['example'], 'id': 'test'})
        >>> get_text_and_attributes_from_element(html_snippet, immediate_text_only=True)
        ('', {'class': ['example'], 'id': 'test'})

        >>> html_snippet = '<div>Welcome <span>User</span>!</div>'
        >>> get_text_and_attributes_from_element(html_snippet)
        ('Welcome User!', {})
        >>> get_text_and_attributes_from_element(html_snippet, immediate_text_only=True)
        ('Welcome !', {})

        >>> html_snippet = '<input type="text" value="Sample" disabled>'
        >>> get_text_and_attributes_from_element(html_snippet)
        ('', {'type': 'text', 'value': 'Sample', 'disabled': ''})

        >>> html_snippet = '<a href="#" title="Link">Click here</a>'
        >>> get_text_and_attributes_from_element(html_snippet)
        ('Click here', {'href': '#', 'title': 'Link'})
    """
    if element:
        if immediate_text_only:
            text = get_immediate_text(element, strip=strip_texts_before_concatenation)
        else:
            text = element.get_text(strip=strip_texts_before_concatenation)
        if text is not None and not text.strip():
            text = ''
        attributes = element.attrs
    else:
        text, attributes = None, {}

    return text, attributes


@support_input_html
def get_tag_text_and_attributes_from_element(
        element,
        immediate_text_only: bool = False,
        strip_texts_before_concatenation: bool = False
) -> Tuple[Optional[str], Optional[str], Mapping[str, str]]:
    """
    Extracts the tag name, combined text content, and attributes from an HTML element.
    This function takes either an HTML string or an HTML elmeent object (BeautifulSoup).

    Args:
        element: A string containing the HTML snippet of a single element or an HTML element object (BeautifulSoup).
        immediate_text_only (bool, optional): If True, extracts only the immediate text (excluding text from child elements). Defaults to False.
        strip_texts_before_concatenation (bool): If True, strings from element and its children will be stripped before being concatenated. Defaults to False.

    Returns:
        tuple: Returns a tuple containing:
            - tag (str): The tag name of the HTML element.
            - text (str): All text content combined from the element and its descendants, stripped of leading/trailing whitespace.
            - attributes (dict): A dictionary of all attributes of the element.

    Examples:
        >>> html_snippet = '<div class="example" id="test"><p>Hello</p><p>World</p></div>'
        >>> get_tag_text_and_attributes_from_element(html_snippet)
        ('div', 'HelloWorld', {'class': ['example'], 'id': 'test'})

        >>> html_snippet = '<input type="text" value="Sample" disabled>'
        >>> get_tag_text_and_attributes_from_element(html_snippet)
        ('input', '', {'type': 'text', 'value': 'Sample', 'disabled': ''})

        >>> html_snippet = '<a href="#" title="Link">Click here</a>'
        >>> get_tag_text_and_attributes_from_element(html_snippet)
        ('a', 'Click here', {'href': '#', 'title': 'Link'})
    """
    if element:
        return (
            element.name,
            *get_text_and_attributes_from_element(
                element,
                immediate_text_only=immediate_text_only,
                strip_texts_before_concatenation=strip_texts_before_concatenation
            )
        )
    else:
        return None, None, {}


@support_input_html
def is_element_hidden(
    element,
    only_consider_explicit_hidden: bool = False,
    enabled_tags: Optional[Iterable[str]] = None
) -> bool:
    """
    Determines whether an HTML element is hidden using comprehensive checks.

    This function checks if the given HTML element is hidden. An element is considered hidden if:
    - It has a 'hidden' attribute.
    - It has a 'style' attribute that includes 'display: none' or 'visibility: hidden'.
    - It has aria-hidden="true"
    - It has a 'class' attribute containing 'hidden' (comprehensive mode only)

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        only_consider_explicit_hidden (bool, optional): If True, only considers elements
            as hidden if they have explicit hidden indicators (hidden attribute, display:none,
            visibility:hidden, aria-hidden="true"). If False (default), also checks for
            'hidden' in class names. Defaults to False.
        enabled_tags (Optional[Iterable[str]], optional): If provided, only check elements with tag names
            in this list. Elements not in the list are considered NOT hidden (return False). This is a
            convenience parameter for filtering by tag type. Defaults to None (check all tags).

    Returns:
        bool: True if element is hidden, False otherwise.

    Examples:
        >>> # Comprehensive mode (default): checks all hidden indicators
        >>> is_element_hidden('<div hidden></div>')
        True
        >>> is_element_hidden('<div style="display: none;"></div>')
        True
        >>> is_element_hidden('<div style="visibility: hidden;"></div>')
        True
        >>> is_element_hidden('<div aria-hidden="true"></div>')
        True
        >>> is_element_hidden('<div class="hidden"></div>')
        True
        >>> is_element_hidden('<div class="hidden sb-expander__pushdownContent"></div>')
        True

        >>> # Explicit mode: only explicit hidden indicators
        >>> is_element_hidden('<div hidden>', only_consider_explicit_hidden=True)
        True
        >>> is_element_hidden('<div style="display: none;">', only_consider_explicit_hidden=True)
        True
        >>> is_element_hidden('<div aria-hidden="true">', only_consider_explicit_hidden=True)
        True
        >>> is_element_hidden('<div class="hidden">', only_consider_explicit_hidden=True)
        False

        >>> # Filter by enabled_tags (convenience channel)
        >>> is_element_hidden('<div hidden>', enabled_tags=('div',))
        True
        >>> is_element_hidden('<span hidden>', enabled_tags=('div',))
        False
        >>> is_element_hidden('<div hidden>', enabled_tags=('div', 'span'))
        True
        >>> is_element_hidden('<span hidden>', enabled_tags=('div', 'span'))
        True

        >>> # Not hidden
        >>> is_element_hidden('<div style="display: block;"></div>')
        False
        >>> is_element_hidden('<div></div>')
        False

        >>> # BeautifulSoup Tag object
        >>> from bs4 import BeautifulSoup
        >>> soup = BeautifulSoup('<div hidden></div>', 'html.parser')
        >>> is_element_hidden(soup.find('div'))
        True
    """
    # Filter non-Tag elements (text nodes, comments, etc.)
    if not isinstance(element, Tag):
        return False

    # Convenience filter: check enabled_tags first
    if enabled_tags is not None and element.name not in enabled_tags:
        return False

    # Check for 'hidden' attribute
    if element.has_attr('hidden'):
        return True

    # Check for aria-hidden="true"
    if element.get('aria-hidden') == 'true':
        return True

    # Check for 'style' attribute containing 'display: none' or 'visibility: hidden'
    style = element.get('style', '')
    if style:
        # Normalize the style string
        style_normalized = style.lower().replace(' ', '')
        if 'display:none' in style_normalized or 'visibility:hidden' in style_normalized:
            return True

    # Comprehensive mode: Check for 'class' attribute containing 'hidden'
    if not only_consider_explicit_hidden:
        class_list = element.get('class', [])
        if 'hidden' in class_list:
            return True

    return False


@support_input_html
def is_element_hidden_(
    element,
    additional_rules: Optional[List[dict]] = None,
    rule_set_name_for_error: str = 'hidden_element_rules',
    only_consider_explicit_hidden: bool = False,
    enabled_tags: Optional[Iterable[str]] = None
) -> bool:
    """
    Determines whether an HTML element should be considered hidden and removed,
    using rule-based evaluation with fallback to comprehensive hidden checking.

    This function uses a two-tier evaluation system:
    1. Rule-based evaluation (higher priority): If additional_rules are provided, evaluate element against rules
       - If rule action is 'keep': return False (element is NOT hidden)
       - If rule action is 'remove': return True (element IS hidden)
       - If no rule matches: fall through to default logic
    2. Default evaluation (fallback): Call `is_element_hidden()` for comprehensive check

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        additional_rules (Optional[List[dict]], optional): List of rule dictionaries for custom hidden logic.
            Each rule can return 'keep' or 'remove'. Defaults to None.
        rule_set_name_for_error (str, optional): Name for error messages if rule matching fails.
            Defaults to 'hidden_element_rules'.
        only_consider_explicit_hidden (bool, optional): Passed to `is_element_hidden()` for
            fallback logic. If True, only explicit hidden indicators are considered.
            Defaults to False.
        enabled_tags (Optional[Iterable[str]], optional): Passed to `is_element_hidden()` for fallback logic.
            If provided, only check elements with tag names in this list. Defaults to None (check all tags).

    Returns:
        bool: True if element should be removed (is hidden), False otherwise.

    Examples:
        >>> # Default behavior: uses is_element_hidden() comprehensive check
        >>> is_element_hidden_('<div hidden>')
        True
        >>> is_element_hidden_('<div class="hidden">')
        True

        >>> # Explicit mode: only explicit hidden indicators
        >>> is_element_hidden_('<div hidden>', only_consider_explicit_hidden=True)
        True
        >>> is_element_hidden_('<div class="hidden">', only_consider_explicit_hidden=True)
        False

        >>> # Convenience channel: filter by enabled_tags
        >>> is_element_hidden_('<div hidden>', enabled_tags=('div',))
        True
        >>> is_element_hidden_('<span hidden>', enabled_tags=('div',))
        False

        >>> # Rule-based: Keep specific hidden elements (e.g., ARIA-hidden decorative elements)
        >>> keep_rule = {
        ...     'return': 'keep',
        ...     'tags': ['div'],
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': ['class'],
        ...     'pattern': '*decorative'
        ... }
        >>> is_element_hidden_('<div class="decorative-icon" aria-hidden="true"></div>', [keep_rule])
        False
        >>> is_element_hidden_('<div hidden>Content</div>', [keep_rule])
        True

        >>> # Rule-based: Remove elements even without hidden attribute (e.g., specific classes)
        >>> remove_rule = {
        ...     'return': 'remove',
        ...     'tags': ['div'],
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': ['class'],
        ...     'pattern': '*collapsed'
        ... }
        >>> is_element_hidden_('<div class="panel-collapsed">Content</div>', [remove_rule])
        True
    """
    # Filter non-Tag elements (text nodes, comments, etc.)
    if not isinstance(element, Tag):
        return False

    # First priority: Evaluate additional rules if provided
    if additional_rules:
        from webaxon.html_utils.element_rule_matching import is_element_matching_rule_set

        action = is_element_matching_rule_set(element, additional_rules, rule_set_name_for_error)

        if action == 'keep':
            # Rule explicitly says to keep this element
            return False
        elif action == 'remove':
            # Rule explicitly says to remove this element
            return True
        # If action is None, fall through to default logic

    # Default logic: Use comprehensive hidden check
    return is_element_hidden(element, only_consider_explicit_hidden, enabled_tags)


# Define interactive element types that can have disabled attribute
INTERACTIVE_ELEMENT_TYPES = ('input', 'button', 'select', 'textarea', 'option', 'optgroup', 'fieldset')


@support_input_html
def is_element_disabled(
    element,
    only_consider_non_interactable_as_disabled: bool = False,
    enabled_tags: Optional[Iterable[str]] = None
) -> bool:
    """
    Determines whether an HTML element is disabled using comprehensive checks.

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        only_consider_non_interactable_as_disabled (bool, optional): If True, only considers elements
            as disabled if they are interactive element types (input, button, select, etc.) with the
            'disabled' attribute. If False, uses comprehensive checking including aria-disabled, readonly,
            and aria-readonly attributes. Defaults to False.
        enabled_tags (Optional[Iterable[str]], optional): If provided, only check elements with tag names
            in this list. Elements not in the list are considered enabled (return False). This is a
            convenience parameter for filtering by tag type. Defaults to None (check all tags).

    Returns:
        bool: True if element is disabled, False otherwise.

    Examples:
        >>> # Comprehensive mode (default): checks all disabled indicators
        >>> is_element_disabled('<input disabled>')
        True
        >>> is_element_disabled('<input aria-disabled="true">')
        True
        >>> is_element_disabled('<input readonly>')
        True
        >>> is_element_disabled('<div aria-disabled="true"></div>')
        True

        >>> # Strict mode: only interactive elements with disabled attribute
        >>> is_element_disabled('<input disabled>', only_consider_non_interactable_as_disabled=True)
        True
        >>> is_element_disabled('<button disabled>', only_consider_non_interactable_as_disabled=True)
        True
        >>> is_element_disabled('<input aria-disabled="true">', only_consider_non_interactable_as_disabled=True)
        False
        >>> is_element_disabled('<input readonly>', only_consider_non_interactable_as_disabled=True)
        False
        >>> is_element_disabled('<div disabled>', only_consider_non_interactable_as_disabled=True)
        False

        >>> # Filter by enabled_tags (convenience channel)
        >>> is_element_disabled('<input disabled>', enabled_tags=('input',))
        True
        >>> is_element_disabled('<button disabled>', enabled_tags=('input',))
        False
        >>> is_element_disabled('<input disabled>', enabled_tags=('input', 'button'))
        True
        >>> is_element_disabled('<button disabled>', enabled_tags=('input', 'button'))
        True
    """
    # Filter non-Tag elements (text nodes, comments, etc.)
    if not isinstance(element, Tag):
        return False

    # Convenience filter: check enabled_tags first
    if enabled_tags is not None and element.name not in enabled_tags:
        return False

    if only_consider_non_interactable_as_disabled:
        # Strict mode: only interactive elements with disabled attribute
        if element.name in INTERACTIVE_ELEMENT_TYPES and element.has_attr('disabled'):
            # Special case: disabled="false" (case-insensitive) is treated as NOT disabled (for JS frameworks)
            disabled_value = element.get('disabled', '')
            if disabled_value.lower() == 'false':
                return False
            return True
        return False

    # Comprehensive mode: check all disabled indicators
    # Check for disabled attribute
    if element.has_attr('disabled'):
        # Special case: disabled="false" (case-insensitive) is treated as NOT disabled (for JS frameworks)
        disabled_value = element.get('disabled', '')
        if disabled_value.lower() == 'false':
            return False
        return True

    # Check for aria-disabled="true"
    if element.get('aria-disabled') == 'true':
        return True

    # Check for readonly attribute (inputs/textareas)
    if element.has_attr('readonly'):
        return True

    # Check for aria-readonly="true"
    if element.get('aria-readonly') == 'true':
        return True

    return False


@support_input_html
def is_element_disabled_(
    element,
    additional_rules: Optional[List[dict]] = None,
    rule_set_name_for_error: str = 'disabled_element_rules',
    only_consider_non_interactable_as_disabled: bool = False,
    enabled_tags: Optional[Iterable[str]] = None
) -> bool:
    """
    Determines whether an HTML element should be considered disabled and removed,
    using rule-based evaluation with fallback to comprehensive disabled checking.

    This function uses a two-tier evaluation system:
    1. Rule-based evaluation (higher priority): If additional_rules are provided, evaluate element against rules
       - If rule action is 'keep': return False (element is NOT disabled)
       - If rule action is 'remove': return True (element IS disabled)
       - If no rule matches: fall through to default logic
    2. Default evaluation (fallback): Call `is_element_disabled()` for comprehensive check

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        additional_rules (Optional[List[dict]], optional): List of rule dictionaries for custom disabled logic.
            Each rule can return 'keep' or 'remove'. Defaults to None.
        rule_set_name_for_error (str, optional): Name for error messages if rule matching fails.
            Defaults to 'disabled_element_rules'.
        only_consider_non_interactable_as_disabled (bool, optional): Passed to `is_element_disabled()` for
            fallback logic. If True, only interactive elements with disabled attribute are considered disabled.
            Defaults to False.
        enabled_tags (Optional[Iterable[str]], optional): Passed to `is_element_disabled()` for fallback logic.
            If provided, only check elements with tag names in this list. Defaults to None (check all tags).

    Returns:
        bool: True if element should be removed (is disabled), False otherwise.

    Examples:
        >>> # Default behavior: uses is_element_disabled() comprehensive check
        >>> is_element_disabled_('<input disabled>')
        True
        >>> is_element_disabled_('<input readonly>')
        True

        >>> # Strict mode: only interactive elements with disabled attribute
        >>> is_element_disabled_('<input disabled>', only_consider_non_interactable_as_disabled=True)
        True
        >>> is_element_disabled_('<input readonly>', only_consider_non_interactable_as_disabled=True)
        False

        >>> # Convenience channel: filter by enabled_tags
        >>> is_element_disabled_('<input disabled>', enabled_tags=('input',))
        True
        >>> is_element_disabled_('<button disabled>', enabled_tags=('input',))
        False

        >>> # Rule-based: Keep specific disabled elements
        >>> keep_rule = {
        ...     'return': 'keep',
        ...     'tags': ['button'],
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': ['class'],
        ...     'pattern': '*important'
        ... }
        >>> is_element_disabled_('<button class="important-btn" disabled>Save</button>', [keep_rule])
        False
        >>> is_element_disabled_('<button disabled>Cancel</button>', [keep_rule])
        True

        >>> # Rule-based: Remove elements even without disabled attribute
        >>> remove_rule = {
        ...     'return': 'remove',
        ...     'tags': ['input'],
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': ['type'],
        ...     'pattern': '*hidden'
        ... }
        >>> is_element_disabled_('<input type="hidden">', [remove_rule])
        True
    """
    # Filter non-Tag elements (text nodes, comments, etc.)
    if not isinstance(element, Tag):
        return False

    # First priority: Evaluate additional rules if provided
    if additional_rules:
        from webaxon.html_utils.element_rule_matching import is_element_matching_rule_set

        action = is_element_matching_rule_set(element, additional_rules, rule_set_name_for_error)

        if action == 'keep':
            # Rule explicitly says to keep this element
            return False
        elif action == 'remove':
            # Rule explicitly says to remove this element
            return True
        # If action is None, fall through to default logic

    # Default logic: Use comprehensive disabled check
    return is_element_disabled(element, only_consider_non_interactable_as_disabled, enabled_tags)


@support_input_html
def has_immediate_text(element) -> bool:
    """
    Checks if the HTML element has immediate text (not including text in child elements).

    This function determines whether an HTML element contains text directly within it,
    excluding any text that is nested within child elements.

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).

    Returns:
        bool: True if the element has immediate text content, False otherwise.

    Examples:
        >>> has_immediate_text('<div>Hello <span>World</span></div>')
        True
        >>> has_immediate_text('<div><span>Hello World</span></div>')
        False
        >>> has_immediate_text('<div></div>')
        False
        >>> from bs4 import BeautifulSoup
        >>> soup = BeautifulSoup('<div>Hello</div>', 'html.parser')
        >>> has_immediate_text(soup.find('div'))
        True
    """
    return (
            bool(element.next)
            and any(isinstance(child, NavigableString) and child.strip() for child in element.children)
    )


@support_input_html
def get_immediate_text(element, strip: bool = False) -> str:
    """
    Retrieves the immediate text content of an HTML element, excluding text from child elements.

    This function extracts text nodes that are direct children of the given HTML element,
    without including text from nested child elements.

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        strip: If True, texts will be

    Returns:
        str: The immediate text content of the element, with leading and trailing whitespace removed.
            If there is no immediate text, returns an empty string.

    Examples:
        >>> get_immediate_text('<div>Hello <span>World</span></div>')
        'Hello '
        >>> get_immediate_text('<div>Hello <span>World</span></div>', strip=True)
        'Hello'
        >>> get_immediate_text('<div><span>Hello World</span></div>')
        ''
        >>> get_immediate_text('<div>   Hello   </div>')
        '   Hello   '
        >>> get_immediate_text('<div>   Hello   </div>', strip=True)
        'Hello'
        >>> get_immediate_text('<div></div>')
        ''
        >>> from bs4 import BeautifulSoup
        >>> soup = BeautifulSoup('<div>Hello <p>there</p>!</div>', 'html.parser')
        >>> element = soup.find('div')
        >>> get_immediate_text(element)
        'Hello !'
    """

    # NOTES:
    # element.contents: A list of all immediate child nodes (including text nodes and tags).
    # element.children: A generator over the same nodes (excluding purely navigable strings if you want them as separate strings).
    # element.next: returns the very next item in the parse tree, which is often not all immediate text nodes.

    if strip:
        immediate_text = ''.join(
            child.strip() for child in element.children if isinstance(child, (str, NavigableString))
        )
    else:
        immediate_text = ''.join(
            child for child in element.children if isinstance(child, (str, NavigableString))
        )
    return immediate_text


def remove_immediate_text(element, always_return_element_object: bool = False):
    """
    Removes immediate text nodes from the HTML element.

    This function removes text nodes that are direct children of the given HTML element,
    without affecting text within child elements.

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        always_return_element_object (bool, optional): If True, always returns the modified
            element object (BeautifulSoup), even if the input was a string. Defaults to False.

    Returns:
        Union[str, bs4.element.Tag]: The modified HTML element. If the input was a string and
            `always_return_element_object` is False, returns the modified element as a string.
            Otherwise, returns the modified element object (BeautifulSoup).

    Examples:
        >>> remove_immediate_text('<div>Hello <span>World</span></div>')
        '<div><span>World</span></div>'

        >>> remove_immediate_text('<div><span>Hello</span> World</div>')
        '<div><span>Hello</span></div>'

        >>> remove_immediate_text('<div></div>')
        '<div></div>'

        >>> remove_immediate_text('<div>Hello</div>', always_return_element_object=True)
        <div></div>

        >>> from bs4 import BeautifulSoup
        >>> soup = BeautifulSoup('<div>Hello</div>', 'html.parser')
        >>> element = soup.find('div')
        >>> modified_element = remove_immediate_text(element)
        >>> str(modified_element)
        '<div></div>'
    """
    element_input_is_string = isinstance(element, str)
    if element_input_is_string:
        element = parse_html_string(element)

    for child in element.children:
        if isinstance(child, NavigableString):
            child.extract()

    if always_return_element_object or not element_input_is_string:
        return element
    else:
        return str(element)


@support_input_html
def get_attribute_names_by_pattern(element, attribute_pattern: Union[str, Iterable[str]]) -> List[str]:
    """
    Get attribute names of an element that match the specified pattern(s).

    This function takes an HTML element (either a BeautifulSoup element or an HTML string),
    and returns a list of its attribute names that match the given pattern(s).

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        attribute_pattern: A single pattern or a list of patterns to match attribute names.
            Patterns can include wildcards, regular expressions, or special string patterns.

    Returns:
        List[str]: A list of attribute names that match the pattern(s). Returns an empty list if no matches.

    Examples:
        >>> html_content = '<div id="content" class="container" data-value="example">Hello, world!</div>'
        >>> get_attribute_names_by_pattern(html_content, '^d')
        ['data-value']
        >>> get_attribute_names_by_pattern(html_content, '*')
        ['id', 'class', 'data-value']
        >>> get_attribute_names_by_pattern(html_content, ['id', 'class'])
        ['id', 'class']
        >>> get_attribute_names_by_pattern(html_content, ['id', '$e'])
        ['id', 'data-value']
        >>> get_attribute_names_by_pattern(html_content, ['!d', 'at'])
        ['id', 'class', 'data-value']
        >>> get_attribute_names_by_pattern(html_content, ['!^data-'])
        ['id', 'class']
    """
    if attribute_pattern == '*':
        return list(element.attrs.keys())
    elif not attribute_pattern:
        return []
    elif isinstance(attribute_pattern, str):
        return [
            attr for attr in element.attrs
            if string_check(attr, attribute_pattern)
        ]
    else:
        return [
            attr for attr in element.attrs
            if any(
                string_check(attr, _attr_pattern)
                for _attr_pattern in attribute_pattern
            )
        ]


@support_input_html
def get_attribute_names_excluding_pattern(element, attribute_pattern: Union[str, Iterable[str]]) -> List[str]:
    """
    Get attribute names of an element excluding those that match the specified pattern(s).

    This function takes an HTML element (either a BeautifulSoup element or an HTML string),
    and returns a list of its attribute names that do not match the given pattern(s).

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        attribute_pattern: A single pattern or a list of patterns to exclude attribute names.
            Patterns can include wildcards, regular expressions, or special string patterns.

    Returns:
        List[str]: A list of attribute names that do not match the pattern(s). Returns an empty list if all attributes match the patterns.

    Examples:
        >>> html_content = '<div id="content" class="container" data-value="example">Hello, world!</div>'
        >>> get_attribute_names_excluding_pattern(html_content, '*')
        []
        >>> get_attribute_names_excluding_pattern(html_content, ['id', 'class'])
        ['data-value']
        >>> get_attribute_names_excluding_pattern(html_content, '^d')
        ['id', 'class']
        >>> get_attribute_names_excluding_pattern(html_content, ['id', '$e'])
        ['class']
        >>> get_attribute_names_excluding_pattern(html_content, ['!d', 'at'])
        []
        >>> get_attribute_names_excluding_pattern(html_content, ['!^data-'])
        ['data-value']
    """
    if attribute_pattern == '*':
        return []
    elif not attribute_pattern:
        return list(element.attrs.keys())
    elif isinstance(attribute_pattern, str):
        return [
            attr for attr in element.attrs
            if not string_check(attr, attribute_pattern)
        ]
    else:
        return [
            attr for attr in element.attrs
            if not any(
                string_check(attr, attr_pattern)
                for attr_pattern in attribute_pattern
            )
        ]


def keep_specified_attributes(element, attributes_to_keep: Union[str, Iterable[str]],
                              always_return_element_object: bool = False):
    """
    Keep specified attributes of an element and remove the rest.

    This function takes an HTML element (either a BeautifulSoup element or an HTML string),
    and removes all attributes except those specified.

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        attributes_to_keep: A single attribute name or a list of attribute names to keep.
            Use '*' to keep all attributes, or an empty string to remove all attributes.
        always_return_element_object (bool, optional): If True, always returns the modified
            element object (BeautifulSoup), even if the input was a string. Defaults to False.

    Returns:
        Union[str, bs4.element.Tag]: The modified HTML element. If the input was a string and
            `always_return_element_object` is False, returns the modified element as a string.
            Otherwise, returns the modified element object (BeautifulSoup).

    Examples:
        >>> from copy import deepcopy
        >>> html_content = '<div id="content" class="container" data-value="example">Hello, world!</div>'
        >>> soup = BeautifulSoup(html_content, 'html.parser')
        >>> element = deepcopy(soup.div)
        >>> str(keep_specified_attributes(element, 'id'))
        '<div id="content">Hello, world!</div>'
        >>> element = deepcopy(soup.div)
        >>> str(keep_specified_attributes(element, ['class', 'data-value']))
        '<div class="container" data-value="example">Hello, world!</div>'
        >>> element = deepcopy(soup.div)
        >>> str(keep_specified_attributes(element, '*'))
        '<div class="container" data-value="example" id="content">Hello, world!</div>'
        >>> element = deepcopy(soup.div)
        >>> str(keep_specified_attributes(element, ''))
        '<div>Hello, world!</div>'
    """
    element_input_is_string = isinstance(element, str)
    if element_input_is_string:
        element = parse_html_string(element)

    attrs_to_remove = get_attribute_names_excluding_pattern(element, attribute_pattern=attributes_to_keep)
    if attrs_to_remove:
        for attr in attrs_to_remove:
            del element[attr]

    if always_return_element_object or not element_input_is_string:
        return element
    else:
        return str(element)


@support_input_html
def extract_attributes(element, attributes: list) -> dict:
    """
    Extracts specified attributes from an HTML element and returns them as a dictionary.

    Args:
        element: A string containing the HTML snippet of a single element or
            an HTML element object (BeautifulSoup).
        attributes (list): A list of attribute names to extract from the element.

    Returns:
        dict: A dictionary containing the specified attributes and their values.

    Examples:
        >>> sample_html = '<div id="123" class="container" data-value="example">Hello, world!</div>'
        >>> extracted_attributes = extract_attributes(sample_html, ['id', 'class', 'data-value'])
        >>> print(extracted_attributes)
        {'id': '123', 'class': ['container'], 'data-value': 'example'}
        >>> # Using an element object
        >>> from bs4 import BeautifulSoup
        >>> soup = BeautifulSoup(sample_html, 'html.parser')
        >>> element = soup.find('div')
        >>> extract_attributes(element, ['id', 'class'])
        {'id': '123', 'class': ['container']}
    """
    if element:
        return {attr: element.get(attr) for attr in attributes if element.get(attr) is not None}
    else:
        return {}


def attribute_value_to_list(value: Union[str, List]) -> List:
    """
    Converts an HTML attribute string into a list of strings, splitting on whitespace.
    If the input is already a list, then the input list is returned.

    Args:
        value (Union[str, List]): The attribute value, which may be a string or already a list.

    Returns:
        List: A list of strings representing the split or original value.

    Example:
        >>> attribute_value_to_list("foo bar  baz")
        ['foo', 'bar', 'baz']
        >>> attribute_value_to_list(['single', 'already', 'list'])
        ['single', 'already', 'list']
    """
    if isinstance(value, List):
        return value
    if not value:
        return []
    return str(value).split()


def merge_attribute_values(
        value1: Union[str, List],
        value2: Union[str, List],
        deduplicate_text_values: bool = False,
        deduplicate_list_values: bool = True
) -> Union[str, List]:
    """
    Merge two attribute values (string or list of strings) with optional substring-based
    and list-based deduplication.

    This function merges two values that may each be either a string or a list of strings.
    Depending on the input types and flags, the result is a single string or a list of strings.
    The key behaviors are:

    1. **Both inputs are strings**:
       - If ``deduplicate_list_values`` is True **and** the two strings are exactly the same,
         return that string (i.e., skip duplicates).
       - If ``deduplicate_text_values`` is True, check whether one string is contained within
         the other (using ``contains_whole_word``). If so, return the containing string.
         Otherwise, return the two strings joined by a space (e.g., ``"foo bar"``).
       - If ``deduplicate_text_values`` is False, simply return the two strings joined by a space.

    2. **One input is a string, the other a list**:
       - Convert the string to a one-element list and combine with the other list.
       - If ``deduplicate_list_values`` is True, remove exact duplicates in the combined list.
       - If ``deduplicate_text_values`` is True, remove any new item if it is contained within
         an existing item (or remove an existing item if it is contained within the new one).

    3. **Both inputs are lists**:
       - Concatenate the two lists.
       - If ``deduplicate_text_values`` is True, skip or remove items that are contained
         within any existing item (or vice versa) as you combine them.
       - If ``deduplicate_list_values`` is True, remove any exact duplicates in order of
         first appearance.

    Args:
        value1: A string or list of strings to merge.
        value2: A string or list of strings to merge.
        deduplicate_text_values (bool, optional):
            If True, performs substring-based checks (via ``contains_whole_word``)
            to skip or replace certain values. Defaults to False.
        deduplicate_list_values (bool, optional):
            If True, removes exact-duplicate items from lists in order of first appearance.
            Defaults to True.

    Returns:
        Either a single string (if both inputs remain strings) or a list of strings.
        The output may be reduced by substring-based or exact-dedup logic based on
        the provided flags.

    Examples:
        # 1) Both are strings
        >>> merge_attribute_values("foo", "bar")
        'foo bar'
        >>> merge_attribute_values("foo", "foo")
        'foo'
        >>> merge_attribute_values("hello", "hell", deduplicate_text_values=True)
        'hello hell'
        >>> merge_attribute_values("abc", "123", deduplicate_text_values=True)
        'abc 123'

        # 2) One string, one list
        >>> merge_attribute_values("foo", ["foo", "bar"])
        ['foo', 'bar']
        >>> merge_attribute_values("foo", ["foo", "bar"], deduplicate_list_values=False)
        ['foo', 'foo', 'bar']
        >>> merge_attribute_values("foo", ["foo", "bar"], deduplicate_text_values=True)
        ['foo', 'bar']
        >>> merge_attribute_values("foo", ["hello", "food"], deduplicate_text_values=True)
        ['foo', 'hello', 'food']

        # 3) Both are lists
        >>> merge_attribute_values(["foo", "bar"], ["bar", "baz"])
        ['foo', 'bar', 'baz']
        >>> merge_attribute_values(["foo", "bar"], ["bar", "baz"], deduplicate_list_values=False)
        ['foo', 'bar', 'bar', 'baz']
        >>> merge_attribute_values(["hello", "hi"], ["he", "hello"], deduplicate_text_values=True)
        ['hi', 'he', 'hello']
    """
    is_value1_list = isinstance(value1, List)
    is_value2_list = isinstance(value2, List)

    if deduplicate_text_values:
        if is_value1_list:
            value1 = dedup_string_list(value1)
        if is_value2_list:
            value2 = dedup_string_list(value2)

    if not is_value1_list:  # value1 is str
        if not is_value2_list:  # value2 is str
            if deduplicate_list_values:
                if value1 == value2:
                    return value1
            if deduplicate_text_values:
                if contains_whole_word(value2, value1):
                    return value2
                elif contains_whole_word(value1, value2):
                    return value1
            return value1 + ' ' + value2
        else:  # value2 is list
            if (
                    (deduplicate_list_values and value1 in value2)
                    or (deduplicate_text_values and any(contains_whole_word(_value, value1) for _value in value2))
            ):
                return value2
            else:
                return [value1] + value2
    else:  # value1 is list
        if not is_value2_list:  # value2 is str
            if (
                    (deduplicate_list_values and value2 in value1)
                    or (deduplicate_text_values and any(contains_whole_word(_value, value2) for _value in value1))
            ):
                return value1
            else:
                return value1 + [value2]
        else:  # value1 and value2 are both list
            if deduplicate_text_values:
                value1_text_dedup = list(
                    filter(lambda x: not any(contains_whole_word(_value, x) for _value in value2), value1))
                value2_text_dedup = (
                    filter(lambda x: not any(contains_whole_word(_value, x) for _value in value1_text_dedup), value2)
                    if value1_text_dedup
                    else value2
                )
                return list(dedup_chain(value1_text_dedup, value2_text_dedup))
            elif deduplicate_list_values:
                return list(dedup_chain(value1, value2))
            else:
                return value1 + value2


@support_input_html2
def merge_attributes(
        element1, element2,
        list_like_attrs: Iterable[str] = None,
        excluded_attrs: Iterable[str] = None,
        deduplicate_text_values: bool = False,
        deduplicate_list_values: bool = True
):
    """
    Merge attributes from ``element1`` into ``element2``, optionally treating some attributes as
    space-delimited lists and excluding specified attributes.

    This function inspects each attribute in ``element1`` and merges it into ``element2``. The
    merging behavior varies depending on whether the attribute is in ``list_like_attrs`` or not.
    Attributes in ``excluded_attrs`` are skipped entirely.

    Args:
        element1 (Union[str, bs4.element.Tag]):
            A BeautifulSoup element or HTML snippet whose attributes will be merged.
        element2 (Union[str, bs4.element.Tag]):
            A BeautifulSoup element or HTML snippet that receives attributes from ``element1``.
        list_like_attrs (Iterable[str], optional):
            A set/list of attribute names (e.g., ``{'class', 'rel'}``) whose values should be
            treated as space-delimited lists. If both elements have these attributes, the lists
            are combined, deduplicated, and sorted. Defaults to ``None`` (i.e., no attributes
            treated as list-like).
        excluded_attrs (Iterable[str], optional):
            A set/list of attribute names (e.g., ``{'style', 'id'}``) that should **not** be
            merged from ``element1`` into ``element2``. Any attribute in this set is skipped.
            Defaults to ``None``.
        deduplicate_text_values (bool, optional):
            If ``True``, performs substring-based deduplication on merged non-list-like attributes
            (via :func:`contains_whole_word`). Defaults to ``False``.
        deduplicate_list_values (bool, optional):
            If ``True``, removes exact duplicates within merged list-like attributes.
            Defaults to ``True``.

    Returns:
        bs4.element.Tag:
            The updated BeautifulSoup Tag corresponding to ``element2``, also modified in place.

    Notes:
        * **Attribute Merging**:
          - New attributes (not in ``element2``) are copied from ``element1``.
          - Existing attributes are combined. If an attribute is in ``list_like_attrs``,
            values are merged as space-delimited sets. Otherwise, values are merged with
            potential substring or exact dedup checks based on the booleans.
        * **Excluding Attributes**:
          - Any attribute name in ``excluded_attrs`` is **skipped**—it is not merged from
            ``element1``.
        * **In-Place Modification**:
          - The returned object is the same as ``element2``, but now updated with attributes
            from ``element1``.

    Returns:
        bs4.element.Tag: The updated version of ``element2`` (also modified in place).

    Examples:
        # 1) Merging 'class' and 'data-info' from one <div> into another
        >>> html1 = '<div class="outer" data-info="p123" style="color:red;"></div>'
        >>> html2 = '<div class="inner" data-info="c123" style="font-size:12px;"></div>'
        >>> merge_attributes(html1, html2)
        <div class="outer inner" data-info="p123 c123" style="color:red; font-size:12px;"></div>

        # 2) Treating 'class' as list-like (space-delimited); merges classes uniquely
        >>> html1 = '<span class="foo bar"></span>'
        >>> html2 = '<span class="bar baz"></span>'
        >>> merge_attributes(html1, html2, list_like_attrs={'class'})
        <span class="foo bar baz"></span>

        # 3) Non-list-like merging (by default): attributes get concatenated with a space
        >>> html1 = '<a data-test="valueA"></a>'
        >>> html2 = '<a data-test="valueB"></a>'
        >>> merge_attributes(html1, html2)
        <a data-test="valueA valueB"></a>

        # 4) Copying over attributes that don't exist in element2
        >>> html1 = '<p id="p123" title="paragraph"></p>'
        >>> html2 = '<p></p>'
        >>> merge_attributes(html1, html2)
        <p id="p123" title="paragraph"></p>

        # 5) Demonstrate deduplicate_text_values=True for substring checks
        >>> html1 = '<div data-info="Hello"></div>'
        >>> html2 = '<div data-info="Hello World"></div>'
        >>> merge_attributes(html1, html2, deduplicate_text_values=True)
        <div data-info="Hello World"></div>

        # 6) Demonstrate deduplicate_list_values=False (avoid removing exact duplicates)
        >>> html1 = '<div data-info="foo"></div>'
        >>> html2 = '<div data-info="foo"></div>'
        >>> merge_attributes(html1, html2, deduplicate_list_values=False)
        <div data-info="foo foo"></div>

        # 7) Excluding certain attributes (e.g. 'style')
        >>> html1 = '<div class="outer" style="color:red;"></div>'
        >>> html2 = '<div class="inner" style="font-size:12px;"></div>'
        >>> merge_attributes(html1, html2, excluded_attrs={'style'})
        <div class="outer inner" style="font-size:12px;"></div>
    """
    for attr_name, element1_value in element1.attrs.items():
        if excluded_attrs and attr_name in excluded_attrs:
            continue
        if attr_name not in element2.attrs:
            # If element2 does not have this attribute, copy it over
            element2.attrs[attr_name] = element1_value
        else:
            # element2 already has this attribute
            element2_value = element2.attrs[attr_name]

            if list_like_attrs and attr_name in list_like_attrs:
                element1_value = attribute_value_to_list(element1_value)
                element2_value = attribute_value_to_list(element2_value)

            element2.attrs[attr_name] = merge_attribute_values(
                element1_value,
                element2_value,
                deduplicate_list_values=deduplicate_list_values,
                deduplicate_text_values=deduplicate_text_values
            )
    return element2
