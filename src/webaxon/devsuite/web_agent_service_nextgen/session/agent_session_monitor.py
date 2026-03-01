"""Session monitoring for web agent service.

Extends the generic SessionMonitor with WebAgent-specific monitoring:
status change detection, lazy agent creation, and queue integration.
"""
from typing import Any

from agent_foundation.ui.queue_interactive import QueueInteractive
from rich_python_utils.common_objects.debuggable import EXCEPTION_LOG_ITEM_KEY
from rich_python_utils.datetime_utils.common import timestamp
from rich_python_utils.service_utils.session_management import SessionMonitor

from webaxon.devsuite.common import DebuggerLogTypes

from ..core.config import ServiceConfig
from ..core.agent_factory import AgentFactory
from ..agents.agent_runner import AgentRunner
from .agent_session import AgentSession
from .agent_session_manager import AgentSessionManager


class AgentSessionMonitor(SessionMonitor):
    """Monitors agent sessions for status changes and cleanup.

    Extends the generic SessionMonitor with:
    - Agent status change detection and acknowledgment
    - Lazy agent creation when messages are waiting
    - Queue-based communication with debugger UI
    """

    def __init__(
        self,
        session_manager: AgentSessionManager,
        queue_service: Any,
        config: ServiceConfig,
        agent_factory: AgentFactory,
        agent_runner: AgentRunner,
        debugger=None,
    ):
        super().__init__(session_manager, config.cleanup_check_interval)
        self._queue_service = queue_service
        self._config = config
        self._agent_factory = agent_factory
        self._agent_runner = agent_runner
        self._debugger = debugger

    def on_monitoring_cycle(self) -> None:
        """Run WebAgent-specific monitoring checks."""
        self.check_status_changes()
        self.check_lazy_agent_creation()

    def check_status_changes(self) -> None:
        """Monitor agent status changes and send acknowledgments."""
        try:
            sessions = self._session_manager.get_all_sessions()

            for session_id, session in sessions.items():
                try:
                    if not session.info.initialized or session.agent is None:
                        continue

                    current_status = self._get_agent_status(session)

                    if current_status != session.info.last_agent_status:
                        session.log_info({
                            'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                            'message': f'Agent status changed for session {session_id}',
                            'old_status': session.info.last_agent_status,
                            'new_status': current_status
                        })

                        self._send_status_ack(session_id, current_status)

                        self._session_manager.update_session(
                            session_id,
                            last_agent_status=current_status
                        )

                except Exception as e:
                    session.log_error({
                        'type': DebuggerLogTypes.ERROR,
                        'message': f'Error checking status for session {session_id}: {str(e)}'
                    })

        except Exception as e:
            self._debugger.log_error({
                EXCEPTION_LOG_ITEM_KEY: e,
            })

    def check_lazy_agent_creation(self) -> None:
        """Check for messages waiting and create agents lazily."""
        if not self._config.new_agent_on_first_submission:
            return

        try:
            sessions = self._session_manager.get_all_sessions()

            for session_id, session in sessions.items():
                try:
                    if session.info.initialized:
                        continue

                    has_messages = self._check_for_waiting_messages(session_id)

                    if has_messages:
                        session.log_info({
                            'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                            'message': f'Creating agent lazily for session {session_id}',
                            'session_type': session.info.session_type,
                            'reason': 'Messages waiting in input queue'
                        })

                        self._create_agent_for_session(session)

                except Exception as e:
                    session.log_error({
                        'type': DebuggerLogTypes.ERROR,
                        'message': f'Error in lazy agent creation for session {session_id}: {str(e)}'
                    })

        except Exception as e:
            self._debugger.log_error({
                EXCEPTION_LOG_ITEM_KEY: e,
            })

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _get_agent_status(self, session: AgentSession) -> str:
        """Get current agent status."""
        if session.agent is None:
            return 'not_created'

        if session.agent_thread is not None:
            if session.agent_thread.is_alive():
                return 'running'
            else:
                return 'stopped'

        return 'ready'

    def _send_status_ack(self, session_id: str, status: str) -> None:
        """Send status acknowledgment to control queue."""
        try:
            ack_message = {
                'type': 'agent_status_change',
                'session_id': session_id,
                'status': status,
                'timestamp': timestamp()
            }

            self._queue_service.put(
                self._config.server_control_queue_id,
                ack_message
            )

        except Exception as e:
            self._debugger.log_error({
                EXCEPTION_LOG_ITEM_KEY: e,
                'session_id': session_id,
            })

    def _check_for_waiting_messages(self, session_id: str) -> bool:
        """Check if there are messages waiting for a session."""
        try:
            session_input_queue_id = f"{self._config.input_queue_id}_{session_id}"
            queue_size = self._queue_service.size(session_input_queue_id)
            return queue_size > 0

        except Exception as e:
            self._debugger.log_error({
                EXCEPTION_LOG_ITEM_KEY: e,
                'session_id': session_id,
            })
            return False

    def _create_agent_for_session(self, session: AgentSession) -> None:
        """Create agent for a session and start the agent thread."""
        try:
            session_input_queue_id = f"{self._config.input_queue_id}_{session.session_id}"

            if self._queue_service.create_queue(session_input_queue_id):
                session.log_info({
                    'type': DebuggerLogTypes.QUEUE_OPERATION,
                    'message': f'Created session-specific input queue: {session_input_queue_id}'
                })

            interactive = QueueInteractive(
                input_queue=self._queue_service,
                response_queue=self._queue_service,
                input_queue_id=session_input_queue_id,
                response_queue_id=self._config.response_queue_id
            )

            agent = self._agent_factory.create_agent(
                interactive=interactive,
                logger=session.session_logger,
                agent_type=session.info.session_type,
                template_version=session.info.template_version
            )

            self._session_manager.update_session(
                session.session_id,
                agent=agent,
                interactive=interactive,
                initialized=True
            )

            session.log_info({
                'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                'message': f'Agent created lazily for session {session.session_id}',
                'session_type': session.info.session_type,
                'input_queue_id': session_input_queue_id
            })

            updated_session = self._session_manager.get(session.session_id)
            if updated_session:
                agent_thread = self._agent_runner.start_agent_thread(
                    updated_session,
                    self._queue_service
                )

                if agent_thread:
                    self._session_manager.update_session(
                        session.session_id,
                        agent_thread=agent_thread
                    )

                    session.log_info({
                        'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                        'message': f'Agent thread started for session {session.session_id}',
                        'thread_name': agent_thread.name
                    })

            if session.session_logger is None:
                return
            log_dir = session.session_logger.session_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path_message = {
                'type': 'log_path_available',
                'message': {
                    'session_id': session.session_id,
                    'log_path': str(log_dir)
                }
            }
            self._queue_service.put(
                self._config.client_control_queue_id,
                log_path_message
            )
            session.log_info({
                'type': DebuggerLogTypes.QUEUE_OPERATION,
                'message': f'Sent log_path_available for session {session.session_id}',
                'log_path': str(log_dir)
            })

        except Exception as e:
            session.log_error({
                'type': DebuggerLogTypes.ERROR,
                'message': f'Error creating agent for session {session.session_id}: {str(e)}'
            })
            raise
