"""
SwitchTo adapter for backward compatibility.

This module provides the _SwitchToAdapter class that enables the
switch_to.window(handle) pattern to work with both Selenium and
Playwright backends.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from webaxon.automation.backends.base import BackendAdapter


class SwitchToAdapter:
    """
    Adapter to provide switch_to.window(handle) pattern for backward compatibility.

    This allows existing code using driver.switch_to.window(handle) to work
    with both Selenium and Playwright backends.

    Usage:
        # In WebDriver class:
        @property
        def switch_to(self):
            return SwitchToAdapter(self._backend)

        # User code (unchanged):
        driver.switch_to.window(handle)

    Methods:
        window(handle): Switch to a specific window/tab
        frame(frame_reference): Switch to a frame (limited support)
        default_content(): Switch back to main document
        active_element(): Get the currently focused element
    """

    def __init__(self, backend: 'BackendAdapter'):
        """
        Initialize the SwitchTo adapter.

        Args:
            backend: The backend adapter to delegate operations to
        """
        self._backend = backend

    def window(self, handle: str) -> None:
        """
        Switch to a specific window/tab by handle.

        Args:
            handle: Window handle string

        Raises:
            ValueError: If the handle doesn't exist
        """
        self._backend.switch_to_window(handle)

    def frame(self, frame_reference: Any) -> None:
        """
        Switch to a frame.

        Note: Frame handling differs significantly between Selenium and Playwright.
        Playwright uses frame_locator() instead of switching context.

        Args:
            frame_reference: Frame element, name, or index

        Raises:
            UnsupportedOperationError: If the backend doesn't support frame switching
        """
        if hasattr(self._backend, 'switch_to_frame'):
            self._backend.switch_to_frame(frame_reference)
        else:
            from webaxon.automation.backends.exceptions import UnsupportedOperationError
            raise UnsupportedOperationError(
                operation="switch_to.frame()",
                backend_type=type(self._backend).__name__,
                message=(
                    "Frame switching works differently in Playwright. "
                    "Use page.frame_locator() for frame-specific operations instead."
                )
            )

    def default_content(self) -> None:
        """
        Switch to the main document (exit frames).

        For Playwright, this is effectively a no-op since Playwright
        doesn't use the same frame switching model as Selenium.

        Raises:
            UnsupportedOperationError: If the backend doesn't support this operation
        """
        if hasattr(self._backend, 'switch_to_default_content'):
            self._backend.switch_to_default_content()
        # For backends that don't have explicit frame context, this is a no-op

    def active_element(self) -> Any:
        """
        Get the currently focused element.

        Returns:
            The currently focused element, or None if no element has focus

        Raises:
            UnsupportedOperationError: If the backend doesn't support this operation
        """
        if hasattr(self._backend, 'get_active_element'):
            return self._backend.get_active_element()
        else:
            from webaxon.automation.backends.exceptions import UnsupportedOperationError
            raise UnsupportedOperationError(
                operation="switch_to.active_element()",
                backend_type=type(self._backend).__name__
            )

    def alert(self) -> Any:
        """
        Switch to an alert dialog.

        Note: Alert handling differs between Selenium and Playwright.
        Playwright uses page.on('dialog', handler) for dialog handling.

        Returns:
            Alert object for interaction

        Raises:
            UnsupportedOperationError: If the backend doesn't support alert switching
        """
        if hasattr(self._backend, 'switch_to_alert'):
            return self._backend.switch_to_alert()
        else:
            from webaxon.automation.backends.exceptions import UnsupportedOperationError
            raise UnsupportedOperationError(
                operation="switch_to.alert",
                backend_type=type(self._backend).__name__,
                message=(
                    "Playwright handles dialogs differently. "
                    "Use page.on('dialog', handler) instead."
                )
            )
