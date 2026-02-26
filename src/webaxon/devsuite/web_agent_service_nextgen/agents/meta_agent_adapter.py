"""Adapter bridging TraceCollector's agent.run() interface with the service's
AgentFactory + QueueInteractive pattern.

The meta agent pipeline's :class:`TraceCollector` calls
``agent.run(task_description, data)`` and expects the result to have a
``session_dir`` attribute.  This adapter wraps the service's agent creation
flow so each ``run()`` call:

1. Creates an isolated session with its own queues and log directory
2. Injects the task as the first user message
3. Runs the agent in a background thread while consuming its responses
4. Stops the agent once it completes a turn or asks for input
5. Returns the ``session_dir`` for trace extraction
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

from science_modeling_tools.ui.queue_interactive import QueueInteractive

logger = logging.getLogger(__name__)


@dataclass
class MetaAgentRunResult:
    """Result of a single meta-agent run.

    Compatible with ``TraceCollector._extract_session_dir()`` which
    checks ``getattr(result, 'session_dir', None)``.
    """

    session_dir: str


class MetaAgentAdapter:
    """Adapts AgentFactory to the ``agent.run(task, data)`` interface
    expected by :class:`TraceCollector`.

    Each call to :meth:`run` creates a completely isolated session with
    its own queues, agent instance, and log directory.  The agent is run
    in a background thread while the adapter consumes agent responses
    from the dedicated response queue.  Once the agent completes its
    turn (``TurnCompleted``) or asks for user input (``PendingInput``),
    the adapter injects an empty message to unblock the agent's input
    read and lets the thread exit.

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
    progress_callback:
        Optional callback ``(current_run, total_runs) -> None`` invoked
        after each agent run completes.
    agent_output_callback:
        Optional callback ``(current_run, response_dict) -> None`` invoked
        whenever the agent produces output (so the CLI can display it).
    """

    # Per-run timeout for waiting for agent output (seconds).
    # Override in tests to avoid long waits.
    agent_run_timeout: int = 300  # 5 minutes

    def __init__(
        self,
        agent_factory: Any,
        session_manager: Any,
        queue_service: Any,
        config: Any,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        agent_output_callback: Optional[Callable[[int, Dict], None]] = None,
        pipeline_dir: Optional[Path] = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._session_manager = session_manager
        self._queue_service = queue_service
        self._config = config
        self._progress_callback = progress_callback
        self._agent_output_callback = agent_output_callback
        self._pipeline_dir = pipeline_dir
        self._run_counter = 0

    def run(
        self,
        task_description: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> MetaAgentRunResult:
        """Execute a single agent run for the given task.

        Creates a fresh session, injects the task as user input,
        runs the agent in a background thread while consuming its
        response queue, and returns the session_dir.

        Parameters
        ----------
        task_description:
            The task for the agent to perform.
        data:
            Optional input data for the run.

        Returns
        -------
        MetaAgentRunResult
            Contains ``session_dir`` for trace extraction.
        """
        self._run_counter += 1
        ts = timestamp().replace(" ", "_").replace(":", "")
        session_id = f"meta_run{self._run_counter:03d}_{ts}"

        logger.info(
            "Meta agent run %d: creating session %s",
            self._run_counter,
            session_id,
        )

        # 1. Create session via session manager
        session_kwargs = {}
        if self._pipeline_dir:
            session_kwargs['base_log_dir'] = self._pipeline_dir / "stage_collection"

        session = self._session_manager.get_or_create(
            session_id=session_id,
            agent_type=self._config.default_agent_type
            if hasattr(self._config, "default_agent_type")
            else "DefaultAgent",
            **session_kwargs,
        )

        # 2. Create session-specific input queue
        input_queue_id = f"{self._config.input_queue_id}_{session_id}"
        self._queue_service.create_queue(input_queue_id)

        # 3. Create dedicated response queue (isolated from main RESPONSE_QUEUE_ID)
        response_queue_id = f"meta_response_{session_id}"
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

        # 9. Run agent in a background thread
        agent_thread = threading.Thread(
            target=self._run_agent_safely,
            args=(agent,),
            daemon=True,
        )
        agent_thread.start()

        # 10. Poll response queue for agent output, forward to CLI
        self._consume_agent_responses(
            response_queue_id, input_queue_id, session_id,
        )

        # 11. Wait for agent thread to finish
        agent_thread.join(timeout=5)

        # 12. Finalize session
        try:
            session.finalize("completed")
        except Exception:
            pass

        # 13. Extract session_dir
        session_dir = ""
        if session.session_logger is not None:
            session_dir = str(session.session_logger.session_dir)

        logger.info(
            "Meta agent run %d completed. session_dir=%s",
            self._run_counter,
            session_dir,
        )

        # 14. Fire progress callback
        if self._progress_callback:
            self._progress_callback(self._run_counter, -1)

        return MetaAgentRunResult(session_dir=session_dir)

    @staticmethod
    def _run_agent_safely(agent: Any) -> None:
        """Run agent() in a thread, catching all exceptions."""
        try:
            agent()
        except Exception as exc:
            logger.warning("Meta agent failed: %s", exc, exc_info=True)

    def _consume_agent_responses(
        self,
        response_queue_id: str,
        input_queue_id: str,
        session_id: str,
    ) -> None:
        """Poll the agent's response queue, forward outputs, and stop the agent.

        Reads messages from the agent's dedicated response queue.  Each
        message is forwarded to the CLI via ``agent_output_callback``.
        When the agent signals ``TurnCompleted`` or ``PendingInput``, we
        inject an empty message on the input queue to unblock the agent's
        ``get_user_input()`` call, allowing the agent thread to exit.
        """
        deadline = time.time() + self.agent_run_timeout

        while time.time() < deadline:
            resp = self._queue_service.get(response_queue_id, blocking=False)
            if resp is None or not isinstance(resp, dict):
                time.sleep(0.3)
                continue

            # Forward agent output to CLI
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
