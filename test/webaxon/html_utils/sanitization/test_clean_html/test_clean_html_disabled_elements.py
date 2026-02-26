"""
End-to-end test for disabled element filtering in clean_html().

This test uses actual HTML data to verify that:
1. Disabled input elements are removed by default
2. Other disabled elements (buttons, selects) are kept by default
3. Custom rules can override the default behavior
"""

import os
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add src directories to path
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(test_dir, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

# Add SciencePythonUtils to path (WebAgent depends on it)
science_utils_root = os.path.abspath(os.path.join(project_root, '..', 'SciencePythonUtils'))
sys.path.insert(0, os.path.join(science_utils_root, 'src'))

from bs4 import BeautifulSoup
from webaxon.html_utils.sanitization import clean_html


def test_default_behavior_removes_disabled_inputs():
    """Test that default clean_html removes disabled inputs but not other disabled elements."""
    print("=" * 80)
    print("Test 1: Default behavior - Remove disabled inputs only")
    print("=" * 80)

    # Create HTML with various disabled elements
    html = """
    <div>
        <input type="text" disabled>
        <input type="email" disabled="">
        <input type="password" disabled="disabled">
        <button disabled>Submit</button>
        <select disabled><option>Option 1</option></select>
        <input type="text">
    </div>
    """

    # Clean HTML with default parameters
    result = clean_html(html)
    soup = BeautifulSoup(result, 'html.parser')

    # Verify disabled inputs are removed
    disabled_inputs = soup.find_all('input', attrs={'disabled': True})
    assert len(disabled_inputs) == 0, f"Expected 0 disabled inputs, found {len(disabled_inputs)}"
    print("✓ All disabled <input> elements removed")

    # Verify non-disabled input is kept
    normal_inputs = soup.find_all('input')
    assert len(normal_inputs) == 1, f"Expected 1 normal input, found {len(normal_inputs)}"
    print("✓ Non-disabled <input> elements preserved")

    # Verify disabled button is kept (by wildcard catch-all rule)
    # Note: clean_html removes the 'disabled' attribute (not in DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP)
    # so we just check that the button element itself is preserved
    buttons = soup.find_all('button')
    assert len(buttons) == 1, f"Expected 1 button element, found {len(buttons)}"
    print("✓ <button> elements preserved (wildcard catch-all rule)")

    # Verify disabled select is kept (by wildcard catch-all rule)
    selects = soup.find_all('select')
    assert len(selects) == 1, f"Expected 1 select element, found {len(selects)}"
    print("✓ <select> elements preserved (wildcard catch-all rule)")

    print()


def test_disable_all_disabled_element_removal():
    """Test that passing empty rule sets disables disabled element removal."""
    print("=" * 80)
    print("Test 2: Disable disabled element removal with empty rule sets")
    print("=" * 80)

    html = """
    <div>
        <input type="text" disabled>
        <button disabled>Submit</button>
    </div>
    """

    # Clean HTML with empty disabled element rule sets
    result = clean_html(html, disabled_element_rule_sets={})
    soup = BeautifulSoup(result, 'html.parser')

    # Verify disabled input is KEPT (no rules)
    # Note: clean_html removes the 'disabled' attribute, so just check element exists
    inputs = soup.find_all('input')
    assert len(inputs) == 1, f"Expected 1 input element (rules disabled), found {len(inputs)}"
    print("✓ <input> elements preserved when disabled_element_rule_sets={}")

    # Verify disabled button is kept
    buttons = soup.find_all('button')
    assert len(buttons) == 1, f"Expected 1 button element, found {len(buttons)}"
    print("✓ <button> elements also preserved")

    print()


def test_custom_rules_remove_multiple_element_types():
    """Test custom rules that remove multiple disabled element types."""
    print("=" * 80)
    print("Test 3: Custom rules - Remove disabled inputs AND buttons")
    print("=" * 80)

    html = """
    <div>
        <input type="text" disabled>
        <button disabled>Submit</button>
        <select disabled><option>Option 1</option></select>
    </div>
    """

    # Create custom rules to remove both inputs and buttons
    custom_rules = {
        '__global__': [
            {
                'return': 'remove',
                'tags': ('input', 'button'),
                'rule-type': 'any-attribute-value-matches-pattern',
                'attributes': ('disabled',),
                'pattern': '*'
            },
            # Catch-all rule to keep other elements (prevents fallback to is_element_disabled)
            {
                'return': 'keep',
                'tags': ('*',)
            }
        ]
    }

    result = clean_html(html, disabled_element_rule_sets=custom_rules)
    soup = BeautifulSoup(result, 'html.parser')

    # Verify disabled inputs removed
    disabled_inputs = soup.find_all('input', attrs={'disabled': True})
    assert len(disabled_inputs) == 0, f"Expected 0 disabled inputs, found {len(disabled_inputs)}"
    print("✓ Disabled <input> elements removed")

    # Verify disabled buttons removed
    disabled_buttons = soup.find_all('button', attrs={'disabled': True})
    assert len(disabled_buttons) == 0, f"Expected 0 disabled buttons, found {len(disabled_buttons)}"
    print("✓ Disabled <button> elements removed")

    # Verify disabled select is kept (not in rule)
    disabled_selects = soup.find_all('select', attrs={'disabled': True})
    assert len(disabled_selects) == 1, f"Expected 1 disabled select (not in rule), found {len(disabled_selects)}"
    print("✓ Disabled <select> preserved (not in custom rule)")

    print()


def test_real_html_data():
    """Test with real HTML data from test_data directory."""
    print("=" * 80)
    print("Test 4: Real HTML data from google_join_waitlist.html")
    print("=" * 80)

    # Read real HTML test data
    test_data_path = os.path.join(
        project_root,
        'test', 'webaxon', 'html_utils', 'sanitization',
        'test_clean_html', 'test_data', 'google_join_waitlist.html'
    )

    with open(test_data_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Add some disabled inputs to the HTML
    html_with_disabled = html.replace(
        '<html',
        '<input type="text" disabled class="test-disabled-input">'
        '<input type="email" class="test-normal-input">'
        '<button disabled class="test-disabled-button">TestButton</button>'
        '<html'
    )

    # Count before cleaning
    soup_before = BeautifulSoup(html_with_disabled, 'html.parser')
    disabled_inputs_before = soup_before.find_all('input', attrs={'disabled': True})

    # Clean HTML with default parameters
    result = clean_html(html_with_disabled)
    soup = BeautifulSoup(result, 'html.parser')

    # Verify disabled input is removed (count decreased by 1)
    disabled_inputs_after = soup.find_all('input', attrs={'disabled': True})
    assert len(disabled_inputs_after) < len(disabled_inputs_before), \
        f"Expected fewer disabled inputs after cleaning, before={len(disabled_inputs_before)}, after={len(disabled_inputs_after)}"
    print(f"✓ Disabled <input> elements removed ({len(disabled_inputs_before)} -> {len(disabled_inputs_after)})")

    # Verify normal input is kept (type="email" should still exist)
    normal_inputs = soup.find_all('input', attrs={'type': 'email'})
    assert len(normal_inputs) >= 1, "Expected normal input to be kept"
    print("✓ Normal <input type='email'> preserved")

    # Verify disabled button is kept (should have disabled attribute preserved)
    disabled_button_with_text = soup.find('button', string='TestButton')
    assert disabled_button_with_text is not None, "Expected disabled button with text 'TestButton' to be kept"
    print("✓ Disabled <button>TestButton</button> preserved")

    print()


def run_all_tests():
    """Run all test functions."""
    print("\n" + "=" * 80)
    print("CLEAN_HTML DISABLED ELEMENT FILTERING END-TO-END TESTS")
    print("=" * 80 + "\n")

    test_functions = [
        test_default_behavior_removes_disabled_inputs,
        test_disable_all_disabled_element_removal,
        test_custom_rules_remove_multiple_element_types,
        test_real_html_data,
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
