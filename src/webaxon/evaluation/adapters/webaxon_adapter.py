"""WebAxon evaluation adapter — delegates to RegularAgentAdapter (default)
or MetaAgentAdapter (fallback).

This adapter bridges the agent-agnostic evaluation framework with WebAxon's
concrete agent infrastructure.  It wraps the underlying adapter to inject:

1. **start_url navigation** via ``agent.base_action``
2. **trajectory capture** by enabling ``WebDriver._capture_trajectory``
3. **max_num_loops** to limit agent LLM turns
4. **resource cleanup** (browser quit, queue deletion)

By default, ``RegularAgentAdapter`` is used — it follows the same code path
as a real user interacting with the CLI service.  Pass
``use_meta_adapter=True`` to fall back to the ``/meta`` command path.
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Optional

from webaxon.evaluation.protocol import EvalAgentAdapter, EvalResult
from .trajectory_capture import capture as capture_trajectory

logger = logging.getLogger(__name__)


class WebAxonAdapter:
    """EvalAgentAdapter implementation for WebAxon agents.

    Constructs the full WebAxon service stack (ServiceConfig, AgentFactory,
    AgentSessionManager, StorageBasedQueueService) and delegates agent
    execution to RegularAgentAdapter (default) or MetaAgentAdapter.
    """

    name = "webaxon"

    def __init__(
        self,
        testcase_root: str | Path,
        agent_type: str = "DefaultAgent",
        template_version: str = "",
        chrome_version: Optional[int] = None,
        headless: bool = False,
        agent_timeout: int = 300,
        knowledge_data_file: Optional[str] = None,
        stay_on_start_url: bool = True,
        use_meta_adapter: bool = False,
        save_screenshots_to_session: bool = True,
    ) -> None:
        self._testcase_root = Path(testcase_root)
        self._agent_type = agent_type
        self._template_version = template_version
        self._agent_timeout = agent_timeout
        self._stay_on_start_url = stay_on_start_url
        self._save_screenshots_to_session = save_screenshots_to_session

        # Temp dir for queue storage
        self._tmp_dir = tempfile.mkdtemp(prefix="webaxon_eval_")

        # Build ServiceConfig
        from webaxon.devsuite.web_agent_service_nextgen.core.config import (
            ServiceConfig,
        )

        self._config = ServiceConfig()
        self._config.debug_mode_service = True
        self._config.synchronous_agent = True
        self._config.default_agent_type = agent_type
        self._config.chrome_version = chrome_version
        if knowledge_data_file:
            self._config.knowledge_data_file = knowledge_data_file

        # Build queue service
        from rich_python_utils.service_utils.queue_service.storage_based_queue_service import (
            StorageBasedQueueService,
        )

        self._queue_service = StorageBasedQueueService(root_path=self._tmp_dir)

        # Build TemplateManager (mirrors WebAgentService._create_template_manager)
        from webaxon.devsuite.web_agent_service_nextgen.agents.template_manager import (
            TemplateManagerWrapper,
        )
        from rich_python_utils.string_utils.formatting.handlebars_format import (
            format_template as handlebars_template_format,
        )

        template_dir = self._testcase_root / self._config.template_dir
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
            config=self._config,
            testcase_root=self._testcase_root,
        )
        self._headless = headless

        # Build AgentSessionManager
        from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_manager import (
            AgentSessionManager,
        )

        # Service log dir is required by AgentSessionManager
        service_log_dir = (
            self._testcase_root / self._config.log_root_path
        )
        service_log_dir.mkdir(parents=True, exist_ok=True)

        self._session_manager = AgentSessionManager(
            config=self._config,
            queue_service=self._queue_service,
            service_log_dir=service_log_dir,
        )

        # Build agent adapter (RegularAgentAdapter by default, MetaAgentAdapter as fallback)
        if use_meta_adapter:
            from webaxon.devsuite.web_agent_service_nextgen.agents.meta_agent_adapter import (
                MetaAgentAdapter,
            )
            self._adapter = MetaAgentAdapter(
                agent_factory=self._agent_factory,
                session_manager=self._session_manager,
                queue_service=self._queue_service,
                config=self._config,
            )
        else:
            from webaxon.devsuite.web_agent_service_nextgen.agents.regular_agent_adapter import (
                RegularAgentAdapter,
            )
            from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import (
                AgentRunner,
            )
            agent_runner = AgentRunner(config=self._config)
            self._adapter = RegularAgentAdapter(
                agent_factory=self._agent_factory,
                session_manager=self._session_manager,
                queue_service=self._queue_service,
                config=self._config,
                agent_runner=agent_runner,
            )
        self._adapter.agent_run_timeout = self._agent_timeout

        # Track last run's WebDriver, screenshot dir, and queue IDs for cleanup
        self._last_webdriver = None
        self._last_screenshot_dir: Optional[Path] = None
        self._last_queue_ids: list[str] = []

    def run_task(
        self,
        goal: str,
        start_url: str,
        max_steps: int,
        trajectory_dir: Path,
    ) -> EvalResult:
        """Run a single evaluation task through the WebAxon agent."""
        trajectory_dir = Path(trajectory_dir)
        trajectory_dir.mkdir(parents=True, exist_ok=True)

        # Prepend start_url constraint if configured
        task_message = goal
        if self._stay_on_start_url and start_url:
            task_message = (
                f"[CONSTRAINT: Start at {start_url}. "
                "Use ONLY this page and pages you can reach from it (same site "
                "or linked pages). Do NOT open search engines (Google, DuckDuckGo, "
                "Bing, etc.).]\n\n" + goal
            )

        start_time = time.time()

        try:
            result = self._run_with_hooks(
                task_message=task_message,
                start_url=start_url,
                max_steps=max_steps,
                trajectory_dir=trajectory_dir,
            )
        except Exception as exc:
            logger.error("WebAxon run_task failed: %s", exc, exc_info=True)
            return EvalResult(
                answer=f"Error: {exc}",
                confidence=0.0,
                action_history=[],
                action_history_readable=[],
                thoughts=[f"Error: {exc}"],
                raw_generations=[],
                screenshot_paths=[],
                duration_seconds=time.time() - start_time,
                error=str(exc),
            )
        finally:
            # Capture screenshot_dir before cleanup resets it
            actual_screenshot_dir = self._last_screenshot_dir or trajectory_dir
            self._cleanup_run_resources()

        # Post-process: extract trajectory from session logs + screenshots
        session_dir = result.session_dir if result else ""
        traj = capture_trajectory(
            session_dir=session_dir,
            trajectory_dir=actual_screenshot_dir,
        )

        duration = time.time() - start_time

        return EvalResult(
            answer=traj.answer,
            confidence=traj.confidence,
            action_history=traj.action_history,
            action_history_readable=traj.action_history_readable,
            thoughts=traj.thoughts,
            raw_generations=traj.raw_generations,
            screenshot_paths=traj.screenshots,
            duration_seconds=round(duration, 2),
            metadata={
                "session_dir": session_dir,
                "screenshot_dir": str(actual_screenshot_dir),
            },
        )

    def _run_with_hooks(
        self,
        task_message: str,
        start_url: str,
        max_steps: int,
        trajectory_dir: Path,
    ):
        """Run the underlying adapter with evaluation hooks.

        We monkey-patch the agent between creation and thread start by
        wrapping AgentFactory.create_agent to intercept the created agent.
        """
        original_create = self._agent_factory.create_agent

        captured_webdriver = None
        captured_screenshot_dir = None

        def patched_create_agent(interactive, logger, agent_type=None, template_version=""):
            agent = original_create(
                interactive=interactive,
                logger=logger,
                agent_type=agent_type or self._agent_type,
                template_version=template_version or self._template_version,
            )

            # Hook 1: Inject start_url as base_action
            if start_url:
                from webaxon.automation.web_agent_actors.common import (
                    _create_web_actor_visit_url_base_action,
                )
                agent.base_action = _create_web_actor_visit_url_base_action(start_url)

            # Hook 2: Set max_num_loops
            if max_steps > 0:
                agent.max_num_loops = max_steps

            # Hook 3: Enable trajectory capture on WebDriver
            nonlocal captured_webdriver, captured_screenshot_dir
            try:
                # planning_agent.actor = master_action_agent (direct callable)
                master_action_agent = agent.actor
                # master_action_agent.actor = MultiActionExecutor({'default': webdriver, ...})
                webdriver = master_action_agent.actor.resolve('default')

                # Determine screenshot destination: session_dir/screenshots/ (persistent)
                # or trajectory_dir (ephemeral, original behavior)
                screenshot_dest = trajectory_dir
                if self._save_screenshots_to_session and hasattr(logger, 'session_dir'):
                    session_screenshot_dir = logger.session_dir / "screenshots"
                    session_screenshot_dir.mkdir(parents=True, exist_ok=True)
                    screenshot_dest = session_screenshot_dir

                webdriver._capture_trajectory = True
                webdriver._trajectory_dir = str(screenshot_dest)
                webdriver._trajectory_step_counter = 0
                captured_webdriver = webdriver
                captured_screenshot_dir = screenshot_dest
                _logger = logging.getLogger(__name__)
                _logger.info("Trajectory capture enabled: %s", screenshot_dest)
            except Exception as exc:
                _logger = logging.getLogger(__name__)
                _logger.warning("Could not enable trajectory capture: %s", exc)

            return agent

        # Temporarily replace create_agent
        self._agent_factory.create_agent = patched_create_agent
        try:
            result = self._adapter.run(task_description=task_message)
        finally:
            self._agent_factory.create_agent = original_create

        self._last_webdriver = captured_webdriver
        self._last_screenshot_dir = Path(captured_screenshot_dir) if captured_screenshot_dir else None
        return result

    def _cleanup_run_resources(self) -> None:
        """Cleanup browser and queues from the last run."""
        # Quit browser explicitly (don't rely on GC)
        if self._last_webdriver is not None:
            try:
                self._last_webdriver.quit()
            except Exception as exc:
                logger.warning("WebDriver quit failed: %s", exc)
            self._last_webdriver = None
        self._last_screenshot_dir = None

    def cleanup(self) -> None:
        """Release all resources — called between tasks in dataset runs."""
        self._cleanup_run_resources()
