"""
Unified exception types for WebDriver backends.

These exceptions provide a consistent error handling interface regardless
of whether Selenium or Playwright is used as the underlying backend.
Each backend adapter wraps backend-specific exceptions into these types.
"""

from typing import Optional


class WebDriverError(Exception):
    """
    Base exception for all WebDriver errors.

    All other WebDriver exceptions inherit from this class, allowing
    callers to catch all WebDriver-related errors with a single handler.
    """
    pass


class ElementNotFoundError(WebDriverError):
    """
    Raised when an element cannot be located.

    Wraps:
    - Selenium: NoSuchElementException
    - Playwright: Element not found (locator.count() == 0)

    Attributes:
        strategy: The locator strategy used (e.g., 'xpath', 'id', 'css selector')
        target: The target value used with the strategy
    """

    def __init__(
        self,
        strategy: str,
        target: str,
        message: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ):
        self.strategy = strategy
        self.target = target
        self.original_exception = original_exception
        super().__init__(message or f"Element not found: {strategy}='{target}'")


class StaleElementError(WebDriverError):
    """
    Raised when an element reference is no longer valid.

    This occurs when:
    - The element was removed from the DOM
    - The element was replaced (e.g., by JavaScript re-rendering)
    - The page was refreshed
    - The element's parent was replaced

    Wraps:
    - Selenium: StaleElementReferenceException
    - Playwright: Element detached from DOM

    Attributes:
        element_description: Optional description of the stale element
    """

    def __init__(
        self,
        message: Optional[str] = None,
        element_description: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ):
        self.element_description = element_description
        self.original_exception = original_exception
        if message is None:
            if element_description:
                message = f"Element is stale: {element_description}"
            else:
                message = "Element is stale and no longer attached to the DOM"
        super().__init__(message)


class WebDriverTimeoutError(WebDriverError):
    """
    Raised when an operation times out.

    NOTE: Named WebDriverTimeoutError (not TimeoutError) to avoid
    shadowing Python's built-in TimeoutError.

    Wraps:
    - Selenium: TimeoutException
    - Playwright: playwright._impl._errors.TimeoutError

    Attributes:
        operation: Description of the operation that timed out
        timeout: The timeout value in seconds
    """

    def __init__(
        self,
        operation: str,
        timeout: float,
        message: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ):
        self.operation = operation
        self.timeout = timeout
        self.original_exception = original_exception
        super().__init__(message or f"Timeout after {timeout}s: {operation}")


class ElementNotInteractableError(WebDriverError):
    """
    Raised when an element cannot be interacted with.

    This occurs when:
    - The element is not visible
    - The element is disabled
    - The element is obscured by another element
    - The element is outside the viewport

    Wraps:
    - Selenium: ElementNotInteractableException, ElementClickInterceptedException
    - Playwright: Element not interactable errors

    Attributes:
        element_description: Optional description of the element
        action_attempted: The action that was attempted (e.g., 'click', 'input')
    """

    def __init__(
        self,
        message: Optional[str] = None,
        element_description: Optional[str] = None,
        action_attempted: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ):
        self.element_description = element_description
        self.action_attempted = action_attempted
        self.original_exception = original_exception
        if message is None:
            parts = ["Element not interactable"]
            if element_description:
                parts.append(f": {element_description}")
            if action_attempted:
                parts.append(f" (attempted: {action_attempted})")
            message = "".join(parts)
        super().__init__(message)


class UnsupportedOperationError(WebDriverError):
    """
    Raised when an operation is not supported by the backend.

    This is used for operations that:
    - Are backend-specific (e.g., CDP commands on Firefox)
    - Haven't been implemented yet
    - Are fundamentally incompatible with the backend

    Attributes:
        operation: The operation that was attempted
        backend_type: The type of backend that doesn't support the operation
    """

    def __init__(
        self,
        operation: str,
        backend_type: str,
        message: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ):
        self.operation = operation
        self.backend_type = backend_type
        self.original_exception = original_exception
        super().__init__(
            message or f"Operation '{operation}' not supported by {backend_type} backend"
        )
