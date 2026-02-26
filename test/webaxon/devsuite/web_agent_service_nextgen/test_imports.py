"""Test that all import paths work correctly for web_agent_service_nextgen.

This test verifies various import methods are functional.
"""
import resolve_path  # Sets up Python path for webaxon imports

print("=" * 70)
print("Web Agent Service - Import Path Tests")
print("=" * 70)
print()

# Method 1: Import everything from main module (recommended for most users)
print("Method 1: Convenience imports from main module")
print("-" * 70)
print("from webaxon.devsuite.web_agent_service_nextgen import (")
print("    WebAgentService,")
print("    ServiceConfig,")
print("    SessionManager,")
print("    AgentFactory,")
print("    QueueManager,")
print("    MessageHandlers,")
print("    AgentRunner,")
print("    TemplateManagerWrapper,")
print("    SessionMonitor")
print(")")
print()

from webaxon.devsuite.web_agent_service_nextgen import (
    WebAgentService,
    ServiceConfig,
    AgentSessionManager,
    AgentFactory,
    QueueManager,
    MessageHandlers,
    AgentRunner,
    TemplateManagerWrapper,
    SessionMonitor
)

print("✓ All components imported successfully")
print()

# Method 2: Import from specific modules (for advanced users)
print("Method 2: Direct module imports")
print("-" * 70)
print("from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig")
print("from webaxon.devsuite.web_agent_service_nextgen.communication import QueueManager")
print("from webaxon.devsuite.web_agent_service_nextgen.agents import AgentRunner")
print("from webaxon.devsuite.web_agent_service_nextgen.session import SessionMonitor")
print()

from webaxon.devsuite.web_agent_service_nextgen.core import ServiceConfig as Config
from webaxon.devsuite.web_agent_service_nextgen.communication import QueueManager as QMgr
from webaxon.devsuite.web_agent_service_nextgen.agents import AgentRunner as Runner
from webaxon.devsuite.web_agent_service_nextgen.session import SessionMonitor as Monitor

print("✓ All components imported successfully")
print()

# Method 3: Simple usage (just the main service)
print("Method 3: Simple usage (main service only)")
print("-" * 70)
print("from webaxon.devsuite.web_agent_service_nextgen import WebAgentService")
print()

from webaxon.devsuite.web_agent_service_nextgen import WebAgentService as Service

print("✓ WebAgentService imported successfully")
print()

# Show version info
print("Package Information")
print("-" * 70)
import webaxon.devsuite.web_agent_service_nextgen as web_agent_service_nextgen
print(f"Version: {web_agent_service_nextgen.__version__}")
print(f"Author: {web_agent_service_nextgen.__author__}")
print(f"License: {web_agent_service_nextgen.__license__}")
print()

# Show available exports
print("Available Exports")
print("-" * 70)
print(f"Main module exports {len(web_agent_service_nextgen.__all__)} components:")
for i, name in enumerate(web_agent_service_nextgen.__all__, 1):
    if not name.startswith('__'):
        print(f"  {i}. {name}")
print()

# Show module structure
print("Module Structure")
print("-" * 70)
print("web_agent_service_nextgen/")
print("├── __init__.py          (main module)")
print("├── service.py           (WebAgentService)")
print("├── launch_service.py    (entry point)")
print("├── core/")
print("│   ├── __init__.py")
print("│   ├── config.py        (ServiceConfig)")
print("│   └── agent_factory.py (AgentFactory)")
print("├── communication/")
print("│   ├── __init__.py")
print("│   ├── queue_manager.py (QueueManager)")
print("│   └── message_handlers.py (MessageHandlers)")
print("├── agents/")
print("│   ├── __init__.py")
print("│   ├── agent_runner.py  (AgentRunner)")
print("│   └── template_manager.py (TemplateManagerWrapper)")
print("└── session/")
print("    ├── __init__.py")
print("    ├── agent_session_info.py (AgentSessionInfo)")
print("    ├── agent_session.py     (AgentSession)")
print("    ├── session_manager.py   (SessionManager)")
print("    └── session_monitor.py   (SessionMonitor)")
print()

print("=" * 70)
print("All import tests PASSED! ✓")
print("=" * 70)
