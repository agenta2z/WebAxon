"""Agent thread management for web agent service.

This module provides the AgentRunner class for managing agent execution
in separate threads or synchronously for debugging.
"""
import threading
import time
import traceback
from typing import Optional, Any

from science_modeling_tools.ui.interactive_base import InteractionFlags
from webaxon.devsuite.common import DebuggerLogTypes

from ..core.config import ServiceConfig
from ..session.agent_session import AgentSession


class AgentRunner:
    """Manages agent thread execution.

    This class handles starting agents in separate threads for production
    or running them synchronously in the main process for debugging.

    Key responsibilities:
    - Create and start agent threads
    - Support synchronous execution for debugging
    - Track thread references in session info
    - Update session status on completion/failure
    - Handle agent execution errors
    """

    def __init__(self, config: ServiceConfig):
        """Initialize the agent runner.

        Args:
            config: Service configuration controlling execution mode
        """
        self._config = config

    def start_agent_thread(
        self,
        session: AgentSession,
        queue_service: Any
    ) -> Optional[threading.Thread]:
        """Start agent in separate thread or run synchronously.

        This method determines whether to run the agent in a separate thread
        (production mode) or synchronously in the main process (debug mode).

        In synchronous mode, this method blocks until the agent completes.
        In async mode, it returns immediately with a thread reference.

        Args:
            session: AgentSession containing the agent
            queue_service: Queue service for communication

        Returns:
            Thread reference if async mode, None if synchronous mode
        """
        if self._config.synchronous_agent:
            # Run synchronously for debugging
            session.log_info({
                'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                'message': f'Running agent synchronously for session {session.session_id}',
                'note': 'Service loop will be blocked while agent runs. Use for debugging only.'
            })

            self.run_agent_synchronously(session, queue_service)
            return None
        else:
            # Create and start thread
            agent_thread = threading.Thread(
                target=self.run_agent_in_thread,
                args=(session, queue_service),
                daemon=True,
                name=f'AgentThread-{session.session_id}'
            )
            agent_thread.start()

            session.log_info({
                'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                'message': f'Agent thread started for session {session.session_id}',
                'thread_name': agent_thread.name,
                'agent_type': session.info.session_type
            })

            return agent_thread

    def run_agent_in_thread(
        self,
        session: AgentSession,
        queue_service: Any
    ) -> None:
        """Run agent in thread (blocking).

        This method runs the agent's main loop, processing messages from
        the input queue until the agent completes or an error occurs.

        The agent status is updated on completion or failure.

        Args:
            session: AgentSession containing the agent
            queue_service: Queue service for communication
        """
        try:
            session.log_info({
                'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                'message': f'Agent thread running for session {session.session_id}',
                'agent_type': session.info.session_type
            })

            # Run the agent - it will process messages from the queue
            # The agent is a callable (Agent.__call__) that blocks until completion
            result = session.agent()

            session.log_info({
                'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                'message': f'Agent completed for session {session.session_id}',
                'result': str(result)
            })

            # Finalize session log manager on success
            session.finalize("completed")

            # Update session status to completed
            session.info.last_agent_status = 'completed'

        except Exception as e:
            # Capture full traceback
            tb_str = traceback.format_exc()
            error_msg = f'Agent execution error: {str(e)}'

            # Log structured error with exception details
            session.log_error({
                'type': DebuggerLogTypes.ERROR,
                'message': error_msg,
                'session_id': session.session_id,
                'exception_type': type(e).__name__,
                'exception_message': str(e),
                'traceback': tb_str
            }, log_type='Error')

            # Finalize session log manager on error
            session.finalize("error")

            # Update session status to error
            session.info.last_agent_status = 'error'

            # Send error response to response queue
            try:
                if session.interactive:
                    session.interactive.send_response(
                        {
                            'session_id': session.session_id,
                            'error': error_msg,
                            'status': 'error'
                        },
                        flag=InteractionFlags.TurnCompleted
                    )
            except Exception as send_error:
                session.log_error({
                    'type': DebuggerLogTypes.ERROR,
                    'message': f'Failed to send error response: {str(send_error)}',
                    'session_id': session.session_id,
                    'exception_type': type(send_error).__name__,
                    'exception_message': str(send_error),
                    'traceback': traceback.format_exc()
                }, log_type='Error')

    def run_agent_synchronously(
        self,
        session: AgentSession,
        queue_service: Any
    ) -> None:
        """Run agent in main process for debugging.

        This method runs the agent synchronously in the main process,
        which enables debugger attachment and step-through debugging.

        The service loop will be blocked while the agent runs.

        Args:
            session: AgentSession containing the agent
            queue_service: Queue service for communication
        """
        try:
            session.log_info({
                'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                'message': f'Running agent synchronously for session {session.session_id}',
                'agent_type': session.info.session_type
            })

            # Run the agent synchronously - blocks until completion
            # The agent is a callable (Agent.__call__) that blocks until completion
            result = session.agent()

            session.log_info({
                'type': DebuggerLogTypes.AGENT_LIFECYCLE,
                'message': f'Agent completed synchronously for session {session.session_id}',
                'result': str(result)
            })

            # Update session status to completed
            session.info.last_agent_status = 'completed'

        except Exception as e:
            # Capture full traceback
            tb_str = traceback.format_exc()
            error_msg = f'Agent execution error (synchronous): {str(e)}'

            # Log structured error with exception details
            session.log_error({
                'type': DebuggerLogTypes.ERROR,
                'message': error_msg,
                'session_id': session.session_id,
                'exception_type': type(e).__name__,
                'exception_message': str(e),
                'traceback': tb_str
            }, log_type='Error')

            # Update session status to error
            session.info.last_agent_status = 'error'

            # Send error response to response queue
            try:
                if session.interactive:
                    session.interactive.send_response(
                        {
                            'session_id': session.session_id,
                            'error': error_msg,
                            'status': 'error'
                        },
                        flag=InteractionFlags.TurnCompleted
                    )
            except Exception as send_error:
                session.log_error({
                    'type': DebuggerLogTypes.ERROR,
                    'message': f'Failed to send error response: {str(send_error)}',
                    'session_id': session.session_id,
                    'exception_type': type(send_error).__name__,
                    'exception_message': str(send_error),
                    'traceback': traceback.format_exc()
                }, log_type='Error')
