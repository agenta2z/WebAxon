"""Adapter that runs agents through the regular service flow.

Unlike :class:`MetaAgentAdapter` (which is designed for the ``/meta`` CLI
command and uses dedicated response queues), this adapter mirrors the
standard user-message path:

1. Creates an isolated session with its own input queue
2. Uses the **shared** response queue (``config.response_queue_id``)
3. Delegates thread management to :class:`AgentRunner` (the canonical path)
4. Filters responses by ``session_id`` on the shared queue

This is the recommended adapter for evaluation runs — it exercises the
same code path as a real user interacting with the service.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from rich_python_utils.datetime_utils.common import timestamp

from agent_foundation.ui.queue_interactive import QueueInteractive

from .agent_runner import AgentRunner

logger = logging.getLogger(__name__)


@dataclass
class RegularAgentRunResult:
    """Result of a single regular agent run.

    Compatible with ``TraceCollector._extract_session_dir()`` which
    checks ``getattr(result, 'session_dir', None)``.
    """

    session_dir: str


class RegularAgentAdapter:
    """Runs agents through the regular service flow.

    Each call to :meth:`run` creates a session with its own input queue
    but writes responses to the shared ``agent_response`` queue.  The
    agent thread is managed by :class:`AgentRunner`, which handles
    session finalization, error reporting, and sync/async execution.

    Parameters
    ----------
    agent_factory:
        The service's AgentFactory instance.
    session_manager:
        The service's AgentSessionManager instance.
    queue_service:
        The service's StorageBasedQueueService instance.
    config:
        The service's ServiceConfig instance.
    agent_runner:
        AgentRunner for canonical thread management.
    progress_callback:
        Optional ``(current_run, total_runs) -> None`` after each run.
    agent_output_callback:
        Optional ``(current_run, response_dict) -> None`` for agent output.
    """

    # Per-run timeout (seconds).  Override in tests.
    agent_run_timeout: int = 300

    def __init__(
        self,
        agent_factory: Any,
        session_manager: Any,
        queue_service: Any,
        config: Any,
        agent_runner: AgentRunner,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        agent_output_callback: Optional[Callable[[int, Dict], None]] = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._session_manager = session_manager
        self._queue_service = queue_service
        self._config = config
        self._agent_runner = agent_runner
        self._progress_callback = progress_callback
        self._agent_output_callback = agent_output_callback
        self._run_counter = 0

    def run(
        self,
        task_description: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> RegularAgentRunResult:
        """Execute a single agent run for the given task.

        Creates a fresh session, injects the task as user input,
        runs the agent via AgentRunner, and returns the session_dir.

        Parameters
        ----------
        task_description:
            The task for the agent to perform.
        data:
            Optional input data for the run.

        Returns
        -------
        RegularAgentRunResult
            Contains ``session_dir`` for trace extraction.
        """
        self._run_counter += 1
        ts = timestamp().replace(" ", "_").replace(":", "")
        session_id = f"eval_run{self._run_counter:03d}_{ts}"

        logger.info(
            "Regular agent run %d: creating session %s",
            self._run_counter,
            session_id,
        )

        # 1. Create session via session manager
        session = self._session_manager.get_or_create(
            session_id=session_id,
            agent_type=self._config.default_agent_type
            if hasattr(self._config, "default_agent_type")
            else "DefaultAgent",
        )

        # 2. Create session-specific input queue
        input_queue_id = f"{self._config.input_queue_id}_{session_id}"
        self._queue_service.create_queue(input_queue_id)

        # 3. Use shared response queue (regular flow)
        response_queue_id = self._config.response_queue_id
        self._queue_service.create_queue(response_queue_id)

        # 4. Create QueueInteractive
        interactive = QueueInteractive(
            input_queue=self._queue_service,
            response_queue=self._queue_service,
            input_queue_id=input_queue_id,
            response_queue_id=response_queue_id,
        )

        # 5. Create agent
        agent = self._agent_factory.create_agent(
            interactive=interactive,
            logger=session.session_logger,
            agent_type=session.info.session_type,
            template_version=session.info.template_version,
        )

        # 6. Update session with agent + interactive
        self._session_manager.update_session(
            session_id,
            agent=agent,
            interactive=interactive,
            initialized=True,
        )

        # 7. Ensure log directory exists
        if session.session_logger is not None:
            log_dir = session.session_logger.session_dir
            log_dir.mkdir(parents=True, exist_ok=True)

        # 8. Inject task as first user message
        user_message = task_description
        if data:
            user_message = f"{task_description}\n\nInput data: {json.dumps(data)}"

        self._queue_service.put(input_queue_id, {
            "user_input": user_message,
            "session_id": session_id,
            "timestamp": timestamp(),
        })

        # 9. Run agent in a background thread so we can poll responses
        #    concurrently.  We use AgentRunner.run_agent_in_thread as the
        #    thread target to get its session finalization and error handling.
        #    (Cannot use start_agent_thread directly because synchronous mode
        #    would block before we reach the response polling loop.)
        updated_session = self._session_manager.get(session_id)
        agent_thread = threading.Thread(
            target=self._agent_runner.run_agent_in_thread,
            args=(updated_session, self._queue_service),
            daemon=True,
            name=f"EvalAgent-{session_id}",
        )
        agent_thread.start()

        # 10. Poll shared response queue for agent output
        self._consume_agent_responses(
            response_queue_id, input_queue_id, session_id,
        )

        # 11. Wait for agent thread to finish
        agent_thread.join(timeout=5)

        # AgentRunner.run_agent_in_thread handles session.finalize().

        # 12. Extract session_dir
        session_dir = ""
        if session.session_logger is not None:
            session_dir = str(session.session_logger.session_dir)

        logger.info(
            "Regular agent run %d completed. session_dir=%s",
            self._run_counter,
            session_dir,
        )

        # 13. Fire progress callback
        if self._progress_callback:
            self._progress_callback(self._run_counter, -1)

        return RegularAgentRunResult(session_dir=session_dir)

    def _consume_agent_responses(
        self,
        response_queue_id: str,
        input_queue_id: str,
        session_id: str,
    ) -> None:
        """Poll the shared response queue, filtering by session_id.

        Since the regular flow uses the shared ``agent_response`` queue,
        we must filter responses by ``session_id`` to avoid consuming
        messages intended for other sessions.
        """
        deadline = time.time() + self.agent_run_timeout

        while time.time() < deadline:
            resp = self._queue_service.get(response_queue_id, blocking=False)
            if resp is None or not isinstance(resp, dict):
                time.sleep(0.3)
                continue

            # Filter by session_id (shared queue may have other sessions)
            resp_session = resp.get("session_id", "")
            if resp_session and resp_session != session_id:
                continue

            # Forward agent output to callback
            if self._agent_output_callback:
                self._agent_output_callback(self._run_counter, resp)

            # Check interaction flag
            flag = resp.get("flag", "")
            if hasattr(flag, "value"):
                flag = flag.value

            status = resp.get("status", "")

            if flag in ("TurnCompleted", "PendingInput") or status in (
                "completed",
                "error",
            ):
                break

        # Inject empty message to unblock agent's get_user_input()
        self._queue_service.put(input_queue_id, {
            "user_input": "",
            "session_id": session_id,
            "timestamp": timestamp(),
        })
