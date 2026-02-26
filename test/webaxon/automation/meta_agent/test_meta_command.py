"""Tests for the /meta command integration: adapter, handler, CLI, and serialization."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from webaxon.devsuite.web_agent_service_nextgen.agents.meta_agent_adapter import (
    MetaAgentAdapter,
    MetaAgentRunResult,
)
from webaxon.devsuite.web_agent_service_nextgen.communication.message_handlers import (
    MessageHandlers,
    _serialize_pipeline_result,
)
from webaxon.devsuite.web_agent_service_nextgen.cli.client import CLIClient


# ---------------------------------------------------------------------------
# MetaAgentAdapter tests
# ---------------------------------------------------------------------------


class TestMetaAgentAdapter:
    """Tests for the MetaAgentAdapter bridging TraceCollector with service agents."""

    @staticmethod
    def _make_adapter(
        agent_factory=None,
        session_manager=None,
        queue_service=None,
        config=None,
        progress_callback=None,
        agent_output_callback=None,
    ):
        if agent_factory is None:
            agent_factory = MagicMock()
        if session_manager is None:
            session_manager = MagicMock()
            session = MagicMock()
            session.session_logger.session_dir = Path("/tmp/sessions/meta_1")
            session.info.session_type = "DefaultAgent"
            session.info.template_version = ""
            session_manager.get_or_create.return_value = session
        if queue_service is None:
            queue_service = MagicMock()
            # The adapter polls queue_service.get(response_queue_id, blocking=False)
            # in _consume_agent_responses. Default MagicMock returns fail
            # isinstance(resp, dict), causing a 300s spin. Return a proper
            # TurnCompleted dict for meta_response_* queues.
            _original_get = queue_service.get

            def _mock_get(queue_id, blocking=False):
                if isinstance(queue_id, str) and "meta_response" in queue_id:
                    return {"flag": "TurnCompleted", "response": "mock"}
                return _original_get(queue_id, blocking=blocking)

            queue_service.get = MagicMock(side_effect=_mock_get)
        if config is None:
            config = MagicMock()
            config.input_queue_id = "INPUT_QUEUE"
            config.default_agent_type = "DefaultAgent"
        adapter = MetaAgentAdapter(
            agent_factory=agent_factory,
            session_manager=session_manager,
            queue_service=queue_service,
            config=config,
            progress_callback=progress_callback,
            agent_output_callback=agent_output_callback,
        )
        # Safety net: keep tests fast even if mock has an edge case
        adapter.agent_run_timeout = 2
        return adapter

    def test_run_creates_session(self):
        adapter = self._make_adapter()
        result = adapter.run("Navigate to login page")

        adapter._session_manager.get_or_create.assert_called_once()
        call_kwargs = adapter._session_manager.get_or_create.call_args
        assert "session_id" in call_kwargs.kwargs or len(call_kwargs.args) >= 1

    def test_run_creates_queues(self):
        adapter = self._make_adapter()
        adapter.run("Test task")

        # Should create both input and response queues
        create_calls = adapter._queue_service.create_queue.call_args_list
        assert len(create_calls) == 2
        queue_ids = [c.args[0] for c in create_calls]
        assert any("INPUT_QUEUE" in qid for qid in queue_ids)
        assert any("meta_response" in qid for qid in queue_ids)

    def test_run_injects_task_as_user_message(self):
        adapter = self._make_adapter()
        adapter.run("Find egg prices on safeway")

        put_calls = adapter._queue_service.put.call_args_list
        assert len(put_calls) >= 1
        # First put should be the task injection
        msg = put_calls[0].args[1]
        assert "Find egg prices on safeway" in msg["user_input"]

    def test_run_injects_data_in_message(self):
        adapter = self._make_adapter()
        adapter.run("Find prices", data={"url": "https://example.com"})

        put_calls = adapter._queue_service.put.call_args_list
        msg = put_calls[0].args[1]
        assert "https://example.com" in msg["user_input"]

    def test_run_calls_agent(self):
        agent_factory = MagicMock()
        mock_agent = MagicMock()
        agent_factory.create_agent.return_value = mock_agent

        adapter = self._make_adapter(agent_factory=agent_factory)
        adapter.run("Test task")

        mock_agent.assert_called_once()

    def test_run_returns_session_dir(self):
        adapter = self._make_adapter()
        result = adapter.run("Test task")

        assert isinstance(result, MetaAgentRunResult)
        assert result.session_dir == str(Path("/tmp/sessions/meta_1"))

    def test_run_finalizes_session(self):
        session = MagicMock()
        session.session_logger.session_dir = Path("/tmp/s1")
        session.info.session_type = "DefaultAgent"
        session.info.template_version = ""

        session_manager = MagicMock()
        session_manager.get_or_create.return_value = session

        adapter = self._make_adapter(session_manager=session_manager)
        adapter.run("Test task")

        session.finalize.assert_called_once_with("completed")

    def test_run_handles_agent_exception(self):
        agent_factory = MagicMock()
        mock_agent = MagicMock(side_effect=RuntimeError("Agent crash"))
        agent_factory.create_agent.return_value = mock_agent

        adapter = self._make_adapter(agent_factory=agent_factory)
        # Should not raise
        result = adapter.run("Test task")
        assert isinstance(result, MetaAgentRunResult)

    def test_progress_callback_fired(self):
        callback = MagicMock()
        adapter = self._make_adapter(progress_callback=callback)
        adapter.run("Test task")

        callback.assert_called_once()
        args = callback.call_args.args
        assert args[0] == 1  # first run

    def test_run_counter_increments(self):
        callback = MagicMock()
        adapter = self._make_adapter(progress_callback=callback)

        adapter.run("Task 1")
        adapter.run("Task 2")

        assert callback.call_count == 2
        assert callback.call_args_list[0].args[0] == 1
        assert callback.call_args_list[1].args[0] == 2

    def test_agent_output_callback_fired(self):
        output_cb = MagicMock()
        adapter = self._make_adapter(agent_output_callback=output_cb)
        adapter.run("Test task")

        output_cb.assert_called_once()
        args = output_cb.call_args.args
        assert args[0] == 1  # run counter
        assert args[1] == {"flag": "TurnCompleted", "response": "mock"}

    def test_empty_message_injected_to_unblock_agent(self):
        adapter = self._make_adapter()
        adapter.run("Test task")

        # Last put should be the empty unblock message on the input queue
        put_calls = adapter._queue_service.put.call_args_list
        last_put = put_calls[-1]
        queue_id = last_put.args[0]
        msg = last_put.args[1]
        assert "INPUT_QUEUE" in queue_id
        assert msg["user_input"] == ""

    def test_agent_runs_in_thread(self):
        adapter = self._make_adapter()

        with patch("threading.Thread") as MockThread:
            mock_thread = MagicMock()
            MockThread.return_value = mock_thread

            adapter.run("Test task")

            MockThread.assert_called_once()
            kwargs = MockThread.call_args.kwargs
            assert kwargs["daemon"] is True
            mock_thread.start.assert_called_once()


# ---------------------------------------------------------------------------
# MessageHandlers.handle_run_meta_agent tests
# ---------------------------------------------------------------------------


class TestHandleRunMetaAgent:
    """Tests for the handle_run_meta_agent message handler."""

    @staticmethod
    def _make_handlers():
        config = MagicMock()
        config.client_control_queue_id = "CLIENT_CONTROL"
        handlers = MessageHandlers(
            session_manager=MagicMock(),
            agent_factory=MagicMock(),
            queue_service=MagicMock(),
            config=config,
        )
        return handlers

    def test_missing_query_sends_error(self):
        handlers = self._make_handlers()
        handlers.handle_run_meta_agent({
            "message": {},
            "timestamp": "2025-01-01",
        })

        put_call = handlers._queue_service.put.call_args
        assert put_call.args[0] == "CLIENT_CONTROL"
        msg = put_call.args[1]
        assert msg["type"] == "run_meta_agent_response"
        assert msg["success"] is False
        assert "query" in msg["error"].lower()

    def test_sends_started_ack(self):
        handlers = self._make_handlers()

        with patch.object(threading.Thread, "start"):
            handlers.handle_run_meta_agent({
                "message": {"query": "Navigate to login"},
                "timestamp": "2025-01-01",
            })

        # First put should be the "started" ack
        first_put = handlers._queue_service.put.call_args_list[0]
        msg = first_put.args[1]
        assert msg["type"] == "run_meta_agent_started"
        assert msg["run_count"] == 5  # default

    def test_custom_run_count_in_started_ack(self):
        handlers = self._make_handlers()

        with patch.object(threading.Thread, "start"):
            handlers.handle_run_meta_agent({
                "message": {"query": "Test", "run_count": 10},
                "timestamp": "2025-01-01",
            })

        first_put = handlers._queue_service.put.call_args_list[0]
        assert first_put.args[1]["run_count"] == 10

    def test_spawns_daemon_thread(self):
        handlers = self._make_handlers()

        with patch("threading.Thread") as MockThread:
            mock_thread = MagicMock()
            MockThread.return_value = mock_thread

            handlers.handle_run_meta_agent({
                "message": {"query": "Navigate to login"},
                "timestamp": "2025-01-01",
            })

            MockThread.assert_called_once()
            kwargs = MockThread.call_args.kwargs
            assert kwargs["daemon"] is True
            assert kwargs["name"] == "MetaAgentPipeline"
            mock_thread.start.assert_called_once()

    def test_debug_mode_runs_synchronously(self):
        handlers = self._make_handlers()

        with patch.object(handlers, "_run_meta_agent_pipeline") as mock_run:
            handlers.handle_run_meta_agent({
                "message": {"query": "Test task", "debug": True},
                "timestamp": "2025-01-01",
            })

            # Should call pipeline directly, not via thread
            mock_run.assert_called_once()

    def test_debug_mode_does_not_spawn_thread(self):
        handlers = self._make_handlers()

        with (
            patch.object(handlers, "_run_meta_agent_pipeline"),
            patch("threading.Thread") as MockThread,
        ):
            handlers.handle_run_meta_agent({
                "message": {"query": "Test task", "debug": True},
                "timestamp": "2025-01-01",
            })

            MockThread.assert_not_called()

    def test_debug_flag_in_started_ack(self):
        handlers = self._make_handlers()

        with patch.object(handlers, "_run_meta_agent_pipeline"):
            handlers.handle_run_meta_agent({
                "message": {"query": "Test task", "debug": True},
                "timestamp": "2025-01-01",
            })

        first_put = handlers._queue_service.put.call_args_list[0]
        msg = first_put.args[1]
        assert msg["debug"] is True


# ---------------------------------------------------------------------------
# CLIClient /meta command tests
# ---------------------------------------------------------------------------


class TestRunMetaAgentCLI:
    """Tests for the CLIClient.run_meta_agent() method."""

    @staticmethod
    def _make_client(tmp_path):
        client = CLIClient(testcase_root=tmp_path)
        client._queue_service = MagicMock()
        client._session_id = "test_session"
        return client

    def test_sends_control_message(self, tmp_path):
        client = self._make_client(tmp_path)
        # Simulate: no started ack (timeout)
        client._queue_service.get.return_value = None

        client.run_meta_agent("Navigate to login", run_count=3)

        put_call = client._queue_service.put.call_args
        msg = put_call.args[1]
        assert msg["type"] == "run_meta_agent"
        assert msg["message"]["query"] == "Navigate to login"
        assert msg["message"]["run_count"] == 3
        assert msg["message"]["debug"] is False

    def test_sends_debug_flag(self, tmp_path):
        client = self._make_client(tmp_path)
        client._queue_service.get.return_value = None

        client.run_meta_agent("Test task", debug=True)

        put_call = client._queue_service.put.call_args
        msg = put_call.args[1]
        assert msg["message"]["debug"] is True

    def test_prints_timeout_when_no_ack(self, tmp_path, capsys):
        client = self._make_client(tmp_path)
        client._queue_service.get.return_value = None

        # Use tiny timeout so test doesn't block
        with patch.object(client, "_wait_for_control_response", return_value=None):
            client.run_meta_agent("Test query")

        captured = capsys.readouterr()
        assert "TIMEOUT" in captured.out

    def test_polls_until_completion(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        # Simulate ack
        ack_response = {"type": "run_meta_agent_started", "run_count": 3}

        # Simulate progress then completion
        responses = [
            {"type": "run_meta_agent_progress", "current_run": 1, "total_runs": 3},
            {"type": "run_meta_agent_progress", "current_run": 2, "total_runs": 3},
            {
                "type": "run_meta_agent_response",
                "success": True,
                "output_path": "/tmp/result.json",
                "summary": "3 traces collected",
            },
        ]
        response_iter = iter(responses)

        def mock_get(queue_id, blocking=False):
            try:
                return next(response_iter)
            except StopIteration:
                return None

        with (
            patch.object(
                client, "_wait_for_control_response", return_value=ack_response
            ),
            patch.object(client._queue_service, "get", side_effect=mock_get),
            patch("time.sleep"),
        ):
            client.run_meta_agent("Test query", run_count=3)

        captured = capsys.readouterr()
        assert "Progress: run 1/3" in captured.out
        assert "Progress: run 2/3" in captured.out
        assert "Completed successfully" in captured.out

    def test_handles_pipeline_failure(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        ack_response = {"type": "run_meta_agent_started", "run_count": 5}

        responses = [
            {
                "type": "run_meta_agent_response",
                "success": False,
                "error": "Agent timeout in collection",
            },
        ]
        response_iter = iter(responses)

        def mock_get(queue_id, blocking=False):
            try:
                return next(response_iter)
            except StopIteration:
                return None

        with (
            patch.object(
                client, "_wait_for_control_response", return_value=ack_response
            ),
            patch.object(client._queue_service, "get", side_effect=mock_get),
            patch("time.sleep"),
        ):
            client.run_meta_agent("Test query")

        captured = capsys.readouterr()
        assert "failed" in captured.out.lower()
        assert "Agent timeout" in captured.out

    def test_displays_agent_output(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        ack_response = {"type": "run_meta_agent_started", "run_count": 3}

        responses = [
            {
                "type": "run_meta_agent_agent_output",
                "current_run": 1,
                "total_runs": 3,
                "agent_response": "I cannot help with consumer pricing queries.",
                "flag": "PendingInput",
            },
            {
                "type": "run_meta_agent_progress",
                "current_run": 1,
                "total_runs": 3,
            },
            {
                "type": "run_meta_agent_response",
                "success": True,
                "output_path": "/tmp/result.json",
                "summary": "1 trace collected",
            },
        ]
        response_iter = iter(responses)

        def mock_get(queue_id, blocking=False):
            try:
                return next(response_iter)
            except StopIteration:
                return None

        with (
            patch.object(
                client, "_wait_for_control_response", return_value=ack_response
            ),
            patch.object(client._queue_service, "get", side_effect=mock_get),
            patch("time.sleep"),
        ):
            client.run_meta_agent("Test query", run_count=3)

        captured = capsys.readouterr()
        assert "cannot help with consumer pricing" in captured.out
        assert "Run 1/3" in captured.out
        assert "Completed successfully" in captured.out


# ---------------------------------------------------------------------------
# Serialization tests (moved from test_meta_agent_cli.py)
# ---------------------------------------------------------------------------


class TestSerializePipelineResult:
    """Tests for _serialize_pipeline_result helper."""

    def test_success_result(self):
        result = MagicMock()
        result.failed_stage = None
        result.error = None
        result.traces = [MagicMock(trace_id="t1"), MagicMock(trace_id="t2")]
        result.graph = MagicMock()
        result.graph.to_dict.return_value = {"nodes": []}
        result.synthesis_report = MagicMock()
        result.synthesis_report.to_dict.return_value = {"summary": "ok"}
        result.validation_results = None
        result.python_script = "print('hello')"
        result.evaluation_results = []

        data = _serialize_pipeline_result(result)

        assert data["success"] is True
        assert data["failed_stage"] is None
        assert data["trace_count"] == 2
        assert data["trace_ids"] == ["t1", "t2"]
        assert data["graph"] == {"nodes": []}
        assert data["python_script"] == "print('hello')"

    def test_failure_result(self):
        result = MagicMock()
        result.failed_stage = "collection"
        result.error = "Agent timeout"
        result.traces = []
        result.graph = None
        result.synthesis_report = None
        result.validation_results = None
        result.python_script = None
        result.evaluation_results = []

        data = _serialize_pipeline_result(result)

        assert data["success"] is False
        assert data["failed_stage"] == "collection"
        assert data["error"] == "Agent timeout"
        assert data["trace_count"] == 0

    def test_serializes_evaluation_results(self):
        result = MagicMock()
        result.failed_stage = None
        result.error = None
        result.traces = []
        result.graph = None
        result.synthesis_report = None
        result.validation_results = None
        result.python_script = None

        eval_result = MagicMock()
        eval_result.trace_id = "t1"
        eval_result.passed = True
        eval_result.reason = "all steps completed"
        result.evaluation_results = [eval_result]

        data = _serialize_pipeline_result(result)

        assert len(data["evaluation_results"]) == 1
        assert data["evaluation_results"][0]["trace_id"] == "t1"
        assert data["evaluation_results"][0]["passed"] is True

    def test_handles_graph_without_to_dict(self):
        result = MagicMock()
        result.failed_stage = None
        result.error = None
        result.traces = []
        result.graph = MagicMock()
        result.graph.to_dict.side_effect = AttributeError("no to_dict")
        result.synthesis_report = None
        result.validation_results = None
        result.python_script = None
        result.evaluation_results = []

        data = _serialize_pipeline_result(result)
        assert "graph" in data  # Falls back to str()


# ---------------------------------------------------------------------------
# StageGateController tests
# ---------------------------------------------------------------------------


class TestStageGateController:
    """Tests for the StageGateController stage-gating lifecycle."""

    @staticmethod
    def _make_controller(wait_timeout=0.5, output_dir=None):
        from webaxon.devsuite.web_agent_service_nextgen.agents.stage_gate_controller import (
            StageGateController,
        )

        queue_service = MagicMock()
        config = MagicMock()
        config.client_control_queue_id = "CLIENT_CONTROL"

        if output_dir is None:
            output_dir = Path("/tmp/meta_debug_test")

        return StageGateController(
            session_id="meta_debug_test_001",
            query="test query",
            queue_service=queue_service,
            config=config,
            output_dir=output_dir,
            wait_timeout=wait_timeout,
        )

    def test_stage_hook_sends_state_message(self):
        controller = self._make_controller()

        # Resume immediately in another thread so hook doesn't block
        def resume_soon():
            import time
            time.sleep(0.05)
            controller.resume()

        t = threading.Thread(target=resume_soon, daemon=True)
        t.start()

        controller.stage_hook("collection", {"trace_count": 5})

        t.join(timeout=2)

        # Verify message was sent
        controller._queue_service.put.assert_called_once()
        call_args = controller._queue_service.put.call_args
        assert call_args.args[0] == "CLIENT_CONTROL"
        msg = call_args.args[1]
        assert msg["type"] == "run_meta_agent_debug_state"
        assert msg["session_id"] == "meta_debug_test_001"
        assert msg["state"] == "COLLECT"
        assert msg["summary"] == {"trace_count": 5}

    def test_stage_hook_blocks_until_resume(self):
        controller = self._make_controller(wait_timeout=5)

        hook_returned = threading.Event()

        def run_hook():
            controller.stage_hook("collection", {"trace_count": 3})
            hook_returned.set()

        t = threading.Thread(target=run_hook, daemon=True)
        t.start()

        # Hook should NOT have returned yet
        assert not hook_returned.wait(timeout=0.1)

        # Resume → hook should return
        controller.resume()
        assert hook_returned.wait(timeout=2)

    def test_abort_raises_pipeline_aborted(self):
        from science_modeling_tools.automation.meta_agent.errors import PipelineAborted

        controller = self._make_controller(wait_timeout=5)

        exc_holder = []

        def run_hook():
            try:
                controller.stage_hook("evaluation", {"passed_count": 3, "total_count": 5})
            except PipelineAborted as e:
                exc_holder.append(e)

        # Need to complete collection first (so state is COLLECT)
        # The hook will block — we need to call stage_hook for "evaluation"
        # but evaluation requires collection to have completed.
        # StageGateController doesn't enforce ordering in stage_hook,
        # it only tracks completed_state. Let's just call evaluation directly.

        t = threading.Thread(target=run_hook, daemon=True)
        t.start()

        import time
        time.sleep(0.05)
        controller.abort()

        t.join(timeout=2)
        assert len(exc_holder) == 1
        assert "evaluation" in str(exc_holder[0])

    def test_timeout_raises_pipeline_aborted(self):
        from science_modeling_tools.automation.meta_agent.errors import PipelineAborted

        controller = self._make_controller(wait_timeout=0.1)

        with pytest.raises(PipelineAborted):
            controller.stage_hook("collection", {"trace_count": 0})

    def test_validate_does_not_block(self):
        controller = self._make_controller(wait_timeout=0.1)

        # VALIDATE should return immediately without blocking
        controller.stage_hook("validation", {"validation_results": None})

        # Should have returned without raising PipelineAborted
        assert controller.completed_state.value == "VALIDATE"

    def test_next_expected_command_sequence(self):
        from webaxon.devsuite.web_agent_service_nextgen.agents.stage_gate_controller import (
            PipelineStage,
        )

        controller = self._make_controller()

        # Before any stage: None (collect is auto-started)
        assert controller.next_expected_command is None

        controller.completed_state = PipelineStage.COLLECT
        assert controller.next_expected_command == "evaluate"

        controller.completed_state = PipelineStage.EVALUATE
        assert controller.next_expected_command == "synthesize"

        controller.completed_state = PipelineStage.SYNTHESIZE
        assert controller.next_expected_command == "validate"

        controller.completed_state = PipelineStage.VALIDATE
        assert controller.next_expected_command is None

    def test_resume_returns_false_when_pipeline_done(self):
        controller = self._make_controller()
        controller.pipeline_done = True

        assert controller.resume() is False

    def test_resume_returns_true_when_active(self):
        controller = self._make_controller()

        assert controller.resume() is True

    def test_build_summary_collect(self):
        from webaxon.devsuite.web_agent_service_nextgen.agents.stage_gate_controller import (
            PipelineStage,
            StageGateController,
        )

        summary = StageGateController._build_summary(
            PipelineStage.COLLECT, {"trace_count": 5}
        )
        assert summary == {"trace_count": 5}

    def test_build_summary_evaluate(self):
        from webaxon.devsuite.web_agent_service_nextgen.agents.stage_gate_controller import (
            PipelineStage,
            StageGateController,
        )

        summary = StageGateController._build_summary(
            PipelineStage.EVALUATE, {"passed_count": 3, "total_count": 5}
        )
        assert summary == {"passed_count": 3, "total_count": 5}

    def test_build_summary_validate_skipped(self):
        from webaxon.devsuite.web_agent_service_nextgen.agents.stage_gate_controller import (
            PipelineStage,
            StageGateController,
        )

        summary = StageGateController._build_summary(
            PipelineStage.VALIDATE, {"validation_results": None}
        )
        assert summary == {"skipped": True}

    def test_build_summary_validate_with_results(self):
        from webaxon.devsuite.web_agent_service_nextgen.agents.stage_gate_controller import (
            PipelineStage,
            StageGateController,
        )

        vr = MagicMock()
        vr.all_passed = True
        vr.success_rate = 1.0
        vr.results = [MagicMock(), MagicMock()]

        summary = StageGateController._build_summary(
            PipelineStage.VALIDATE, {"validation_results": vr}
        )
        assert summary == {"all_passed": True, "success_rate": 1.0, "result_count": 2}

    def test_checkpoint_path_in_state_message(self):
        controller = self._make_controller(output_dir=Path("/tmp/pipeline_dir"))

        # VALIDATE doesn't block, so use it to test message content
        controller.stage_hook("validation", {"validation_results": None})

        msg = controller._queue_service.put.call_args.args[1]
        assert "stage_validation" in msg["checkpoint_path"]
        assert msg["checkpoint_path"].endswith("checkpoint.json")

    def test_unknown_stage_is_ignored(self):
        controller = self._make_controller()
        # Should not raise or send messages
        controller.stage_hook("unknown_stage", {})

        controller._queue_service.put.assert_not_called()
        assert controller.completed_state is None


# ---------------------------------------------------------------------------
# Meta debug command handler tests
# ---------------------------------------------------------------------------


class TestMetaDebugCommand:
    """Tests for handle_meta_debug_command and related handlers in MessageHandlers."""

    @staticmethod
    def _make_handlers():
        config = MagicMock()
        config.client_control_queue_id = "CLIENT_CONTROL"
        handlers = MessageHandlers(
            session_manager=MagicMock(),
            agent_factory=MagicMock(),
            queue_service=MagicMock(),
            config=config,
        )
        return handlers

    def test_unknown_command_sends_error(self):
        handlers = self._make_handlers()
        handlers.handle_meta_debug_command({
            "message": {"command": "foobar"},
        })

        msg = handlers._queue_service.put.call_args.args[1]
        assert msg["type"] == "meta_debug_error"
        assert "foobar" in msg["error"]

    def test_collect_missing_query_sends_error(self):
        handlers = self._make_handlers()
        handlers.handle_meta_debug_command({
            "message": {"command": "collect", "query": ""},
        })

        msg = handlers._queue_service.put.call_args.args[1]
        assert msg["type"] == "meta_debug_error"
        assert "query" in msg["error"].lower()

    def test_collect_creates_session_and_starts_thread(self):
        handlers = self._make_handlers()
        handlers._agent_factory._testcase_root = Path("/tmp/test_root")

        with (
            patch("threading.Thread") as MockThread,
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            mock_thread = MagicMock()
            MockThread.return_value = mock_thread

            handlers.handle_meta_debug_command({
                "message": {"command": "collect", "query": "find prices", "run_count": 3},
            })

            # Thread started
            MockThread.assert_called_once()
            mock_thread.start.assert_called_once()
            kwargs = MockThread.call_args.kwargs
            assert kwargs["daemon"] is True
            assert "MetaDebug" in kwargs["name"]

            # Session stored
            assert len(handlers._debug_sessions) == 1

            # Session created ack sent
            put_calls = handlers._queue_service.put.call_args_list
            ack_msg = put_calls[0].args[1]
            assert ack_msg["type"] == "meta_debug_session_created"
            assert "meta_debug_" in ack_msg["session_id"]

    def test_collect_enforces_max_sessions(self):
        handlers = self._make_handlers()

        # Pre-fill 5 sessions
        for i in range(5):
            handlers._debug_sessions[f"session_{i}"] = MagicMock()

        handlers.handle_meta_debug_command({
            "message": {"command": "collect", "query": "test"},
        })

        msg = handlers._queue_service.put.call_args.args[1]
        assert msg["type"] == "meta_debug_error"
        assert "5" in msg["error"]

    def test_advance_session_not_found_sends_error(self):
        handlers = self._make_handlers()
        handlers.handle_meta_debug_command({
            "message": {"command": "evaluate", "session_id": "nonexistent"},
        })

        msg = handlers._queue_service.put.call_args.args[1]
        assert msg["type"] == "meta_debug_error"
        assert "not found" in msg["error"].lower()

    def test_advance_wrong_stage_sends_error(self):
        handlers = self._make_handlers()

        from webaxon.devsuite.web_agent_service_nextgen.agents.stage_gate_controller import (
            PipelineStage,
        )

        controller = MagicMock()
        controller.next_expected_command = "evaluate"

        handlers._debug_sessions["sid_1"] = controller

        handlers.handle_meta_debug_command({
            "message": {"command": "synthesize", "session_id": "sid_1"},
        })

        msg = handlers._queue_service.put.call_args.args[1]
        assert msg["type"] == "meta_debug_error"
        assert "evaluate" in msg["error"]
        assert "synthesize" in msg["error"]

    def test_advance_resumes_controller(self):
        handlers = self._make_handlers()

        controller = MagicMock()
        controller.next_expected_command = "evaluate"
        controller.resume.return_value = True

        handlers._debug_sessions["sid_1"] = controller

        handlers.handle_meta_debug_command({
            "message": {"command": "evaluate", "session_id": "sid_1"},
        })

        controller.resume.assert_called_once()
        # No error message sent
        handlers._queue_service.put.assert_not_called()

    def test_advance_pipeline_exited_sends_error(self):
        handlers = self._make_handlers()

        controller = MagicMock()
        controller.next_expected_command = "evaluate"
        controller.resume.return_value = False  # pipeline already done

        handlers._debug_sessions["sid_1"] = controller

        handlers.handle_meta_debug_command({
            "message": {"command": "evaluate", "session_id": "sid_1"},
        })

        msg = handlers._queue_service.put.call_args.args[1]
        assert msg["type"] == "meta_debug_error"
        assert "exited" in msg["error"].lower()

    def test_abort_calls_controller_abort(self):
        handlers = self._make_handlers()

        controller = MagicMock()
        handlers._debug_sessions["sid_1"] = controller

        handlers.handle_meta_debug_command({
            "message": {"command": "abort", "session_id": "sid_1"},
        })

        controller.abort.assert_called_once()

    def test_abort_session_not_found_sends_error(self):
        handlers = self._make_handlers()
        handlers.handle_meta_debug_command({
            "message": {"command": "abort", "session_id": "nonexistent"},
        })

        msg = handlers._queue_service.put.call_args.args[1]
        assert msg["type"] == "meta_debug_error"
        assert "not found" in msg["error"].lower()

    def test_status_single_session(self):
        handlers = self._make_handlers()

        from webaxon.devsuite.web_agent_service_nextgen.agents.stage_gate_controller import (
            PipelineStage,
        )

        controller = MagicMock()
        controller.query = "find prices"
        controller.completed_state = PipelineStage.COLLECT
        controller.next_expected_command = "evaluate"
        controller.pipeline_done = False

        handlers._debug_sessions["sid_1"] = controller

        handlers.handle_meta_debug_command({
            "message": {"command": "status", "session_id": "sid_1"},
        })

        msg = handlers._queue_service.put.call_args.args[1]
        assert msg["type"] == "meta_debug_status"
        assert msg["session_id"] == "sid_1"
        assert msg["completed_state"] == "COLLECT"
        assert msg["next_command"] == "evaluate"

    def test_status_all_sessions(self):
        handlers = self._make_handlers()

        from webaxon.devsuite.web_agent_service_nextgen.agents.stage_gate_controller import (
            PipelineStage,
        )

        c1 = MagicMock()
        c1.query = "query 1"
        c1.completed_state = PipelineStage.COLLECT
        c1.next_expected_command = "evaluate"

        c2 = MagicMock()
        c2.query = "query 2"
        c2.completed_state = PipelineStage.SYNTHESIZE
        c2.next_expected_command = "validate"

        handlers._debug_sessions["sid_1"] = c1
        handlers._debug_sessions["sid_2"] = c2

        handlers.handle_meta_debug_command({
            "message": {"command": "status"},
        })

        msg = handlers._queue_service.put.call_args.args[1]
        assert msg["type"] == "meta_debug_status"
        assert len(msg["sessions"]) == 2

    def test_shutdown_debug_sessions(self):
        handlers = self._make_handlers()

        c1 = MagicMock()
        c2 = MagicMock()
        handlers._debug_sessions["s1"] = c1
        handlers._debug_sessions["s2"] = c2

        handlers.shutdown_debug_sessions()

        c1.abort.assert_called_once()
        c2.abort.assert_called_once()

    def test_dispatch_routes_to_correct_handler(self):
        handlers = self._make_handlers()

        for cmd, method_name in [
            ("evaluate", "_handle_debug_advance"),
            ("synthesize", "_handle_debug_advance"),
            ("validate", "_handle_debug_advance"),
            ("status", "_handle_debug_status"),
            ("abort", "_handle_debug_abort"),
        ]:
            with patch.object(handlers, method_name) as mock_method:
                handlers.handle_meta_debug_command({
                    "message": {"command": cmd, "session_id": "sid"},
                })
                mock_method.assert_called_once()


# ---------------------------------------------------------------------------
# CLI meta debug command tests
# ---------------------------------------------------------------------------


class TestMetaDebugCLI:
    """Tests for CLIClient meta debug command parsing and display."""

    @staticmethod
    def _make_client(tmp_path):
        client = CLIClient(testcase_root=tmp_path)
        client._queue_service = MagicMock()
        client._session_id = "test_session"
        return client

    def test_parse_collect_args_simple(self):
        query, run_count = CLIClient._parse_collect_args("find egg prices")
        assert query == "find egg prices"
        assert run_count == 5  # default

    def test_parse_collect_args_with_runs(self):
        query, run_count = CLIClient._parse_collect_args("find egg prices --runs 10")
        assert query == "find egg prices"
        assert run_count == 10

    def test_parse_collect_args_runs_only_at_end(self):
        query, run_count = CLIClient._parse_collect_args(
            "search --runs on marathon training --runs 3"
        )
        assert query == "search --runs on marathon training"
        assert run_count == 3

    def test_parse_collect_args_empty(self):
        query, run_count = CLIClient._parse_collect_args("")
        assert query == ""
        assert run_count == 5

    def test_handle_meta_debug_collect_sends_message(self, tmp_path):
        client = self._make_client(tmp_path)
        client._queue_service.get.return_value = None

        with patch.object(client, "_poll_debug_stage_responses"):
            client._run_debug_collect("find prices", 3)

        put_call = client._queue_service.put.call_args
        msg = put_call.args[1]
        assert msg["type"] == "meta_debug_command"
        assert msg["message"]["command"] == "collect"
        assert msg["message"]["query"] == "find prices"
        assert msg["message"]["run_count"] == 3

    def test_handle_meta_debug_advance_sends_message(self, tmp_path):
        client = self._make_client(tmp_path)
        client._queue_service.get.return_value = None

        with patch.object(client, "_poll_debug_stage_responses"):
            client._run_debug_advance("evaluate", "sid_123")

        put_call = client._queue_service.put.call_args
        msg = put_call.args[1]
        assert msg["type"] == "meta_debug_command"
        assert msg["message"]["command"] == "evaluate"
        assert msg["message"]["session_id"] == "sid_123"

    def test_display_stage_result_collect(self, tmp_path, capsys):
        CLIClient._display_stage_result({
            "state": "COLLECT",
            "session_id": "sid_1",
            "summary": {"trace_count": 5},
            "next_command": "evaluate",
            "checkpoint_path": "/tmp/checkpoint.json",
        })

        captured = capsys.readouterr()
        assert "COLLECT completed" in captured.out
        assert "Traces collected: 5" in captured.out
        assert "evaluate" in captured.out
        assert "checkpoint.json" in captured.out

    def test_display_stage_result_evaluate(self, tmp_path, capsys):
        CLIClient._display_stage_result({
            "state": "EVALUATE",
            "session_id": "sid_1",
            "summary": {"passed_count": 3, "total_count": 5},
            "next_command": "synthesize",
            "checkpoint_path": "",
        })

        captured = capsys.readouterr()
        assert "EVALUATE completed" in captured.out
        assert "Passed: 3/5" in captured.out

    def test_display_stage_result_validate_skipped(self, tmp_path, capsys):
        CLIClient._display_stage_result({
            "state": "VALIDATE",
            "session_id": "sid_1",
            "summary": {"skipped": True},
            "next_command": None,
            "checkpoint_path": "",
        })

        captured = capsys.readouterr()
        assert "skipped" in captured.out.lower()

    def test_display_stage_result_validate_with_results(self, tmp_path, capsys):
        CLIClient._display_stage_result({
            "state": "VALIDATE",
            "session_id": "sid_1",
            "summary": {"all_passed": True, "success_rate": 1.0, "result_count": 3},
            "next_command": None,
            "checkpoint_path": "",
        })

        captured = capsys.readouterr()
        assert "All passed: True" in captured.out
        assert "100.0%" in captured.out

    def test_display_final_result_success(self, tmp_path, capsys):
        CLIClient._display_final_result({
            "success": True,
            "output_path": "/tmp/result.json",
            "summary": "3 traces collected",
        })

        captured = capsys.readouterr()
        assert "Completed successfully" in captured.out
        assert "/tmp/result.json" in captured.out

    def test_display_final_result_failure(self, tmp_path, capsys):
        CLIClient._display_final_result({
            "success": False,
            "error": "Agent timeout in collection",
        })

        captured = capsys.readouterr()
        assert "failed" in captured.out.lower()
        assert "Agent timeout" in captured.out

    def test_poll_debug_handles_session_created(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        responses = [
            {"type": "meta_debug_session_created", "session_id": "sid_new"},
            {
                "type": "run_meta_agent_debug_state",
                "state": "COLLECT",
                "session_id": "sid_new",
                "summary": {"trace_count": 5},
                "next_command": "evaluate",
                "checkpoint_path": "",
            },
        ]
        response_iter = iter(responses)

        def mock_get(queue_id, blocking=False):
            try:
                return next(response_iter)
            except StopIteration:
                return None

        with (
            patch.object(client._queue_service, "get", side_effect=mock_get),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 1, 2, 3]),
        ):
            client._poll_debug_stage_responses(session_id=None)

        captured = capsys.readouterr()
        assert "Session sid_new created" in captured.out
        assert "COLLECT completed" in captured.out

    def test_poll_debug_validate_continues_to_final(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        responses = [
            {
                "type": "run_meta_agent_debug_state",
                "state": "VALIDATE",
                "session_id": "sid_1",
                "summary": {"all_passed": True, "success_rate": 1.0, "result_count": 2},
                "next_command": None,
                "checkpoint_path": "",
            },
            {
                "type": "run_meta_agent_response",
                "success": True,
                "output_path": "/tmp/result.json",
                "summary": "done",
            },
        ]
        response_iter = iter(responses)

        def mock_get(queue_id, blocking=False):
            try:
                return next(response_iter)
            except StopIteration:
                return None

        with (
            patch.object(client._queue_service, "get", side_effect=mock_get),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 1, 2, 3]),
        ):
            client._poll_debug_stage_responses(session_id="sid_1")

        captured = capsys.readouterr()
        assert "VALIDATE completed" in captured.out
        assert "Completed successfully" in captured.out

    def test_poll_debug_handles_error(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        responses = [
            {"type": "meta_debug_error", "error": "Session not found"},
        ]
        response_iter = iter(responses)

        def mock_get(queue_id, blocking=False):
            try:
                return next(response_iter)
            except StopIteration:
                return None

        with (
            patch.object(client._queue_service, "get", side_effect=mock_get),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 1]),
        ):
            client._poll_debug_stage_responses(session_id="sid_1")

        captured = capsys.readouterr()
        assert "Session not found" in captured.out

    def test_subcommand_dispatch_collect(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        with patch.object(client, "_run_debug_collect") as mock:
            client._handle_meta_debug_command("collect find egg prices --runs 3")

        mock.assert_called_once_with("find egg prices", 3)

    def test_subcommand_dispatch_evaluate(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        with patch.object(client, "_run_debug_advance") as mock:
            client._handle_meta_debug_command("evaluate sid_123")

        mock.assert_called_once_with("evaluate", "sid_123")

    def test_subcommand_missing_args(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        client._handle_meta_debug_command("evaluate")

        captured = capsys.readouterr()
        assert "Usage" in captured.out

    def test_subcommand_unknown(self, tmp_path, capsys):
        client = self._make_client(tmp_path)

        client._handle_meta_debug_command("foobar")

        captured = capsys.readouterr()
        assert "Usage" in captured.out
        assert "collect" in captured.out
