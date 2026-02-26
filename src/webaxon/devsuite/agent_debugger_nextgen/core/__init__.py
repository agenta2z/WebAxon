"""Core modules for agent debugger.

This package contains core abstractions and utilities:
- config: Configuration management
- session: Session state management
"""

from webaxon.devsuite.agent_debugger_nextgen.core.config import DebuggerConfig
from webaxon.devsuite.agent_debugger_nextgen.core.session import DebuggerSessionInfo, SessionManager

__all__ = ['DebuggerConfig', 'DebuggerSessionInfo', 'SessionManager']
