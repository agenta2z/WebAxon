"""Property-based test for Log Path Message Delivery (Property 9).

**Validates: Requirements 1.1, 1.3, 1.4**

For any session where an agent is created, the `log_path_available` message SHALL
be sent to the client control queue containing the correct session directory path.
The path SHALL point to an existing directory. The message SHALL include the
session_id and the absolute filesystem path to the session's agent log directory.
"""

import resolve_path  # noqa: F401 - must be first import

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import AgentRunner
from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_monitor import (
    AgentSessionMonitor,
)
from rich_python_utils.service_utils.session_management import (
    SessionLogger as SessionLogManager,
)

# --- Strategies ---

session_ids = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=15,
)

agent_types = st.sampled_from([
    "PromptBasedActionAgent",
    "PromptBasedPlanningAgent",
    "TestAgent",
    "DefaultAgent",
])


class MockQueueService:
    """Minimal mock queue service that records all put() calls."""

    def __init__(self):
        self.messages: Dict[str, List[Any]] = {}
        self._queues: Dict[str, List[Any]] = {}

    def put(self, queue_id: str, message: Any) -> None:
        self.messages.setdefault(queue_id, []).append(message)

    def get(self, queue_id: str, blocking: bool = True) -> Any:
        if queue_id in self._queues and self._queues[queue_id]:
            return self._queues[queue_id].pop(0)
        return None

    def peek(self, queue_id: str) -> Any:
        if queue_id in self._queues and self._queues[queue_id]:
            return self._queues[queue_id][0]
        return None

    def has_messages(self, queue_id: str) -> bool:
        return bool(self._queues.get(queue_id))

    def create_queue(self, queue_id: str) -> bool:
        if queue_id not in self._queues:
            self._queues[queue_id] = []
            return True
        return False

    def clear(self, queue_id: str = None) -> None:
        if queue_id:
            self._queues.pop(queue_id, None)
            self.messages.pop(queue_id, None)
        else:
            self._queues.clear()
            self.messages.clear()

    def close(self) -> None:
        pass


def _build_monitor(tmp_dir, session_id, agent_type, attach_session_logger=True):
    """Helper: create config, queue, session, monitor, and optionally a SessionLogger.

    Returns (monitor, queue_service, config, session_logger_or_None, session_manager).
    """
    config = ServiceConfig()
    queue_service = MockQueueService()
    session_manager = SessionManager(id='test', log_name='Test', logger=[print], always_add_logging_based_logger=False, config=config, queue_service=queue_service, service_log_dir=tmp_dir)

    session_logger = None
    if attach_session_logger:
        agent_log_dir = tmp_dir / "agent_logs"
        agent_log_dir.mkdir(parents=True, exist_ok=True)
        session_logger = SessionLogManager(
            base_log_dir=agent_log_dir,
            session_id=session_id,
            session_type=agent_type,
        )

    session = session_manager.get_or_create(session_id)
    session_manager.update_session(
        session_id,
        session_type=agent_type,
        initialized=False,
    )

    # Directly set the session logger on the session object
    if attach_session_logger:
        session._session_logger = session_logger
    else:
        session._session_logger = None

    agent_factory = Mock(spec=AgentFactory)
    mock_agent = Mock()
    mock_agent.logger = {}
    agent_factory.create_agent.return_value = mock_agent

    agent_runner = Mock(spec=AgentRunner)
    agent_runner.start_agent_thread.return_value = None

    monitor = AgentSessionMonitor(
        session_manager, queue_service, config, agent_factory, agent_runner
    )

    return monitor, queue_service, config, session_logger, session_manager


def _get_log_path_messages(queue_service, config):
    """Extract log_path_available messages from the client control queue."""
    control_messages = queue_service.messages.get(
        config.client_control_queue_id, []
    )
    return [m for m in control_messages if m.get("type") == "log_path_available"]


class TestLogPathMessageProperty:
    """Property 9: Log Path Message Delivery."""

    @given(session_id=session_ids, agent_type=agent_types)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_log_path_message_sent_after_agent_creation(self, session_id, agent_type):
        """A log_path_available message is sent to client_control queue after agent creation.

        **Validates: Requirements 1.1, 1.3, 1.4**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            monitor, queue_service, config, sess_logger, sm = _build_monitor(
                tmp_dir, session_id, agent_type
            )
            session = sm.get(session_id)
            monitor._create_agent_for_session(session)

            msgs = _get_log_path_messages(queue_service, config)
            assert len(msgs) >= 1, (
                f"Expected at least one log_path_available message, got {len(msgs)}"
            )
            msg = msgs[-1]
            assert msg["type"] == "log_path_available"
            assert "message" in msg
            assert msg["message"]["session_id"] == session_id
            assert "log_path" in msg["message"]
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, agent_type=agent_types)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_log_path_points_to_existing_directory(self, session_id, agent_type):
        """The log_path in the message points to an existing directory.

        **Validates: Requirements 1.1, 1.3, 1.4**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            monitor, queue_service, config, sess_logger, sm = _build_monitor(
                tmp_dir, session_id, agent_type
            )
            session = sm.get(session_id)
            monitor._create_agent_for_session(session)

            msgs = _get_log_path_messages(queue_service, config)
            assert len(msgs) >= 1
            log_path = Path(msgs[-1]["message"]["log_path"])
            assert log_path.exists(), f"log_path '{log_path}' does not exist"
            assert log_path.is_dir(), f"log_path '{log_path}' is not a directory"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, agent_type=agent_types)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_log_path_matches_session_logger_dir(self, session_id, agent_type):
        """The log_path in the message matches the SessionLogger's session_dir.

        **Validates: Requirements 1.1, 1.3**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            monitor, queue_service, config, sess_logger, sm = _build_monitor(
                tmp_dir, session_id, agent_type
            )
            session = sm.get(session_id)
            monitor._create_agent_for_session(session)

            msgs = _get_log_path_messages(queue_service, config)
            assert len(msgs) >= 1
            reported_path = msgs[-1]["message"]["log_path"]
            expected_path = str(sess_logger.session_dir)
            assert reported_path == expected_path, (
                f"log_path '{reported_path}' != session_dir '{expected_path}'"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, agent_type=agent_types)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_message_contains_correct_session_id(self, session_id, agent_type):
        """The session_id in the log_path_available message matches the session.

        **Validates: Requirements 1.3**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            monitor, queue_service, config, sess_logger, sm = _build_monitor(
                tmp_dir, session_id, agent_type
            )
            session = sm.get(session_id)
            monitor._create_agent_for_session(session)

            msgs = _get_log_path_messages(queue_service, config)
            assert len(msgs) >= 1
            assert msgs[-1]["message"]["session_id"] == session_id
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(session_id=session_ids, agent_type=agent_types)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_no_log_path_message_without_session_logger(self, session_id, agent_type):
        """No log_path_available message is sent when session_logger is None.

        **Validates: Requirements 1.1**
        """
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            monitor, queue_service, config, sess_logger, sm = _build_monitor(
                tmp_dir, session_id, agent_type, attach_session_logger=False
            )
            session = sm.get(session_id)
            monitor._create_agent_for_session(session)

            msgs = _get_log_path_messages(queue_service, config)
            assert len(msgs) == 0, (
                f"Expected no log_path_available messages when session_logger "
                f"is None, got {len(msgs)}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
