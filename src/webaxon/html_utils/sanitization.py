import re
from functools import partial
from types import MappingProxyType
from typing import Iterable, Union, Mapping, Tuple, Sequence, Optional

from bs4 import BeautifulSoup, Comment, Tag

from rich_python_utils.algorithms.tree.traversal import post_order_traversal
from webaxon.html_utils.common import (
    is_element_hidden,
    is_element_hidden_,
    is_element_disabled,
    is_element_disabled_,
    keep_specified_attributes,
    has_immediate_text,
    remove_immediate_text,
    support_input_html, get_immediate_text,
    HTML_COMMON_NON_INTERACTABLE_TAGS, HTML_COMMON_LIST_LIKE_ATTRIBUTES
)
from webaxon.html_utils.common import merge_attributes as _merge_attributes
from webaxon.html_utils.element_identification import extract_incremental_html_change, ATTR_NAME_INCREMENTAL_ID
from webaxon.html_utils.element_rule_matching import (
    is_element_matching_rule_set,
    get_active_rules,
    RULESET_NAME_GLOBAL,
    ACTIVATION_FLAG_PRESERVE_CONTAINER,
    RULE_TYPE_ANY_ATTRIBUTE_VALUE_MATCHES_PATTERN
)

DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE = ('script', 'style')
DEFAULT_HTML_TAGS_REPLACE_BY_BEGIN_END_MARKS = MappingProxyType({
    'strong': ('**', '**'),
    'b': ('**', '**'),
    'em': ('**', '**'),
    'i': ('_', '_'),
    'p': ('\n', '\n')
})
DEFAULT_HTML_CLEAN_TAGS_TO_KEEP = (
    'a', 'button', 'input', 'ul', 'ol', 'li', 'select', 'option'
)
DEFAULT_HTML_CLEAN_TAGS_TO_KEEP_WITH_EXTRA_CONTENTS = DEFAULT_HTML_CLEAN_TAGS_TO_KEEP + (
    'img', 'video', 'audio', 'embed', 'object', 'iframe'
)
DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP = (
    'class', 'href', '*name', '*label', 'alt', 'src', 'type', 'data', '*title', 'srcdoc', 'disabled')

DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP_WITH_INCREMENTAL_ID = DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP + (
    ATTR_NAME_INCREMENTAL_ID,)

DEFAULT_ADDITIONAL_RULES = MappingProxyType({
    RULESET_NAME_GLOBAL: (
        MappingProxyType({
            'return': 'keep',
            'tags': ('div',),
            'activation_flags': (ACTIVATION_FLAG_PRESERVE_CONTAINER,),
            'rule-type': RULE_TYPE_ANY_ATTRIBUTE_VALUE_MATCHES_PATTERN,
            'attributes': ('class', '*name', '*title', 'id'),
            'pattern': '*@ scroll|list|view|editor'
        }),
    )
})

DEFAULT_ADDITIONAL_RULES_FOR_DISABLED_ELEMENTS = MappingProxyType({
    RULESET_NAME_GLOBAL: (
        # Rule 1: Remove disabled input elements
        MappingProxyType({
            'return': 'remove',
            'tags': ('input',),  # Conservative: only inputs by default
            'rule-type': RULE_TYPE_ANY_ATTRIBUTE_VALUE_MATCHES_PATTERN,
            'attributes': ('disabled',),
            'pattern': '!/false'  # Match any disabled value except "false" (case-insensitive, for JS frameworks)
        }),
        # Rule 2: Keep all other elements (prevents fallback to comprehensive check)
        MappingProxyType({
            'return': 'keep',
            'tags': ('*',)  # Wildcard: matches all tags
        }),
    )
})

# Default rules for hidden element filtering
# By default, use a special sentinel dict that triggers comprehensive is_element_hidden() checking
# This enables full hidden element detection (hidden attr, display:none, visibility:hidden,
# aria-hidden="true", class="hidden")
# To disable hidden element removal entirely, pass hidden_element_rule_sets={} or None
# To keep specific hidden elements, add custom rules with 'keep' actions
# Special marker dict that is non-empty (truthy) but has a special key
DEFAULT_ADDITIONAL_RULES_FOR_HIDDEN_ELEMENTS = MappingProxyType({'__use_comprehensive_check__': True})

DEFAULT_RULE_ACTIVATION_FLAGS = (
    ACTIVATION_FLAG_PRESERVE_CONTAINER,
)


def clean_newlines_between_tags(html: str, exclude_tags: tuple = ('pre', 'textarea')) -> str:
    """
    Removes multiple newlines between HTML tags while preserving newlines within specified tags.

    This function processes an HTML string to collapse multiple consecutive newlines between HTML tags
    into a single newline. It ensures that newlines within the content of specified tags (e.g., `<pre>`, `<textarea>`)
    remain untouched, preserving their formatting.

    Args:
        html (str): The HTML content to process.
        exclude_tags (tuple, optional): A tuple of tag names whose internal newlines should be preserved.
            Defaults to `('pre', 'textarea')`. If set to `None`, no tags are excluded, and all newlines between tags
            will be processed.

    Returns:
        str: The processed HTML string with multiple newlines between tags reduced.

    Examples:
        >>> html_input = "<div><p>First Paragraph</p><p>Second Paragraph</p></div>"
        >>> result = clean_newlines_between_tags(html_input)
        >>> print(result)
        <div><p>First Paragraph</p><p>Second Paragraph</p></div>

        >>> html_input = "<div><p>First Paragraph</p><p>Second\\n\\n Paragraph</p></div>"
        >>> result = clean_newlines_between_tags(html_input)
        >>> print(result)
        <div><p>First Paragraph</p><p>Second
        <BLANKLINE>
         Paragraph</p></div>

        >>> html_input = "<div>\\n\\n<p>First Paragraph</p>\\n\\n<p>Second Paragraph</p>\\n</div>"
        >>> expected_output = "<div>\\n<p>First Paragraph</p>\\n<p>Second Paragraph</p>\\n</div>"
        >>> result = clean_newlines_between_tags(html_input)
        >>> print(result)
        <div>
        <p>First Paragraph</p>
        <p>Second Paragraph</p>
        </div>

        >>> html_input = "<div>\\n\\n<pre>\\nLine one.\\nLine two.\\n</pre>\\n\\n</div>"
        >>> expected_output = "<div>\\n<pre>\\nLine one.\\nLine two.\\n</pre>\\n</div>"
        >>> result = clean_newlines_between_tags(html_input)
        >>> print(result)
        <div>
        <pre>
        Line one.
        Line two.
        </pre>
        </div>

        >>> html_input = "<div>\\n\\n<textarea>\\nUser input here.\\n</textarea>\\n\\n</div>"
        >>> expected_output = "<div>\\n<textarea>\\nUser input here.\\n</textarea>\\n</div>"
        >>> result = clean_newlines_between_tags(html_input)
        >>> print(result)
        <div>
        <textarea>
        User input here.
        </textarea>
        </div>

        >>> html_input = "<div>\\n\\n<p>Paragraph with <span>inline</span> elements.</p>\\n\\n</div>"
        >>> expected_output = "<div>\\n<p>Paragraph with <span>inline</span> elements.</p>\\n</div>"
        >>> result = clean_newlines_between_tags(html_input)
        >>> print(result)
        <div>
        <p>Paragraph with <span>inline</span> elements.</p>
        </div>

        # No exclusions; all newlines between tags are processed
        >>> html_input = "<div>\\n\\n<pre>\\nLine one.\\nLine two.\\n</pre>\\n\\n</div>"
        >>> expected_output = "<div>\\n<pre>\\nLine one.\\nLine two.\\n</pre>\\n</div>"
        >>> result = clean_newlines_between_tags(html_input, exclude_tags=None)
        >>> print(result)
        <div>
        <pre>
        Line one.
        Line two.
        </pre>
        </div>

        # Excluding additional tags
        >>> html_input = "<div>\\n\\n<code>\\nprint('Hello, World!')\\n</code>\\n\\n</div>"
        >>> expected_output = "<div>\\n<code>\\nprint('Hello, World!')\\n</code>\\n</div>"
        >>> result = clean_newlines_between_tags(html_input, exclude_tags=('pre', 'textarea', 'code'))
        >>> print(result)
        <div>
        <code>
        print('Hello, World!')
        </code>
        </div>

        # More complex example with nested tags and multiple exclusions
        >>> html_input = (
        ...     "<section>\\n   \\n"
        ...     "<header>\\n\\n"
        ...     "<h1>Welcome</h1>\\n\\n"
        ...     "<nav>\\n\\n"
        ...     "<ul>\\n\\n"
        ...     "<li>Home</li>\\n\\n"
        ...     "<li>About</li>\\n\\n"
        ...     "<li>Contact</li>\\n\\n"
        ...     "</ul>\\n\\n"
        ...     "</nav>\\n\\n"
        ...     "</header>\\n\\n"
        ...     "<article>\\n\\n"
        ...     "<p>This is a\\n <strong>sample</strong> article.\\n</p>\\n\\n"
        ...     "<pre>\\nCode block\\nwith multiple lines\\n</pre>\\n\\n"
        ...     "</article>\\n    \\n"
        ...     "<footer>\\n\\n"
        ...     "<p>©   2024 Company</p>\\n\\n"
        ...     "</footer>\\n\\n"
        ...     "</section>"
        ... )
        >>> result = clean_newlines_between_tags(html_input, exclude_tags=('pre', 'textarea', 'code', 'nav'))
        >>> print(result)
        <section>
        <header>
        <h1>Welcome</h1>
        <nav>
        <ul>
        <li>Home</li>
        <li>About</li>
        <li>Contact</li>
        </ul>
        </nav>
        </header>
        <article>
        <p>This is a
         <strong>sample</strong> article.
        </p>
        <pre>
        Code block
        with multiple lines
        </pre>
        </article>
        <footer>
        <p>©   2024 Company</p>
        </footer>
        </section>

    Notes:
        - The function uses regular expressions to identify and replace multiple newlines between tags.
        - It does not modify the content within the excluded tags, ensuring that formatting within tags like `<pre>` is preserved.
        - If `exclude_tags` is set to `None`, no tags are excluded, and all newlines between tags will be processed.

    Raises:
        TypeError: If `html` is not a string or if `exclude_tags` is not a tuple or `None`.
    """
    if not isinstance(html, str):
        raise TypeError("html must be a string.")
    if exclude_tags is not None and not isinstance(exclude_tags, tuple):
        raise TypeError("exclude_tags must be a tuple of tag names or None.")

    if exclude_tags is None:
        exclude_tags = ()

    # Create a regex pattern to match newlines between tags, excluding specified tags
    if exclude_tags:
        # Join the exclude_tags into a regex pattern
        excluded = '|'.join(re.escape(tag) for tag in exclude_tags)
        pattern = r'>(?!\s*<\/?(?:{}))\s*\n\s*<'.format(excluded)
    else:
        pattern = r'>\s*\n\s*<'

    replacement = '>\n<'

    # Replace the matched patterns
    cleaned_html = re.sub(pattern, replacement, html)

    # # Collapse multiple consecutive newlines into a single newline
    cleaned_html = re.sub(r'>\n{2,}<', '>\n<', cleaned_html)

    return cleaned_html


@support_input_html
def collapse_repeated_tags(
        element,
        tags_to_consider: Iterable[str] = HTML_COMMON_NON_INTERACTABLE_TAGS,
        merge_attributes: bool = True,
        merge_attributes_exclusion: Iterable[str] = None,
        list_like_attrs: Iterable[str] = HTML_COMMON_LIST_LIKE_ATTRIBUTES,
        cross_tag_collapse: bool = False
):
    """
   Collapse nested tags in a single pass (stack-based DFS post-order), optionally
    merging attributes and allowing cross-tag collapsing.

    This function traverses the DOM bottom-up, looking for situations where:
      1. A parent tag is in ``tags_to_consider``.
      2. The parent has exactly one element child (no sibling tags).
      3. The parent has no non-whitespace text outside that child (via :func:`get_immediate_text`).

    **Normal Collapse** (default):
      - Parent and child **must share the same tag name** (e.g., both <div>).

    **Cross-Tag Collapse**:
      - If ``cross_tag_collapse=True``, the parent and child **only need to be** in
        ``tags_to_consider``, but **do not** need the same tag name. For instance,
        a `<div>` parent could collapse into a `<span>` child, merging their attributes.

    When a collapse occurs:
      - If ``merge_attributes`` is True, attributes from the parent are merged
        into the child (via an internal :func:`_merge_attributes`).
      - The parent node is then removed from the DOM, replaced by its single child.
      - This can happen even if the ``root_element`` itself collapses, in which
        case the newly promoted child becomes the top-level node.

    Because this function is decorated with ``@support_input_html``, the input
    ``root_element`` is already a BeautifulSoup element or soup object (no string
    parsing here). The DOM is modified **in place**.

    Args:
        element (bs4.element.Tag or bs4.BeautifulSoup):
            A BeautifulSoup Tag or soup object to process in place.
        tags_to_consider (Iterable[str], optional):
            One or more tag names that can be collapsed if nested. Defaults to
            ``HTML_COMMON_NON_INTERACTABLE_TAGS`` (e.g., 'div', 'span', etc.).
        merge_attributes (bool, optional):
            If True, merges the parent's attributes into the child before collapsing.
            Defaults to True.
        list_like_attrs (Iterable[str], optional):
            A set/list of attribute names (e.g., ``{'class', 'rel'}``) that should be
            merged as space-delimited lists with deduplication. Defaults to ``{'class'}``.
        cross_tag_collapse (bool, optional):
            If False (default), parent and child **must share the same tag name** to collapse.
            If True, any single child *in* ``tags_to_consider`` can replace its parent
            *also in* ``tags_to_consider``—even if their names differ.

    Returns:
        bs4.element.Tag or bs4.BeautifulSoup:
            The updated ``root_element`` (or its replacement if it was collapsed).
            If the top-level node collapses into its single child, that child
            effectively becomes the new root in the DOM tree.

    Examples:
        # 1) Basic collapse of nested <div> elements:
        >>> html = \"\"\"<div class="outer"><div class="inner">Hello</div></div>\"\"\"
        >>> new_soup = collapse_repeated_tags(html, tags_to_consider=('div',))
        >>> print(new_soup)
        <div class="outer inner">Hello</div>
        >>> html = \"\"\"<div class="level1"><div class="level1"><p>Some text</p></div></div>\"\"\"
        >>> new_soup = collapse_repeated_tags(html, tags_to_consider=('div',))
        >>> print(new_soup)
        <div class="level1"><p>Some text</p></div>

        # 2) Parent has non-whitespace text => no collapse:
        >>> html = \"\"\"<div class="outer">Text <div class="inner">Hello</div></div>\"\"\"
        >>> new_soup = collapse_repeated_tags(html, tags_to_consider=('div',))
        >>> print(new_soup)
        <div class="outer">Text <div class="inner">Hello</div></div>

        # 3) Multiple children => no collapse:
        >>> html = \"\"\"<div><div class="child1">A</div><div class="child2">B</div></div>\"\"\"
        >>> new_soup = collapse_repeated_tags(html, tags_to_consider=('div',))
        >>> print(new_soup)
        <div><div class="child1">A</div><div class="child2">B</div></div>

        # 4) Collapsing but preserving parent attributes by merging them:
        >>> html = \"\"\"<span id="parent" class="outer"><span class="inner">Text</span></span>\"\"\"
        >>> new_soup = collapse_repeated_tags(html, tags_to_consider=('span',), merge_attributes=True)
        >>> print(new_soup)
        <span class="outer inner" id="parent">Text</span>

        # 5) Disabling attribute merging:
        >>> html = \"\"\"<div class="outer" data-info="p123"><div class="inner">Hello</div></div>\"\"\"
        >>> new_soup = collapse_repeated_tags(html, tags_to_consider=('div',), merge_attributes=False)
        >>> print(new_soup)
        <div class="inner">Hello</div>

        # 6) Root element itself collapses (becomes its child):
        >>> html = \"\"\"<div><div class="outer"><div class="inner">Hello</div></div></div>\"\"\"
        >>> new_soup = collapse_repeated_tags(html, tags_to_consider=('div',))
        >>> print(new_soup)
        <div class="outer inner">Hello</div>

        # 7) Multiple tag types to consider (both <div> and <span>):
        >>> html = \"\"\"<div class="wrap">
        ...   <div class="outer">
        ...     <div class="outer">
        ...       <span class="middle">
        ...         <span class="middle inner">Hello</span>
        ...       </span>
        ...     </div>
        ...   </div>
        ... </div>\"\"\"
        >>> new_soup = collapse_repeated_tags(html, tags_to_consider=('div', 'span'))
        >>> print(new_soup)
        <div class="wrap outer">
        <span class="middle inner">Hello</span>
        </div>
        >>> new_soup = collapse_repeated_tags(html, tags_to_consider=('div', 'span'), cross_tag_collapse=True)
        >>> print(new_soup)
        <span class="wrap outer middle inner">Hello</span>

        # 8) Two realistic complex examples:
        >>> html = \"\"\"<div __id__="1827" class="span12 widget-span widget-type-cell dnd-column">
        ... <div __id__="1828" class="row-fluid-wrapper row-depth-1 row-number-9 dnd-row">
        ... <div __id__="1829" class="row-fluid">
        ... <div __id__="1831" class="hs_cos_wrapper hs_cos_wrapper_widget hs_cos_wrapper_type_module">
        ... <h3 __id__="1841">Swim Clinics</h3>
        ... <h4 __id__="1842">Focused Training for Advanced Swimmers</h4>
        ... <p __id__="1843">Our stroke clinics are ideal for swimmers looking to refine specific techniques or prepare for competitive events. With targeted instruction from experienced coaches, swimmers improve efficiency, strength, and speed in the water.</p>
        ... <strong __id__="1845">Clinic Options</strong>
        ... <p __id__="1846"><strong __id__="1847">Stroke Clinics:</strong> Focus on perfecting stroke mechanics.</p>
        ... <p __id__="1848"><strong __id__="1849">Starts &amp; Turns Clinics:</strong> Learn the fundamentals of competitive starts and turns to gain an edge in races.</p>
        ... </div>
        ... </div>
        ... </div>
        ... </div>\"\"\"
        >>> new_soup = collapse_repeated_tags(
        ...     html,
        ...     tags_to_consider=('div', 'span'),
        ...     cross_tag_collapse=True,
        ...     merge_attributes_exclusion=('__id__',)
        ... )
        >>> print(new_soup)
        <div __id__="1831" class="span12 widget-span widget-type-cell dnd-column row-fluid-wrapper row-depth-1 row-number-9 dnd-row hs_cos_wrapper_widget hs_cos_wrapper_type_module">
        <h3 __id__="1841">Swim Clinics</h3>
        <h4 __id__="1842">Focused Training for Advanced Swimmers</h4>
        <p __id__="1843">Our stroke clinics are ideal for swimmers looking to refine specific techniques or prepare for competitive events. With targeted instruction from experienced coaches, swimmers improve efficiency, strength, and speed in the water.</p>
        <strong __id__="1845">Clinic Options</strong>
        <p __id__="1846"><strong __id__="1847">Stroke Clinics:</strong> Focus on perfecting stroke mechanics.</p>
        <p __id__="1848"><strong __id__="1849">Starts &amp; Turns Clinics:</strong> Learn the fundamentals of competitive starts and turns to gain an edge in races.</p>
        </div>
        >>> html = \"\"\"<div __id__="1827" class="span12 widget-span widget-type-cell dnd-column">
        ... <div __id__="581" class="row-fluid-wrapper row-depth-1 row-number-2 dnd-row">
        ... <div __id__="582" class="row-fluid">
        ... <div __id__="584" class="hs_cos_wrapper hs_cos_wrapper_widget hs_cos_wrapper_type_module">
        ... <span __id__="593">Swim Lessons in Bellevue (Kelsey Creek)</span>
        ... <span __id__="595">Safety for All, Confidence for Life.</span>
        ... <a __id__="597" class="cta-primary ga-safesplash-signup" href="https://app.iclasspro.com/portal/bellevuewa/classes?__hstc=167463265.d0093c0c031aefa85c4726eb13ca07b9.1738195760736.1738195760736.1738195760736.1&amp;__hssc=167463265.1.1738195760736&amp;__hsfp=1877921029">Enroll Now</a>
        ... </div>
        ... </div>
        ... </div>
        ... <div __id__="601" class="row-fluid-wrapper row-depth-1 row-number-3 dnd-row">
        ... <div __id__="603" class="span12 widget-span widget-type-custom_widget dnd-module">
        ... <div __id__="604" class="hs_cos_wrapper hs_cos_wrapper_widget hs_cos_wrapper_type_module">
        ... <h2 __id__="613">Bellevue Swim Lessons Hosted at La Fitness</h2>
        ... <p __id__="614">Ready to make a splash in Bellevue? SafeSplash offers swimming lessons for all ages and skill levels, right near Kelsey Creek and Larsen Lake. Whether you're a beginner or looking to refine your swimming technique, our expert instructors are here to guide you every stroke of the way.</p>
        ... <p __id__="615">At SafeSplash Bellevue, we focus on water safety, skill-building, and building confidence in the water. Our comprehensive swim programs are designed for children and adults alike, with a variety of class options that cater to different schedules and skill levels. We believe in creating a positive, supportive environment where swimmers can thrive and develop at their own pace.</p>
        ... <p __id__="616">Conveniently located on Bellevue’s Eastside, SafeSplash is your go-to spot for swimming lessons near Kelsey Creek. Our facility provides a safe and welcoming space for families to learn and grow together. Whether you’re preparing your little one for their first swim or looking to refine your own skills, SafeSplash in Bellevue is the place to be. Come see why we’re a trusted choice for swim lessons in Bellevue, WA!</p>
        ... <a __id__="618" class="cta-primary" href="https://www.safesplash.com/locations/bellevue-kelsey-creek-wa/swim-lessons">LEARN MORE ABOUT OUR PROGRAMS</a>
        ... </div>
        ... </div>
        ... </div>
        ... </div>\"\"\"
        >>> new_soup = collapse_repeated_tags(
        ...     BeautifulSoup(html),
        ...     tags_to_consider=('div', 'span'),
        ...     cross_tag_collapse=True,
        ...     merge_attributes_exclusion=('__id__',)
        ... )
        >>> print(new_soup)
        <html><body><div __id__="1827" class="span12 widget-span widget-type-cell dnd-column">
        <div __id__="584" class="row-fluid-wrapper row-depth-1 row-number-2 dnd-row hs_cos_wrapper_widget hs_cos_wrapper_type_module">
        <span __id__="593">Swim Lessons in Bellevue (Kelsey Creek)</span>
        <span __id__="595">Safety for All, Confidence for Life.</span>
        <a __id__="597" class="cta-primary ga-safesplash-signup" href="https://app.iclasspro.com/portal/bellevuewa/classes?__hstc=167463265.d0093c0c031aefa85c4726eb13ca07b9.1738195760736.1738195760736.1738195760736.1&amp;__hssc=167463265.1.1738195760736&amp;__hsfp=1877921029">Enroll Now</a>
        </div>
        <div __id__="604" class="row-fluid-wrapper row-depth-1 row-number-3 dnd-row span12 widget-span widget-type-custom_widget dnd-module hs_cos_wrapper_widget hs_cos_wrapper_type_module">
        <h2 __id__="613">Bellevue Swim Lessons Hosted at La Fitness</h2>
        <p __id__="614">Ready to make a splash in Bellevue? SafeSplash offers swimming lessons for all ages and skill levels, right near Kelsey Creek and Larsen Lake. Whether you're a beginner or looking to refine your swimming technique, our expert instructors are here to guide you every stroke of the way.</p>
        <p __id__="615">At SafeSplash Bellevue, we focus on water safety, skill-building, and building confidence in the water. Our comprehensive swim programs are designed for children and adults alike, with a variety of class options that cater to different schedules and skill levels. We believe in creating a positive, supportive environment where swimmers can thrive and develop at their own pace.</p>
        <p __id__="616">Conveniently located on Bellevue’s Eastside, SafeSplash is your go-to spot for swimming lessons near Kelsey Creek. Our facility provides a safe and welcoming space for families to learn and grow together. Whether you’re preparing your little one for their first swim or looking to refine your own skills, SafeSplash in Bellevue is the place to be. Come see why we’re a trusted choice for swim lessons in Bellevue, WA!</p>
        <a __id__="618" class="cta-primary" href="https://www.safesplash.com/locations/bellevue-kelsey-creek-wa/swim-lessons">LEARN MORE ABOUT OUR PROGRAMS</a>
        </div>
        </div></body></html>
        >>> new_soup2 = collapse_repeated_tags(
        ...     new_soup,
        ...     tags_to_consider=('div', 'span'),
        ...     cross_tag_collapse=True,
        ...     merge_attributes_exclusion=('__id__',)
        ... )
        >>> print(str(new_soup2) == str(new_soup))
        True
    """

    if list_like_attrs is None:
        list_like_attrs = {"class"}

    replaced_map = {}  # old_node -> new_node if collapsed

    def get_tag_children(node: Tag):
        if isinstance(node, Tag):
            return list(filter(lambda _child: isinstance(_child, Tag), node.children))

    def process_node_for_collapse(node: Tag):
        """
        Called in post-order by post_order_traversal once a node's children are processed.
        - Rebuild child references if any children were collapsed.
        - Check if the node should itself collapse.
        - Update replaced_map if so.
        """
        if not isinstance(node, Tag):
            return node  # e.g., NavigableString or None

        # 1) Rebuild this node’s children if any child was replaced
        #    to keep the DOM in sync.
        new_children = []
        has_replacement = False
        for child in node.children:
            if isinstance(child, Tag) and child in replaced_map:
                new_children.append(replaced_map[child])
                has_replacement = True
            else:
                new_children.append(child)

        if has_replacement:
            node.clear()
            for child in new_children:
                node.append(child)

        # 2) Decide if we collapse this node
        if node.name in tags_to_consider:
            # gather the immediate Tag children
            tag_children = [c for c in node.children if isinstance(c, Tag)]
            if len(tag_children) == 1:
                only_child = tag_children[0]
                # either same tag, or cross-tag is allowed
                same_or_cross = (
                        only_child.name == node.name
                        or (cross_tag_collapse and only_child.name in tags_to_consider)
                )
                # no parent text
                if same_or_cross and not get_immediate_text(node, strip=True):
                    # 3) Merge attributes if requested
                    if merge_attributes:
                        _merge_attributes(
                            node,
                            only_child,
                            list_like_attrs=list_like_attrs,
                            excluded_attrs=merge_attributes_exclusion,
                            deduplicate_list_values=True,
                            deduplicate_text_values=True
                        )
                    # 4) Mark node as replaced by its single child
                    replaced_map[node] = only_child
                    return only_child

        # If we don’t collapse, mark node → node
        replaced_map[node] = node
        return node

    # 5) Run the post-order traversal
    post_order_traversal(
        element,
        get_children=get_tag_children,  # how to find child tags
        process_node=process_node_for_collapse,
        get_value=None,  # we’re dealing directly with Tag objects,
        return_iterator=False
    )

    # 6) Return the (possibly collapsed) new root
    return replaced_map.get(element, element)


def clean_html(
        html_content: str,
        tags_to_always_remove: Iterable[str] = DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE,
        replace_tags_by_begin_end_marks: Optional[
            Mapping[str, Union[str, Tuple[str, str]]]] = DEFAULT_HTML_TAGS_REPLACE_BY_BEGIN_END_MARKS,
        tags_to_keep: Iterable[str] = DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
        attributes_to_keep: Union[str, Iterable[str]] = DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP,
        keep_elements_with_immediate_text: bool = True,
        remove_comments: bool = True,
        remove_extra_newlines_between_tags: bool = True,
        collapse_non_interactive_tags: Union[bool, Iterable[str]] = False,
        collapse_non_interactive_tags_merge_attributes_exclusion: Iterable[str] = None,
        keep_only_incremental_change: Union[bool, float] = 0.9,
        html_content_to_compare: str = None,
        consider_text_for_comparison: bool = False,
        keep_all_text_in_hierarchy_for_incremental_change: bool = True,
        ignore_attrs_for_comparison=None,
        additional_rule_sets: Mapping = DEFAULT_ADDITIONAL_RULES,
        additional_rule_to_trigger: str = None,
        additional_rule_set_activation_flags: Optional[Sequence[str]] = DEFAULT_RULE_ACTIVATION_FLAGS,
        disabled_element_rule_sets: Mapping = DEFAULT_ADDITIONAL_RULES_FOR_DISABLED_ELEMENTS,
        disabled_element_rule_activation_flags: Optional[Sequence[str]] = None,
        hidden_element_rule_sets: Mapping = DEFAULT_ADDITIONAL_RULES_FOR_HIDDEN_ELEMENTS,
        hidden_element_rule_activation_flags: Optional[Sequence[str]] = None
):
    """
    Cleans HTML content by selectively preserving and removing specified elements and attributes,
    with support for rule-based element processing, text replacement, and incremental change extraction.

    This function provides a flexible HTML sanitization system with the following capabilities:
    - Tag filtering (keep specific tags, remove others)
    - Attribute filtering (preserve only specified attributes)
    - Tag-to-text replacement (replace tags with begin/end markers)
    - Rule-based element processing (keep/remove elements based on complex matching rules)
    - Incremental change detection (extract only changed portions of HTML)
    - Tag collapsing (merge nested non-interactive tags)
    - Comment and whitespace cleanup

    Args:
        html_content (str):
            The HTML content to clean.

        tags_to_always_remove (Iterable[str], optional):
            Tags that should be removed from the HTML regardless of other parameters.
            Defaults to DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE ('script', 'style').

        replace_tags_by_begin_end_marks (Optional[Mapping[str, Union[str, Tuple[str, str]]]], optional):
            Dictionary mapping tag names to replacement markers. Each value can be:
            - A string: used as both begin and end marker (e.g., {'code': '`'} -> `text`)
            - A tuple (begin, end): different begin and end markers (e.g., {'strong': ('**', '**')} -> **text**)
            - (None, None): remove tag but keep text content
            Set to None to disable tag replacement.
            Defaults to DEFAULT_HTML_TAGS_REPLACE_BY_BEGIN_END_MARKS.

        tags_to_keep (Iterable[str], optional):
            Tags that should be preserved in the HTML. All other tags will be unwrapped (removed but text kept)
            unless they match other criteria.
            Defaults to DEFAULT_HTML_CLEAN_TAGS_TO_KEEP.

        attributes_to_keep (Union[str, Iterable[str]], optional):
            Attributes that should be preserved on retained tags. Supports wildcards (e.g., '*name' matches
            'data-name', 'aria-name', etc.). All other attributes are removed.
            Defaults to DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP.

        keep_elements_with_immediate_text (bool, optional):
            If True, elements not in `tags_to_keep` but containing direct text will be retained (with attributes filtered).
            If False, such elements will be unwrapped (tag removed, text kept).
            Defaults to True.

        remove_comments (bool, optional):
            If True, removes all HTML comments from the content.
            Defaults to True.

        remove_extra_newlines_between_tags (bool, optional):
            If True, collapses multiple consecutive newlines between HTML tags into single newlines.
            Defaults to True.

        collapse_non_interactive_tags (Union[bool, Iterable[str]], optional):
            Controls collapsing of nested non-interactive container tags (e.g., <div><div>text</div></div> -> <div>text</div>).
            - If True: collapses tags in HTML_COMMON_NON_INTERACTABLE_TAGS
            - If Iterable[str]: collapses specified tags
            - If False: no collapsing
            Defaults to False.

        collapse_non_interactive_tags_merge_attributes_exclusion (Iterable[str], optional):
            When collapsing tags, attributes in this list will not be merged from parent to child.
            Useful to prevent ID conflicts.
            Defaults to None.

        keep_only_incremental_change (Union[bool, float], optional):
            Controls incremental change extraction between `html_content` and `html_content_to_compare`:
            - False: no extraction, use full `html_content`
            - True: always use extracted incremental changes
            - Float [0, 1]: use incremental changes if their size is < threshold * original size
            Defaults to 0.9.

        html_content_to_compare (str, optional):
            Previous HTML content to compare against when using incremental change extraction.
            Required if `keep_only_incremental_change` is True or a float.
            Defaults to None.

        consider_text_for_comparison (bool, optional):
            Whether to consider text content when comparing elements during incremental change extraction.
            If True, text changes are included in comparison. If False, only structural changes matter.
            Defaults to False.

        keep_all_text_in_hierarchy_for_incremental_change (bool, optional):
            When extracting incremental changes with hierarchy:
            - True: keep all text nodes in ancestor hierarchy
            - False: keep only text within changed elements
            Defaults to True.

        ignore_attrs_for_comparison (Sequence[str], optional):
            Attribute names to ignore during comparison when extracting incremental changes.
            These attributes are only ignored for comparison; they're retained in output HTML.
            Useful for ignoring auto-generated IDs or timestamps.
            Defaults to None.

        additional_rule_sets (Mapping[str, List[dict]], optional):
            Dictionary mapping rule set names to lists of rule dictionaries. Rules allow complex
            element matching with actions like 'keep' or 'remove'. Each rule has:
            - 'return': action ('keep', 'remove', etc.)
            - 'tags': list of tag names to match
            - 'rule-type': matching algorithm (e.g., 'any-attribute-value-matches-pattern')
            - 'attributes': attribute name patterns to match
            - 'pattern': value pattern to match
            - 'activation_flags' (optional): list of flags required to activate this rule
            The special rule set '__global__' is always processed first.
            Defaults to DEFAULT_ADDITIONAL_RULES.

        additional_rule_to_trigger (str, optional):
            Name of a specific rule set to trigger in addition to global rules.
            Useful for activating context-specific rule sets.
            Defaults to None.

        additional_rule_set_activation_flags (Sequence[str], optional):
            Activation flags that control which rules are active. Rules with an 'activation_flags' field
            will only be active if at least one of their flags matches one of the provided flags.
            Rules without 'activation_flags' are always active.
            Example: ['preserve_container'] activates rules requiring the 'preserve_container' flag.
            Defaults to None.

        disabled_element_rule_sets (Mapping[str, List[dict]], optional):
            Dictionary mapping rule set names to lists of rule dictionaries for disabled element filtering.
            Rules allow complex logic for determining which disabled elements to remove. Rules have higher
            priority than default disabled attribute checking.
            - The special rule set '__global__' is always processed
            - Each rule can return 'keep' (don't remove) or 'remove' (remove even if not disabled)
            Defaults to DEFAULT_ADDITIONAL_RULES_FOR_DISABLED_ELEMENTS (removes only disabled <input> elements,
            keeps all other elements via wildcard catch-all rule).

        disabled_element_rule_activation_flags (Sequence[str], optional):
            Activation flags that control which disabled element rules are active. Rules with an
            'activation_flags' field will only be active if at least one of their flags matches one
            of the provided flags. Rules without 'activation_flags' are always active.
            Defaults to None.

        hidden_element_rule_sets (Mapping[str, List[dict]], optional):
            Dictionary mapping rule set names to lists of rule dictionaries for hidden element filtering.
            Rules allow complex logic for determining which hidden elements to remove. Rules have higher
            priority than default hidden attribute checking.
            - The special rule set '__global__' is always processed
            - Each rule can return 'keep' (don't remove) or 'remove' (remove even if not hidden)
            Defaults to DEFAULT_ADDITIONAL_RULES_FOR_HIDDEN_ELEMENTS (removes all hidden elements via
            comprehensive check: hidden attribute, display:none, visibility:hidden, aria-hidden="true",
            class="hidden").

        hidden_element_rule_activation_flags (Sequence[str], optional):
            Activation flags that control which hidden element rules are active. Rules with an
            'activation_flags' field will only be active if at least one of their flags matches one
            of the provided flags. Rules without 'activation_flags' are always active.
            Defaults to None.

    Returns:
        str: The cleaned HTML content as a string.

    Examples:
        **Basic Tag and Attribute Filtering:**

        >>> # Keep only specific tags and attributes
        >>> html = "<div><a href='http://example.com'>Link</a><script>alert('Hi');</script></div>"
        >>> clean_html(
        ...     html,
        ...     tags_to_always_remove=['script'],
        ...     tags_to_keep=['a'],
        ...     attributes_to_keep=['href']
        ... )
        '<a href="http://example.com">Link</a>'

        >>> # Keep elements with text content
        >>> html = "<div>Hello <span>World</span><script>Code()</script></div>"
        >>> clean_html(html, tags_to_always_remove=['script'], tags_to_keep=[], keep_elements_with_immediate_text=True)
        '<div>Hello <span>World</span></div>'

        >>> # Remove all tags and their text
        >>> html = "<div><span>More text</span></div>"
        >>> clean_html(html, tags_to_keep=[], replace_tags_by_begin_end_marks={}, keep_elements_with_immediate_text=False)
        ''

        **Tag-to-Text Replacement:**

        >>> # Replace tags with markdown-style markers
        >>> html = "<p>Hello <strong>world</strong>. <em>Cool</em> text! <b>Bold2</b></p>"
        >>> mark_map = {
        ...    'strong': ('**','**'),  # **text**
        ...    'em': ('//','//'),      # //text//
        ...    'b': (None, None)       # just text (remove tag)
        ... }
        >>> result = clean_html(html, replace_tags_by_begin_end_marks=mark_map, tags_to_keep=['p'])
        >>> print(result)
        <p>Hello **world**. //Cool// text! Bold2</p>

        **Hidden Element Removal:**

        >>> # Elements with 'hidden' attribute are removed
        >>> html = '''<div>
        ...     <p hidden>Hidden paragraph.</p>
        ...     <p>This paragraph is visible.</p>
        ... </div>'''
        >>> clean_html(html, tags_to_keep=['p'], attributes_to_keep=[], replace_tags_by_begin_end_marks=None)
        '<p>This paragraph is visible.</p>'

        >>> # Elements with 'visibility: hidden' style are removed
        >>> html = '''<div>
        ...     <span style="visibility: hidden;">Hidden span.</span>
        ...     <span>Visible span.</span>
        ... </div>'''
        >>> cleaned = clean_html(html, tags_to_keep=['span'], attributes_to_keep=[])
        >>> print(cleaned)
        <span>Visible span.</span>

        **Rule-Based Element Processing with Activation Flags:**

        >>> # Without activation flags - conditional rules are inactive
        >>> html = '<div class="scrollable-view"><p>Content</p></div><div class="normal"><span>Text</span></div>'
        >>> clean_html(html, tags_to_keep=['p'], attributes_to_keep=[], additional_rule_set_activation_flags=None)
        '<div>\\nContent\\n</div><span>Text</span>'

        >>> # With activation flags - rules with matching flags become active
        >>> clean_html(
        ...     html,
        ...     tags_to_keep=['p'],
        ...     attributes_to_keep=['class'],
        ...     replace_tags_by_begin_end_marks=None,
        ...     additional_rule_set_activation_flags=['preserve_container']
        ... )
        '<div class="scrollable-view"><p>Content</p></div><span>Text</span>'

        **Comment Removal:**

        >>> html = "<div><!-- This is a comment --><p>Visible text</p><!-- Another comment --></div>"
        >>> cleaned = clean_html(html)
        >>> print(cleaned)
        <div>
        Visible text
        </div>

        >>> # Hidden parent elements and all their children are removed
        >>> html = '''<div style="display: none;">
        ...     <p>This paragraph is hidden.</p>
        ... </div>
        ... <div>
        ...     <p>This paragraph is visible.</p>
        ... </div>'''
        >>> cleaned = clean_html(html, tags_to_keep=['p', 'a'], attributes_to_keep=['href'])
        >>> print(cleaned)
        <div>
        <BLANKLINE>
        This paragraph is visible.
        <BLANKLINE>
        </div>

        **Complex Real-World Example:**

        >>> # Extracting specific content from a complex blog article
        >>> complex_html = "<article>" + \\
        ...     "<header>" + \\
        ...     "<h1>Blog Title</h1>" + \\
        ...     "<p>Published on <time datetime='2023-10-01'>October 1, 2023</time></p>" + \\
        ...     "</header>" + \\
        ...     "<section>" + \\
        ...     "<h2>Introduction</h2>" + \\
        ...     "<p>This is a <strong>great</strong> article about <a href='http://example.com'>example topics</a>.</p>" + \\
        ...     "</section>" + \\
        ...     "<aside>" + \\
        ...     "<h3>About the Author</h3>" + \\
        ...     "<p>Author Name is a renowned writer.</p>" + \\
        ...     "</aside>" + \\
        ...     "<footer>" + \\
        ...     "<p>Contact: <a href='mailto:info@example.com'>info@example.com</a></p>" + \\
        ...     "<ul><li>Privacy Policy</li><li>Terms of Use</li></ul>" + \\
        ...     "</footer>" + \\
        ...     "</article>"
        >>> clean_html(
        ...     complex_html,
        ...     replace_tags_by_begin_end_marks={},
        ...     tags_to_keep=['a', 'h1', 'h2'],
        ...     attributes_to_keep=['href'],
        ...     keep_elements_with_immediate_text=True
        ... )
        '<h1>Blog Title</h1><p>Published on <time>October 1, 2023</time></p><h2>Introduction</h2><p>This is a <strong>great</strong> article about <a href="http://example.com">example topics</a>.</p><h3>About the Author</h3><p>Author Name is a renowned writer.</p><p>Contact: <a href="mailto:info@example.com">info@example.com</a></p><li>Privacy Policy</li><li>Terms of Use</li>'

        **Disabled Element Filtering (Default Behavior):**

        >>> # By default, disabled input elements are removed
        >>> html = '''<form>
        ...     <input type="text" name="username" disabled>
        ...     <input type="email" name="email">
        ...     <button disabled>Submit</button>
        ... </form>'''
        >>> result = clean_html(html, tags_to_keep=['input', 'button'], attributes_to_keep=['type', 'name', 'disabled'])
        >>> 'disabled' in result
        True
        >>> result.count('<input')  # Only the enabled input remains
        1
        >>> result.count('<button')  # Disabled button is preserved (not an input)
        1

        >>> # Test disabled="false" is NOT removed (JavaScript framework support)
        >>> html_false = '''<div>
        ...     <input type="text" disabled="false">
        ...     <input type="password" disabled="true">
        ... </div>'''
        >>> result = clean_html(html_false, tags_to_keep=['input'], attributes_to_keep=['type', 'disabled'])
        >>> result.count('<input')  # Only disabled="false" remains
        1
        >>> 'type="text"' in result  # The disabled="false" input is kept
        True

        >>> # Case-insensitive handling of disabled="false"
        >>> html_case = '<input type="email" disabled="FALSE"><input type="tel" disabled="True">'
        >>> result = clean_html(html_case, tags_to_keep=['input'], attributes_to_keep=['type', 'disabled'])
        >>> 'type="email"' in result  # disabled="FALSE" is kept (case-insensitive)
        True
        >>> 'type="tel"' not in result  # disabled="True" is removed
        True

        **Custom Disabled Element Rules:**

        >>> # Remove both disabled inputs AND buttons with custom rules
        >>> html = '''<form>
        ...     <input type="text" disabled>
        ...     <button disabled>Cancel</button>
        ...     <button>Submit</button>
        ...     <select disabled><option>Choice</option></select>
        ... </form>'''
        >>> custom_rules = {
        ...     '__global__': [
        ...         {
        ...             'return': 'remove',
        ...             'tags': ('input', 'button'),
        ...             'rule-type': 'any-attribute-value-matches-pattern',
        ...             'attributes': ('disabled',),
        ...             'pattern': '!/false'
        ...         },
        ...         {
        ...             'return': 'keep',
        ...             'tags': ('*',)
        ...         }
        ...     ]
        ... }
        >>> result = clean_html(
        ...     html,
        ...     tags_to_keep=['input', 'button', 'select'],
        ...     attributes_to_keep=['type', 'disabled'],
        ...     disabled_element_rule_sets=custom_rules
        ... )
        >>> result.count('<input')  # Disabled input removed
        0
        >>> result.count('<button')  # Only enabled button remains
        1
        >>> result.count('<select')  # Disabled select kept (not in custom rules)
        1

        >>> # Disable all disabled element removal with empty rule sets
        >>> html = '<input type="text" disabled><button disabled>Click</button>'
        >>> result = clean_html(html, tags_to_keep=['input', 'button'], attributes_to_keep=['type', 'disabled'], disabled_element_rule_sets={})
        >>> result.count('disabled')  # Both elements kept when rules are disabled
        2

        **Advanced: Keep Important Disabled Elements with Priority Rules:**

        >>> # Keep disabled buttons with "important" class, remove other disabled inputs
        >>> html = '''<form>
        ...     <input type="text" disabled class="normal">
        ...     <button disabled class="important-save">Save</button>
        ...     <button disabled class="normal">Cancel</button>
        ... </form>'''
        >>> priority_rules = {
        ...     '__global__': [
        ...         {
        ...             'return': 'keep',
        ...             'tags': ('button',),
        ...             'rule-type': 'any-attribute-value-matches-pattern',
        ...             'attributes': ('class',),
        ...             'pattern': '*important'
        ...         },
        ...         {
        ...             'return': 'remove',
        ...             'tags': ('input', 'button'),
        ...             'rule-type': 'any-attribute-value-matches-pattern',
        ...             'attributes': ('disabled',),
        ...             'pattern': '!/false'
        ...         },
        ...         {
        ...             'return': 'keep',
        ...             'tags': ('*',)
        ...         }
        ...     ]
        ... }
        >>> result = clean_html(
        ...     html,
        ...     tags_to_keep=['input', 'button'],
        ...     attributes_to_keep=['type', 'class', 'disabled'],
        ...     disabled_element_rule_sets=priority_rules
        ... )
        >>> result.count('<input')  # Disabled input removed
        0
        >>> result.count('important-save')  # Important disabled button kept (rule priority)
        1
        >>> result.count('normal')  # Normal disabled button removed
        0

        **Hidden Element Filtering with Rules:**

        >>> # Default: Remove all hidden elements (comprehensive check)
        >>> html = '''<div>
        ...     <div hidden>Hidden with attribute</div>
        ...     <div style="display: none;">Hidden with display:none</div>
        ...     <div style="visibility: hidden;">Hidden with visibility:hidden</div>
        ...     <div aria-hidden="true">ARIA hidden</div>
        ...     <div class="hidden">Hidden class</div>
        ...     <div>Visible content</div>
        ... </div>'''
        >>> result = clean_html(html, tags_to_keep=['div'], attributes_to_keep=[])
        >>> result.count('<div')  # Only 2 divs remain: outer wrapper + visible content
        2
        >>> 'Visible content' in result
        True
        >>> 'Hidden' not in result  # All hidden content removed
        True

        >>> # Keep specific hidden elements with custom rules (e.g., ARIA-hidden decorative elements)
        >>> html = '''<div>
        ...     <div class="icon decorative" aria-hidden="true">Icon</div>
        ...     <div hidden>Really hidden</div>
        ...     <div>Visible</div>
        ... </div>'''
        >>> keep_decorative_rule = {
        ...     '__global__': [
        ...         {
        ...             'return': 'keep',
        ...             'tags': ('div',),
        ...             'rule-type': 'any-attribute-value-matches-pattern',
        ...             'attributes': ('class',),
        ...             'pattern': '*decorative'
        ...         }
        ...     ]
        ... }
        >>> result = clean_html(
        ...     html,
        ...     tags_to_keep=['div'],
        ...     attributes_to_keep=['class', 'aria-hidden'],
        ...     hidden_element_rule_sets=keep_decorative_rule
        ... )
        >>> 'decorative' in result  # ARIA-hidden decorative element kept by rule
        True
        >>> 'Really hidden' not in result  # Regular hidden div removed by fallback to is_element_hidden()
        True

        >>> # Disable all hidden element removal
        >>> html = '<div><div hidden>Hidden</div><div>Visible</div></div>'
        >>> result = clean_html(html, tags_to_keep=['div'], attributes_to_keep=['hidden'], hidden_element_rule_sets={})
        >>> result.count('hidden')  # Hidden attribute preserved when removal disabled
        1
        >>> result.count('<div')  # Both divs kept
        3

        **Combined: Disabled + Hidden Element Filtering:**

        >>> # Elements can be both hidden and disabled - both checks apply
        >>> html = '''<div>
        ...     <input type="text" disabled>
        ...     <input type="email" hidden>
        ...     <input type="password" disabled hidden>
        ...     <input type="number">
        ... </div>'''
        >>> result = clean_html(html, tags_to_keep=['input'], attributes_to_keep=['type'])
        >>> result.count('<input')  # Only the normal input remains (others disabled/hidden)
        1
        >>> 'type="number"' in result
        True
    """
    if collapse_non_interactive_tags is True:
        collapse_non_interactive_tags = HTML_COMMON_NON_INTERACTABLE_TAGS

    if keep_only_incremental_change and html_content_to_compare is not None:
        if keep_only_incremental_change is True:
            max_relative_change_for_extraction = 0
        elif isinstance(keep_only_incremental_change, float) and 0 <= keep_only_incremental_change <= 1:
            max_relative_change_for_extraction = keep_only_incremental_change
        else:
            raise ValueError(
                f"'keep_only_incremental_change' can either be True "
                f"or a float in range [0, 1]; got {keep_only_incremental_change}"
            )

        html_content = extract_incremental_html_change(
            html_content_old=html_content_to_compare,
            html_content_new=html_content,
            max_relative_change_for_extraction=max_relative_change_for_extraction,
            consider_text_for_comparison=consider_text_for_comparison,
            keep_all_text_in_hierarchy_for_incremental_change=keep_all_text_in_hierarchy_for_incremental_change,
            ignore_attrs_for_comparison=ignore_attrs_for_comparison
        )

    soup = BeautifulSoup(html_content, 'html.parser')

    # Get active rules based on activation flags
    active_rules, rule_set_name_for_error = get_active_rules(
        additional_rule_sets=additional_rule_sets,
        additional_rule_to_trigger=additional_rule_to_trigger,
        additional_rule_set_activation_flags=additional_rule_set_activation_flags,
        global_rule_set_name=RULESET_NAME_GLOBAL
    )

    # Remove explicitly unwanted tags
    for tag in tags_to_always_remove:
        for element in soup.find_all(tag):
            element.decompose()

    # Remove hidden and disabled elements in a SINGLE pass (performance optimization)
    # Determine if we should process hidden elements (empty dict or None means skip)
    use_hidden_check = hidden_element_rule_sets
    # Determine if we should process disabled elements (empty dict or None means skip)
    use_disabled_check = disabled_element_rule_sets

    # Activate rules for hidden elements (only if not empty dict and not sentinel)
    activate_is_element_hidden_rules = None
    is_element_hidden_rule_set_name = None
    if hidden_element_rule_sets and '__use_comprehensive_check__' not in hidden_element_rule_sets:
        if len(hidden_element_rule_sets) > 0:
            activate_is_element_hidden_rules, is_element_hidden_rule_set_name = get_active_rules(
                additional_rule_sets=hidden_element_rule_sets,
                additional_rule_to_trigger=None,
                additional_rule_set_activation_flags=hidden_element_rule_activation_flags,
                global_rule_set_name=RULESET_NAME_GLOBAL
            )

    # Activate rules for disabled elements (only if not empty dict)
    activate_is_element_disabled_rules = None
    is_element_disabled_rule_set_name = None
    if disabled_element_rule_sets and len(disabled_element_rule_sets) > 0:
        activate_is_element_disabled_rules, is_element_disabled_rule_set_name = get_active_rules(
            additional_rule_sets=disabled_element_rule_sets,
            additional_rule_to_trigger=None,
            additional_rule_set_activation_flags=disabled_element_rule_activation_flags,
            global_rule_set_name=RULESET_NAME_GLOBAL
        )

    # Create combined filter function
    def is_hidden_or_disabled(element):
        """Check if element is hidden OR disabled (OR logic)."""
        # Check hidden
        if use_hidden_check:
            # If rules are activated, use rule-based check; otherwise use direct comprehensive check
            if activate_is_element_hidden_rules is not None:
                if is_element_hidden_(
                    element,
                    additional_rules=activate_is_element_hidden_rules,
                    rule_set_name_for_error=is_element_hidden_rule_set_name or 'hidden_element_rules'
                ):
                    return True
            else:
                # No custom rules - use direct comprehensive check (default behavior)
                if is_element_hidden(element):
                    return True

        # Check disabled
        if use_disabled_check:
            if activate_is_element_disabled_rules is not None:
                if is_element_disabled_(
                    element,
                    additional_rules=activate_is_element_disabled_rules,
                    rule_set_name_for_error=is_element_disabled_rule_set_name or 'disabled_element_rules'
                ):
                    return True

        return False

    # Remove all hidden or disabled elements in ONE pass
    if use_hidden_check or use_disabled_check:
        for element in soup.find_all(is_hidden_or_disabled):
            element.decompose()

    # For tags by marks
    if replace_tags_by_begin_end_marks:
        for tag_name, marks in replace_tags_by_begin_end_marks.items():
            if isinstance(marks, str):
                begin_mark = end_mark = marks
            else:
                begin_mark, end_mark = marks
            begin_mark = begin_mark or ""
            end_mark = end_mark or ""

            for element in soup.find_all(tag_name):
                # Get all text inside the tag (flattening any children)
                inner_text = element.get_text()
                # Build new text node with the user-defined markers
                new_str = f"{begin_mark}{inner_text}{end_mark}"
                # Replace the whole tag with that single text node
                element.replace_with(soup.new_string(new_str))

    # Cleaning remaining elements
    for element in list(soup.find_all()):
        # Evaluate additional rules first (if active)
        if active_rules:
            action = is_element_matching_rule_set(element, active_rules, rule_set_name_for_error)
            if action == 'keep':
                keep_specified_attributes(element, attributes_to_keep)
                continue
            elif action == 'remove':
                element.decompose()
                continue
            # action is None, falls through to existing logic

        if element.name in tags_to_keep:
            keep_specified_attributes(element, attributes_to_keep)
        elif has_immediate_text(element):
            if keep_elements_with_immediate_text:
                keep_specified_attributes(element, attributes_to_keep)
            else:
                remove_immediate_text(element)
                element.unwrap()
        else:
            element.unwrap()

    # Optionally remove comments
    if remove_comments:
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.extract()

    # Optionally collapse non-interactive tags
    if collapse_non_interactive_tags:
        soup = collapse_repeated_tags(
            soup,
            tags_to_consider=collapse_non_interactive_tags,
            merge_attributes=True,
            merge_attributes_exclusion=collapse_non_interactive_tags_merge_attributes_exclusion,
            cross_tag_collapse=True
        )

    cleaned_html = str(soup).strip()

    # Optionally remove multiple newlines between tags
    if remove_extra_newlines_between_tags:
        cleaned_html = clean_newlines_between_tags(cleaned_html)

    return cleaned_html
