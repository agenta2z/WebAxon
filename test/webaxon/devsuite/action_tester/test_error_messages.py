"""
Test error message quality in ActionTesterManager.

This test verifies that error messages are detailed, helpful, and actionable
by directly reading and analyzing the source code.
"""
from pathlib import Path
import re


def read_manager_source():
    """Read the manager.py source code."""
    manager_path = Path(__file__).parent.parent.parent.parent / "src" / "webaxon" / "devsuite" / "agent_debugger_nextgen" / "action_tester" / "manager.py"
    with open(manager_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_error_messages(source_code):
    """Extract all error messages from the source code."""
    # Pattern to find multi-line strings that look like error messages
    pattern = r"'([^']*❌[^']*(?:\n[^']*)*?)'"
    matches = re.findall(pattern, source_code, re.MULTILINE)
    
    # Also find messages with warning icon
    pattern2 = r"'([^']*⚠️[^']*(?:\n[^']*)*?)'"
    matches.extend(re.findall(pattern2, source_code, re.MULTILINE))
    
    return matches


def test_error_message_structure():
    """Test that all error messages follow the expected structure."""
    source = read_manager_source()
    error_messages = extract_error_messages(source)
    
    print(f"Found {len(error_messages)} error messages to analyze\n")
    
    required_elements = {
        'has_icon': lambda msg: '❌' in msg or '⚠️' in msg or '✅' in msg or 'ℹ️' in msg,
        'has_title': lambda msg: 'Failed:' in msg or 'Warning:' in msg or 'Error:' in msg,
        'has_action_section': lambda msg: 'Action Required' in msg or 'action' in msg.lower(),
        'has_numbered_steps': lambda msg: any(f'{i}.' in msg for i in range(1, 6)),
    }
    
    issues = []
    
    for i, msg in enumerate(error_messages, 1):
        print(f"Analyzing message {i}:")
        print(f"  Preview: {msg[:80]}...")
        
        checks = {
            'Icon': required_elements['has_icon'](msg),
            'Title': required_elements['has_title'](msg),
            'Action Section': required_elements['has_action_section'](msg),
            'Numbered Steps': required_elements['has_numbered_steps'](msg),
        }
        
        for check_name, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"    {status} {check_name}")
            if not passed:
                issues.append(f"Message {i} missing: {check_name}")
        
        print()
    
    if issues:
        print("❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ All error messages are well-structured!")
        return True


def test_specific_error_scenarios():
    """Test that specific error scenarios have appropriate messages."""
    source = read_manager_source()
    
    scenarios = {
        'Browser launch failure': [
            'ChromeDriver Not Found',
            'Chrome Browser Not Found',
            'Permission Denied',
            'Port Already In Use',
        ],
        'JSON validation': [
            'Empty Input',
            'JSON Syntax Error',
            'Missing Required Field',
        ],
        'Sequence execution': [
            'Element Not Found',
            'Timeout',
            'Stale Element',
            'Element Not Interactable',
        ],
        'Element ID injection': [
            'No Page Loaded',
            'JavaScript Execution Error',
        ],
        'Test management': [
            'No Active Browser',
            'Test Not Found',
        ],
    }
    
    print("Checking coverage of error scenarios:\n")
    
    all_covered = True
    for category, expected_errors in scenarios.items():
        print(f"{category}:")
        for error_type in expected_errors:
            if error_type in source:
                print(f"  ✓ {error_type}")
            else:
                print(f"  ✗ {error_type} - NOT FOUND")
                all_covered = False
        print()
    
    if all_covered:
        print("✅ All error scenarios are covered!")
    else:
        print("❌ Some error scenarios are missing")
    
    return all_covered


def test_actionable_guidance():
    """Test that error messages provide actionable guidance."""
    source = read_manager_source()
    
    # Check for common actionable phrases
    actionable_phrases = [
        'Click',
        'Try',
        'Check',
        'Ensure',
        'Install',
        'Restart',
        'Wait',
        'Navigate',
        'Refresh',
        'Close',
    ]
    
    print("Checking for actionable guidance:\n")
    
    found_phrases = {}
    for phrase in actionable_phrases:
        count = source.count(phrase)
        found_phrases[phrase] = count
        if count > 0:
            print(f"  ✓ '{phrase}' used {count} times")
    
    total_actions = sum(found_phrases.values())
    print(f"\nTotal actionable instructions: {total_actions}")
    
    if total_actions >= 50:  # Arbitrary threshold
        print("✅ Error messages provide plenty of actionable guidance!")
        return True
    else:
        print("⚠️ Consider adding more actionable guidance")
        return False


def test_requirements_coverage():
    """Test that all requirements from task 36 are addressed."""
    source = read_manager_source()
    
    requirements = {
        'Browser launch failures': 'launch_browser',
        'JSON validation failures': 'validate_sequence_json',
        'Sequence execution failures': 'execute_sequence',
        'ID injection failures': 'add_element_ids',
        'Test management failures': ['create_test', 'close_test', 'switch_to_test'],
    }
    
    print("Checking requirements coverage:\n")
    
    all_covered = True
    for requirement, methods in requirements.items():
        if isinstance(methods, str):
            methods = [methods]
        
        print(f"{requirement}:")
        for method in methods:
            if f"def {method}" in source:
                # Check if the method has enhanced error handling
                method_start = source.find(f"def {method}")
                method_end = source.find("\n    def ", method_start + 1)
                if method_end == -1:
                    method_end = len(source)
                
                method_code = source[method_start:method_end]
                
                # Count error messages in this method
                error_count = method_code.count('❌') + method_code.count('⚠️')
                
                if error_count > 0:
                    print(f"  ✓ {method} - {error_count} error message(s)")
                else:
                    print(f"  ⚠️ {method} - No enhanced error messages found")
                    all_covered = False
            else:
                print(f"  ✗ {method} - Method not found")
                all_covered = False
        print()
    
    if all_covered:
        print("✅ All requirements are covered!")
    else:
        print("⚠️ Some requirements may need more attention")
    
    return all_covered


if __name__ == "__main__":
    print("=" * 70)
    print("ERROR HANDLING QUALITY TESTS")
    print("=" * 70)
    print()
    
    results = []
    
    print("TEST 1: Error Message Structure")
    print("-" * 70)
    results.append(("Structure", test_error_message_structure()))
    print()
    
    print("TEST 2: Error Scenario Coverage")
    print("-" * 70)
    results.append(("Scenarios", test_specific_error_scenarios()))
    print()
    
    print("TEST 3: Actionable Guidance")
    print("-" * 70)
    results.append(("Actionable", test_actionable_guidance()))
    print()
    
    print("TEST 4: Requirements Coverage")
    print("-" * 70)
    results.append(("Requirements", test_requirements_coverage()))
    print()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s} {status}")
    
    all_passed = all(result[1] for result in results)
    print()
    if all_passed:
        print("🎉 All tests passed! Error handling is comprehensive and actionable.")
    else:
        print("⚠️ Some tests failed. Review the output above for details.")
    
    exit(0 if all_passed else 1)
