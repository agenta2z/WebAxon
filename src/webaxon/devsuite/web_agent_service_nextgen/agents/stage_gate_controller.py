"""Stage gate controller for the meta agent pipeline.

Manages the blocking/resuming lifecycle for ``/meta-debug`` stage-by-stage
execution.  Each :class:`StageGateController` instance is tied to a single
debug pipeline session and is used as the ``stage_hook`` callback for
:class:`MetaAgentPipeline`.

The controller sends ``run_meta_agent_debug_state`` messages to the CLI
after each stage completes, then blocks the pipeline thread until the user
issues the next ``/meta-debug`` command (or aborts).
"""

from __future__ import annotations

import logging
from enum import Enum
from threading import Event, Lock
from typing import Any, Dict, Optional

from rich_python_utils.datetime_utils.common import timestamp

from agent_foundation.automation.meta_agent.errors import PipelineAborted

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """The 4 pipeline stage groups."""

    COLLECT = "COLLECT"
    EVALUATE = "EVALUATE"
    SYNTHESIZE = "SYNTHESIZE"
    VALIDATE = "VALIDATE"


# Ordered sequence of expected stages.
_STAGE_SEQUENCE = [
    PipelineStage.COLLECT,
    PipelineStage.EVALUATE,
    PipelineStage.SYNTHESIZE,
    PipelineStage.VALIDATE,
]

# Map pipeline stage_hook names (noun forms) to PipelineStage.
_HOOK_NAME_TO_STAGE = {
    "collection": PipelineStage.COLLECT,
    "evaluation": PipelineStage.EVALUATE,
    "synthesis": PipelineStage.SYNTHESIZE,
    "validation": PipelineStage.VALIDATE,
}

# Map CLI subcommand names to PipelineStage.
_COMMAND_TO_STAGE = {
    "collect": PipelineStage.COLLECT,
    "evaluate": PipelineStage.EVALUATE,
    "synthesize": PipelineStage.SYNTHESIZE,
    "validate": PipelineStage.VALIDATE,
}


class StageGateController:
    """Controls the stage-by-stage gating for a single meta-agent pipeline run.

    Used as the ``stage_hook`` callback for :class:`MetaAgentPipeline`.
    After each stage group completes, the controller sends a state message
    to the CLI and blocks the pipeline thread until the user resumes or
    aborts.

    Parameters
    ----------
    session_id:
        The debug session identifier (e.g. ``meta_debug_20260225_143000``).
    query:
        The original user query.
    queue_service:
        The service's queue service for sending messages.
    config:
        The service config (provides ``client_control_queue_id``).
    output_dir:
        The pipeline session directory (for checkpoint paths in messages).
    wait_timeout:
        Maximum seconds to wait for a resume/abort before auto-aborting.
    """

    def __init__(
        self,
        session_id: str,
        query: str,
        queue_service: Any,
        config: Any,
        output_dir: Any,
        wait_timeout: float = 30 * 60,
    ) -> None:
        self.session_id = session_id
        self.query = query
        self._queue_service = queue_service
        self._config = config
        self._output_dir = output_dir
        self.wait_timeout = wait_timeout
        self._continue_event = Event()
        self._lock = Lock()
        self._aborted = False
        self.completed_state: Optional[PipelineStage] = None
        self.pipeline_done = False

    @property
    def next_expected_command(self) -> Optional[str]:
        """Return the next expected CLI subcommand, or None if done."""
        if self.completed_state is None:
            return None  # collect is auto-started, not resumed
        idx = _STAGE_SEQUENCE.index(self.completed_state)
        if idx + 1 < len(_STAGE_SEQUENCE):
            return _STAGE_SEQUENCE[idx + 1].value.lower()
        return None  # all stages done

    def stage_hook(self, stage_name: str, data: dict) -> None:
        """Called by pipeline after each stage group.

        Sends a state message to the CLI, then blocks the pipeline thread
        until :meth:`resume` or :meth:`abort` is called.  The last stage
        (VALIDATE) does NOT block — the pipeline should complete and send
        ``run_meta_agent_response``.

        Note: Checkpoint saving is handled by the pipeline's
        ``_save_stage_checkpoint()`` BEFORE this hook is called.
        """
        state = _HOOK_NAME_TO_STAGE.get(stage_name)
        if state is None:
            return

        self.completed_state = state
        self._send_state_message(state, data)

        # Don't block on the last stage — the pipeline should complete
        # and send run_meta_agent_response.  The CLI polls for both
        # debug_state and final response in the same polling loop.
        if state == PipelineStage.VALIDATE:
            return

        # Block and wait for next command
        self._continue_event.clear()
        signaled = self._continue_event.wait(timeout=self.wait_timeout)
        if not signaled or self._aborted:
            raise PipelineAborted(stage_name)

    def resume(self) -> bool:
        """Resume the pipeline.

        Returns ``False`` if the pipeline already exited (TOCTOU-safe:
        checks ``pipeline_done`` under lock).
        """
        with self._lock:
            if self.pipeline_done:
                return False
            self._aborted = False
            self._continue_event.set()
            return True

    def abort(self) -> None:
        """Signal the pipeline to abort."""
        with self._lock:
            self._aborted = True
            self._continue_event.set()

    def _send_state_message(self, state: PipelineStage, data: dict) -> None:
        """Send a ``run_meta_agent_debug_state`` message to the CLI."""
        summary = self._build_summary(state, data)
        checkpoint_path = ""
        if self._output_dir is not None:
            stage_name = {
                PipelineStage.COLLECT: "collection",
                PipelineStage.EVALUATE: "evaluation",
                PipelineStage.SYNTHESIZE: "synthesis",
                PipelineStage.VALIDATE: "validation",
            }.get(state, "")
            if stage_name:
                checkpoint_path = str(
                    self._output_dir / f"stage_{stage_name}" / "checkpoint.json"
                )

        message = {
            "type": "run_meta_agent_debug_state",
            "session_id": self.session_id,
            "state": state.value,
            "next_command": self.next_expected_command,
            "summary": summary,
            "checkpoint_path": checkpoint_path,
            "timestamp": timestamp(),
        }
        self._queue_service.put(self._config.client_control_queue_id, message)

    @staticmethod
    def _build_summary(state: PipelineStage, data: dict) -> Dict[str, Any]:
        """Build a state-specific summary dict for the CLI."""
        if state == PipelineStage.COLLECT:
            return {"trace_count": data.get("trace_count", 0)}
        elif state == PipelineStage.EVALUATE:
            return {
                "passed_count": data.get("passed_count", 0),
                "total_count": data.get("total_count", 0),
            }
        elif state == PipelineStage.SYNTHESIZE:
            summary: Dict[str, Any] = {
                "has_graph": data.get("graph") is not None,
            }
            report = data.get("synthesis_report")
            if report is not None and hasattr(report, "to_dict"):
                summary["synthesis_report"] = report.to_dict()
            return summary
        elif state == PipelineStage.VALIDATE:
            vr = data.get("validation_results")
            if vr is None:
                return {"skipped": True}
            return {
                "all_passed": vr.all_passed,
                "success_rate": vr.success_rate,
                "result_count": len(vr.results),
            }
        return {}
