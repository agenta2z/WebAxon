"""Browser tools wrapper for WebAxon sidecar.

This module provides a high-level interface to WebAxon's browser automation
capabilities, designed for integration with OpenClaw.

Architecture:
    The sidecar uses WebAxon's evaluation adapter pattern to interface with
    the agent infrastructure. For simple browser operations (navigate, snapshot,
    act), we use the WebDriver directly. For full agentic tasks, we use the
    RegularAgentAdapter.
"""

import asyncio
import base64
import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import WebAxonSidecarConfig, ensure_workspace

logger = logging.getLogger(__name__)


@dataclass
class BrowserState:
    """Current state of the browser."""

    url: str = ""
    title: str = ""
    html: str = ""
    element_refs: List[Dict[str, Any]] = field(default_factory=list)
    screenshot_base64: Optional[str] = None


@dataclass
class ActionResult:
    """Result of a browser action."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class BrowserTools:
    """
    High-level browser automation interface for OpenClaw integration.

    This class uses WebAxon's WebDriver for direct browser operations and
    the RegularAgentAdapter for full agentic task execution.
    """

    def __init__(self, config: WebAxonSidecarConfig):
        self.config = config
        self._webdriver = None
        self._adapter = None
        self._agent_factory = None
        self._session_manager = None
        self._queue_service = None
        self._tmp_dir = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize WebAxon components."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            try:
                await asyncio.to_thread(self._initialize_sync)
                self._initialized = True
                logger.info("WebAxon BrowserTools initialized successfully")

            except ImportError as e:
                logger.error(f"Failed to import WebAxon components: {e}")
                raise RuntimeError(
                    "WebAxon not installed. Please install webaxon package."
                ) from e
            except Exception as e:
                logger.error(f"Failed to initialize WebAxon: {e}")
                raise

    def _initialize_sync(self) -> None:
        """Synchronous initialization of WebAxon components."""
        # Ensure workspace exists
        workspace_path = Path(ensure_workspace(self.config.workspace))

        # Create temp dir for queue storage
        self._tmp_dir = tempfile.mkdtemp(prefix="webaxon_sidecar_")

        # Build ServiceConfig
        from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig

        service_config = ServiceConfig()
        service_config.debug_mode_service = self.config.debug_mode
        service_config.synchronous_agent = self.config.synchronous_agent
        service_config.default_agent_type = self.config.agent_type
        service_config.chrome_version = self.config.chrome_version

        # Build queue service
        from rich_python_utils.service_utils.queue_service.storage_based_queue_service import (
            StorageBasedQueueService,
        )

        self._queue_service = StorageBasedQueueService(root_path=self._tmp_dir)

        # Build TemplateManager
        from webaxon.devsuite.web_agent_service_nextgen.agents.template_manager import (
            TemplateManagerWrapper,
        )
        from rich_python_utils.string_utils.formatting.handlebars_format import (
            format_template as handlebars_template_format,
        )

        template_dir = workspace_path / service_config.template_dir
        template_wrapper = TemplateManagerWrapper(
            template_dir=template_dir,
            template_formatter=handlebars_template_format,
        )

        # Build AgentFactory
        from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import (
            AgentFactory,
        )

        self._agent_factory = AgentFactory(
            template_manager=template_wrapper.get_template_manager(),
            config=service_config,
            testcase_root=workspace_path,
        )

        # Build AgentSessionManager
        from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_manager import (
            AgentSessionManager,
        )

        service_log_dir = workspace_path / service_config.log_root_path
        service_log_dir.mkdir(parents=True, exist_ok=True)

        self._session_manager = AgentSessionManager(
            config=service_config,
            queue_service=self._queue_service,
            service_log_dir=service_log_dir,
        )

        # Build RegularAgentAdapter for agentic tasks
        from webaxon.devsuite.web_agent_service_nextgen.agents.regular_agent_adapter import (
            RegularAgentAdapter,
        )
        from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import (
            AgentRunner,
        )

        agent_runner = AgentRunner(config=service_config)
        self._adapter = RegularAgentAdapter(
            agent_factory=self._agent_factory,
            session_manager=self._session_manager,
            queue_service=self._queue_service,
            config=service_config,
            agent_runner=agent_runner,
        )
        self._adapter.agent_run_timeout = self.config.agent_timeout

        # Initialize WebDriver for direct browser operations
        self._init_webdriver(workspace_path)

        # Inject the sidecar's WebDriver into config so AgentFactory reuses it
        # instead of creating a new Selenium-based one
        if self._webdriver is not None:
            service_config.injected_webdriver = self._webdriver

        self._config = service_config
        self._workspace_path = workspace_path

    def _init_webdriver(self, workspace_path: Path) -> None:
        """Initialize the WebDriver for direct browser operations."""
        from webaxon.automation.web_driver import WebDriver

        backend_name = self.config.backend  # "playwright" or "selenium"

        if backend_name == "playwright":
            from webaxon.automation.backends import PlaywrightBackend

            backend = PlaywrightBackend()
            backend.initialize(
                browser_type="chromium",
                headless=self.config.headless,
            )
            self._webdriver = WebDriver(backend=backend)
        else:
            # Default to Selenium
            from webaxon.automation.backends.selenium.driver_factory import WebAutomationDrivers

            # Use regular Chrome (not UndetectedChrome) for Docker compatibility
            self._webdriver = WebDriver(
                driver_type=WebAutomationDrivers.Chrome,
                headless=self.config.headless,
            )

        logger.info(f"WebDriver ({backend_name}) initialized")

    async def shutdown(self) -> None:
        """Shutdown the browser and cleanup resources."""
        async with self._lock:
            try:
                if self._webdriver is not None:
                    await asyncio.to_thread(self._webdriver.quit)
                    self._webdriver = None
            except Exception as e:
                logger.warning(f"Error shutting down WebDriver: {e}")

            self._adapter = None
            self._agent_factory = None
            self._session_manager = None
            self._queue_service = None
            self._initialized = False
            logger.info("WebAxon BrowserTools shutdown complete")

    async def navigate(self, url: str) -> ActionResult:
        """
        Navigate to a URL.

        Args:
            url: The URL to navigate to.

        Returns:
            ActionResult with navigation outcome.
        """
        await self.initialize()

        try:
            await asyncio.to_thread(self._webdriver.get, url)
            state = await self.get_state()
            return ActionResult(
                success=True,
                message=f"Navigated to {url}",
                data={"url": state.url, "title": state.title},
            )
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return ActionResult(success=False, message=f"Navigation failed: {e}")

    async def get_state(self) -> BrowserState:
        """
        Get the current browser state including cleaned HTML.

        Returns:
            BrowserState with current page information.
        """
        await self.initialize()

        try:
            # Get page info from WebDriver (properties)
            url = self._webdriver.current_url
            title = self._webdriver.title

            # Get cleaned HTML with element refs
            html = await asyncio.to_thread(self._get_clean_html)
            element_refs = self._extract_element_refs(html)

            return BrowserState(
                url=url or "",
                title=title or "",
                html=html or "",
                element_refs=element_refs,
            )
        except Exception as e:
            logger.error(f"Failed to get browser state: {e}")
            return BrowserState()

    def _get_clean_html(self) -> str:
        """Get cleaned HTML from the current page."""
        from webaxon.html_utils.sanitization import clean_html

        # Get raw HTML from WebDriver
        raw_html = self._webdriver.page_source

        # Apply WebAxon's HTML cleaning pipeline
        cleaned = clean_html(raw_html)
        return cleaned

    async def get_snapshot(self, include_screenshot: bool = False) -> Dict[str, Any]:
        """
        Get a snapshot of the current page state.

        Args:
            include_screenshot: Whether to include a base64-encoded screenshot.

        Returns:
            Dict with page snapshot data.
        """
        state = await self.get_state()

        snapshot = {
            "url": state.url,
            "title": state.title,
            "html": state.html,
            "refs": state.element_refs,
        }

        if include_screenshot:
            screenshot = await self.take_screenshot()
            snapshot["screenshot"] = screenshot.data.get("base64") if screenshot.success else None

        return snapshot

    async def take_screenshot(self) -> ActionResult:
        """
        Take a screenshot of the current page.

        Returns:
            ActionResult with base64-encoded screenshot.
        """
        await self.initialize()

        try:
            import tempfile
            import os

            # Use a temp file to capture screenshot
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                screenshot_path = f.name

            await asyncio.to_thread(self._webdriver.capture_screenshot, screenshot_path)

            # Read and encode
            with open(screenshot_path, "rb") as f:
                screenshot_bytes = f.read()
            os.unlink(screenshot_path)

            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return ActionResult(
                success=True,
                message="Screenshot captured",
                data={"base64": screenshot_b64},
            )
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ActionResult(success=False, message=f"Screenshot failed: {e}")

    async def execute_action(
        self,
        kind: str,
        ref: Optional[str] = None,
        text: Optional[str] = None,
        direction: Optional[str] = None,
        **kwargs,
    ) -> ActionResult:
        """
        Execute a browser action.

        Args:
            kind: Action type (click, type, scroll, select, etc.)
            ref: Element reference (e.g., "e12" or "12")
            text: Text to type (for type action)
            direction: Scroll direction (for scroll action)
            **kwargs: Additional action parameters

        Returns:
            ActionResult with action outcome.
        """
        await self.initialize()

        try:
            # Parse element ref to get the element ID
            element_id = self._parse_element_ref(ref) if ref else None

            # Resolve element by __id__ attribute if provided
            element = None
            if element_id:
                from webaxon.automation.schema import TargetStrategy
                element = self._webdriver.resolve_action_target(
                    TargetStrategy.FRAMEWORK_ID, element_id
                )

            # Map action kind to WebDriver execute_single_action
            if kind == "click":
                await asyncio.to_thread(
                    self._webdriver.execute_single_action,
                    element=element,
                    action_type="click",
                )
                return ActionResult(success=True, message=f"Clicked element {ref}")

            elif kind == "type":
                if not text:
                    return ActionResult(success=False, message="No text provided for type action")
                await asyncio.to_thread(
                    self._webdriver.execute_single_action,
                    element=element,
                    action_type="input_text",
                    action_args={"text": text},
                )
                return ActionResult(success=True, message=f"Typed '{text}' into element {ref}")

            elif kind == "scroll":
                scroll_dir = direction or "Down"
                # For scroll, element can be None (scrolls viewport)
                await asyncio.to_thread(
                    self._webdriver.execute_single_action,
                    element=element,
                    action_type="scroll",
                    action_args={"direction": scroll_dir.capitalize()},
                )
                return ActionResult(success=True, message=f"Scrolled {scroll_dir}")

            elif kind == "select":
                value = kwargs.get("value")
                await asyncio.to_thread(
                    self._webdriver.execute_single_action,
                    element=element,
                    action_type="select_option",
                    action_args={"value": value},
                )
                return ActionResult(success=True, message=f"Selected '{value}' in element {ref}")

            elif kind == "hover":
                await asyncio.to_thread(
                    self._webdriver.execute_single_action,
                    element=element,
                    action_type="hover",
                )
                return ActionResult(success=True, message=f"Hovered over element {ref}")

            elif kind == "press":
                key = kwargs.get("key", "Enter")
                await asyncio.to_thread(
                    self._webdriver.execute_script,
                    f"document.dispatchEvent(new KeyboardEvent('keydown', {{'key': '{key}'}}));"
                )
                return ActionResult(success=True, message=f"Pressed key '{key}'")

            elif kind == "wait":
                duration = kwargs.get("duration", 1.0)
                await asyncio.sleep(duration)
                return ActionResult(success=True, message=f"Waited {duration} seconds")

            else:
                return ActionResult(success=False, message=f"Unknown action kind: {kind}")

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return ActionResult(success=False, message=f"Action failed: {e}")

    async def run_task(self, task: str, start_url: Optional[str] = None) -> ActionResult:
        """
        Run a full agentic task.

        This invokes WebAxon's planning agent to autonomously complete a task.

        Args:
            task: Natural language task description.
            start_url: Optional starting URL.

        Returns:
            ActionResult with task outcome.
        """
        await self.initialize()

        try:
            # Build task message with start_url constraint
            task_message = task
            if start_url:
                task_message = (
                    f"[CONSTRAINT: Start at {start_url}. "
                    "Use ONLY this page and pages you can reach from it.]\n\n" + task
                )

            # Inject start_url as base_action in the agent
            original_create = self._agent_factory.create_agent

            def patched_create_agent(interactive, logger, agent_type=None, template_version=""):
                agent = original_create(
                    interactive=interactive,
                    logger=logger,
                    agent_type=agent_type or self.config.agent_type,
                    template_version=template_version,
                )

                # Inject start_url as base_action
                if start_url:
                    from webaxon.automation.web_agent_actors.common import (
                        _create_web_actor_visit_url_base_action,
                    )
                    agent.base_action = _create_web_actor_visit_url_base_action(start_url)

                # Set max_num_loops
                if self.config.max_steps > 0:
                    agent.max_num_loops = self.config.max_steps

                return agent

            # Capture agent outputs via callback
            agent_responses = []

            def capture_output(run_num, resp_dict):
                import sys
                print(f"[webaxon-capture] Agent output #{len(agent_responses)}: keys={list(resp_dict.keys()) if isinstance(resp_dict, dict) else type(resp_dict)}", file=sys.stderr, flush=True)
                print(f"[webaxon-capture] Full response: {resp_dict}", file=sys.stderr, flush=True)
                agent_responses.append(resp_dict)

            self._adapter._agent_output_callback = capture_output
            # Ensure timeout is sufficient for long-running tasks
            self._adapter.agent_run_timeout = max(self._adapter.agent_run_timeout, 1800)

            # Run with patched agent factory
            self._agent_factory.create_agent = patched_create_agent
            try:
                result = await asyncio.to_thread(
                    self._adapter.run, task_description=task_message
                )
            finally:
                self._agent_factory.create_agent = original_create

            # Extract the agent's final response content
            # Strategy: check captured responses first, then drain remaining queue items
            final_response = ""

            # Also drain any remaining responses from the queue
            if self._queue_service and hasattr(self._config, 'response_queue_id'):
                for _ in range(100):  # safety limit
                    leftover = self._queue_service.get(self._config.response_queue_id, blocking=False)
                    if leftover is None:
                        break
                    if isinstance(leftover, dict):
                        agent_responses.append(leftover)

            # Find the best response — last non-trivial 'response' value
            for resp in reversed(agent_responses):
                content = resp.get("response", "") or resp.get("answer", "") or resp.get("content", "") or resp.get("message", "")
                # Handle list responses (agent may send [reasoning, answer])
                if isinstance(content, list):
                    content = " ".join(str(c) for c in content if c)
                if content and isinstance(content, str) and len(content) > 20:
                    final_response = content
                    break

            # Parse result
            import sys
            print(f"[webaxon-capture] Total captured responses: {len(agent_responses)}", file=sys.stderr, flush=True)
            print(f"[webaxon-capture] Final response length: {len(final_response)}", file=sys.stderr, flush=True)
            if agent_responses:
                for i, r in enumerate(agent_responses[-3:]):
                    resp_preview = str(r.get("response", ""))[:200]
                    print(f"[webaxon-capture] Response[-{len(agent_responses)-i}]: {resp_preview}", file=sys.stderr, flush=True)

            success = result is not None and hasattr(result, 'session_dir')
            message = final_response if final_response else ("Task completed" if success else "Task failed")

            return ActionResult(
                success=success,
                message=message,
                data={
                    "session_dir": str(result.session_dir) if hasattr(result, 'session_dir') else None,
                    "response_count": len(agent_responses),
                } if result else None,
            )
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return ActionResult(success=False, message=f"Task failed: {e}")

    def _extract_element_refs(self, html: str) -> List[Dict[str, Any]]:
        """
        Extract element references from cleaned HTML.

        WebAxon adds __id__ attributes to interactive elements.
        This extracts them for use in action targeting.
        """
        refs = []
        # Pattern to match elements with __id__ attribute
        pattern = r'<(\w+)[^>]*\s__id__="(\d+)"[^>]*>(.*?)</\1>'

        for match in re.finditer(pattern, html, re.DOTALL):
            tag, element_id, content = match.groups()
            refs.append({
                "ref": f"e{element_id}",
                "tag": tag,
                "id": element_id,
                "text": content.strip()[:100] if content else "",
            })

        return refs

    def _parse_element_ref(self, ref: str) -> str:
        """
        Parse element reference to get the numeric ID.

        Handles formats like "e12", "12", "@e12"
        """
        if ref is None:
            return None

        # Remove common prefixes
        ref = ref.lstrip("@e")
        ref = ref.lstrip("e")

        return ref

    @property
    def is_initialized(self) -> bool:
        """Check if the browser tools are initialized."""
        return self._initialized

    @property
    def backend_type(self) -> str:
        """Get the current backend type."""
        return self.config.backend
