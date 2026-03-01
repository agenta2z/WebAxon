"""
WebDriver-Specific Monitor Implementation

This module provides browser-specific monitoring functionality for ActionGraph/ActionFlow.
It contains the concrete layer that depends on WebDriver/Selenium.

Components:
- MonitorConditionType: Enum for built-in condition types
- MonitorCondition: Condition specification class with check() method
- create_monitor(): Factory function for element monitoring on current tab

The generic layer (MonitorNode, MonitorResult, MonitorStatus) lives in
ScienceModelingTools.automation.schema.monitor and is executor-agnostic.
"""

import time
from enum import Enum
from collections.abc import Mapping
from typing import Any, Callable, Optional, Tuple, Union, TYPE_CHECKING

from attr import attrs, attrib

# Import generic layer from ScienceModelingTools
from agent_foundation.automation.schema.monitor import (
    MonitorResult,
    MonitorStatus,
)
from rich_python_utils.common_objects.workflow.common.worknode_base import NextNodesSelector
from webaxon.automation.web_driver_protocols import MonitorCapableDriver

if TYPE_CHECKING:
    from agent_foundation.automation.schema.common import TargetSpec, TargetSpecWithFallback


class MonitorConditionType(str, Enum):
    """Built-in monitor condition types for browser monitoring.
    
    These condition types are specific to WebDriver-based monitoring:
    - ELEMENT_PRESENT: Wait for an element to appear in the DOM
    - ELEMENT_ABSENT: Wait for an element to disappear from the DOM
    - TEXT_CONTAINS: Wait for specific text to appear on the page
    - TEXT_CHANGED: Wait for text content to change from initial value
    - ATTRIBUTE_CHANGED: Wait for element attribute to change
    - VALUE_CHANGED: Wait for input value to change
    - CUSTOM: Use a custom callable for condition checking
    """
    ELEMENT_PRESENT = "element_present"
    ELEMENT_ABSENT = "element_absent"
    TEXT_CONTAINS = "text_contains"
    TEXT_CHANGED = "text_changed"
    TEXT_CHANGES = "text_changes"  # Alias for TEXT_CHANGED (backward compat)
    ATTRIBUTE_CHANGED = "attribute_changed"
    VALUE_CHANGED = "value_changed"
    CUSTOM = "custom"


@attrs
class MonitorCondition:
    """
    Specification for a monitor condition - WebDriver specific.

    Defines what condition to check when monitoring an element. Supports built-in
    condition types (element present/absent, text contains/changes) and
    custom callables for complex conditions.

    Note: Element resolution is handled by create_monitor() using TargetSpec.
    This class only specifies WHAT condition to check, not HOW to find the element.

    Attributes:
        condition_type: Type of condition to check
        expected_text: Text to search for (TEXT_CONTAINS)
        attribute_name: Attribute to monitor (ATTRIBUTE_CHANGED)
        event_confirmation_time: Debounce time in seconds (condition must remain
                                 true for this duration before being reported as met)
        custom_callable: Custom function for CUSTOM condition type.
                        Should accept (driver, element) and return (bool, matched_content) or bool.

    Example:
        >>> # Wait for specific text on page
        >>> condition = MonitorCondition(
        ...     condition_type=MonitorConditionType.TEXT_CONTAINS,
        ...     expected_text="Order Complete"
        ... )

        >>> # Wait for text change with debounce
        >>> condition = MonitorCondition(
        ...     condition_type=MonitorConditionType.TEXT_CHANGED,
        ...     event_confirmation_time=5.0  # Wait 5s to confirm stable
        ... )

        >>> # Custom condition
        >>> def check_price(driver, element):
        ...     price = float(element.text.replace("$", ""))
        ...     return (price < 100, price)
        >>> condition = MonitorCondition(
        ...     condition_type=MonitorConditionType.CUSTOM,
        ...     custom_callable=check_price
        ... )
    """
    condition_type: MonitorConditionType = attrib()
    expected_text: Optional[str] = attrib(default=None)
    attribute_name: Optional[str] = attrib(default=None)
    event_confirmation_time: float = attrib(default=0.0)
    custom_callable: Optional[Callable] = attrib(default=None)
    _initial_text: Optional[str] = attrib(default=None, init=False)
    _initial_attribute: Optional[str] = attrib(default=None, init=False)
    _initial_value: Optional[str] = attrib(default=None, init=False)
    _condition_first_met_time: Optional[float] = attrib(default=None, init=False)
    
    def check(self, driver, element=None) -> Tuple[bool, Optional[Any]]:
        """
        Check if condition is met.

        Args:
            driver: WebDriver wrapper that implements MonitorCapableDriver protocol.
                    Used for TEXT_CONTAINS fallback (finds body element if no element provided).
            element: Optional pre-resolved element (for element-based monitoring).
                     Element resolution is handled by create_monitor() using TargetSpec.

        Returns:
            Tuple of (condition_met: bool, matched_content: Any)
        """
        # Normalize TEXT_CHANGES to TEXT_CHANGED
        condition_type = self.condition_type
        if condition_type == MonitorConditionType.TEXT_CHANGES:
            condition_type = MonitorConditionType.TEXT_CHANGED
        
        if condition_type == MonitorConditionType.ELEMENT_PRESENT:
            # Element resolution is handled by create_monitor() using TargetSpec
            if element is not None:
                return self._apply_debounce(True, element.text if element else None)
            # Element not resolved - condition not met
            self._reset_debounce()
            return (False, None)
        
        elif condition_type == MonitorConditionType.ELEMENT_ABSENT:
            # Element resolution is handled by create_monitor() using TargetSpec
            if element is not None:
                # Element was resolved, so it exists - condition not met
                self._reset_debounce()
                return (False, None)
            # Element not resolved - element is absent, condition met
            return self._apply_debounce(True, None)
        
        elif condition_type == MonitorConditionType.TEXT_CONTAINS:
            try:
                if element is not None:
                    text = element.text if element else ""
                else:
                    body = driver.find_element("tag name", "body")
                    text = body.text if body else ""
                if self.expected_text and self.expected_text in text:
                    return self._apply_debounce(True, self.expected_text)
                self._reset_debounce()
                return (False, None)
            except Exception:
                self._reset_debounce()
                return (False, None)
        
        elif condition_type == MonitorConditionType.TEXT_CHANGED:
            # Element resolution is handled by create_monitor() using TargetSpec
            if element is None:
                self._reset_debounce()
                return (False, None)
            try:
                current_text = element.text if element else ""
                if self._initial_text is None:
                    object.__setattr__(self, '_initial_text', current_text)
                    return (False, None)  # First check, record baseline
                if current_text != self._initial_text:
                    return self._apply_debounce(True, current_text)
                self._reset_debounce()
                return (False, None)
            except Exception:
                self._reset_debounce()
                return (False, None)
        
        elif condition_type == MonitorConditionType.ATTRIBUTE_CHANGED:
            # Element resolution is handled by create_monitor() using TargetSpec
            if element is None:
                self._reset_debounce()
                return (False, None)
            try:
                attr_name = self.attribute_name or "class"
                current_attr = element.get_attribute(attr_name)
                if self._initial_attribute is None:
                    object.__setattr__(self, '_initial_attribute', current_attr)
                    return (False, None)  # First check, record baseline
                if current_attr != self._initial_attribute:
                    return self._apply_debounce(True, current_attr)
                self._reset_debounce()
                return (False, None)
            except Exception:
                self._reset_debounce()
                return (False, None)
        
        elif condition_type == MonitorConditionType.VALUE_CHANGED:
            # Element resolution is handled by create_monitor() using TargetSpec
            import logging
            _logger = logging.getLogger(__name__)
            if element is None:
                _logger.debug(f"[MonitorCondition.check] VALUE_CHANGED: element is None")
                self._reset_debounce()
                return (False, None)
            try:
                current_value = element.get_attribute("value") or ""
                _logger.debug(f"[MonitorCondition.check] VALUE_CHANGED: condition_id={id(self)}, current_value='{current_value}', initial_value='{self._initial_value}'")
                if self._initial_value is None:
                    object.__setattr__(self, '_initial_value', current_value)
                    _logger.debug(f"[MonitorCondition.check] VALUE_CHANGED: Recording baseline: '{current_value}'")
                    return (False, None)  # First check, record baseline
                if current_value != self._initial_value:
                    _logger.debug(f"[MonitorCondition.check] VALUE_CHANGED: Value changed! Applying debounce...")
                    met, content = self._apply_debounce(True, current_value)
                    if met:
                        # Reset baseline to current value for continuous monitoring
                        # This allows detecting the NEXT change after this one
                        _logger.debug(f"[MonitorCondition.check] VALUE_CHANGED: Condition met! Resetting baseline to '{current_value}'")
                        object.__setattr__(self, '_initial_value', current_value)
                        self._reset_debounce()  # Reset debounce for next detection
                    return (met, content)
                self._reset_debounce()
                return (False, None)
            except Exception as e:
                _logger.debug(f"[MonitorCondition.check] VALUE_CHANGED: Exception: {e}")
                self._reset_debounce()
                return (False, None)
        
        elif condition_type == MonitorConditionType.CUSTOM:
            if self.custom_callable:
                result = self.custom_callable(driver)
                if isinstance(result, tuple):
                    met, content = result
                else:
                    met, content = bool(result), result
                if met:
                    return self._apply_debounce(True, content)
                self._reset_debounce()
                return (False, content)  # Preserve content even when not met
            return (False, None)
        
        return (False, None)
    
    def _apply_debounce(self, met: bool, content: Any) -> Tuple[bool, Optional[Any]]:
        """Apply debounce logic if event_confirmation_time is set."""
        import logging
        _logger = logging.getLogger(__name__)

        if self.event_confirmation_time <= 0:
            _logger.debug(f"[_apply_debounce] No debounce configured, returning immediately")
            return (met, content)

        current_time = time.time()
        if self._condition_first_met_time is None:
            object.__setattr__(self, '_condition_first_met_time', current_time)
            _logger.debug(f"[_apply_debounce] Starting debounce timer at {current_time}")
            return (False, None)  # Start debounce timer

        elapsed = current_time - self._condition_first_met_time
        _logger.debug(f"[_apply_debounce] Debounce elapsed: {elapsed:.1f}s / {self.event_confirmation_time}s")
        if elapsed >= self.event_confirmation_time:
            _logger.debug(f"[_apply_debounce] Debounce complete! Condition confirmed.")
            return (True, content)  # Debounce period passed
        return (False, None)  # Still in debounce period
    
    def _reset_debounce(self):
        """Reset debounce timer when condition becomes false."""
        if self._condition_first_met_time is not None:
            object.__setattr__(self, '_condition_first_met_time', None)


def _extract_webdriver(webdriver_or_executor: Any) -> Any:
    """
    Extract the actual webdriver from various action_executor formats.

    ActionGraph passes self.action_executor to create_monitor(), which may be:
    - Direct webdriver instance (returns as-is)
    - Dict with 'default' key: {'default': webdriver, 'find_element_agent': agent}
    - MultiActionExecutor with callable or callable_mapping

    This allows ActionGraph to remain generic (executor-agnostic) while WebAgent's
    concrete layer handles the extraction.

    Args:
        webdriver_or_executor: The webdriver or action_executor passed by ActionGraph

    Returns:
        The actual webdriver instance
    """
    # Try lazy import of MultiActionExecutor for isinstance check
    try:
        from agent_foundation.automation.schema.action_executor import MultiActionExecutor
        has_multi_executor = True
    except ImportError:
        has_multi_executor = False

    # Case 1: MultiActionExecutor wrapper
    if has_multi_executor and isinstance(webdriver_or_executor, MultiActionExecutor):
        # Try callable first (single executor mode)
        if webdriver_or_executor.callable is not None:
            return webdriver_or_executor.callable
        # Then try callable_mapping with 'default' key
        if webdriver_or_executor.callable_mapping is not None:
            default_executor = webdriver_or_executor.callable_mapping.get('default')
            if default_executor is not None:
                return default_executor
        # Fall through to return original (will fail protocol check with helpful error)

    # Case 2: Dict-like mapping
    if isinstance(webdriver_or_executor, Mapping):
        default_executor = webdriver_or_executor.get('default')
        if default_executor is not None:
            return default_executor
        # Fall through to return original

    # Case 3: Direct webdriver instance (or unknown type - will fail protocol check)
    return webdriver_or_executor


def create_monitor_callbacks(
    webdriver: MonitorCapableDriver,
    target: 'Union[TargetSpec, TargetSpecWithFallback]',
    condition: MonitorCondition,
    interval: float = 0.5,
    continuous: bool = False,
    enable_auto_setup: bool = True,
    action_executor: Optional[Any] = None,
    html_context_provider: Optional[Callable[[], str]] = None,
) -> Tuple[Callable[..., 'Union[MonitorResult, NextNodesSelector]'], Callable[[], None], Callable[[], bool]]:
    """
    Unified factory function that creates an element monitoring callable.

    This is the primary API for creating monitors. It monitors an element on the
    CURRENT tab (no new tab is created). Use `visit_url` action first if you need
    to navigate to a different page.

    Returns a tuple of (iteration, setup_action, verify_setup):
    - iteration: Callable that performs one check, returns MonitorResult
    - setup_action: Callable that switches to the monitored tab (auto setup)
    - verify_setup: Callable that returns True if on correct tab (verification)

    The iteration callable:
    - Resolves the target element using webdriver.resolve_action_target
    - For TargetSpecWithFallback, tries strategies in order on first iteration
      and locks to the first successful strategy for subsequent iterations
    - Checks the condition each iteration
    - Handles debounce via condition.event_confirmation_time
    - Returns MonitorResult (or NextNodesSelector if continuous=True)

    This is the concrete implementation passed to MonitorNode.iteration.

    Continuous Monitoring Mode (continuous=True):
        When enabled, returns NextNodesSelector instead of plain MonitorResult when
        condition is met. This enables interleaved execution where:
        1. Monitor detects condition met
        2. Downstream actions execute
        3. Monitor re-runs to check condition again
        4. Loop continues until monitor returns plain result

        Requires a self-edge on the monitor node (monitor.add_next(monitor)) for the
        loop to work. ActionGraph.action("monitor", continuous=True) handles this.

    Auto Setup (setup_action):
        The returned setup_action callable switches to the monitored tab before
        condition checking. This is needed in continuous monitoring where downstream
        actions may execute in different tabs.

        Pass to MonitorNode.setup_action. Control via enable_auto_setup:
        - enable_auto_setup=True (default): Auto-switch to monitored tab
        - enable_auto_setup=False: Skip auto-switch (for demos/manual control)

    Verify Setup (verify_setup):
        The returned verify_setup callable checks if we're on the correct tab.
        Returns True if on monitored tab, False otherwise.

        Pass to MonitorNode.verify_setup. Control via enable_verify_setup:
        - enable_verify_setup=True (default): Verify before checking condition
        - enable_verify_setup=False: Skip verification

        When verify_setup returns False, the monitor iteration returns "not met"
        immediately, effectively pausing until the user switches to the correct tab.

    Args:
        webdriver: WebDriver wrapper instance that implements MonitorCapableDriver protocol.
                   Must have resolve_action_target, register_monitor_tab, unregister_monitor_tab,
                   current_window_handle, and find_element methods.
        target: TargetSpec or TargetSpecWithFallback for the element to monitor.
                For TargetSpecWithFallback, strategies are tried in order on first
                iteration, and the first successful one is used for all subsequent checks.
        condition: MonitorCondition specifying what to watch for
        interval: Seconds to wait between checks (default 0.5)
        continuous: If True, returns NextNodesSelector when condition is met,
                    enabling continuous monitoring loop. Default False.

                    Note: When continuous=True, enable_auto_setup must also be True.
                    This is because neither Selenium nor Playwright can detect manual
                    tab switches by the user. The monitor must programmatically switch
                    back to the monitored tab after downstream actions complete.
        enable_auto_setup: Whether MonitorNode will use auto-setup to switch tabs.
                    Should match the value passed to MonitorNode.enable_auto_setup.
                    Default True.

                    Note: For continuous monitoring (continuous=True), this must be True.
                    Manual tab switching detection is not supported by browser automation
                    APIs (neither Selenium nor Playwright can detect which tab the user
                    is viewing).
        action_executor: Optional executor (e.g., MultiActionExecutor) for resolving
                    agent-based targets. Required when target uses strategy='agent'.
                    The executor must have a 'find_element_agent' registered that can
                    resolve natural language element descriptions.
        html_context_provider: Optional callable that returns the current HTML context.
                    Required for agent-based targets with options=['static'] to enable
                    xpath caching. If not provided, agent resolution runs every iteration.
                    Typically: lambda: webdriver.page_source

    Returns:
        Tuple of (iteration, setup_action, verify_setup):
        - iteration: Callable that performs one monitor iteration
        - setup_action: Callable that switches to monitored tab (auto setup)
        - verify_setup: Callable that returns True if on monitored tab

    Raises:
        TypeError: If webdriver does not implement MonitorCapableDriver protocol

    Example:
        >>> from webaxon.automation.web_driver import WebDriver
        >>> from webaxon.automation.monitor import (
        ...     MonitorCondition, MonitorConditionType, create_monitor
        ... )
        >>> from agent_foundation.automation.schema import MonitorNode, TargetSpec
        >>>
        >>> webdriver = WebDriver()
        >>> # For input/textarea elements, use VALUE_CHANGED (monitors get_attribute("value"))
        >>> # For regular elements like div/span, use TEXT_CHANGED (monitors element.text)
        >>> condition = MonitorCondition(
        ...     condition_type=MonitorConditionType.VALUE_CHANGED,
        ...     event_confirmation_time=5.0  # Debounce: wait 5s to confirm stable
        ... )
        >>>
        >>> iteration = create_monitor(
        ...     webdriver=webdriver,
        ...     target=TargetSpec(strategy="xpath", value="//textarea[@title='Search']"),
        ...     condition=condition,
        ...     interval=0.5
        ... )
        >>>
        >>> # Use with MonitorNode
        >>> monitor_node = MonitorNode(
        ...     name="element_monitor",
        ...     iteration=iteration,
        ...     max_repeat=100,
        ... )
    """
    # Validate: continuous monitoring requires auto-setup
    # Manual tab switching detection is not supported by browser automation APIs
    if continuous and not enable_auto_setup:
        raise ValueError(
            "continuous=True requires enable_auto_setup=True. "
            "Manual tab switch detection is not supported by browser automation APIs "
            "(neither Selenium nor Playwright can detect which tab the user is viewing). "
            "The monitor must programmatically switch back to the monitored tab after "
            "downstream actions complete."
        )

    # Import here to avoid circular imports at module level
    from agent_foundation.automation.schema.common import TargetSpec, TargetSpecWithFallback

    # Extract actual webdriver from action_executor formats (dict, MultiActionExecutor, etc.)
    # ActionGraph passes self.action_executor which may be a dict or wrapper, not the raw webdriver
    webdriver = _extract_webdriver(webdriver)

    # Validate webdriver implements MonitorCapableDriver protocol
    if not isinstance(webdriver, MonitorCapableDriver):
        raise TypeError(
            f"webdriver must implement MonitorCapableDriver protocol. "
            f"Use WebDriver wrapper from webaxon.automation.web_driver, not raw Selenium driver. "
            f"Missing methods: {_get_missing_protocol_methods(webdriver, MonitorCapableDriver)}"
        )

    # State captured in closure
    state = {
        'check_count': 0,
        'tab_handle': None,  # Track which tab we're monitoring
        'resolved_target': None,  # Locked TargetSpec after first successful resolution
    }

    def _resolve_agent_target(target_spec: 'TargetSpec') -> 'TargetSpec':
        """Resolve agent-based target to a concrete xpath target.
        
        Uses the find_element_agent to resolve natural language description
        to an element, then generates an xpath for subsequent iterations.
        
        Args:
            target_spec: TargetSpec with strategy='agent'
            
        Returns:
            TargetSpec with strategy='xpath' and resolved xpath value
            
        Raises:
            ValueError: If action_executor is not provided or find_element_agent not registered
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        if action_executor is None:
            raise ValueError(
                "action_executor is required for agent-based target resolution. "
                "Pass action_executor to create_monitor() when using strategy='agent'."
            )
        
        # Import Agent class for isinstance check
        from agent_foundation.agents.agent import Agent
        
        # Resolve find_element_agent from executor
        if hasattr(action_executor, 'resolve'):
            find_agent = action_executor.resolve('find_element_agent')
        else:
            raise ValueError(
                "action_executor must have a 'resolve' method (e.g., MultiActionExecutor). "
                f"Got: {type(action_executor)}"
            )
        
        if not isinstance(find_agent, Agent):
            raise ValueError(
                f"find_element_agent must be an Agent instance, got: {type(find_agent)}"
            )
        
        _logger.debug(f"[_resolve_agent_target] Calling find_element_agent with: {target_spec.value}")
        
        # Call agent with natural language description
        # Agent returns element reference (e.g., __id__ value)
        result = find_agent(
            user_input=target_spec.value,
            options=target_spec.options
        )
        
        # Agent output should be the element identifier (e.g., __id__ value)
        element_id = result.output if hasattr(result, 'output') else result
        _logger.debug(f"[_resolve_agent_target] Agent returned element_id: {element_id}")
        
        # Check if static caching is requested
        is_static = target_spec.options and 'static' in target_spec.options
        
        if is_static and html_context_provider is not None:
            # Generate xpath for caching
            try:
                from webaxon.html_utils.element_identification import elements_to_xpath, find_element_by_attribute

                html_context = html_context_provider()
                element = find_element_by_attribute(html_context, '__id__', element_id)

                if element is not None:
                    xpath = elements_to_xpath(element, html_context)
                    _logger.debug(f"[_resolve_agent_target] Generated xpath for static caching: {xpath}")
                    return TargetSpec(strategy='xpath', value=xpath)
            except Exception as e:
                _logger.warning(f"[_resolve_agent_target] Failed to generate xpath, falling back to __id__: {e}")
        
        # Fall back to __id__ strategy
        return TargetSpec(strategy='__id__', value=element_id)

    def set_tab_handle(new_value: str, caller: str) -> None:
        """Set tab_handle with logging to track all assignments."""
        import logging
        _logger = logging.getLogger(__name__)
        old_value = state['tab_handle']
        state['tab_handle'] = new_value
        _logger.debug(
            f"[set_tab_handle] ASSIGNMENT by '{caller}': "
            f"old='{old_value}' -> new='{new_value}'"
        )
        if old_value is not None and old_value != new_value:
            _logger.warning(
                f"[set_tab_handle] WARNING: tab_handle CHANGED from '{old_value}' to '{new_value}'! "
                f"This may indicate a bug - monitored tab should not change."
            )

    def monitor_iteration(prev_result=None) -> NextNodesSelector:
        """Execute one monitor iteration.

        Always returns NextNodesSelector to give the monitor explicit control
        over which downstream nodes run. This applies to both continuous and
        standard modes.
        """
        import logging
        _logger = logging.getLogger(__name__)
        _logger.debug(f"[monitor_iteration] Starting iteration {state['check_count'] + 1}, continuous={continuous}")
        _logger.debug(f"[monitor_iteration] Current state: tab_handle='{state['tab_handle']}', check_count={state['check_count']}")

        try:
            # First call: register current tab as monitored
            if state['tab_handle'] is None:
                set_tab_handle(webdriver.current_window_handle(), "monitor_iteration:first_call")
                webdriver.register_monitor_tab(state['tab_handle'])
                _logger.debug(f"[monitor_iteration] Registered tab: {state['tab_handle']}")

            # NOTE: Setup action (e.g., switch to monitored tab) is now handled by
            # MonitorNode.setup_action, not here. This keeps iteration pure.

            # Resolve target element
            element = None
            if state['resolved_target'] is not None:
                # Use previously locked target (already resolved from agent if applicable)
                try:
                    element = webdriver.resolve_action_target(
                        state['resolved_target'].strategy,
                        state['resolved_target'].value
                    )
                except Exception:
                    element = None
            elif isinstance(target, TargetSpecWithFallback):
                # First iteration with fallback: try strategies in order
                for spec in target.strategies:
                    try:
                        # Check if this spec uses agent strategy
                        spec_strategy = spec.strategy.value if hasattr(spec.strategy, 'value') else str(spec.strategy)
                        if spec_strategy == 'agent':
                            # Resolve agent target to concrete target
                            resolved_spec = _resolve_agent_target(spec)
                            element = webdriver.resolve_action_target(resolved_spec.strategy, resolved_spec.value)
                            if element is not None:
                                # Lock to resolved target for subsequent iterations
                                state['resolved_target'] = resolved_spec
                                break
                        else:
                            element = webdriver.resolve_action_target(spec.strategy, spec.value)
                            if element is not None:
                                # Lock to this strategy for subsequent iterations
                                state['resolved_target'] = spec
                                break
                    except Exception:
                        continue
            else:
                # Single TargetSpec - check if it uses agent strategy
                try:
                    target_strategy = target.strategy.value if hasattr(target.strategy, 'value') else str(target.strategy)
                    if target_strategy == 'agent':
                        # Resolve agent target to concrete target
                        resolved_spec = _resolve_agent_target(target)
                        element = webdriver.resolve_action_target(resolved_spec.strategy, resolved_spec.value)
                        state['resolved_target'] = resolved_spec  # Lock resolved target
                    else:
                        element = webdriver.resolve_action_target(target.strategy, target.value)
                        state['resolved_target'] = target  # Lock for consistency
                except Exception:
                    element = None

            # Check condition (webdriver implements find_element for condition.check)
            _logger.debug(f"[monitor_iteration] Checking condition, element={'found' if element else 'not found'}")
            met, content = condition.check(webdriver, element)
            state['check_count'] += 1
            _logger.debug(f"[monitor_iteration] Condition check #{state['check_count']}: met={met}, content={content}")

            if met:
                # NOTE: Do NOT unregister tab here on success.
                # The tab should remain registered so subsequent actions (e.g., visit_url)
                # can detect it's monitored and open in a new tab instead.
                # The tab handle is returned in metadata for callers to unregister later.
                result = MonitorResult(
                    success=True,
                    status=MonitorStatus.CONDITION_MET,
                    matched_content=content,
                    check_count=state['check_count'],
                    metadata={'tab_handle': state['tab_handle']}
                )

                # Always return NextNodesSelector for explicit downstream control
                # continuous=True: include_self=True (re-run monitor after downstream)
                # continuous=False: include_self=False (no re-run, just run downstream once)
                return NextNodesSelector(
                    include_self=continuous,
                    include_others=True,
                    result=result
                )

            # Note: Poll interval delay is now handled by MonitorNode._execute_iteration()

            result = MonitorResult(
                success=False,
                status=MonitorStatus.MAX_ITERATIONS,  # Will be updated if loop continues
                check_count=state['check_count']
            )

            # Always return NextNodesSelector for explicit downstream control
            # continuous=True: include_self=True (keep polling via self-edge)
            # continuous=False: include_self=False (internal repeat loop handles polling)
            # Both modes: include_others=False (don't run downstream until condition met)
            return NextNodesSelector(
                include_self=continuous,
                include_others=False,
                result=result
            )
        except Exception as e:
            # Unregister tab on error
            if state['tab_handle']:
                webdriver.unregister_monitor_tab(state['tab_handle'])
            result = MonitorResult(
                success=False,
                status=MonitorStatus.ERROR,
                check_count=state['check_count'],
                error_message=str(e)
            )
            # Error: don't run downstream, don't self-loop
            return NextNodesSelector(
                include_self=False,
                include_others=False,
                result=result
            )

    def setup_action() -> None:
        """Switch to the monitored tab before condition check.

        This is the default auto setup action for browser monitoring. It ensures
        the webdriver is on the correct tab before checking the condition.

        Should be passed to MonitorNode.setup_action parameter.
        """
        import logging
        _logger = logging.getLogger(__name__)
        _logger.debug(f"[setup_action] >>> CALLED - state id={id(state)}, tab_handle='{state['tab_handle']}'")

        if state['tab_handle'] is not None:
            current_tab = webdriver.current_window_handle()
            if current_tab != state['tab_handle']:
                _logger.debug(f"[setup_action] Switching from {current_tab} to monitored tab {state['tab_handle']}")
                webdriver.switch_to.window(state['tab_handle'])
                _logger.debug(f"[setup_action] Switch complete. Now on: {webdriver.current_window_handle()}")
            else:
                _logger.debug(f"[setup_action] Already on monitored tab {state['tab_handle']}, no switch needed")
        else:
            _logger.debug(f"[setup_action] tab_handle is None, nothing to switch to")

    def verify_setup() -> bool:
        """Verify we're on the correct monitored tab.

        Returns True if the current tab is the monitored tab, False otherwise.
        Used to prevent false positives when checking conditions on wrong tabs.

        Should be passed to MonitorNode.verify_setup parameter.
        """
        import logging
        _logger = logging.getLogger(__name__)
        _logger.debug(f"[verify_setup] >>> CALLED - state id={id(state)}, tab_handle='{state['tab_handle']}'")

        if state['tab_handle'] is None:
            # Tab not registered yet - first iteration, allow it
            _logger.debug(f"[verify_setup] tab_handle is None, returning True (first iteration)")
            return True

        current_tab = webdriver.current_window_handle()
        is_correct_tab = current_tab == state['tab_handle']
        _logger.debug(
            f"[verify_setup] current_tab={current_tab}, monitored_tab={state['tab_handle']}, "
            f"is_correct={is_correct_tab}"
        )
        return is_correct_tab

    return monitor_iteration, setup_action, verify_setup


def _get_missing_protocol_methods(obj: Any, protocol: type) -> list:
    """
    Get list of methods/properties missing from obj that are required by protocol.

    Args:
        obj: Object to check
        protocol: Protocol class to check against

    Returns:
        List of missing method/property names
    """
    missing = []
    for name in dir(protocol):
        if name.startswith('_'):
            continue
        if not hasattr(obj, name):
            missing.append(name)
    return missing


# Backward compatibility alias
create_monitor = create_monitor_callbacks
