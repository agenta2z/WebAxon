"""
Action Tester Module

Provides browser automation testing functionality for the agent debugger.
"""
from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager, get_action_tester_manager
from webaxon.devsuite.agent_debugger_nextgen.action_tester.models import (
    Test,
    TestInfo,
    BrowserStatus,
    SequenceValidationResult,
    ActionStepResult,
    ElementIDResult,
    get_default_sequence_template
)

__all__ = [
    'ActionTesterManager',
    'get_action_tester_manager',
    'Test',
    'TestInfo',
    'BrowserStatus',
    'SequenceValidationResult',
    'ActionStepResult',
    'ElementIDResult',
    'get_default_sequence_template'
]
