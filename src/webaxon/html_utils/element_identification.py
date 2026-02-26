from typing import Mapping, Optional, Any, Sequence, Union, List, Tuple, Dict
import re
from enum import StrEnum
import bs4
from bs4 import BeautifulSoup, Tag, NavigableString
from lxml import etree

from webaxon.html_utils.common import parse_html_string, get_text_and_attributes_from_element, \
    support_input_html, support_input_html2, copy_html_element_name_and_attrs

# Import readability scoring (optional - graceful degradation if not available)
try:
    from rich_python_utils.nlp_utils.readability import get_string_readability_score
    _HAS_READABILITY = True
except ImportError:
    _HAS_READABILITY = False
    get_string_readability_score = None

# Import dynamic content detection (optional - graceful degradation if not available)
try:
    from rich_python_utils.nlp_utils.string_patterns import contains_dynamic_content
    _HAS_DYNAMIC_DETECTION = True
except ImportError:
    _HAS_DYNAMIC_DETECTION = False
    contains_dynamic_content = None

ATTR_NAME_INCREMENTAL_ID = '__id__'

# Generic CSS framework classes to skip when generating xpaths
GENERIC_CLASSES = {
    'btn', 'button', 'container', 'row', 'col', 'form-control', 'd-flex',
    'flex', 'grid', 'block', 'inline', 'hidden', 'visible', 'active',
    'disabled', 'selected', 'checked', 'focus', 'hover', 'error', 'success',
    'warning', 'info', 'primary', 'secondary', 'text', 'bg', 'border',
}

# Tailwind-style utility class prefixes (only match when followed by digits: p-4, mt-2)
UTILITY_CLASS_PREFIXES = {
    'p-', 'm-', 'px-', 'py-', 'mx-', 'my-', 'pt-', 'pb-', 'pl-', 'pr-',
    'mt-', 'mb-', 'ml-', 'mr-', 'w-', 'h-', 'min-', 'max-',
}

# Patterns for dynamic/hash-like values that should be skipped in xpath generation
# These patterns indicate auto-generated or minified values that are not stable
HASH_LIKE_VALUE_PATTERNS = [
    r'^react-',           # React
    r'^ember\d+',         # Ember
    r'^ng-',              # Angular
    r'^:r\d+:',           # React 18 useId
    r'^[a-f0-9]{8,}$',    # UUID-like (8+ lowercase hex chars)
    r'^\d+$',             # Pure numeric
    # Google-style minified IDs: mixed case with unusual patterns
    # e.g., APjFqb, gLFyf, RNmpXc (not normal words like "Search" or "Submit")
]


def _looks_like_hash(value: str) -> bool:
    """
    Check if value looks like a minified/hash ID rather than a meaningful word.

    Detects patterns like: APjFqb, gLFyf, RNmpXc, gb_70
    Does NOT flag: Search, Submit, email, password, button-1

    Heuristics:
    - Has uppercase letter after lowercase (unusual casing): gLFyf, APjFqb
    - Has lowercase after uppercase in middle: APjFqb
    - Mix of letters and digits in short string: gb_70, a1b2c3
    - Consecutive uppercase in middle of word: gLFyf
    """
    if len(value) < 4 or len(value) > 12:
        return False

    # Skip if contains spaces (likely meaningful phrase)
    if ' ' in value:
        return False

    # Check for unusual casing patterns (not standard words or camelCase)
    # Pattern: lowercase followed by uppercase (mid-word caps): gLFyf, APjFqb
    has_unusual_caps = bool(re.search(r'[a-z][A-Z]', value))

    # Check for consecutive uppercase in the middle (not at start)
    has_mid_consecutive_upper = bool(re.search(r'.[A-Z]{2}', value))

    # Check for digit mixed with letters (but not just trailing number like button-1)
    has_mixed_digits = bool(re.search(r'[a-zA-Z]\d[a-zA-Z]', value))

    # Check for underscore followed by digits (framework pattern): gb_70
    has_underscore_digits = bool(re.search(r'_\d+$', value))

    return has_unusual_caps or has_mid_consecutive_upper or has_mixed_digits or has_underscore_digits

# Attribute priority for generating lean xpaths
# Note: data-stid is used by Expedia and similar sites for stable test identifiers
XPATH_ATTR_PRIORITY = [
    'id', 'name', 'title', 'value', 'href', 'for', 'aria-label',
    'placeholder', 'data-testid', 'data-stid', 'data-qa', 'data-id', 'type', 'role'
]

# Attributes that typically contain human-readable descriptions
# These get a readability boost since their purpose is to be descriptive
# - title, aria-label, placeholder, alt: Always human-facing text
# - value: User-facing label for submit buttons (input[type=submit], button)
SEMANTIC_ATTRS = {'title', 'aria-label', 'placeholder', 'alt', 'value'}

# Readability boost for semantic attributes (added to score)
# Must be > 0.164 to prioritize "Google Search" (0.336) over "submit" (0.5)
SEMANTIC_ATTR_BOOST = 0.2


class XPathResolutionMode(StrEnum):
    """
    Strategy for resolving non-unique XPath expressions in elements_to_xpath().

    When no unique xpath can be found for an element, this mode determines
    how to handle the situation.
    """

    UNIQUE_ONLY = "unique_only"
    """Raise ValueError if no unique xpath can be found (default behavior)."""

    FIRST_MATCH = "first_match"
    """Return xpath with [1] index to select first match (e.g., '(//div)[1]')."""

    MATCH_BY_HTML = "match_by_html"
    """Find element by comparing HTML structure using compare_elements()."""

    MATCH_BY_SIGNATURE = "match_by_signature"
    """Find element by comparing signatures using get_element_signature()."""

    MATCH_BY_TEXT = "match_by_text"
    """Find element by comparing text content only using element.get_text()."""


@support_input_html2
def compare_elements(
        element1,
        element2,
        ignore_attrs: Optional[Sequence[str]] = None,
        consider_children: bool = False,
        consider_immediate_text_only: bool = False,
        strip_texts_before_concatenation: bool = False,
) -> bool:
    """Compares two HTML elements for equality.

    This function compares two HTML elements (either as strings or HTML element objects (BeautifulSoup))
    to determine if they are structurally and semantically equal. It checks the tag names,
    text content, and attributes, with options to ignore certain attributes during comparison
    and to consider or ignore child elements.

    Args:
        element1: The first element to compare.
        element2: The second element to compare.
        ignore_attrs (Sequence[str], optional): A list of attribute names to ignore during comparison. Defaults to None.
        consider_children (bool, optional): If True, compares the child elements recursively. If False, only compares the root elements' tag names, attributes, and text content. Defaults to True.
        consider_immediate_text_only (bool, optional): If True, extracts only the immediate text (excluding text from child elements). Defaults to False.
        strip_texts_before_concatenation (bool, optional): If True, texts will be stripped before concatenation. Defaults to False.

    Returns:
        bool: True if elements are considered equal, False otherwise.

    Examples:
        >>> html1 = '<div id="content"><p>Hello</p></div>'
        >>> html2 = '<div id="content"><p>Hello</p></div>'
        >>> compare_elements(html1, html2)
        True

        >>> html3 = '<div id="content"><p>Hi</p></div>'
        >>> compare_elements(html1, html3)
        False

        # Ignoring an attribute during comparison
        >>> html4 = '<div id="content"><p>Hello</p></div>'
        >>> html5 = '<div id="main"><p>Hello</p></div>'
        >>> compare_elements(html4, html5)
        False
        >>> compare_elements(html4, html5, ignore_attrs=['id'])
        True

        # Comparing elements with different attributes
        >>> html6 = '<div class="container" style="color:red;"><p>Hello</p></div>'
        >>> html7 = '<div class="container"><p>Hello</p></div>'
        >>> compare_elements(html6, html7)
        False
        >>> compare_elements(html6, html7, ignore_attrs=['style'])
        True

        # Comparing elements with nested structures
        >>> html8 = '<ul><li>Item 1</li><li>Item 2</li></ul>'
        >>> html9 = '<ul><li>Item 1</li><li>Item 2</li></ul>'
        >>> compare_elements(html8, html9)
        True

        >>> html10 = '<ul><li>Item 1</li><li>Item 3</li></ul>'
        >>> compare_elements(html8, html10)
        False

        # Comparing elements with different tag names
        >>> html11 = '<div><p>Hello</p></div>'
        >>> html12 = '<section><p>Hello</p></section>'
        >>> compare_elements(html11, html12)
        False

        # Comparing elements with additional attributes in one
        >>> html13 = '<div id="content" class="main"><p>Hello</p></div>'
        >>> html14 = '<div id="content"><p>Hello</p></div>'
        >>> compare_elements(html13, html14)
        False
        >>> compare_elements(html13, html14, ignore_attrs=['class'])
        True

        # Comparing elements with different text content
        >>> html15 = '<div><p>Hello World</p></div>'
        >>> html16 = '<div><p>Hello</p></div>'
        >>> compare_elements(html15, html16)
        False

        # Comparing elements where text content differs only in whitespace
        >>> html17 = '<div><p>Hello</p> Kitty</div>'
        >>> html18 = '<div><p>  Hello  </p> Kitty</div>'
        >>> compare_elements(html17, html18)
        False
        >>> compare_elements(html17, html18, consider_immediate_text_only=True)
        True
        >>> compare_elements(html17, html18, strip_texts_before_concatenation=True)
        True

        # Comparing elements without considering children
        >>> html19 = '<div class="container"><p>Hello</p></div>'
        >>> html20 = '<div class="container"><span>Hello</span></div>'
        >>> compare_elements(html19, html20, consider_children=True)
        False
        >>> compare_elements(html19, html20, consider_children=False)
        True
        >>> compare_elements(html19, html20, consider_children=False, consider_immediate_text_only=True)
        True

        # Comparing elements with different text in root element
        >>> html21 = '<div>Hello</div>'
        >>> html22 = '<div>Hi</div>'
        >>> compare_elements(html21, html22)
        False
        >>> compare_elements(html21, html22, consider_children=False)
        False

        # Comparing elements with same attributes but different children
        >>> html23 = '<div class="container"></div>'
        >>> html24 = '<div class="container"><p>Content</p></div>'
        >>> compare_elements(html23, html24)
        False
        >>> compare_elements(html23, html24, consider_children=True)
        False
        >>> compare_elements(html23, html24, consider_children=False, consider_immediate_text_only=True)
        True
    """
    if element1 is None or element2 is None:
        return element1 == element2

    if element1.name != element2.name:
        return False

    if ignore_attrs is None:
        ignore_attrs = ()

    # Extract text and attributes from root elements
    text1, attrs1 = get_text_and_attributes_from_element(
        element1,
        immediate_text_only=consider_immediate_text_only,
        strip_texts_before_concatenation=strip_texts_before_concatenation
    )
    text2, attrs2 = get_text_and_attributes_from_element(
        element2,
        immediate_text_only=consider_immediate_text_only,
        strip_texts_before_concatenation=strip_texts_before_concatenation
    )

    if text1.strip() != text2.strip():
        return False

    # Ignore specified attributes
    attrs1 = {k: v for k, v in attrs1.items() if k not in ignore_attrs}
    attrs2 = {k: v for k, v in attrs2.items() if k not in ignore_attrs}

    if attrs1 != attrs2:
        return False

    if not consider_children:
        return True

    # Recursively compare child elements
    children1 = [child for child in element1.contents if not isinstance(child, NavigableString) or child.strip()]
    children2 = [child for child in element2.contents if not isinstance(child, NavigableString) or child.strip()]

    if len(children1) != len(children2):
        return False

    for child1, child2 in zip(children1, children2):
        if isinstance(child1, str):
            if isinstance(child2, str):
                if child1 != child2:
                    return False
            else:
                return False
        else:
            if isinstance(child2, str):
                return False
            if not compare_elements(child1, child2, ignore_attrs, consider_children=True):
                return False

    return True


@support_input_html
def get_element_signature(
        element,
        ignore_attrs: Optional[Sequence[str]] = None,
        consider_children: bool = False,
        consider_text: bool = True,
        consider_immediate_text_only: bool = False,
        strip_texts_before_concatenation: bool = False
) -> str:
    """Generates a normalized string signature for an element.

    This function creates a normalized string representation of an HTML element,
    which can be used to compare elements or generate unique identifiers. It includes
    the tag name, sorted attributes (excluding those in `ignore_attrs`), and optionally
    includes the signatures of child elements if `consider_children` is True.

    **If `consider_immediate_text_only` is True, only the immediate text content of the element
    is included, excluding text from child elements.**

    Args:
        element (Union[str, bs4.element.Tag]): The element to generate a signature for. Can be an HTML string or a BeautifulSoup Tag object.
        ignore_attrs (Sequence[str], optional): A list of attribute names to ignore. Defaults to None.
        consider_children (bool, optional): Whether to include children in the signature. Defaults to **False**.
        consider_text (bool, optional): Whether to include the text content of the element in the signature. If False, text content is excluded. Defaults to **True**.
        consider_immediate_text_only (bool, optional): **If True, includes only the immediate text of the element, excluding text from child elements.** Defaults to False.
        strip_texts_before_concatenation (bool, optional): If True, texts will be stripped before concatenation. Defaults to False.

    Returns:
        str: A normalized string representation of the element.

    Examples:
        >>> element_html = '<div id="content">Welcome <span>User</span>!</div>'

        >>> get_element_signature(element_html)
        '<div id="content">Welcome User!</div>'

        # Excluding text content
        >>> get_element_signature(element_html, consider_text=False)
        '<div id="content"></div>'

        # Setting consider_immediate_text_only as True
        >>> get_element_signature(element_html, consider_immediate_text_only=True)
        '<div id="content">Welcome !</div>'

        # Stripping texts before concatenation
        >>> get_element_signature(element_html, strip_texts_before_concatenation=True)
        '<div id="content">WelcomeUser!</div>'

        # Setting both consider_immediate_text_only and strip_texts_before_concatenation as True
        >>> get_element_signature(element_html, consider_immediate_text_only=True, strip_texts_before_concatenation=True)
        '<div id="content">Welcome!</div>'

        # Including children in the signature
        >>> get_element_signature(element_html, consider_children=True)
        '<div id="content">Welcome <span>User</span>!</div>'

        # Including children in the signature and setting consider_immediate_text_only as True
        >>> get_element_signature(element_html, consider_children=True, consider_immediate_text_only=True)
        '<div id="content">Welcome <span>User</span>!</div>'

        # Including children in the signature and setting both consider_immediate_text_only and strip_texts_before_concatenation as True
        >>> get_element_signature(element_html, consider_children=True, consider_immediate_text_only=True, strip_texts_before_concatenation = True)
        '<div id="content">Welcome<span>User</span>!</div>'

        # Ignoring attributes
        >>> get_element_signature(element_html, ignore_attrs=['id'])
        '<div>Welcome User!</div>'
        >>> get_element_signature(element_html, ignore_attrs=['id'], consider_immediate_text_only=True)
        '<div>Welcome !</div>'
        >>> get_element_signature(element_html, ignore_attrs=['id'], consider_immediate_text_only=True, strip_texts_before_concatenation=True)
        '<div>Welcome!</div>'
        >>> get_element_signature(element_html, ignore_attrs=['id'], consider_children=True, consider_immediate_text_only=True, strip_texts_before_concatenation=True)
        '<div>Welcome<span>User</span>!</div>'
    """

    if ignore_attrs is None:
        ignore_attrs = ()

    # Extract tag name, text, and attributes using get_text_and_attributes_from_element
    tag_name = element.name
    text, attributes = get_text_and_attributes_from_element(
        element,
        immediate_text_only=consider_immediate_text_only,
        strip_texts_before_concatenation=strip_texts_before_concatenation
    )

    # Ignore specified attributes
    attributes = {k: v for k, v in attributes.items() if k not in ignore_attrs}

    # Sort attributes
    sorted_attrs = sorted(
        (key, ' '.join(sorted(v)) if isinstance(v, list) else v)
        for key, v in attributes.items()
    )

    # Build attribute string
    attr_str = ''.join(
        f' {key}="{value}"' for key, value in sorted_attrs
    )

    # Build the signature
    if consider_children:
        # Include children signatures
        child_signatures = ''
        for child in element.contents:
            if isinstance(child, NavigableString):
                child_text = child
                if strip_texts_before_concatenation:
                    child_text = child_text.strip()
                if child_text:
                    child_signatures += child_text
            elif isinstance(child, Tag):
                child_signatures += get_element_signature(
                    child,
                    ignore_attrs=ignore_attrs,
                    consider_children=consider_children,
                    consider_text=consider_text,
                    consider_immediate_text_only=consider_immediate_text_only
                )
        signature = f'<{tag_name}{attr_str}>{child_signatures}</{tag_name}>'
    else:
        # Exclude children, only include text
        if text and consider_text:
            signature = f'<{tag_name}{attr_str}>{text}</{tag_name}>'
        else:
            signature = f'<{tag_name}{attr_str}></{tag_name}>'

    return signature


@support_input_html2
def find_incremental_elements(
        element1,
        element2,
        keep_hierarchy: bool = True,
        consider_text_for_comparison: bool = True,
        keep_all_text_in_hierarchy_for_incremental_change: bool = True,
        strip_texts_before_concatenation: bool = False,
        ignore_attrs_for_comparison=None
):
    """Finds elements present in `element2` but not in `element1`.

    Optionally keeps the hierarchy of the new elements and controls how text nodes are handled
    within the hierarchy.

    Args:
        element1 (Union[str, bs4.element.Tag]): The first HTML document or element as a string or BeautifulSoup Tag.
        element2 (Union[str, bs4.element.Tag]): The second HTML document or element as a string or BeautifulSoup Tag.
        keep_hierarchy (bool, optional): Whether to keep the hierarchy of the new elements.
            If True, returns a root element containing the hierarchy of new elements.
            If False, returns a flat list of new elements. Defaults to False.
        consider_text_for_comparison (bool, optional): Whether to consider text content when comparing elements.
            - If True, text content is considered in the comparison.
            - If False, text content is ignored.
            Defaults to False.
        keep_all_text_in_hierarchy_for_incremental_change (bool, optional): When `keep_hierarchy` is True, this determines
            whether to keep all text nodes in the hierarchy. If True, all text nodes are kept.
            If False, only text nodes within new elements are kept. Defaults to True.
        strip_texts_before_concatenation (bool, optional): If True, text nodes will be stripped of
            leading and trailing whitespace before concatenation during signature generation.
            This can affect whether elements are considered identical. Defaults to False.
        ignore_attrs_for_comparison (Sequence[str], optional): A list of attribute names to ignore during comparison. Defaults to None.
            These attributes are only ignored for comparison. The output HTML elements shoudl still have these attributes.

    Returns:
        Union[List[bs4.element.Tag], bs4.element.Tag]:
            - If `keep_hierarchy` is False, returns a flat list of new HTML elements.
            - If `keep_hierarchy` is True, returns a root HTML element containing the hierarchy of new elements.

    Examples:
        # Example with text nodes only in new elements
        >>> html1 = '<div>Hello <p>Hello</p></div>'
        >>> html2 = '<div>Hello <p>Hello</p><p>World</p></div>'

        # Example without hierarchy
        >>> new_elements = find_incremental_elements(html1, html2, keep_hierarchy=False)
        >>> for elem in new_elements:
        ...     print(elem)
        <p>World</p>

        # Example with hierarchy
        >>> incremental_tree = find_incremental_elements(html1, html2, keep_hierarchy=True)
        >>> print(str(incremental_tree).strip())
        <div>Hello <p>World</p></div>

        # A more complex example with hierarchy
        >>> html1 = '<body><div id="content">Hello <p>Hello</p></div></body>'
        >>> html2 = '<body><div id="content">Hello <p>Hello</p><p>New</p></div><footer>Footer</footer></body>'
        >>> incremental_tree = find_incremental_elements(html1, html2, keep_hierarchy=True)
        >>> print(str(incremental_tree).strip())
        <body><div id="content">Hello <p>New</p></div><footer>Footer</footer></body>

        # Example demonstrating `keep_all_text_in_hierarchy=False`
        >>> html1 = '<div>Hello <p>Hello</p>Hi</div>'
        >>> html2 = '<div>Hello <p>Hello</p><p>World</p>Hi</div>'
        >>> incremental_tree = find_incremental_elements(html1, html2, keep_hierarchy=True, keep_all_text_in_hierarchy_for_incremental_change=False)
        >>> print(str(incremental_tree).strip())
        <div><p>World</p></div>

        # Example demonstrating `strip_texts_before_concatenation=True`
        >>> html1 = '<div><p> Hello </p></div>'
        >>> html2 = '<div><p>Hello</p><p>World</p></div>'
        >>> new_elements = find_incremental_elements(html1, html2, strip_texts_before_concatenation=True)
        >>> for elem in new_elements:
        ...     print(elem)
        <p>World</p>

        # Example with `ignore_attrs`.
        # Note the specified attributes are only ignored for comparison.
        # The output element should still have the attributes.
        >>> html1 = '<div id="content"><p>Hello</p></div>'
        >>> html2 = '<div id="main"><p>Hello</p><p id="new">World</p></div>'
        >>> incremental_tree = find_incremental_elements(html1, html2, keep_hierarchy=True, ignore_attrs_for_comparison=['id'])
        >>> print(str(incremental_tree).strip())
        <div id="main"><p id="new">World</p></div>

        # Complex example with nested structures
        >>> html1 = '''
        ... <html>
        ...   <body>
        ...     <div class="container">
        ...       <h1>Welcome</h1>
        ...       <p>Introduction</p>
        ...     </div>
        ...   </body>
        ... </html>
        ... '''
        >>> html2 = '''
        ... <html>
        ...   <body>
        ...     <div class="container">
        ...       <h1>Welcome</h1>
        ...       <p>Introduction</p>
        ...       <p>New Content</p>
        ...     </div>
        ...     <footer>Contact us</footer>
        ...   </body>
        ... </html>
        ... '''
        >>> incremental_tree = find_incremental_elements(html1, html2, keep_hierarchy=True)
        >>> print(str(incremental_tree).strip())
        <html><body><div class="container"><p>New Content</p></div><footer>Contact us</footer></body></html>

        # Example with text nodes only in new elements
        >>> html1 = '<div><p>Old Content</p></div>'
        >>> html2 = '<div><p>Old Content</p><p>New Content</p>Extra text</div>'
        >>> incremental_tree = find_incremental_elements(
        ...     html1, html2,
        ...     keep_hierarchy=True,
        ...     keep_all_text_in_hierarchy_for_incremental_change=False
        ... )
        >>> print(str(incremental_tree).strip())
        <div><p>Old Content</p><p>New Content</p>Extra text</div>
        >>> incremental_tree = find_incremental_elements(
        ...     html1, html2,
        ...     keep_hierarchy=True,
        ...     consider_text_for_comparison=False,
        ...     keep_all_text_in_hierarchy_for_incremental_change=False
        ... )
        >>> print(str(incremental_tree).strip())
        None
    """

    if ignore_attrs_for_comparison is None:
        ignore_attrs_for_comparison = ()

    # Collect signatures from element1
    signatures1 = set()
    for elem in (element1, *element1.find_all()):
        signature = get_element_signature(
            elem,
            ignore_attrs_for_comparison,
            consider_children=False,
            consider_text=consider_text_for_comparison,
            consider_immediate_text_only=True,
            strip_texts_before_concatenation=strip_texts_before_concatenation
        )
        signatures1.add(signature)

    if keep_hierarchy:
        def find_new_elements_recursive(new_element):
            if isinstance(new_element, NavigableString):
                return NavigableString(str(new_element)) if keep_all_text_in_hierarchy_for_incremental_change else None

            signature = get_element_signature(
                new_element,
                ignore_attrs=ignore_attrs_for_comparison,
                consider_children=False,
                consider_text=consider_text_for_comparison,
                consider_immediate_text_only=True,
                strip_texts_before_concatenation=strip_texts_before_concatenation
            )

            if signature not in signatures1:
                # New element, copy entirely
                return new_element

            # Element exists in old, but maybe its children contain new elements
            new_element_copy = copy_html_element_name_and_attrs(
                new_element,
                copy_children=False
            )

            all_child_strings = True
            new_element_contents = list(new_element.contents)
            for child in new_element_contents:
                if isinstance(child, NavigableString):
                    child = str(child).strip('\n')
                    child_copy = NavigableString(child) if bool(
                        child) and keep_all_text_in_hierarchy_for_incremental_change else None
                else:
                    child_copy = find_new_elements_recursive(child)
                    all_child_strings = False

                if child_copy:
                    new_element_copy.append(child_copy)

            if new_element_copy.contents and not all_child_strings:
                return new_element_copy
            else:
                return None  # No new elements in this subtree

        incremental_tree = find_new_elements_recursive(element2)
        return incremental_tree
    else:
        # Find elements in element2 that are not in element1
        new_elements = []
        for elem in (element2, *element2.find_all()):
            signature = get_element_signature(
                elem,
                ignore_attrs_for_comparison,
                consider_children=False,
                consider_text=consider_text_for_comparison,
                consider_immediate_text_only=True,
                strip_texts_before_concatenation=strip_texts_before_concatenation
            )
            if signature not in signatures1:
                new_elements.append(elem)
        return new_elements


def extract_incremental_html_change(
        html_content_old: str,
        html_content_new: str,
        max_relative_change_for_extraction: float = 0.9,
        max_absolute_change_for_extraction: int = 0,
        min_relative_change_for_extraction: float = 0,
        min_absolute_change_for_extraction: int = 0,
        consider_text_for_comparison: bool = True,
        keep_all_text_in_hierarchy_for_incremental_change: bool = True,
        ignore_attrs_for_comparison=(ATTR_NAME_INCREMENTAL_ID,)
) -> str:
    """
    Extracts the incremental changes between two HTML documents, with minimum and
    maximum thresholds (both relative and absolute) to decide whether to apply
    the incremental snippet or keep the full new HTML.

    This function compares `html_content_old` and `html_content_new` to find only
    the “new or changed” parts (the “incremental snippet”). If the snippet’s size
    is within specified min–max bounds, it returns that snippet; otherwise, it
    returns the entire `html_content_new`.

    **Thresholds Explained**:
    1. **Relative Threshold** (`relative_change`) is:
        (length of incremental snippet) / (length of `html_content_new`).
       - **Max** (`max_relative_change_for_extraction`):
         If nonzero, the snippet must be *strictly below* this ratio to be used.
         If 0 (or False), this check is disabled (no upper bound).
       - **Min** (`min_relative_change_for_extraction`):
         If nonzero, the snippet must be *at least* this ratio to be used.
         If 0 (or False), this check is disabled (no lower bound).

    2. **Absolute Threshold** (`absolute_change`) is:
        (length of incremental snippet) in characters (or bytes).
       - **Max** (`max_absolute_change_for_extraction`):
         If nonzero, the snippet must be *strictly below* this integer to be used.
         If 0 (or False), this check is disabled (no upper bound).
       - **Min** (`min_absolute_change_for_extraction`):
         If nonzero, the snippet must be *at least* this integer to be used.
         If 0 (or False), this check is disabled (no lower bound).

    An incremental snippet is only returned if it simultaneously satisfies:
      - **max_relative** (if > 0),
      - **max_absolute** (if > 0),
      - **min_relative** (if > 0),
      - **min_absolute** (if > 0).

    Otherwise, the full `html_content_new` is returned.

    Args:
        html_content_old (str):
            The original HTML content.

        html_content_new (str):
            The new or updated HTML content to compare against the original.

        max_relative_change_for_extraction (float, optional):
            If > 0 and <= 1.0, the snippet’s relative size must be below this
            ratio to be returned. Defaults to 0.9.
            If 0 (or False), no upper bound is applied for relative size.

        max_absolute_change_for_extraction (int, optional):
            If > 0, the snippet’s absolute length must be below this integer.
            Defaults to 0 (disabled).

        min_relative_change_for_extraction (float, optional):
            If > 0 and <= 1.0, the snippet’s relative size must be at least
            this ratio. Defaults to 0 (disabled).

        min_absolute_change_for_extraction (int, optional):
            If > 0, the snippet’s absolute length must be at least this integer.
            Defaults to 0 (disabled).

        consider_text_for_comparison (bool, optional):
            If True, text content is compared and can trigger incremental changes.
            If False, only element structure/attributes are considered.
            Defaults to True.

        keep_all_text_in_hierarchy_for_incremental_change (bool, optional):
            If True, retains all text nodes in the parent hierarchy of new elements.
            If False, only text directly related to newly inserted elements is kept.
            Defaults to True.

        ignore_attrs_for_comparison (Sequence[str], optional):
            Attributes (by name) to ignore during comparison. They remain in the
            output HTML if present, but do not cause differences.
            Defaults to (ATTR_NAME_INCREMENTAL_ID,).

    Returns:
        str:
            The incremental snippet (new or changed portions) if all thresholds
            are satisfied; otherwise, the full `html_content_new`.

    Raises:
        ValueError:
            - If any max/min relative threshold is not in the range (0,1) (when not zero).
            - If any max/min absolute threshold is not a positive integer (when not zero).


    Examples:
        >>> html_old = '<div><p>Hello</p></div>'
        >>> html_new = '<div><p>Hello</p><p>World</p></div>'

        >>> extract_incremental_html_change(html_old, html_new, max_relative_change_for_extraction=0)
        '<div><p>World</p></div>'

        >>> # With threshold as a float (e.g., 0.5)
        >>> extract_incremental_html_change(html_old, html_new, max_relative_change_for_extraction=0.9)
        '<div><p>World</p></div>'

        >>> # When the incremental change is small relative to the threshold
        >>> extract_incremental_html_change(html_old, html_new, max_relative_change_for_extraction=0.5)
        '<div><p>Hello</p><p>World</p></div>'

        >>> # Ignoring text content during comparison
        >>> html_old = '<div><p>Hello</p></div>'
        >>> html_new = '<div><p>Hi</p></div>'
        >>> extract_incremental_html_change(html_old, html_new, consider_text_for_comparison=False)
        '<div><p>Hi</p></div>'

        >>> # Considering text content during comparison
        >>> extract_incremental_html_change(html_old, html_new, consider_text_for_comparison=True)
        '<div><p>Hi</p></div>'

        >>> # Using ignore attributes for comparison
        >>> html_old = '<div id="content"><p>Hello</p></div>'
        >>> html_new = '<div id="main"><p>Hello</p><p>World</p></div>'
        >>> extract_incremental_html_change(html_old, html_new, ignore_attrs_for_comparison=['id'])
        '<div id="main"><p>World</p></div>'

        >>> # When threshold is False (no extraction)
        >>> extract_incremental_html_change(html_old, html_new, max_relative_change_for_extraction=False)
        '<div id="main"><p>Hello</p><p>World</p></div>'

        >>> # Complex example with nested structures
        >>> html_old = '''
        ... <html>
        ...   <body>
        ...     <div class="container">
        ...       <h1>Welcome</h1>
        ...       <p>Introduction</p>
        ...     </div>
        ...   </body>
        ... </html>
        ... '''
        >>> html_new = '''
        ... <html>
        ...   <body>
        ...     <div class="container">
        ...       <h1>Welcome</h1>
        ...       <p>Introduction</p>
        ...       <p>New Content</p>
        ...     </div>
        ...     <footer>Contact us</footer>
        ...   </body>
        ... </html>
        ... '''
        >>> result = extract_incremental_html_change(html_old, html_new, max_relative_change_for_extraction=0)
        >>> print(result.strip())
        <html><body><div class="container"><p>New Content</p></div><footer>Contact us</footer></body></html>
    """

    # region Validate extraction thresholds
    if max_relative_change_for_extraction:
        if not (
                isinstance(max_relative_change_for_extraction, float)
                and 0.0 <= max_relative_change_for_extraction <= 1.0
        ):
            raise ValueError(
                "'relative_threshold_for_extraction' must be a float in range [0,1]."
            )

    if max_absolute_change_for_extraction:
        if not (
                isinstance(max_absolute_change_for_extraction, int)
                and max_absolute_change_for_extraction > 0
        ):
            raise ValueError(
                "'absolute_threshold_for_extraction' must be a positive integer."
            )

    if min_relative_change_for_extraction:
        if not (
                isinstance(min_relative_change_for_extraction, float)
                and 0.0 <= min_relative_change_for_extraction <= 1.0
        ):
            raise ValueError(
                "'min_relative_change_for_extraction' must be a float in range [0, 1]."
            )

    if min_absolute_change_for_extraction:
        if not (
                isinstance(min_absolute_change_for_extraction, int)
                and min_absolute_change_for_extraction > 0
        ):
            raise ValueError(
                "'min_absolute_change_for_extraction' must be a positive integer."
            )
    # endregion

    incremental_elements = find_incremental_elements(
        element1=html_content_old,
        element2=html_content_new,
        keep_hierarchy=True,
        consider_text_for_comparison=consider_text_for_comparison,
        keep_all_text_in_hierarchy_for_incremental_change=keep_all_text_in_hierarchy_for_incremental_change,
        ignore_attrs_for_comparison=ignore_attrs_for_comparison
    )

    if incremental_elements is not None:
        html_content_incremental = str(incremental_elements)
        relative_change = len(html_content_incremental) / len(html_content_new)
        absolute_change = len(html_content_incremental)
        if (
                # if the change is too significant, then it is not incremental change
                ((not max_relative_change_for_extraction) or relative_change < max_relative_change_for_extraction)
                and ((not max_absolute_change_for_extraction) or (absolute_change < max_absolute_change_for_extraction))
                # if the change is considered minimal, then it is not incremental change
                and ((not min_relative_change_for_extraction) or relative_change >= min_relative_change_for_extraction)
                and ((not min_absolute_change_for_extraction) or absolute_change >= min_absolute_change_for_extraction)
        ):
            html_content_new = html_content_incremental

    return html_content_new


def find_element_by_attribute(html_content: str, attribute_name: str, attribute_value: str) -> str:
    """
    Finds the HTML element with the specified attribute and value.

    Args:
        html_content: A string containing HTML content to be searched.
        attribute_name: The name of the attribute to search for.
        attribute_value: The value of the attribute to match.

    Returns:
        The HTML representation of the found element, or an empty string if not found.

    Examples:
        >>> sample_html = '''
        ... <div __id__="123">Hello, world!</div>
        ... <div __id__="456">Another div</div>
        ... <span __id__="123">Span with matching id</span>
        ... '''
        >>> found_element = find_element_by_attribute(sample_html, '__id__', '123')
        >>> str(found_element)
        '<div __id__="123">Hello, world!</div>'

        This example demonstrates finding an element with the specified attribute and value ('__id__="123"') within a more complex HTML structure.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    found_element = soup.find(attrs={attribute_name: attribute_value})
    return found_element


def find_element_by_any_attribute(html_content: str, attributes: Mapping[str, str]) -> str:
    soup = BeautifulSoup(html_content, 'html.parser')
    for attribute_name, attribute_value in attributes.items():
        found_element = soup.find(attrs={attribute_name: attribute_value})
        if found_element:
            return found_element


def get_xpath(
        tag_name: Optional[str] = '*',
        attributes: Mapping[str, Any] = None,
        text: str = None,
        immediate_text: str = None
) -> str:
    """
    Generate an XPath expression based on an optional tag name, attribute key-value pairs, and optional text content.

    Args:
        tag_name (str, optional): The tag name of the element. Defaults to '*' which matches any tag.
        attributes (dict, optional): A dictionary containing attribute key-value pairs.
        text (str, optional): The text content to search for within the element and its descendants.
        immediate_text (str, optional): The immediate text content to search for within the element.

    Returns:
        str: The generated XPath expression.

    Example:
        >>> get_xpath('a', {'class': ['uitk-tab-anchor'], 'href': '/Flights'})
        '//a[contains(@class, "uitk-tab-anchor") and @href="/Flights"]'
        >>> get_xpath('a', {'class': ['uitk-tab-anchor'], 'href': '/Flights'}, "Book Now")
        '//a[contains(@class, "uitk-tab-anchor") and @href="/Flights" and contains(., "Book Now")]'
        >>> get_xpath(attributes={'class': ['button'], 'type': 'submit'}, text="Click Here")
        '//*[contains(@class, "button") and @type="submit" and contains(., "Click Here")]'

        >>> from lxml import etree
        >>> from lxml.html import fromstring
        >>> html_doc = '''
        ... <div class="container">
        ...     <h1>Welcome to My Site</h1>
        ...     <p class="description">Learn more about our services.</p>
        ...     <div class="button-container">
        ...         <button type="submit" class="btn primary large" onclick="submitForm()">Submit</button>
        ...         <button type="button" class="btn secondary">Cancel</button>
        ...     </div>
        ...     <a href="/contact" class="link" title="Contact Us">Contact us today!</a>
        ...     <div class="footer">
        ...         <p class="info">Visit our blog for more information.</p>
        ...         <p class="info">Follow us on <a href="/social" class="link social">social media</a></p>
        ...     </div>
        ... </div>
        ... '''
        >>> tree = fromstring(html_doc)
        >>> xpath_submit_button = get_xpath('button', attributes={'type': 'submit', 'class': ['btn', 'primary', 'large']}, immediate_text='Submit')
        >>> submit_button = tree.xpath(xpath_submit_button)
        >>> submit_button[0].text.strip() if submit_button else 'No Button Found'
        'Submit'
    """
    if not tag_name:
        tag_name = '*'
    xpath_parts = [f"//{tag_name}"]
    conditions = []
    if attributes:
        if not isinstance(attributes, Mapping):
            raise TypeError(
                f"'attributes' must be a key/value mapping; got '{attributes}' of type '{type(attributes)}'")
        for key, value in attributes.items():
            if isinstance(value, str):
                conditions.append(f'@{key}="{value}"')
            elif isinstance(value, Sequence):  # Handling attributes with multiple possible values
                conditions.extend([f'contains(@{key}, "{v}")' for v in value])
            else:
                conditions.append(f'@{key}="{value}"')

    if text:
        conditions.append(f'contains(., "{text}")')

    if immediate_text:
        conditions.append(f'contains(text(), "{immediate_text}")')

    if conditions:
        xpath_parts.append('[' + ' and '.join(conditions) + ']')
    return ''.join(xpath_parts)


def add_unique_index_to_html(html_content: str, index_name: str = ATTR_NAME_INCREMENTAL_ID) -> str:
    """
    Adds a unique index to each HTML tag in the provided HTML content using a specified attribute name.

    Args:
        html_content (str): A string containing HTML content to be processed.
        index_name (str): The attribute name to use for the index. Defaults to ATTR_NAME_INCREMENTAL_ID ('__id__').

    Returns:
        str: Modified HTML content with unique index attributes added to each tag.

    Examples:
        This example demonstrates how each tag in the HTML string is assigned a unique index based on the order it appears, using the default index name '__id__'.
        >>> sample_html = "<div><p>Hello</p><p>World</p></div>"
        >>> modified_html = add_unique_index_to_html(sample_html)
        >>> print(modified_html)
        <div __id__="0"><p __id__="1">Hello</p><p __id__="2">World</p></div>

    """
    soup = BeautifulSoup(html_content, 'html.parser')

    index = 0  # Initialize a counter
    for element in soup.descendants:
        if element.name is not None:  # Check if it is a tag and not a string
            element[index_name] = str(index)
            index += 1

    return str(soup)


# ============================================================================
# Elements to XPath Utility
# ============================================================================

def _escape_xpath_string(value: str) -> str:
    """
    Escape string for use in XPath attribute comparison.

    Handles values containing single quotes, double quotes, or both.

    Args:
        value: The string value to escape

    Returns:
        Escaped string suitable for XPath (with quotes)

    Examples:
        >>> _escape_xpath_string("simple")
        "'simple'"
        >>> _escape_xpath_string("it's")
        '"it\\'s"'
        >>> _escape_xpath_string('say "hello"')
        '\\'say "hello"\\''
        >>> _escape_xpath_string("it's \"complex\"")
        "concat('it', \"'\", 's \"complex\"')"
    """
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    # Contains both quotes - use concat()
    # After split("'"), parts cannot contain ', so safe to wrap in single quotes
    # Single quotes CAN contain double quotes in XPath
    parts = value.split("'")
    result_parts = []
    for i, part in enumerate(parts):
        if part:
            result_parts.append(f"'{part}'")  # always single quotes
        if i < len(parts) - 1:
            result_parts.append('"\'"')  # literal ' wrapped in double quotes
    return f"concat({', '.join(result_parts)})"


def _is_hash_like_value(value: str) -> bool:
    """
    Check if a value appears to be a hash or dynamically generated.

    Hash-like values include:
    - Framework-generated IDs (react-, ember123, ng-, :r0:)
    - UUID-like hex strings (8+ hex chars)
    - Pure numeric IDs
    - Short mixed-case alphanumeric with unusual patterns (Google minified: APjFqb, gLFyf)

    Args:
        value: The attribute value to check

    Returns:
        True if value looks like a hash/dynamic value that should be skipped
    """
    # Check against explicit patterns
    for pattern in HASH_LIKE_VALUE_PATTERNS:
        if re.match(pattern, value):
            return True
    # Check for hash-like appearance using heuristics
    return _looks_like_hash(value)


def _is_generic_class(class_name: str) -> bool:
    """Check if a class name is generic or hash-like."""
    # Check against known generic classes (exact match only)
    if class_name in GENERIC_CLASSES:
        return True

    # Check utility class prefixes (only if followed by digits, e.g., p-4, mt-2)
    for prefix in UTILITY_CLASS_PREFIXES:
        if class_name.startswith(prefix):
            suffix = class_name[len(prefix):]
            # Only match if suffix starts with digit (utility class like p-4)
            # Not BEM-style like p-top_nav (meaningful)
            if suffix and suffix[0].isdigit():
                return True

    # Check for hash-like classes (random-looking alphanumeric)
    if re.match(r'^[a-zA-Z][a-zA-Z0-9]{5,}$', class_name):
        # Likely a minified/hashed class if it's long alphanumeric
        if not any(c in class_name for c in '-_'):
            return True
    return False


def _get_element_text(element: Tag) -> Optional[str]:
    """Get immediate text content of element (not including children)."""
    texts = [t.strip() for t in element.strings if t.strip()]
    if texts:
        # Use the first substantial text
        return texts[0] if len(texts[0]) <= 50 else None
    return None


def _generate_base_xpath(element: Tag, exclude_attrs: Sequence[str]) -> List[str]:
    """
    Generate candidate xpaths for a single element without parent context.

    Returns list of candidate xpaths sorted by value readability.
    Attributes with hash-like values are skipped to prefer stable attributes.
    More readable attribute values (e.g., 'Search') are preferred over
    cryptic ones (e.g., 'q').
    """
    tag_name = element.name
    # Collect (xpath, readability_score) tuples
    candidates_with_scores: List[Tuple[str, float]] = []

    # Strategy 1 & 2: Attributes in priority order (skip hash-like and dynamic values)
    for attr in XPATH_ATTR_PRIORITY:
        if attr in exclude_attrs:
            continue
        val = element.get(attr)
        if val:
            if isinstance(val, list):
                val = ' '.join(val)
            # Skip hash-like values - they're unstable
            if _is_hash_like_value(val):
                continue
            # Skip dynamic/personalized content (dates, counts, prices, etc.) - equally unstable
            if _HAS_DYNAMIC_DETECTION and contains_dynamic_content is not None:
                if contains_dynamic_content(val):
                    continue
            escaped = _escape_xpath_string(val)
            xpath = f"//{tag_name}[@{attr}={escaped}]"

            # Score readability of the attribute value
            if _HAS_READABILITY and get_string_readability_score is not None:
                score = get_string_readability_score(val)
            else:
                # Fallback: use simple heuristics
                # Longer values with spaces are generally more readable
                score = min(1.0, len(val) / 20) if ' ' in val else min(0.5, len(val) / 20)

            # Boost semantic attributes (title, aria-label, placeholder, alt)
            # These are human-facing descriptors, so prefer them over technical attrs
            if attr in SEMANTIC_ATTRS:
                score += SEMANTIC_ATTR_BOOST

            candidates_with_scores.append((xpath, score))

    # Strategy 3: Text content (high readability - it's visible text)
    text = _get_element_text(element)
    if text:
        escaped = _escape_xpath_string(text)
        xpath = f"//{tag_name}[normalize-space(text())={escaped}]"
        # Text content is usually very readable
        if _HAS_READABILITY and get_string_readability_score is not None:
            score = get_string_readability_score(text)
        else:
            score = 0.8  # Text content is generally readable
        candidates_with_scores.append((xpath, score))

    # Strategy 4: Attribute combinations (type + another attr)
    if element.get('type') and 'type' not in exclude_attrs:
        type_val = element.get('type')
        for attr in ['name', 'value', 'placeholder']:
            if attr in exclude_attrs:
                continue
            val = element.get(attr)
            if val:
                type_escaped = _escape_xpath_string(type_val)
                val_escaped = _escape_xpath_string(val)
                xpath = f"//{tag_name}[@type={type_escaped} and @{attr}={val_escaped}]"
                # Score based on the attribute value
                if _HAS_READABILITY and get_string_readability_score is not None:
                    score = get_string_readability_score(val)
                else:
                    score = min(0.5, len(val) / 20)
                candidates_with_scores.append((xpath, score))

    # Strategy 5: Class-based (if distinctive classes exist)
    classes = element.get('class', [])
    if isinstance(classes, str):
        classes = classes.split()
    distinctive_classes = [c for c in classes if not _is_generic_class(c)]
    if distinctive_classes:
        # Try single distinctive class, scored by readability
        for cls in distinctive_classes[:2]:  # Limit to first 2
            escaped = _escape_xpath_string(cls)
            xpath = f"//{tag_name}[contains(@class, {escaped})]"
            # Score the class name's readability
            if _HAS_READABILITY and get_string_readability_score is not None:
                score = get_string_readability_score(cls)
            else:
                # Fallback: use length heuristic
                score = min(0.5, len(cls) / 30)
            candidates_with_scores.append((xpath, score))

    # Sort by readability score (highest first)
    candidates_with_scores.sort(key=lambda x: x[1], reverse=True)

    # Extract just the xpaths
    candidates = [xpath for xpath, score in candidates_with_scores]

    # Fallback: just the tag name (lowest priority)
    candidates.append(f"//{tag_name}")

    return candidates


def _add_parent_context(element: Tag, base_xpath: str, depth: int, exclude_attrs: Sequence[str]) -> Optional[str]:
    """
    Add parent context to an xpath up to the specified depth.

    Args:
        element: The target element
        base_xpath: The xpath for the element (starting with //)
        depth: How many parent levels to add (1 = immediate parent)
        exclude_attrs: Attributes to exclude

    Returns:
        XPath with parent context, or None if depth exceeds available parents
    """
    if depth <= 0:
        return base_xpath

    # Get ancestors up to depth
    ancestors = []
    parent = element.parent
    for _ in range(depth):
        if parent is None or parent.name in ('[document]', None):
            break
        ancestors.append(parent)
        parent = parent.parent

    if len(ancestors) < depth:
        return None  # Not enough parents

    # Build parent xpath prefix
    prefix_parts = []
    for ancestor in reversed(ancestors):
        ancestor_candidates = _generate_base_xpath(ancestor, exclude_attrs)
        # Use first candidate (most specific)
        if ancestor_candidates:
            # Remove leading // for ancestor parts
            part = ancestor_candidates[0]
            if part.startswith('//'):
                part = part[2:]
            prefix_parts.append(part)

    if not prefix_parts:
        return base_xpath

    # Combine: //ancestor1//ancestor2//element
    prefix = '//' + '//'.join(prefix_parts)
    # base_xpath starts with //, we need to append with //
    element_part = base_xpath[2:] if base_xpath.startswith('//') else base_xpath
    return f"{prefix}//{element_part}"


def _validate_xpath(xpath: str, html_context: str, expected_elements: List[Tag]) -> bool:
    """
    Validate that an xpath returns exactly the expected elements.

    Args:
        xpath: The xpath to test
        html_context: The HTML document
        expected_elements: List of BeautifulSoup Tags we expect to match

    Returns:
        True if xpath matches exactly the expected elements
    """
    try:
        # Parse HTML with lxml for xpath evaluation
        tree = etree.HTML(html_context)
        results = tree.xpath(xpath)

        if len(results) != len(expected_elements):
            return False

        # Build set of expected element identifiers
        # Use __id__ if available, otherwise use (tag_name, text_content) tuple
        expected_identifiers = set()
        for expected in expected_elements:
            expected_id = expected.get(ATTR_NAME_INCREMENTAL_ID)
            if expected_id:
                expected_identifiers.add(('__id__', expected_id))
            else:
                # Fallback: use tag name + text content as identifier
                tag_name = expected.name
                text_content = expected.get_text(strip=True)[:50] if expected.get_text(strip=True) else ''
                expected_identifiers.add(('tag_text', tag_name, text_content))

        # Build set of result identifiers
        result_identifiers = set()
        for result in results:
            result_id = result.get(ATTR_NAME_INCREMENTAL_ID)
            if result_id:
                result_identifiers.add(('__id__', result_id))
            else:
                # Fallback: use tag name + text content as identifier
                tag_name = result.tag
                # Use itertext() to get ALL nested text (like BeautifulSoup's get_text())
                # result.text only gets direct text, not nested text
                text_content = ''.join(result.itertext()).strip()[:50]
                result_identifiers.add(('tag_text', tag_name, text_content))

        # Check if all expected elements are found in results
        # Note: We check if expected is subset of results (results may have more due to xpath matching)
        # But since we already checked len(results) == len(expected_elements), this is an exact match check
        return expected_identifiers == result_identifiers
    except Exception:
        return False


def _find_matching_element_position(
    xpath: str,
    html_context: str,
    target_element: Tag,
    mode: XPathResolutionMode,
    **resolution_args,
) -> Optional[str]:
    """
    Find position of target element among xpath matches.

    When an xpath matches multiple elements, this function finds which one
    corresponds to the target element by comparing using the specified mode.

    Args:
        xpath: XPath expression that matches multiple elements
        html_context: Full HTML document
        target_element: BeautifulSoup Tag to find
        mode: Resolution mode (MATCH_BY_HTML, MATCH_BY_SIGNATURE, MATCH_BY_TEXT)
        **resolution_args: Arguments passed to comparison function

    Returns:
        Positional xpath like (//div)[2] if found, None otherwise.
    """
    try:
        tree = etree.HTML(html_context)
        results = tree.xpath(xpath)

        if not results:
            return None

        # Prepare target for comparison based on mode
        if mode == XPathResolutionMode.MATCH_BY_TEXT:
            target_text = target_element.get_text(strip=True)
        elif mode == XPathResolutionMode.MATCH_BY_SIGNATURE:
            target_sig = get_element_signature(target_element, **resolution_args)
        # MATCH_BY_HTML uses compare_elements directly, no prep needed

        # Check each result
        for i, result in enumerate(results, 1):
            # Convert lxml element to BeautifulSoup for comparison
            result_html = etree.tostring(result, encoding='unicode')
            result_soup = BeautifulSoup(result_html, 'html.parser').find()

            if result_soup is None:
                continue

            match_found = False

            if mode == XPathResolutionMode.MATCH_BY_HTML:
                # Use compare_elements() for flexible HTML comparison
                match_found = compare_elements(
                    target_element, result_soup, **resolution_args
                )

            elif mode == XPathResolutionMode.MATCH_BY_SIGNATURE:
                # Compare signatures
                result_sig = get_element_signature(result_soup, **resolution_args)
                match_found = (target_sig == result_sig)

            elif mode == XPathResolutionMode.MATCH_BY_TEXT:
                # Compare text content only
                result_text = result_soup.get_text(strip=True)
                match_found = (target_text == result_text)

            if match_found:
                return f"({xpath})[{i}]"

        return None
    except Exception:
        return None


def _find_common_ancestor(elements: List[Tag]) -> Optional[Tag]:
    """
    Find the lowest common ancestor of multiple elements.

    Args:
        elements: List of BeautifulSoup Tags

    Returns:
        Common ancestor Tag, or None if elements don't share a parent
    """
    if not elements:
        return None
    if len(elements) == 1:
        return elements[0].parent

    # Get ancestors for first element
    first_ancestors = []
    parent = elements[0].parent
    while parent and parent.name not in ('[document]', None):
        first_ancestors.append(parent)
        parent = parent.parent

    # Find first common ancestor
    for ancestor in first_ancestors:
        is_common = True
        for elem in elements[1:]:
            if ancestor not in list(elem.parents):
                is_common = False
                break
        if is_common:
            return ancestor

    return None


def _generate_multi_xpath(
    elements: List[Tag],
    common_ancestor: Optional[Tag],
    depth: int,
    exclude_attrs: Sequence[str]
) -> List[str]:
    """
    Generate xpath candidates for multiple elements.

    Returns list of candidate xpaths that might match all elements.
    """
    if not elements:
        return []

    candidates = []
    tag_name = elements[0].name

    # Check if all elements have same tag
    same_tag = all(e.name == tag_name for e in elements)
    if not same_tag:
        tag_name = '*'

    # Strategy M1: Common parent + child tag
    if common_ancestor:
        parent_candidates = _generate_base_xpath(common_ancestor, exclude_attrs)
        for parent_xpath in parent_candidates[:3]:  # Limit
            # Direct child
            candidates.append(f"{parent_xpath}/{tag_name}")
            # Descendant
            candidates.append(f"{parent_xpath}//{tag_name}")

    # Strategy M2: Common attribute pattern
    # Check if all elements share the same attribute value
    for attr in ['name', 'type', 'class']:
        if attr in exclude_attrs:
            continue
        first_val = elements[0].get(attr)
        if first_val:
            if isinstance(first_val, list):
                first_val = ' '.join(first_val)
            all_same = all(
                e.get(attr) == first_val or
                (isinstance(e.get(attr), list) and ' '.join(e.get(attr)) == first_val)
                for e in elements
            )
            if all_same:
                escaped = _escape_xpath_string(first_val)
                candidates.append(f"//{tag_name}[@{attr}={escaped}]")

    # Strategy M3: Common parent path + tag
    if common_ancestor:
        candidates.append(f"//{common_ancestor.name}//{tag_name}")

    return candidates


def elements_to_xpath(
    elements: Union[Tag, Sequence[Tag]],
    html_context: str,
    exclude_attrs: Sequence[str] = (ATTR_NAME_INCREMENTAL_ID,),
    max_depth: int = 3,
    resolution_mode: XPathResolutionMode = XPathResolutionMode.UNIQUE_ONLY,
    **resolution_args,
) -> str:
    """
    Generate the leanest xpath to uniquely identify one or more elements.

    Uses incremental depth: starts with simplest xpath (no parent context),
    then progressively adds parent context until exact match is found.

    Args:
        elements: Single BeautifulSoup Tag or list of Tags to generate xpath for
        html_context: Full HTML document for validation
        exclude_attrs: Attributes to exclude from xpath generation (e.g., '__id__')
        max_depth: Maximum parent levels to include for context.
                   Use -1 for unlimited depth (try all ancestors).
        resolution_mode: Strategy for handling non-unique xpath matches.
                        - UNIQUE_ONLY: Raise ValueError if not unique (default)
                        - FIRST_MATCH: Return xpath with [1] index
                        - MATCH_BY_HTML: Find element using compare_elements()
                        - MATCH_BY_SIGNATURE: Find element using get_element_signature()
                        - MATCH_BY_TEXT: Find element by text content only
        **resolution_args: Additional arguments passed to the comparison function.
                          For MATCH_BY_HTML (compare_elements): ignore_attrs, consider_children, etc.
                          For MATCH_BY_SIGNATURE (get_element_signature): ignore_attrs, consider_text, etc.

    Returns:
        XPath string that matches exactly the input element(s)

    Raises:
        ValueError: If no valid xpath can be generated within max_depth
                   (and resolution_mode is UNIQUE_ONLY)

    Examples:
        >>> html = '<div><input title="Search" type="text"/></div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> elem = soup.find('input')
        >>> xpath = elements_to_xpath(elem, html)
        >>> xpath  # Should use title attribute
        "//input[@title='Search']"

        >>> # With resolution mode for non-unique elements
        >>> xpath = elements_to_xpath(elem, html,
        ...     resolution_mode=XPathResolutionMode.MATCH_BY_SIGNATURE,
        ...     ignore_attrs=['data-reactid'])
    """
    # Normalize to list
    if isinstance(elements, Tag):
        element_list = [elements]
    else:
        element_list = list(elements)

    if not element_list:
        raise ValueError("No elements provided")

    # Single element case
    if len(element_list) == 1:
        element = element_list[0]

        # Get base xpath candidates (depth 0)
        base_candidates = _generate_base_xpath(element, exclude_attrs)

        # Try each candidate at increasing depths
        current_depth = 0
        max_iterations = max_depth if max_depth >= 0 else 100  # Reasonable limit for unlimited

        while current_depth <= max_iterations:
            for base_xpath in base_candidates:
                if current_depth == 0:
                    xpath = base_xpath
                else:
                    xpath = _add_parent_context(element, base_xpath, current_depth, exclude_attrs)
                    if xpath is None:
                        continue

                if _validate_xpath(xpath, html_context, element_list):
                    return xpath

            current_depth += 1

        # Last resort: positional xpath using __id__ matching
        # If element has __id__, we can reliably find its position among matches.
        # Use the best descriptive xpath candidate (not just //tag) for better readability.
        elem_id = element.get(ATTR_NAME_INCREMENTAL_ID)
        if elem_id and base_candidates:
            base_xpath = base_candidates[0]  # Use best descriptive xpath
            try:
                tree = etree.HTML(html_context)
                all_matching = tree.xpath(base_xpath)

                # Find the position of our element by __id__ matching
                for i, match in enumerate(all_matching, 1):
                    if match.get(ATTR_NAME_INCREMENTAL_ID) == elem_id:
                        positional_xpath = f"({base_xpath})[{i}]"
                        if _validate_xpath(positional_xpath, html_context, element_list):
                            return positional_xpath
                        break
            except Exception:
                pass

        # Apply resolution mode for non-unique xpath
        if resolution_mode == XPathResolutionMode.UNIQUE_ONLY:
            raise ValueError(f"Could not generate unique xpath for element within max_depth={max_depth}")

        elif resolution_mode == XPathResolutionMode.FIRST_MATCH:
            # Return best candidate with [1] index
            if base_candidates:
                best_xpath = base_candidates[0]
                return f"({best_xpath})[1]"

        elif resolution_mode in (XPathResolutionMode.MATCH_BY_HTML,
                                  XPathResolutionMode.MATCH_BY_SIGNATURE,
                                  XPathResolutionMode.MATCH_BY_TEXT):
            # Try each candidate xpath, find matching element by comparison
            for xpath_candidate in base_candidates:
                result = _find_matching_element_position(
                    xpath_candidate, html_context, element,
                    resolution_mode, **resolution_args
                )
                if result:
                    return result

        raise ValueError(f"Could not find matching element with resolution_mode={resolution_mode}")

    # Multiple elements case
    common_ancestor = _find_common_ancestor(element_list)

    # Get multi-element xpath candidates
    multi_candidates = _generate_multi_xpath(element_list, common_ancestor, 0, exclude_attrs)

    # Try each candidate
    for xpath in multi_candidates:
        if _validate_xpath(xpath, html_context, element_list):
            return xpath

    # Strategy M4: Union of individual xpaths (fallback)
    individual_xpaths = []
    for elem in element_list:
        try:
            single_xpath = elements_to_xpath(
                elem, html_context, exclude_attrs, max_depth,
                resolution_mode, **resolution_args
            )
            individual_xpaths.append(single_xpath)
        except ValueError:
            pass

    if individual_xpaths:
        union_xpath = ' | '.join(individual_xpaths)
        if _validate_xpath(union_xpath, html_context, element_list):
            return union_xpath

    raise ValueError(f"Could not generate xpath for {len(element_list)} elements")
