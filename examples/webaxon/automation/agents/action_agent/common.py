"""
Common utilities for action agent examples.

This module provides shared functionality for action agent example scripts:
- Project path setup
- Logging configuration
- Test result tracking
- Action extraction and summarization
"""

import os
import sys
import logging
from typing import List, Dict, Any, Optional


def setup_project_paths():
    """
    Add project roots to sys.path for local imports.

    Returns:
        str: The project root path
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", "..", "..", ".."))
    projects_root = os.path.abspath(os.path.join(project_root, ".."))

    # Add WebAgent src
    sys.path.insert(0, os.path.join(project_root, "src"))

    # Add science packages if they exist
    for pkg in ["SciencePythonUtils", "ScienceModelingTools"]:
        pkg_src = os.path.join(projects_root, pkg, "src")
        if os.path.exists(pkg_src) and pkg_src not in sys.path:
            sys.path.insert(0, pkg_src)

    return project_root


def setup_logging(name: str = __name__, level: int = logging.INFO):
    """
    Configure logging and return a logger.

    Args:
        name: Logger name (default: module name)
        level: Logging level (default: INFO)

    Returns:
        logging.Logger: Configured logger instance
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(name)


class TestResult:
    """Track test results with pass/fail status."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize TestResult.

        Args:
            logger: Optional logger for output. If None, uses module logger.
        """
        self.passed: List[str] = []
        self.failed: List[tuple] = []
        self._logger = logger or logging.getLogger(__name__)

    def check(self, name: str, condition: bool, error_msg: str = ""):
        """
        Check a condition and record result.

        Args:
            name: Test name
            condition: True if test passed
            error_msg: Error message if test failed
        """
        if condition:
            self.passed.append(name)
            self._logger.info(f"[PASS] {name}")
        else:
            self.failed.append((name, error_msg))
            self._logger.error(f"[FAIL] {name}: {error_msg}")

    def summary(self) -> bool:
        """
        Print summary and return True if all passed.

        Returns:
            bool: True if all tests passed
        """
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Passed: {len(self.passed)}")
        print(f"Failed: {len(self.failed)}")

        if self.failed:
            print("\nFailed tests:")
            for name, error in self.failed:
                print(f"  - {name}: {error}")

        success = len(self.failed) == 0
        print(f"\nOverall: {'SUCCESS' if success else 'FAILURE'}")
        return success


def extract_executed_actions(agent) -> List[Dict[str, Any]]:
    """
    Extract executed actions from agent's state history.

    Args:
        agent: The PromptBasedActionAgent after execution

    Returns:
        List of action dictionaries with type, target, args, reasoning
    """
    executed_actions = []

    if not hasattr(agent, 'states') or agent.states is None:
        return executed_actions

    # Iterate through agent states to extract actions
    for i, state_item in enumerate(agent.states):
        if not hasattr(state_item, 'response') or state_item.response is None:
            continue

        response = state_item.response

        # AgentResponse.next_actions contains the planned/executed actions
        if hasattr(response, 'next_actions') and response.next_actions:
            for action_group in response.next_actions:
                # action_group can be a tuple of alternative actions
                if isinstance(action_group, (list, tuple)):
                    for action in action_group:
                        action_info = _extract_action_info(action, i)
                        if action_info:
                            executed_actions.append(action_info)
                else:
                    action_info = _extract_action_info(action_group, i)
                    if action_info:
                        executed_actions.append(action_info)

    return executed_actions


def _extract_action_info(action, step_index: int) -> Optional[Dict[str, Any]]:
    """
    Extract info from a single AgentAction object.

    Args:
        action: AgentAction object
        step_index: The step/iteration index

    Returns:
        Dictionary with action details, or None if invalid
    """
    if action is None:
        return None

    # Handle AgentAction objects
    action_type = getattr(action, 'type', None) or getattr(action, 'action_type', None)
    if not action_type:
        return None

    return {
        'step': step_index + 1,
        'type': action_type,
        'target': getattr(action, 'target', None),
        'args': getattr(action, 'args', None),
        'reasoning': getattr(action, 'reasoning', None),
        'result': getattr(action, 'result', None),
    }


def print_action_summary(actions: List[Dict[str, Any]]):
    """
    Print a formatted summary of executed actions.

    Args:
        actions: List of action dictionaries from extract_executed_actions()
    """
    print("\n" + "=" * 60)
    print("EXECUTED ACTIONS SUMMARY")
    print("=" * 60)

    if not actions:
        print("No actions were executed.")
        return

    print(f"Total actions: {len(actions)}\n")

    for i, action in enumerate(actions, 1):
        print(f"Action {i}:")
        print(f"  Step:      {action.get('step', 'N/A')}")
        print(f"  Type:      {action.get('type', 'N/A')}")
        print(f"  Target:    {action.get('target', 'N/A')}")

        # Format args nicely
        args = action.get('args')
        if args:
            if isinstance(args, dict):
                args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
            else:
                args_str = str(args)
            print(f"  Args:      {args_str}")

        # Truncate reasoning if too long
        reasoning = action.get('reasoning', '')
        if reasoning:
            if len(reasoning) > 100:
                reasoning = reasoning[:100] + "..."
            print(f"  Reasoning: {reasoning}")

        # Show result status if available
        result = action.get('result')
        if result:
            if isinstance(result, dict):
                status = result.get('status', 'completed')
                print(f"  Result:    {status}")
            else:
                print(f"  Result:    (data returned)")

        print()

    # Summary by action type
    print("-" * 40)
    print("Actions by Type:")
    action_types: Dict[str, int] = {}
    for action in actions:
        atype = action.get('type', 'Unknown')
        action_types[atype] = action_types.get(atype, 0) + 1

    for atype, count in sorted(action_types.items()):
        print(f"  {atype}: {count}")
