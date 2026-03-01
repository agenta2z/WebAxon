"""Property-based test for public interface documentation."""
import sys
import resolve_path  # Setup import paths

import inspect
from pathlib import Path
from hypothesis import given, strategies as st, settings

def get_all_public_classes_and_methods():
    items = []
    modules_to_check = [
        ('core.config', 'ServiceConfig'),
        ('session.agent_session_info', 'AgentSessionInfo'),
        ('session.agent_session', 'AgentSession'),
        ('session.session_manager', 'SessionManager'),
        ('core.agent_factory', 'AgentFactory'),
        ('communication.queue_manager', 'QueueManager'),
        ('communication.message_handlers', 'MessageHandlers'),
        ('agents.agent_runner', 'AgentRunner'),
        ('agents.template_manager', 'TemplateManagerWrapper'),
        ('session.session_monitor', 'SessionMonitor'),
        ('service', 'WebAgentService'),
    ]
    for module_path, class_name in modules_to_check:
        try:
            module = __import__(f'webaxondevsuite.web_agent_service_nextgen.{module_path}', fromlist=[class_name])
            cls = getattr(module, class_name)
            items.append((f'{module_path}.{class_name}', cls, 'class'))
            for method_name in dir(cls):
                if not method_name.startswith('_'):
                    method = getattr(cls, method_name)
                    if callable(method):
                        items.append((f'{module_path}.{class_name}.{method_name}', method, 'method'))
        except Exception as e:
            print(f"Warning: Could not import {module_path}.{class_name}: {e}")
    return items

# Feature: web-agent-service-modularization, Property 49: Public Interface Documentation
# Validates: Requirements 13.2
@settings(max_examples=100)
@given(item_index=st.integers(min_value=0, max_value=1000))
def test_public_interface_documentation(item_index):
    items = get_all_public_classes_and_methods()
    if not items:
        raise AssertionError("No public classes or methods found to test")
    actual_index = item_index % len(items)
    name, obj, obj_type = items[actual_index]
    docstring = inspect.getdoc(obj)
    assert docstring is not None, f"{obj_type.capitalize()} {name} is missing a docstring."
    assert len(docstring.strip()) >= 10, f"{obj_type.capitalize()} {name} has a docstring that is too short."

def test_all_public_classes_have_docstrings():
    items = get_all_public_classes_and_methods()
    if not items:
        raise AssertionError("No public classes or methods found to test")
    print(f"\nChecking {len(items)} public classes and methods for documentation...")
    print("=" * 70)
    missing_docs = []
    short_docs = []
    for name, obj, obj_type in items:
        docstring = inspect.getdoc(obj)
        if docstring is None:
            missing_docs.append((name, obj_type))
        elif len(docstring.strip()) < 10:
            short_docs.append((name, obj_type, docstring))
    if missing_docs:
        print("\nX Missing docstrings:")
        for name, obj_type in missing_docs:
            print(f"  - {obj_type}: {name}")
    if short_docs:
        print("\nX Docstrings too short (< 10 characters):")
        for name, obj_type, doc in short_docs:
            print(f"  - {obj_type}: {name}")
            print(f"    Docstring: '{doc}'")
    assert not missing_docs, f"{len(missing_docs)} public classes/methods are missing docstrings."
    assert not short_docs, f"{len(short_docs)} public classes/methods have docstrings that are too short."
    print(f"\nOK All {len(items)} public classes and methods have proper documentation")

def test_specific_classes_have_detailed_docstrings():
    key_classes = [
        ('core.config', 'ServiceConfig'),
        ('session.session_manager', 'SessionManager'),
        ('core.agent_factory', 'AgentFactory'),
        ('communication.message_handlers', 'MessageHandlers'),
        ('service', 'WebAgentService'),
    ]
    print("\nChecking key classes for detailed documentation...")
    print("=" * 70)
    for module_path, class_name in key_classes:
        try:
            module = __import__(f'webaxondevsuite.web_agent_service_nextgen.{module_path}', fromlist=[class_name])
            cls = getattr(module, class_name)
            docstring = inspect.getdoc(cls)
            assert docstring is not None, f"{class_name} is missing a docstring"
            assert len(docstring) >= 50, f"{class_name} docstring is too short ({len(docstring)} chars)."
            print(f"OK {class_name}: {len(docstring)} characters")
        except Exception as e:
            raise AssertionError(f"Error checking {class_name}: {e}")
    print(f"\nOK All key classes have detailed documentation")

if __name__ == '__main__':
    print("Running property-based tests for public interface documentation...")
    print("=" * 70)
    print()
    print("1. Testing all public classes and methods have docstrings...")
    print("-" * 70)
    try:
        test_all_public_classes_have_docstrings()
    except AssertionError as e:
        print(f"\nX Test failed: {e}")
        sys.exit(1)
    print()
    print("2. Testing key classes have detailed docstrings...")
    print("-" * 70)
    try:
        test_specific_classes_have_detailed_docstrings()
    except AssertionError as e:
        print(f"\nX Test failed: {e}")
        sys.exit(1)
    print()
    print("3. Running property-based test with 100 random examples...")
    print("-" * 70)
    try:
        test_public_interface_documentation()
        print()
        print("OK Property test passed: Public interface documentation verified")
        print("  All public classes and methods have proper docstrings")
    except Exception as e:
        print(f"\nX Property test failed: {e}")
        sys.exit(1)
    print()
    print("=" * 70)
    print("All property-based tests passed!")
    print()
    print("Summary:")
    print("  - All public classes have docstrings")
    print("  - All public methods have docstrings")
    print("  - Key classes have detailed documentation")
    print("  - Property verified across 100 random test cases")
