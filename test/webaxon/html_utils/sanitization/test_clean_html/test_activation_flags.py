"""
Tests for clean_html activation flags, specifically the 'preserve_container' flag.

This test module verifies that the activation flag system works correctly by testing
critical behavioral differences when flags are enabled vs disabled. Tests focus on
key conditions rather than exact output matching to remain resilient to minor changes
in clean_html logic.
"""

import pytest
import re
from bs4 import BeautifulSoup

from webaxon.html_utils.sanitization import (
    clean_html,
    DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
    DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP
)
from .conftest import (
    count_divs_with_pattern,
    has_div_with_class,
    extract_text_content,
    count_total_divs
)


class TestPreserveContainerActivationFlag:
    """
    Test suite for the 'preserve_container' activation flag.

    The 'preserve_container' flag controls whether divs with 'scroll', 'list', or 'view'
    in their class/name/title attributes are preserved or unwrapped during HTML cleaning.
    """

    def test_containers_removed_without_flag(self, slack_test_html):
        """
        Test that without preserve_container flag, matching containers are unwrapped.

        When the flag is NOT active, divs matching the pattern should be removed/unwrapped,
        leaving only their content. This test verifies that the count of matching divs
        is minimal (close to 0).
        """
        result = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP,
            additional_rule_set_activation_flags=None  # NO FLAG
        )

        # Critical assertion: Matching containers should be minimal/removed
        scroll_count = count_divs_with_pattern(result, r'scroll')
        list_count = count_divs_with_pattern(result, r'list')
        view_count = count_divs_with_pattern(result, r'view')

        # Allow up to 5 of each type (some edge cases might slip through)
        assert scroll_count < 5, \
            f"Expected few 'scroll' divs without flag, got {scroll_count}"
        assert list_count < 5, \
            f"Expected few 'list' divs without flag, got {list_count}"
        assert view_count < 5, \
            f"Expected few 'view' divs without flag, got {view_count}"

    def test_containers_preserved_with_flag(self, slack_test_html):
        """
        Test that with preserve_container flag, matching containers are kept.

        When the flag IS active, divs matching the pattern should be preserved.
        Based on research, slack_test_page.html contains ~75 matching divs,
        so we expect a significant number to be preserved.
        """
        result = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP,
            additional_rule_set_activation_flags=['preserve_container']  # FLAG ON
        )

        # Critical assertion: Many matching containers should be kept
        scroll_count = count_divs_with_pattern(result, r'scroll')
        list_count = count_divs_with_pattern(result, r'list')
        view_count = count_divs_with_pattern(result, r'view')

        # Based on research: ~75 total matching divs in slack_test_page.html
        # We expect at least 20 to be preserved (conservative estimate)
        total_count = scroll_count + list_count + view_count

        assert total_count > 20, \
            f"Expected many preserved divs with flag, got {total_count} " \
            f"(scroll: {scroll_count}, list: {list_count}, view: {view_count})"

    def test_significant_difference_between_modes(self, slack_test_html):
        """
        Test that flag activation causes significant difference in container count.

        This is the most critical test: it verifies that the activation flag actually
        changes behavior in a meaningful way. The difference should be substantial
        (at least 20 more containers with the flag enabled).
        """
        result_without = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=['class'],
            additional_rule_set_activation_flags=None
        )
        result_with = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=['class'],
            additional_rule_set_activation_flags=['preserve_container']
        )

        count_without = count_divs_with_pattern(result_without, r'scroll|list|view')
        count_with = count_divs_with_pattern(result_with, r'scroll|list|view')

        # Critical assertion: Significant difference (at least 20 more containers)
        difference = count_with - count_without

        assert difference > 20, \
            f"Expected significant difference with flag, got {difference} " \
            f"(without: {count_without}, with: {count_with})"

    def test_specific_slack_containers_preserved(self, slack_test_html):
        """
        Test that specific critical Slack containers are preserved with flag.

        This test verifies that important container patterns are actually present
        in the output when the flag is enabled. These patterns are common in the
        Slack UI and should be preserved.
        """
        result = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=['class'],
            additional_rule_set_activation_flags=['preserve_container']
        )

        # Critical patterns that should be preserved (at least one div with each)
        critical_patterns = ['view', 'list', 'scroll']

        for pattern in critical_patterns:
            assert has_div_with_class(result, pattern), \
                f"Expected div with '{pattern}' in class to be preserved with flag"

    def test_content_preserved_in_both_modes(self, slack_test_html):
        """
        Test that text content is preserved regardless of activation flag.

        The activation flag should only affect container structure, not the actual
        text content. This test verifies that the same text is present in both modes.
        """
        result_without = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            additional_rule_set_activation_flags=None
        )
        result_with = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            additional_rule_set_activation_flags=['preserve_container']
        )

        text_without = extract_text_content(result_without)
        text_with = extract_text_content(result_with)

        # Critical assertion: Similar text content length
        # Allow minor differences due to whitespace handling
        length_diff = abs(len(text_without) - len(text_with))
        max_allowed_diff = 100  # characters

        assert length_diff < max_allowed_diff, \
            f"Text content length differs too much: {length_diff} characters " \
            f"(without: {len(text_without)}, with: {len(text_with)})"

    def test_class_attributes_preserved_with_flag(self, slack_test_html):
        """
        Test that class attributes are preserved on kept containers.

        When containers are kept (flag enabled), their class attributes should
        also be preserved. This test verifies that preserved divs have their
        class attributes intact with the expected patterns.
        """
        result = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=['class'],
            additional_rule_set_activation_flags=['preserve_container']
        )

        soup = BeautifulSoup(result, 'html.parser')

        # Find divs that have the pattern in their classes
        matching_divs = [
            d for d in soup.find_all('div')
            if d.get('class') and
            any(re.search(r'scroll|list|view', c, re.I)
                for c in d.get('class', []))
        ]

        # Critical assertion: Multiple divs with classes preserved
        assert len(matching_divs) > 10, \
            f"Expected multiple divs with classes preserved, got {len(matching_divs)}"

        # Verify first few actually have the expected patterns in classes
        for div in matching_divs[:5]:  # Check first 5
            classes = ' '.join(div.get('class', []))
            assert re.search(r'scroll|list|view', classes, re.I), \
                f"Expected pattern in preserved div classes: {classes}"

    def test_total_div_count_higher_with_flag(self, slack_test_html):
        """
        Test that total div count is higher when preserve_container flag is enabled.

        This is an additional sanity check: when containers are preserved,
        the total number of divs in the output should be higher.
        """
        result_without = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=['class'],
            additional_rule_set_activation_flags=None
        )
        result_with = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=['class'],
            additional_rule_set_activation_flags=['preserve_container']
        )

        total_without = count_total_divs(result_without)
        total_with = count_total_divs(result_with)

        # Critical assertion: More divs with flag enabled
        assert total_with > total_without, \
            f"Expected more divs with flag, got without: {total_without}, with: {total_with}"

        # Should have at least 20 more divs (conservative)
        difference = total_with - total_without
        assert difference > 20, \
            f"Expected significant increase in div count, got {difference}"

    def test_specific_class_c_virtual_list_scroll_container(self, slack_test_html):
        """
        Test that specific Slack classes are handled correctly with activation flag.

        This test verifies several real-world Slack container classes that demonstrate
        the preserve_container flag behavior:
        - WITHOUT flag: divs should be removed/unwrapped (classes not present in output)
        - WITH flag: divs should be kept with their class attributes preserved

        Classes tested:
        - c-virtual_list__scroll_container: Virtual list scroll container
        - c-scrollbar: Scrollbar component
        - c-virtual_list: Virtual list container

        Note: Some classes like 'c-message_list' may remain in output regardless of flag
        due to being in content areas or other preservation rules, so they are not tested here.
        """
        result_without = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=['class'],
            additional_rule_set_activation_flags=None  # NO FLAG
        )
        result_with = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=['class'],
            additional_rule_set_activation_flags=['preserve_container']  # FLAG ON
        )

        # Test classes that clearly demonstrate the flag behavior
        test_classes = [
            'c-virtual_list__scroll_container',
            'c-scrollbar',
            'c-virtual_list'
        ]

        for class_name in test_classes:
            # Check if the specific class exists in the output
            class_exists_without = class_name in result_without
            class_exists_with = class_name in result_with

            # Critical assertion: Class should NOT exist without flag, but SHOULD exist with flag
            assert not class_exists_without, \
                f"Class '{class_name}' should be removed without preserve_container flag"
            assert class_exists_with, \
                f"Class '{class_name}' should be preserved with preserve_container flag"

            # Additional verification: Check it's actually in a div element with the flag
            if class_exists_with:
                soup = BeautifulSoup(result_with, 'html.parser')
                matching_div = soup.find('div', class_=lambda c: c and class_name in c)
                assert matching_div is not None, \
                    f"Class '{class_name}' should be in a div element"
                assert 'class' in matching_div.attrs, \
                    f"Div with '{class_name}' should have class attribute"


class TestActivationFlagEdgeCases:
    """Test edge cases and error conditions for activation flags."""

    def test_empty_activation_flags_list(self, slack_test_html):
        """Test that empty activation flags list behaves like None."""
        result_none = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            additional_rule_set_activation_flags=None
        )
        result_empty = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            additional_rule_set_activation_flags=[]
        )

        count_none = count_divs_with_pattern(result_none, r'scroll|list|view')
        count_empty = count_divs_with_pattern(result_empty, r'scroll|list|view')

        # Should behave the same way (minimal containers)
        assert abs(count_none - count_empty) < 5, \
            f"Empty list should behave like None (none: {count_none}, empty: {count_empty})"

    def test_non_matching_activation_flag(self, slack_test_html):
        """Test that non-matching activation flag doesn't activate rules."""
        result = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            additional_rule_set_activation_flags=['non_existent_flag']
        )

        count = count_divs_with_pattern(result, r'scroll|list|view')

        # Should behave like no flag (minimal containers)
        assert count < 5, \
            f"Non-matching flag should not activate rules, got {count} matching divs"

    def test_multiple_activation_flags(self, slack_test_html):
        """Test that preserve_container flag works when passed with other flags."""
        result = clean_html(
            slack_test_html,
            tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
            attributes_to_keep=['class'],
            additional_rule_set_activation_flags=['preserve_container', 'other_flag']
        )

        count = count_divs_with_pattern(result, r'scroll|list|view')

        # preserve_container should still work
        assert count > 20, \
            f"preserve_container should work with multiple flags, got {count} matching divs"
