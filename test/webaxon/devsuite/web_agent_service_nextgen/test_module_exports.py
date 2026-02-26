"""Test script to verify all module exports work correctly.

This script tests that:
1. All __init__.py files have proper exports
2. All exported classes can be imported
3. Import paths are clean and work as expected
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path


def test_main_module_exports():
    """Test main module exports."""
    print("Testing main module exports...")
    
    # Test main module import
    from webaxon.devsuite import web_agent_service_nextgen
    
    # Check version info
    assert hasattr(web_agent_service_nextgen, '__version__')
    assert hasattr(web_agent_service_nextgen, '__author__')
    assert hasattr(web_agent_service_nextgen, '__license__')
    print(f"  ✓ Version: {web_agent_service_nextgen.__version__}")
    print(f"  ✓ Author: {web_agent_service_nextgen.__author__}")
    print(f"  ✓ License: {web_agent_service_nextgen.__license__}")
    
    # Check main service class
    assert hasattr(web_agent_service_nextgen, 'WebAgentService')
    print("  ✓ WebAgentService available")
    
    # Check core components
    assert hasattr(web_agent_service_nextgen, 'ServiceConfig')
    assert hasattr(web_agent_service_nextgen, 'AgentSessionInfo')
    assert hasattr(web_agent_service_nextgen, 'SessionManager')
    assert hasattr(web_agent_service_nextgen, 'AgentFactory')
    print("  ✓ Core components available")
    
    # Check communication components
    assert hasattr(web_agent_service_nextgen, 'QueueManager')
    assert hasattr(web_agent_service_nextgen, 'MessageHandlers')
    print("  ✓ Communication components available")
    
    # Check agent components
    assert hasattr(web_agent_service_nextgen, 'AgentRunner')
    assert hasattr(web_agent_service_nextgen, 'TemplateManagerWrapper')
    print("  ✓ Agent components available")
    
    # Check session components
    assert hasattr(web_agent_service_nextgen, 'SessionMonitor')
    print("  ✓ Session components available")
    
    # Check __all__
    assert hasattr(web_agent_service_nextgen, '__all__')
    expected_exports = {
        '__version__', '__author__', '__license__',
        'WebAgentService',
        'ServiceConfig', 'AgentSessionInfo', 'AgentSession', 'SessionManager', 'AgentFactory',
        'QueueManager', 'MessageHandlers',
        'AgentRunner', 'TemplateManagerWrapper',
        'SessionMonitor'
    }
    actual_exports = set(web_agent_service_nextgen.__all__)
    assert expected_exports == actual_exports, f"Expected {expected_exports}, got {actual_exports}"
    print(f"  ✓ __all__ contains {len(actual_exports)} exports")
    
    print("✓ Main module exports: PASS\n")


def test_core_module_exports():
    """Test core module exports."""
    print("Testing core module exports...")
    
    from webaxon.devsuite.web_agent_service_nextgen import core
    
    # Check exports
    assert hasattr(core, 'ServiceConfig')
    assert hasattr(core, 'AgentFactory')
    assert hasattr(core, 'AgentSessionInfo')
    assert hasattr(core, 'AgentSession')
    assert hasattr(core, 'SessionManager')
    print("  ✓ All core components available")

    # Check __all__
    assert hasattr(core, '__all__')
    expected_exports = {'ServiceConfig', 'AgentSessionInfo', 'AgentSession', 'SessionManager', 'AgentFactory'}
    actual_exports = set(core.__all__)
    assert expected_exports == actual_exports
    print(f"  ✓ __all__ contains {len(actual_exports)} exports")

    # Test direct imports
    from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig
    from webaxon.devsuite.web_agent_service_nextgen.core import AgentFactory
    from webaxon.devsuite.web_agent_service_nextgen.core import AgentSessionInfo
    from webaxon.devsuite.web_agent_service_nextgen.core import AgentSession
    from webaxon.devsuite.web_agent_service_nextgen.core import AgentSessionManager
    print("  ✓ Direct imports work")
    
    print("✓ Core module exports: PASS\n")


def test_communication_module_exports():
    """Test communication module exports."""
    print("Testing communication module exports...")
    
    from webaxon.devsuite.web_agent_service_nextgen import communication
    
    # Check exports
    assert hasattr(communication, 'QueueManager')
    assert hasattr(communication, 'MessageHandlers')
    print("  ✓ All communication components available")
    
    # Check __all__
    assert hasattr(communication, '__all__')
    expected_exports = {'QueueManager', 'MessageHandlers'}
    actual_exports = set(communication.__all__)
    assert expected_exports == actual_exports
    print(f"  ✓ __all__ contains {len(actual_exports)} exports")
    
    # Test direct imports
    from webaxon.devsuite.web_agent_service_nextgen.communication import QueueManager
    from webaxon.devsuite.web_agent_service_nextgen.communication import MessageHandlers
    print("  ✓ Direct imports work")
    
    print("✓ Communication module exports: PASS\n")


def test_agents_module_exports():
    """Test agents module exports."""
    print("Testing agents module exports...")
    
    from webaxon.devsuite.web_agent_service_nextgen import agents
    
    # Check exports
    assert hasattr(agents, 'AgentRunner')
    assert hasattr(agents, 'TemplateManagerWrapper')
    print("  ✓ All agent components available")
    
    # Check __all__
    assert hasattr(agents, '__all__')
    expected_exports = {'AgentRunner', 'MetaAgentAdapter', 'MetaAgentRunResult', 'TemplateManagerWrapper'}
    actual_exports = set(agents.__all__)
    assert expected_exports == actual_exports, f"Expected {expected_exports}, got {actual_exports}"
    print(f"  ✓ __all__ contains {len(actual_exports)} exports")

    # Test direct imports
    from webaxon.devsuite.web_agent_service_nextgen.agents import AgentRunner
    from webaxon.devsuite.web_agent_service_nextgen.agents import MetaAgentAdapter
    from webaxon.devsuite.web_agent_service_nextgen.agents import MetaAgentRunResult
    from webaxon.devsuite.web_agent_service_nextgen.agents import TemplateManagerWrapper
    print("  ✓ Direct imports work")
    
    print("✓ Agents module exports: PASS\n")


def test_session_module_exports():
    """Test session module exports."""
    print("Testing session module exports...")

    from webaxon.devsuite.web_agent_service_nextgen import session

    # Check exports
    assert hasattr(session, 'SessionMonitor')
    assert hasattr(session, 'SessionManager')
    assert hasattr(session, 'AgentSession')
    assert hasattr(session, 'AgentSessionInfo')
    print("  ✓ All session components available")

    # Check __all__
    assert hasattr(session, '__all__')
    expected_exports = {'SessionMonitor', 'SessionManager', 'AgentSession', 'AgentSessionInfo', 'SessionLogger'}
    actual_exports = set(session.__all__)
    assert expected_exports == actual_exports
    print(f"  ✓ __all__ contains {len(actual_exports)} exports")

    # Test direct imports
    from webaxon.devsuite.web_agent_service_nextgen.session import SessionMonitor
    from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager
    from webaxon.devsuite.web_agent_service_nextgen.session import AgentSession
    from webaxon.devsuite.web_agent_service_nextgen.session import AgentSessionInfo
    print("  ✓ Direct imports work")

    print("✓ Session module exports: PASS\n")


def test_convenience_imports():
    """Test convenience imports from main module."""
    print("Testing convenience imports...")
    
    # Test that all components can be imported from main module
    from webaxon.devsuite.web_agent_service_nextgen import (
        WebAgentService,
        ServiceConfig,
        AgentSessionInfo,
        AgentSession,
        AgentSessionManager,
        AgentFactory,
        QueueManager,
        MessageHandlers,
        AgentRunner,
        TemplateManagerWrapper,
        SessionMonitor
    )
    
    print("  ✓ All components importable from main module")
    
    # Verify they're the same classes as from submodules
    from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig as CoreServiceConfig
    from webaxon.devsuite.web_agent_service_nextgen.communication import QueueManager as CommQueueManager
    from webaxon.devsuite.web_agent_service_nextgen.agents import AgentRunner as AgentsAgentRunner
    from webaxon.devsuite.web_agent_service_nextgen.session import SessionMonitor as SessionSessionMonitor

    assert ServiceConfig is CoreServiceConfig
    assert QueueManager is CommQueueManager
    assert AgentRunner is AgentsAgentRunner
    assert SessionMonitor is SessionSessionMonitor
    print("  ✓ Re-exported classes are identical to originals")
    
    print("✓ Convenience imports: PASS\n")


def test_module_docstrings():
    """Test that all modules have proper docstrings."""
    print("Testing module docstrings...")
    
    from webaxon.devsuite import web_agent_service_nextgen
    from webaxon.devsuite.web_agent_service_nextgen import core, communication, agents, session

    modules = [
        ('web_agent_service_nextgen', web_agent_service_nextgen),
        ('core', core),
        ('communication', communication),
        ('agents', agents),
        ('session', session)
    ]
    
    for name, module in modules:
        assert module.__doc__ is not None, f"{name} missing docstring"
        assert len(module.__doc__) > 50, f"{name} docstring too short"
        print(f"  ✓ {name} has docstring ({len(module.__doc__)} chars)")
    
    print("✓ Module docstrings: PASS\n")


def main():
    """Run all tests."""
    print("=" * 70)
    print("Testing Module Exports")
    print("=" * 70)
    print()
    
    try:
        test_main_module_exports()
        test_core_module_exports()
        test_communication_module_exports()
        test_agents_module_exports()
        test_session_module_exports()
        test_convenience_imports()
        test_module_docstrings()
        
        print("=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
