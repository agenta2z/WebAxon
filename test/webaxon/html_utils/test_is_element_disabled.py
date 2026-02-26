"""
Comprehensive test suite for is_element_disabled and is_element_disabled_ functions.

Tests cover:
1. Basic disabled attribute detection
2. ARIA disabled attributes
3. Readonly attributes
4. Strict mode (only_consider_non_interactable_as_disabled)
5. Enabled tags filtering (convenience channel)
6. Rule-based filtering
7. Edge cases (boolean attributes, empty values, etc.)
"""

import os
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add src directories to path
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(test_dir, '..', '..', '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

# Add SciencePythonUtils to path (WebAgent depends on it)
science_utils_root = os.path.abspath(os.path.join(project_root, '..', 'SciencePythonUtils'))
sys.path.insert(0, os.path.join(science_utils_root, 'src'))

from bs4 import BeautifulSoup
from webaxon.html_utils.common import is_element_disabled, is_element_disabled_


def test_basic_disabled_attribute():
    """Test basic disabled attribute detection."""
    print("=" * 80)
    print("Test 1: Basic disabled attribute detection")
    print("=" * 80)

    # Test input with disabled attribute
    html = '<input disabled>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element) == True, "Input with disabled should be disabled"
    print("✓ <input disabled> is detected as disabled")

    # Test input without disabled attribute
    html = '<input>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element) == False, "Input without disabled should not be disabled"
    print("✓ <input> is not disabled")

    # Test button with disabled
    html = '<button disabled>Click</button>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('button')
    assert is_element_disabled(element) == True, "Button with disabled should be disabled"
    print("✓ <button disabled> is detected as disabled")

    # Test select with disabled
    html = '<select disabled><option>One</option></select>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('select')
    assert is_element_disabled(element) == True, "Select with disabled should be disabled"
    print("✓ <select disabled> is detected as disabled")

    print()


def test_aria_disabled():
    """Test ARIA disabled attribute detection."""
    print("=" * 80)
    print("Test 2: ARIA disabled attribute detection")
    print("=" * 80)

    # Test aria-disabled="true"
    html = '<input aria-disabled="true">'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element) == True, "Input with aria-disabled='true' should be disabled"
    print("✓ <input aria-disabled='true'> is detected as disabled")

    # Test aria-disabled="false"
    html = '<input aria-disabled="false">'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element) == False, "Input with aria-disabled='false' should not be disabled"
    print("✓ <input aria-disabled='false'> is not disabled")

    # Test div with aria-disabled (non-interactive element)
    html = '<div aria-disabled="true">Content</div>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('div')
    assert is_element_disabled(element) == True, "Div with aria-disabled='true' should be disabled"
    print("✓ <div aria-disabled='true'> is detected as disabled")

    print()


def test_readonly_attributes():
    """Test readonly attribute detection."""
    print("=" * 80)
    print("Test 3: Readonly attribute detection")
    print("=" * 80)

    # Test readonly attribute
    html = '<input readonly>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element) == True, "Input with readonly should be disabled"
    print("✓ <input readonly> is detected as disabled")

    # Test aria-readonly="true"
    html = '<input aria-readonly="true">'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element) == True, "Input with aria-readonly='true' should be disabled"
    print("✓ <input aria-readonly='true'> is detected as disabled")

    # Test textarea with readonly
    html = '<textarea readonly></textarea>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('textarea')
    assert is_element_disabled(element) == True, "Textarea with readonly should be disabled"
    print("✓ <textarea readonly> is detected as disabled")

    print()


def test_strict_mode():
    """Test strict mode (only_consider_non_interactable_as_disabled=True)."""
    print("=" * 80)
    print("Test 4: Strict mode (only interactive elements with disabled attribute)")
    print("=" * 80)

    # Test interactive element with disabled in strict mode
    html = '<input disabled>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element, only_consider_non_interactable_as_disabled=True) == True
    print("✓ Strict mode: <input disabled> is disabled")

    # Test interactive element with aria-disabled in strict mode (should NOT be disabled)
    html = '<input aria-disabled="true">'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element, only_consider_non_interactable_as_disabled=True) == False
    print("✓ Strict mode: <input aria-disabled='true'> is NOT disabled")

    # Test interactive element with readonly in strict mode (should NOT be disabled)
    html = '<input readonly>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element, only_consider_non_interactable_as_disabled=True) == False
    print("✓ Strict mode: <input readonly> is NOT disabled")

    # Test non-interactive element with disabled in strict mode (should NOT be disabled)
    html = '<div disabled>Content</div>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('div')
    assert is_element_disabled(element, only_consider_non_interactable_as_disabled=True) == False
    print("✓ Strict mode: <div disabled> is NOT disabled (div is not interactive)")

    # Test button with disabled in strict mode
    html = '<button disabled>Click</button>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('button')
    assert is_element_disabled(element, only_consider_non_interactable_as_disabled=True) == True
    print("✓ Strict mode: <button disabled> is disabled")

    print()


def test_enabled_tags_convenience_channel():
    """Test enabled_tags parameter (convenience channel)."""
    print("=" * 80)
    print("Test 5: Enabled tags filtering (convenience channel)")
    print("=" * 80)

    # Test input disabled with enabled_tags=('input',)
    html = '<input disabled>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element, enabled_tags=('input',)) == True
    print("✓ <input disabled> with enabled_tags=('input',) is disabled")

    # Test button disabled with enabled_tags=('input',) - should NOT be disabled
    html = '<button disabled>Click</button>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('button')
    assert is_element_disabled(element, enabled_tags=('input',)) == False
    print("✓ <button disabled> with enabled_tags=('input',) is NOT disabled (button not in enabled_tags)")

    # Test button disabled with enabled_tags=('input', 'button')
    html = '<button disabled>Click</button>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('button')
    assert is_element_disabled(element, enabled_tags=('input', 'button')) == True
    print("✓ <button disabled> with enabled_tags=('input', 'button') is disabled")

    # Test select disabled with enabled_tags=('input',) - should NOT be disabled
    html = '<select disabled><option>One</option></select>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('select')
    assert is_element_disabled(element, enabled_tags=('input',)) == False
    print("✓ <select disabled> with enabled_tags=('input',) is NOT disabled (select not in enabled_tags)")

    print()


def test_rule_based_filtering_keep():
    """Test rule-based filtering with 'keep' action."""
    print("=" * 80)
    print("Test 6: Rule-based filtering - 'keep' action")
    print("=" * 80)

    # Rule: Keep buttons with class containing 'important'
    keep_rule = [{
        'return': 'keep',
        'tags': ('button',),
        'attributes': ('class',),
        'pattern': '*important'
    }]

    # Test button with important class and disabled (should be kept)
    html = '<button class="btn-important" disabled>Save</button>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('button')
    assert is_element_disabled_(element, keep_rule) == False
    print("✓ <button class='btn-important' disabled> with keep rule: NOT disabled (kept)")

    # Test button without important class and disabled (should be disabled)
    html = '<button disabled>Cancel</button>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('button')
    assert is_element_disabled_(element, keep_rule) == True
    print("✓ <button disabled> with keep rule: disabled (rule doesn't match)")

    # Test button with important class but not disabled (should not be disabled)
    html = '<button class="btn-important">Save</button>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('button')
    assert is_element_disabled_(element, keep_rule) == False
    print("✓ <button class='btn-important'> with keep rule: NOT disabled (kept by rule, no disabled attr)")

    print()


def test_rule_based_filtering_remove():
    """Test rule-based filtering with 'remove' action."""
    print("=" * 80)
    print("Test 7: Rule-based filtering - 'remove' action")
    print("=" * 80)

    # Rule: Remove inputs with type='hidden'
    remove_rule = [{
        'return': 'remove',
        'tags': ('input',),
        'attributes': ('type',),
        'pattern': '*hidden'
    }]

    # Test hidden input (should be removed/disabled even without disabled attribute)
    html = '<input type="hidden" name="csrf">'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, remove_rule) == True
    print("✓ <input type='hidden'> with remove rule: disabled (removed by rule)")

    # Test text input (should not be disabled)
    html = '<input type="text">'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, remove_rule) == False
    print("✓ <input type='text'> with remove rule: NOT disabled (rule doesn't match)")

    # Test hidden input with disabled attribute (should be removed)
    html = '<input type="hidden" disabled>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, remove_rule) == True
    print("✓ <input type='hidden' disabled> with remove rule: disabled (removed by rule)")

    print()


def test_wildcard_catch_all_rule():
    """Test wildcard catch-all rule."""
    print("=" * 80)
    print("Test 8: Wildcard catch-all rule")
    print("=" * 80)

    # Rules: Remove disabled inputs, keep everything else
    rules = [
        {
            'return': 'remove',
            'tags': ('input',),
            'attributes': ('disabled',),
            'pattern': '*'
        },
        {
            'return': 'keep',
            'tags': '*'  # Wildcard: matches all tags
        }
    ]

    # Test disabled input (should be removed)
    html = '<input disabled>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, rules) == True
    print("✓ <input disabled> with catch-all rules: disabled (first rule matches)")

    # Test disabled button (should be kept by catch-all)
    html = '<button disabled>Click</button>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('button')
    assert is_element_disabled_(element, rules) == False
    print("✓ <button disabled> with catch-all rules: NOT disabled (catch-all 'keep' rule matches)")

    # Test disabled select (should be kept by catch-all)
    html = '<select disabled><option>One</option></select>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('select')
    assert is_element_disabled_(element, rules) == False
    print("✓ <select disabled> with catch-all rules: NOT disabled (catch-all 'keep' rule matches)")

    # Test regular input (should be kept by catch-all)
    html = '<input>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, rules) == False
    print("✓ <input> with catch-all rules: NOT disabled (catch-all 'keep' rule matches)")

    print()


def test_empty_attribute_values():
    """Test handling of empty attribute values (boolean attributes)."""
    print("=" * 80)
    print("Test 9: Empty attribute values (boolean HTML attributes)")
    print("=" * 80)

    # Test disabled with empty value (boolean attribute)
    html = '<input disabled="">'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element) == True
    print("✓ <input disabled=''> is detected as disabled")

    # Test disabled with value (non-standard but should still work)
    html = '<input disabled="disabled">'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(element) == True
    print("✓ <input disabled='disabled'> is detected as disabled")

    # Test with rule matching empty values
    rules = [{
        'return': 'remove',
        'tags': ('input',),
        'attributes': ('disabled',),
        'pattern': '*'  # Should match empty string value
    }]

    html = '<input disabled>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, rules) == True
    print("✓ <input disabled> matches '*' pattern in rules (empty value)")

    print()


def test_combined_parameters():
    """Test combining enabled_tags with only_consider_non_interactable_as_disabled."""
    print("=" * 80)
    print("Test 10: Combined parameters (enabled_tags + strict mode)")
    print("=" * 80)

    # Test input disabled with both parameters
    html = '<input disabled>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(
        element,
        only_consider_non_interactable_as_disabled=True,
        enabled_tags=('input',)
    ) == True
    print("✓ <input disabled> with strict mode + enabled_tags=('input',): disabled")

    # Test button disabled with enabled_tags not including button
    html = '<button disabled>Click</button>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('button')
    assert is_element_disabled(
        element,
        only_consider_non_interactable_as_disabled=True,
        enabled_tags=('input',)
    ) == False
    print("✓ <button disabled> with strict mode + enabled_tags=('input',): NOT disabled (button not in enabled_tags)")

    # Test input readonly with strict mode and enabled_tags
    html = '<input readonly>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled(
        element,
        only_consider_non_interactable_as_disabled=True,
        enabled_tags=('input',)
    ) == False
    print("✓ <input readonly> with strict mode + enabled_tags=('input',): NOT disabled (readonly not counted in strict mode)")

    print()


def test_rule_based_with_fallback():
    """Test rule-based filtering with fallback to comprehensive check."""
    print("=" * 80)
    print("Test 11: Rule-based with fallback to comprehensive check")
    print("=" * 80)

    # Empty rules - should fall back to comprehensive check
    rules = []

    html = '<input disabled>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, rules) == True
    print("✓ <input disabled> with empty rules: disabled (falls back to comprehensive check)")

    html = '<input readonly>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, rules) == True
    print("✓ <input readonly> with empty rules: disabled (falls back to comprehensive check)")

    html = '<input>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, rules) == False
    print("✓ <input> with empty rules: NOT disabled (falls back to comprehensive check)")

    # None rules - same as empty
    html = '<input disabled>'
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input')
    assert is_element_disabled_(element, None) == True
    print("✓ <input disabled> with None rules: disabled (falls back to comprehensive check)")

    print()


def run_all_tests():
    """Run all test functions."""
    print("\n" + "=" * 80)
    print("IS_ELEMENT_DISABLED COMPREHENSIVE TEST SUITE")
    print("=" * 80 + "\n")

    test_functions = [
        test_basic_disabled_attribute,
        test_aria_disabled,
        test_readonly_attributes,
        test_strict_mode,
        test_enabled_tags_convenience_channel,
        test_rule_based_filtering_keep,
        test_rule_based_filtering_remove,
        test_wildcard_catch_all_rule,
        test_empty_attribute_values,
        test_combined_parameters,
        test_rule_based_with_fallback,
    ]

    failed_tests = []

    for test_func in test_functions:
        try:
            test_func()
        except AssertionError as e:
            print(f"✗ FAILED: {test_func.__name__}")
            print(f"  Error: {e}")
            failed_tests.append((test_func.__name__, str(e)))
        except Exception as e:
            print(f"✗ ERROR in {test_func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed_tests.append((test_func.__name__, f"Unexpected error: {e}"))

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    if failed_tests:
        print(f"\n❌ {len(failed_tests)} test(s) FAILED:\n")
        for test_name, error in failed_tests:
            print(f"  - {test_name}")
            print(f"    {error}\n")
        return False
    else:
        print("\n✅ All tests PASSED!")
        print(f"\nTotal tests run: {len(test_functions)}")
        return True


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
