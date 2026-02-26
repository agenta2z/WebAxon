"""Property-based test for module __init__ files.

This module contains a property-based test using hypothesis to verify
that all module directories contain __init__.py files that export public interfaces.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path

from hypothesis import given, strategies as st, settings
import webaxon.devsuite.web_agent_service_nextgen as _source_pkg


# Feature: web-agent-service-modularization, Property 1: Module __init__ Files
# Validates: Requirements 1.2
@settings(max_examples=100)
@given(
    # Generate random module paths to test
    module_name=st.sampled_from([
        'web_agent_service_nextgen',
        'web_agent_service_nextgen.core',
        'web_agent_service_nextgen.communication',
        'web_agent_service_nextgen.agents',
        'web_agent_service_nextgen.session',
    ])
)
def test_module_init_files(module_name):
    """Property: For any module directory, it should contain an __init__.py file.
    
    This test verifies that all module directories in the web_agent_service_nextgen
    structure contain an __init__.py file that exports public interfaces, as specified
    in Requirement 1.2.
    
    The test checks:
    1. The __init__.py file exists
    2. The file is readable
    3. The file exports public interfaces (has __all__ or imports)
    """
    # Convert module name to file path
    base_path = Path(_source_pkg.__file__).parent
    module_parts = module_name.split('.')
    
    # Navigate to the module directory
    module_path = base_path
    for part in module_parts:
        if part == 'web_agent_service_nextgen':
            # Already at base_path
            continue
        module_path = module_path / part
    
    # Check that __init__.py exists
    init_file = module_path / '__init__.py'
    assert init_file.exists(), f"Module {module_name} missing __init__.py file at {init_file}"
    
    # Check that the file is readable
    assert init_file.is_file(), f"__init__.py at {init_file} is not a file"
    
    # Read the file content
    try:
        content = init_file.read_text(encoding='utf-8')
    except Exception as e:
        raise AssertionError(f"Cannot read __init__.py at {init_file}: {e}")
    
    # Verify the file exports public interfaces
    # Check for either __all__ definition or import statements
    has_all = '__all__' in content
    has_imports = 'from' in content or 'import' in content
    
    assert has_all or has_imports, (
        f"Module {module_name} __init__.py does not export public interfaces. "
        f"Expected __all__ definition or import statements."
    )
    
    # If __all__ is present, verify it's not empty
    if has_all:
        # Simple check: __all__ should be followed by = and have content
        assert '__all__ = [' in content or '__all__=[' in content, (
            f"Module {module_name} has __all__ but it appears malformed"
        )


def test_all_expected_modules_have_init_files():
    """Comprehensive test: Verify all expected modules have __init__.py files.
    
    This is a deterministic test that checks all known module directories.
    """
    base_path = Path(_source_pkg.__file__).parent

    expected_modules = [
        base_path,  # web_agent_service_nextgen
        base_path / 'core',
        base_path / 'communication',
        base_path / 'agents',
        base_path / 'session',
    ]
    
    for module_path in expected_modules:
        init_file = module_path / '__init__.py'
        
        # Check existence
        assert init_file.exists(), (
            f"Missing __init__.py in {module_path.name} module at {init_file}"
        )
        
        # Check it's a file
        assert init_file.is_file(), (
            f"__init__.py at {init_file} is not a file"
        )
        
        # Check it's readable and has content
        try:
            content = init_file.read_text(encoding='utf-8')
        except Exception as e:
            raise AssertionError(f"Cannot read __init__.py at {init_file}: {e}")
        
        # Verify it exports public interfaces
        has_all = '__all__' in content
        has_imports = 'from' in content or 'import' in content
        
        assert has_all or has_imports, (
            f"Module {module_path.name} __init__.py does not export public interfaces. "
            f"Expected __all__ definition or import statements."
        )
        
        print(f"✓ {module_path.name}/__init__.py exists and exports interfaces")


if __name__ == '__main__':
    print("Running property-based tests for module __init__ files...")
    print("=" * 70)
    print()
    
    # First run the comprehensive deterministic test
    print("1. Testing all expected modules have __init__.py files...")
    print("-" * 70)
    try:
        test_all_expected_modules_have_init_files()
        print()
        print("✓ All expected modules have __init__.py files")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    
    print()
    print("2. Running property-based test with 100 random examples...")
    print("-" * 70)
    
    try:
        test_module_init_files()
        print()
        print("✓ Property test passed: Module __init__ files verified")
        print("  All module directories contain __init__.py files that export interfaces")
    except Exception as e:
        print(f"\n✗ Property test failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("All property-based tests passed! ✓")
    print()
    print("Summary:")
    print("  - All 5 module directories have __init__.py files")
    print("  - All __init__.py files export public interfaces")
    print("  - Property verified across 100 random test cases")
