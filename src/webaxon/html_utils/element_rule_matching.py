"""
Element rule matching system for HTML sanitization.

This module provides functions to validate and evaluate rules that determine
whether HTML elements should be kept, removed, or otherwise processed based on
their tag names, attribute names, and attribute values.
"""

from typing import List, Optional, Mapping, Sequence

from bs4 import Tag, BeautifulSoup

from rich_python_utils.string_utils.comparison import string_check

# Special rule set name that always triggers automatically
RULESET_NAME_GLOBAL = '__global__'

ACTIVATION_FLAG_PRESERVE_CONTAINER = 'preserve_container'
RULE_TYPE_ANY_ATTRIBUTE_VALUE_MATCHES_PATTERN = 'any-attribute-value-matches-pattern'


def validate_rule(rule: Mapping, rule_set_name: str, rule_index: int) -> None:
    """
    Validate the structure and content of an individual rule.

    Args:
        rule: The rule dictionary to validate
        rule_set_name: Name of the rule set (for error messages)
        rule_index: Index of the rule in the set (for error messages)

    Raises:
        ValueError: If the rule is invalid

    Required fields:
        - 'return' (str): The action to return if rule matches (e.g., 'keep', 'remove')
        - 'tags' (list of str): List of tag names to match
        - 'rule-type' (str): Type of rule (currently only 'any-attribute-value-matches-pattern')
        - 'attributes' (list of str): List of attribute name patterns to match
        - 'pattern' (str): Pattern to match against attribute values

    Examples:
        >>> # Valid rule
        >>> valid_rule = {
        ...     'return': 'keep',
        ...     'tags': ['div'],
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': ['class', '*name'],
        ...     'pattern': '*@ view|body'
        ... }
        >>> validate_rule(valid_rule, 'test_set', 0)

        >>> # Missing required field
        >>> invalid_rule = {
        ...     'return': 'keep',
        ...     'tags': ['div']
        ... }
        >>> try:
        ...     validate_rule(invalid_rule, 'test_set', 0)
        ... except ValueError as e:
        ...     print('missing' in str(e).lower())
        True

        >>> # Invalid 'return' field (empty string)
        >>> invalid_rule = {
        ...     'return': '',
        ...     'tags': ['div'],
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': ['class'],
        ...     'pattern': '*test'
        ... }
        >>> try:
        ...     validate_rule(invalid_rule, 'test_set', 0)
        ... except ValueError as e:
        ...     print("'return' must be a non-empty string" in str(e))
        True

        >>> # Invalid 'tags' field (not a list)
        >>> invalid_rule = {
        ...     'return': 'keep',
        ...     'tags': 'div',
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': ['class'],
        ...     'pattern': '*test'
        ... }
        >>> try:
        ...     validate_rule(invalid_rule, 'test_set', 0)
        ... except ValueError as e:
        ...     print("'tags' must be a non-empty list" in str(e))
        True

        >>> # Invalid 'tags' field (empty list)
        >>> invalid_rule = {
        ...     'return': 'keep',
        ...     'tags': [],
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': ['class'],
        ...     'pattern': '*test'
        ... }
        >>> try:
        ...     validate_rule(invalid_rule, 'test_set', 0)
        ... except ValueError as e:
        ...     print("'tags' must be a non-empty list" in str(e))
        True

        >>> # Unsupported rule-type
        >>> invalid_rule = {
        ...     'return': 'keep',
        ...     'tags': ['div'],
        ...     'rule-type': 'unsupported-type',
        ...     'attributes': ['class'],
        ...     'pattern': '*test'
        ... }
        >>> try:
        ...     validate_rule(invalid_rule, 'test_set', 0)
        ... except ValueError as e:
        ...     print('unsupported rule-type' in str(e))
        True

        >>> # Invalid 'attributes' field (empty list)
        >>> invalid_rule = {
        ...     'return': 'keep',
        ...     'tags': ['div'],
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': [],
        ...     'pattern': '*test'
        ... }
        >>> try:
        ...     validate_rule(invalid_rule, 'test_set', 0)
        ... except ValueError as e:
        ...     print("'attributes' must be a non-empty list" in str(e))
        True

        >>> # Invalid 'pattern' field (empty string)
        >>> invalid_rule = {
        ...     'return': 'keep',
        ...     'tags': ['div'],
        ...     'rule-type': 'any-attribute-value-matches-pattern',
        ...     'attributes': ['class'],
        ...     'pattern': ''
        ... }
        >>> try:
        ...     validate_rule(invalid_rule, 'test_set', 0)
        ... except ValueError as e:
        ...     print("'pattern' must be a non-empty string" in str(e))
        True
    """
    if not isinstance(rule, Mapping):
        raise ValueError(
            f"Rule {rule_index} in rule set '{rule_set_name}' is not a mapping (dict), got {type(rule).__name__}"
        )

    # Check required fields
    # When tags='*' or tags contains '*' (wildcard), rule-type, attributes, and pattern are optional
    required_fields = ['return', 'tags']
    tags = rule.get('tags', [])
    is_wildcard = tags == '*' or (isinstance(tags, (list, tuple)) and '*' in tags)
    if not is_wildcard:
        required_fields.extend(['rule-type', 'attributes', 'pattern'])

    for field in required_fields:
        if field not in rule:
            raise ValueError(
                f"Rule {rule_index} in rule set '{rule_set_name}' missing required field '{field}'"
            )

    # Validate 'return' field
    if not isinstance(rule['return'], str) or not rule['return']:
        raise ValueError(
            f"Rule {rule_index} in rule set '{rule_set_name}': 'return' must be a non-empty string, "
            f"got {type(rule['return']).__name__}: {repr(rule['return'])}"
        )

    # Validate 'tags' field - allow wildcard '*' as string or in list/tuple
    if rule['tags'] == '*':
        # Wildcard string is valid
        pass
    elif isinstance(rule['tags'], (list, tuple)):
        if not rule['tags']:
            raise ValueError(
                f"Rule {rule_index} in rule set '{rule_set_name}': 'tags' must be a non-empty list/tuple or wildcard '*', "
                f"got empty {type(rule['tags']).__name__}"
            )
        for i, tag in enumerate(rule['tags']):
            if not isinstance(tag, str) or not tag:
                raise ValueError(
                    f"Rule {rule_index} in rule set '{rule_set_name}': 'tags[{i}]' must be a non-empty string, "
                    f"got {type(tag).__name__}: {repr(tag)}"
                )
    else:
        raise ValueError(
            f"Rule {rule_index} in rule set '{rule_set_name}': 'tags' must be a list/tuple of tag names or wildcard '*', "
            f"got {type(rule['tags']).__name__}"
        )

    # Validate 'rule-type' field (if present)
    if 'rule-type' in rule:
        if not isinstance(rule['rule-type'], str) or not rule['rule-type']:
            raise ValueError(
                f"Rule {rule_index} in rule set '{rule_set_name}': 'rule-type' must be a non-empty string, "
                f"got {type(rule['rule-type']).__name__}: {repr(rule['rule-type'])}"
            )

        # Currently only support 'any-attribute-value-matches-pattern'
        supported_types = [RULE_TYPE_ANY_ATTRIBUTE_VALUE_MATCHES_PATTERN]
        if rule['rule-type'] not in supported_types:
            raise ValueError(
                f"Rule {rule_index} in rule set '{rule_set_name}': unsupported rule-type '{rule['rule-type']}', "
                f"supported types: {supported_types}"
            )

    # Validate 'attributes' field (if present)
    if 'attributes' in rule:
        if not isinstance(rule['attributes'], (list, tuple)):
            raise ValueError(
                f"Rule {rule_index} in rule set '{rule_set_name}': 'attributes' must be a list or tuple, "
                f"got {type(rule['attributes']).__name__}"
            )
        # Allow empty attributes for catch-all rules
        for i, attr in enumerate(rule['attributes']):
            if not isinstance(attr, str) or not attr:
                raise ValueError(
                    f"Rule {rule_index} in rule set '{rule_set_name}': 'attributes[{i}]' must be a non-empty string, "
                    f"got {type(attr).__name__}: {repr(attr)}"
                )

    # Validate 'pattern' field (if present)
    if 'pattern' in rule:
        if not isinstance(rule['pattern'], str) or not rule['pattern']:
            raise ValueError(
                f"Rule {rule_index} in rule set '{rule_set_name}': 'pattern' must be a non-empty string, "
                f"got {type(rule['pattern']).__name__}: {repr(rule['pattern'])}"
            )


def validate_rule_set(rule_set_name: str, rules: Sequence) -> None:
    """
    Validate an entire rule set.

    Args:
        rule_set_name: Name of the rule set
        rules: List of rule dictionaries to validate

    Raises:
        ValueError: If the rule set is invalid

    Examples:
        >>> # Valid rule set
        >>> valid_rules = [
        ...     {
        ...         'return': 'keep',
        ...         'tags': ['div'],
        ...         'rule-type': 'any-attribute-value-matches-pattern',
        ...         'attributes': ['class'],
        ...         'pattern': '*@ view|body'
        ...     }
        ... ]
        >>> validate_rule_set('test_set', valid_rules)

        >>> # Multiple valid rules
        >>> valid_rules = [
        ...     {
        ...         'return': 'keep',
        ...         'tags': ['div'],
        ...         'rule-type': 'any-attribute-value-matches-pattern',
        ...         'attributes': ['class'],
        ...         'pattern': '*@ view|body'
        ...     },
        ...     {
        ...         'return': 'remove',
        ...         'tags': ['span'],
        ...         'rule-type': 'any-attribute-value-matches-pattern',
        ...         'attributes': ['*id'],
        ...         'pattern': '*hidden'
        ...     }
        ... ]
        >>> validate_rule_set('test_set', valid_rules)

        >>> # Invalid: not a list
        >>> try:
        ...     validate_rule_set('test_set', 'not a list')
        ... except ValueError as e:
        ...     print('must be a list' in str(e))
        True

        >>> # Invalid: empty list
        >>> try:
        ...     validate_rule_set('test_set', [])
        ... except ValueError as e:
        ...     print('is empty' in str(e))
        True

        >>> # Invalid: contains invalid rule
        >>> invalid_rules = [
        ...     {
        ...         'return': 'keep',
        ...         'tags': ['div']
        ...         # missing required fields
        ...     }
        ... ]
        >>> try:
        ...     validate_rule_set('test_set', invalid_rules)
        ... except ValueError as e:
        ...     print('missing' in str(e).lower())
        True
    """
    if not isinstance(rules, (list, tuple)):
        raise ValueError(
            f"Rule set '{rule_set_name}' must be a list or tuple, got {type(rules).__name__}"
        )

    if not rules:
        raise ValueError(
            f"Rule set '{rule_set_name}' is empty"
        )

    # Validate each rule
    for i, rule in enumerate(rules):
        validate_rule(rule, rule_set_name, i)


def get_active_rules(
        additional_rule_sets: Optional[Mapping[str, List[dict]]] = None,
        additional_rule_to_trigger: Optional[str] = None,
        additional_rule_set_activation_flags: Optional[Sequence[str]] = None,
        global_rule_set_name: str = '__global__'
) -> tuple[Optional[List[dict]], Optional[str]]:
    """
    Get active rules based on rule sets, triggered rule names, and activation flags.

    This function filters rules from rule sets based on their activation flags and returns
    only the rules that should be active given the provided activation flags.

    Args:
        additional_rule_sets: Dictionary mapping rule set names to lists of rule dictionaries
        additional_rule_to_trigger: Name of a specific rule set to trigger
        additional_rule_set_activation_flags: Sequence of activation flags that are currently active
        global_rule_set_name: Name of the global rule set that always applies (default: '__global__')

    Returns:
        A tuple of (active_rules, rule_set_name_for_error):
            - active_rules: List of active rule dictionaries, or None if no rules are active
            - rule_set_name_for_error: String describing active rule sets for error messages, or None

    Rule Activation Logic:
        1. Global rules (from global_rule_set_name) are always processed
        2. For each rule, check if it has an 'activation_flags' field:
           - If NO 'activation_flags' field exists: rule is always active
           - If 'activation_flags' exists but additional_rule_set_activation_flags is None/empty: rule is NOT active
           - If 'activation_flags' exists and additional_rule_set_activation_flags is provided:
             rule is active if ANY flag in 'activation_flags' matches ANY flag in additional_rule_set_activation_flags
        3. If additional_rule_to_trigger is specified, also process rules from that rule set

    Examples:
        >>> # Rule set with activation flags
        >>> rule_sets = {
        ...     '__global__': [
        ...         {
        ...             'return': 'keep',
        ...             'tags': ['div'],
        ...             'activation_flags': ['preserve_container'],
        ...             'rule-type': 'any-attribute-value-matches-pattern',
        ...             'attributes': ['class'],
        ...             'pattern': '*@ scroll|list|view'
        ...         },
        ...         {
        ...             'return': 'keep',
        ...             'tags': ['span'],
        ...             'rule-type': 'any-attribute-value-matches-pattern',
        ...             'attributes': ['class'],
        ...             'pattern': '*tooltip'
        ...         }
        ...     ]
        ... }

        >>> # Test 1: No activation flags provided - only rule without activation_flags is active
        >>> active, name = get_active_rules(rule_sets, None, None)
        >>> len(active)
        1
        >>> active[0]['tags']
        ['span']

        >>> # Test 2: With matching activation flag - both rules active
        >>> active, name = get_active_rules(rule_sets, None, ['preserve_container'])
        >>> len(active)
        2

        >>> # Test 3: With non-matching activation flag - only rule without activation_flags is active
        >>> active, name = get_active_rules(rule_sets, None, ['some_other_flag'])
        >>> len(active)
        1
        >>> active[0]['tags']
        ['span']

        >>> # Test 4: No rule sets provided
        >>> active, name = get_active_rules(None, None, None)
        >>> active is None
        True

        >>> # Test 5: Empty rule sets
        >>> active, name = get_active_rules({}, None, None)
        >>> active is None
        True

        >>> # Test 6: Additional rule set triggered
        >>> rule_sets = {
        ...     '__global__': [
        ...         {
        ...             'return': 'keep',
        ...             'tags': ['div'],
        ...             'rule-type': 'any-attribute-value-matches-pattern',
        ...             'attributes': ['class'],
        ...             'pattern': '*container'
        ...         }
        ...     ],
        ...     'special': [
        ...         {
        ...             'return': 'keep',
        ...             'tags': ['span'],
        ...             'activation_flags': ['special_mode'],
        ...             'rule-type': 'any-attribute-value-matches-pattern',
        ...             'attributes': ['class'],
        ...             'pattern': '*highlight'
        ...         }
        ...     ]
        ... }
        >>> active, name = get_active_rules(rule_sets, 'special', ['special_mode'])
        >>> len(active)
        2
        >>> name
        '__global__ + special'

        >>> # Test 7: Rule set name in error message
        >>> active, name = get_active_rules(rule_sets, None, None)
        >>> name
        '__global__'
    """
    if not additional_rule_sets:
        return None, None

    active_rules = []
    rule_set_names = []

    # Process global rules first
    if global_rule_set_name in additional_rule_sets:
        global_rules = additional_rule_sets[global_rule_set_name]
        validate_rule_set(global_rule_set_name, global_rules)

        # Filter rules based on activation flags
        for rule in global_rules:
            if 'activation_flags' not in rule:
                # No activation_flags means always active
                active_rules.append(rule)
            elif additional_rule_set_activation_flags:
                # Check if any activation flag matches
                rule_flags = rule.get('activation_flags', [])
                if any(flag in additional_rule_set_activation_flags for flag in rule_flags):
                    active_rules.append(rule)

        if active_rules:
            rule_set_names.append(global_rule_set_name)

    # Process specifically triggered rule set
    if additional_rule_to_trigger:
        if additional_rule_to_trigger not in additional_rule_sets:
            raise ValueError(f"Rule set '{additional_rule_to_trigger}' not found in additional_rule_sets")

        # Don't add global rules twice if they were explicitly triggered
        if additional_rule_to_trigger != global_rule_set_name:
            triggered_rules = additional_rule_sets[additional_rule_to_trigger]
            validate_rule_set(additional_rule_to_trigger, triggered_rules)

            # Filter triggered rules based on activation flags
            for rule in triggered_rules:
                if 'activation_flags' not in rule:
                    # No activation_flags means always active
                    active_rules.append(rule)
                elif additional_rule_set_activation_flags:
                    # Check if any activation flag matches
                    rule_flags = rule.get('activation_flags', [])
                    if any(flag in additional_rule_set_activation_flags for flag in rule_flags):
                        active_rules.append(rule)

            if any(rule for rule in triggered_rules if 'activation_flags' not in rule or
                                                       (additional_rule_set_activation_flags and
                                                        any(flag in additional_rule_set_activation_flags for flag in
                                                            rule.get('activation_flags', [])))):
                rule_set_names.append(additional_rule_to_trigger)

    # Return None if no rules are active
    if not active_rules:
        return None, None

    # Build error message name
    rule_set_name_for_error = ' + '.join(rule_set_names) if rule_set_names else None

    return active_rules, rule_set_name_for_error


def is_element_matching_rule_set(element: Tag, rules: list, rule_set_name: str) -> Optional[str]:
    """
    Evaluate if an element matches any rule in the rule set.

    Args:
        element: BeautifulSoup Tag element to evaluate
        rules: List of validated rule dictionaries
        rule_set_name: Name of the rule set (for error messages)

    Returns:
        The 'return' value from the first matching rule, or None if no rule matches

    Rule matching logic for 'any-attribute-value-matches-pattern' (default if 'rule-type' not specified):
        1. Check if element.name matches any tag in rule['tags']
           - Supports wildcard: rule['tags'] can be '*' to match any element
        2. If rule has no 'attributes' field or empty attributes, return rule['return'] (catch-all)
        3. For each attribute on the element:
           - Check if attribute NAME matches ANY pattern in rule['attributes'] (using string_check)
           - If attribute name matches, check if attribute VALUE matches rule['pattern']
           - If both match, return rule['return']
        4. Continue to next rule if no match
        5. Return None if no rules match

    Examples:
        >>> # Example rule set
        >>> rules = [
        ...     {
        ...         'return': 'keep',
        ...         'tags': ['div'],
        ...         'rule-type': 'any-attribute-value-matches-pattern',
        ...         'attributes': ['class', '*name', '*title'],
        ...         'pattern': '*@ view|body|presentation'
        ...     }
        ... ]

        >>> # Test case 1: class attribute matches pattern
        >>> html = '<div class="p-workspace__primary_view_body">Content</div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('div')
        >>> is_element_matching_rule_set(element, rules, 'test_set')
        'keep'

        >>> # Test case 2: data-name attribute matches pattern (name matches '*name')
        >>> html = '<div data-name="scrollable-view-panel">Content</div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('div')
        >>> is_element_matching_rule_set(element, rules, 'test_set')
        'keep'

        >>> # Test case 3: aria-title attribute matches pattern (title matches '*title')
        >>> html = '<div aria-title="presentation-mode">Content</div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('div')
        >>> is_element_matching_rule_set(element, rules, 'test_set')
        'keep'

        >>> # Test case 4: attribute name matches but value doesn't
        >>> html = '<div class="unrelated-content">Content</div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('div')
        >>> result = is_element_matching_rule_set(element, rules, 'test_set')
        >>> result is None
        True

        >>> # Test case 5: wrong tag name
        >>> html = '<span class="p-workspace__primary_view_body">Content</span>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('span')
        >>> result = is_element_matching_rule_set(element, rules, 'test_set')
        >>> result is None
        True

        >>> # Test case 6: attribute name doesn't match any pattern
        >>> html = '<div id="some-view-id">Content</div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('div')
        >>> result = is_element_matching_rule_set(element, rules, 'test_set')
        >>> result is None
        True

        >>> # Test case 7: multiple attributes, class matches
        >>> html = '<div class="main-presentation" id="content" data-name="other">Content</div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('div')
        >>> is_element_matching_rule_set(element, rules, 'test_set')
        'keep'

        >>> # Test case 8: first-match-wins with multiple rules
        >>> rules_multi = [
        ...     {
        ...         'return': 'remove',
        ...         'tags': ['div'],
        ...         'rule-type': 'any-attribute-value-matches-pattern',
        ...         'attributes': ['class'],
        ...         'pattern': '*hidden'
        ...     },
        ...     {
        ...         'return': 'keep',
        ...         'tags': ['div'],
        ...         'rule-type': 'any-attribute-value-matches-pattern',
        ...         'attributes': ['class'],
        ...         'pattern': '*view'
        ...     }
        ... ]
        >>> html = '<div class="hidden-view">Content</div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('div')
        >>> is_element_matching_rule_set(element, rules_multi, 'test_set')
        'remove'

        >>> # Test case 9: list-valued attributes (e.g., class with multiple values)
        >>> html = '<div class="container primary view">Content</div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('div')
        >>> is_element_matching_rule_set(element, rules, 'test_set')
        'keep'

        >>> # Test case 10: wildcard tag matching with '*'
        >>> wildcard_rules = [
        ...     {
        ...         'return': 'remove',
        ...         'tags': ('input',),
        ...         'rule-type': 'any-attribute-value-matches-pattern',
        ...         'attributes': ('disabled',),
        ...         'pattern': '*'
        ...     },
        ...     {
        ...         'return': 'keep',
        ...         'tags': '*'  # Wildcard: matches any tag
        ...     }
        ... ]
        >>> # Test disabled input: matches first rule
        >>> html = '<input disabled>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('input')
        >>> is_element_matching_rule_set(element, wildcard_rules, 'test_set')
        'remove'
        >>> # Test disabled button: skips first rule, matches wildcard 'keep' rule
        >>> html = '<button disabled>Click</button>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('button')
        >>> is_element_matching_rule_set(element, wildcard_rules, 'test_set')
        'keep'
        >>> # Test any other element: matches wildcard 'keep' rule
        >>> html = '<div>Content</div>'
        >>> soup = BeautifulSoup(html, 'html.parser')
        >>> element = soup.find('div')
        >>> is_element_matching_rule_set(element, wildcard_rules, 'test_set')
        'keep'
    """
    for rule in rules:
        # Check if element tag matches (supports wildcard '*' string or ['*'] list)
        rule_tags = rule.get('tags', ())
        is_wildcard = rule_tags == '*' or (isinstance(rule_tags, (list, tuple)) and '*' in rule_tags)
        if not is_wildcard and element.name not in rule_tags:
            continue

        # Handle different rule types (default to RULE_TYPE_ANY_ATTRIBUTE_VALUE_MATCHES_PATTERN)
        rule_type = rule.get('rule-type', RULE_TYPE_ANY_ATTRIBUTE_VALUE_MATCHES_PATTERN)
        if rule_type == RULE_TYPE_ANY_ATTRIBUTE_VALUE_MATCHES_PATTERN:
            # If no attributes specified, this is a catch-all rule for the matched tags
            if 'attributes' not in rule or not rule['attributes']:
                return rule['return']

            # Check each attribute on the element
            for attr_name, attr_value in element.attrs.items():
                # Check if attribute name matches any pattern in 'attributes'
                name_matches = False
                for name_pattern in rule['attributes']:
                    if string_check(attr_name, name_pattern):
                        name_matches = True
                        break

                if not name_matches:
                    continue

                # Attribute name matches, now check if value matches pattern
                # Handle list-valued attributes (e.g., class="foo bar")
                if isinstance(attr_value, list):
                    attr_value = ' '.join(attr_value)
                elif not isinstance(attr_value, str):
                    # Convert to string for comparison
                    attr_value = str(attr_value)

                # Check if attribute value matches the pattern
                if string_check(attr_value, rule['pattern']):
                    # Both attribute name and value match - return the action
                    return rule['return']

    # No rule matched
    return None
