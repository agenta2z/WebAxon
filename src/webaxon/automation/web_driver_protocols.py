"""
WebDriver Protocol Definitions

This module defines Protocol classes that specify the required interfaces
for different WebDriver capabilities. These protocols enable type checking
and ensure that driver implementations have the necessary methods.

Protocols:
- MonitorCapableDriver: Required interface for monitoring functionality
"""

from typing import Any, Protocol, Union, runtime_checkable


@runtime_checkable
class MonitorCapableDriver(Protocol):
    """
    Protocol defining the required interface for a driver to support monitoring.

    This protocol ensures that the webdriver passed to create_monitor() has all
    the necessary methods for element resolution and tab tracking. The WebDriver
    wrapper from webaxon.automation.web_driver implements this protocol.

    Required capabilities:
    - resolve_action_target: Resolve TargetSpec to element using strategy
    - register_monitor_tab / unregister_monitor_tab: Track monitored tabs
    - current_window_handle: Get current browser tab handle
    - find_element: Find element by locator (used by MonitorCondition.check)
    """

    @property
    def current_window_handle(self) -> str:
        """Get the handle of the current window/tab."""
        ...

    def resolve_action_target(
        self,
        strategy: Union[str, Any],
        action_target: str
    ) -> Any:
        """
        Resolve element using strategy.

        Args:
            strategy: Resolution strategy (TargetStrategy enum or string)
            action_target: Strategy-specific value (e.g., element ID, XPath)

        Returns:
            Resolved element or literal value
        """
        ...

    def register_monitor_tab(self, handle: str) -> None:
        """Register a tab as being used for monitoring."""
        ...

    def unregister_monitor_tab(self, handle: str) -> None:
        """Unregister a monitored tab."""
        ...

    def find_element(self, by: str, value: str) -> Any:
        """Find element by locator strategy (used by MonitorCondition.check)."""
        ...
