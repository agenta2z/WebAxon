"""Property-based test for Property 8: Structured Error Completeness.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

For any exception caught during agent execution, the structured error log entry
SHALL contain the `exception_type`, `exception_message`, and `traceback` fields.
The `traceback` field SHALL be a non-empty string containing the formatted stack trace.
"""
import resolve_path  # Must be first import

from unittest.mock import Mock, MagicMock
from hypothesis import given, strategies as st, settings

from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import AgentRunner
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session.agent_session import AgentSession


# Strategy: generate exception class names and messages
exception_types = st.sampled_from([
    RuntimeError, ValueError, TypeError, KeyError, AttributeError,
    IOError, OSError, IndexError, ZeroDivisionError, FileNotFoundError,
    ConnectionError, TimeoutError, PermissionError, NotImplementedError,
])

exception_messages = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
    min_size=1,
    max_size=200,
)

session_ids = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N')),
    min_size=1,
    max_size=50,
)


def _create_session_with_capturing_logger(session_id: str):
    """Create a mock session whose log_error captures calls."""
    session = Mock()
    session.session_id = session_id
    session.info = Mock()
    session.info.session_type = 'TestAgent'
    session.info.last_agent_status = None
    session.interactive = Mock()
    session.finalize = Mock()

    # Capture all log_error calls
    captured_errors = []

    def capture_log_error(log_item, log_type=None, message_id=None):
        captured_errors.append(log_item)

    session.log_error = Mock(side_effect=capture_log_error)
    session.log_info = Mock()

    return session, captured_errors


@given(
    exc_type=exception_types,
    exc_msg=exception_messages,
    session_id=session_ids,
)
@settings(max_examples=50)
def test_run_agent_in_thread_structured_error_completeness(exc_type, exc_msg, session_id):
    """Property 8: run_agent_in_thread logs structured error with all required fields.

    **Validates: Requirements 9.1, 9.3, 9.4**
    """
    config = ServiceConfig()
    runner = AgentRunner(config)

    session, captured_errors = _create_session_with_capturing_logger(session_id)

    # Agent that raises the given exception
    def failing_agent():
        raise exc_type(exc_msg)

    session.agent = failing_agent
    queue_service = Mock()

    runner.run_agent_in_thread(session, queue_service)

    # There should be at least one error logged
    assert len(captured_errors) >= 1, "Expected at least one error log entry"

    error_entry = captured_errors[0]

    # Verify all required structured fields exist
    assert 'exception_type' in error_entry, "Missing 'exception_type' field"
    assert 'exception_message' in error_entry, "Missing 'exception_message' field"
    assert 'traceback' in error_entry, "Missing 'traceback' field"

    # Verify exception_type matches the actual exception class name
    assert error_entry['exception_type'] == exc_type.__name__, (
        f"Expected exception_type '{exc_type.__name__}', got '{error_entry['exception_type']}'"
    )

    # Verify exception_message matches what str(e) produces
    # Note: KeyError wraps its argument in quotes, so str(KeyError('x')) == "'x'"
    try:
        raise exc_type(exc_msg)
    except Exception as expected_exc:
        expected_message = str(expected_exc)

    assert error_entry['exception_message'] == expected_message, (
        f"Expected exception_message '{expected_message}', got '{error_entry['exception_message']}'"
    )

    # Verify traceback is a non-empty string containing the stack trace
    tb = error_entry['traceback']
    assert isinstance(tb, str), f"traceback should be a string, got {type(tb)}"
    assert len(tb) > 0, "traceback should be non-empty"
    assert 'Traceback' in tb, "traceback should contain 'Traceback'"

    # Verify session_id is included
    assert error_entry.get('session_id') == session_id

    # Verify session status was set to error
    assert session.info.last_agent_status == 'error'


@given(
    exc_type=exception_types,
    exc_msg=exception_messages,
    session_id=session_ids,
)
@settings(max_examples=50)
def test_run_agent_synchronously_structured_error_completeness(exc_type, exc_msg, session_id):
    """Property 8: run_agent_synchronously logs structured error with all required fields.

    **Validates: Requirements 9.1, 9.2, 9.3, 9.4**
    """
    config = ServiceConfig()
    runner = AgentRunner(config)

    session, captured_errors = _create_session_with_capturing_logger(session_id)

    # Agent that raises the given exception
    def failing_agent():
        raise exc_type(exc_msg)

    session.agent = failing_agent
    queue_service = Mock()

    runner.run_agent_synchronously(session, queue_service)

    # There should be at least one error logged
    assert len(captured_errors) >= 1, "Expected at least one error log entry"

    error_entry = captured_errors[0]

    # Verify all required structured fields exist
    assert 'exception_type' in error_entry, "Missing 'exception_type' field"
    assert 'exception_message' in error_entry, "Missing 'exception_message' field"
    assert 'traceback' in error_entry, "Missing 'traceback' field"

    # Verify exception_type matches the actual exception class name
    assert error_entry['exception_type'] == exc_type.__name__

    # Verify exception_message matches what str(e) produces
    try:
        raise exc_type(exc_msg)
    except Exception as expected_exc:
        expected_message = str(expected_exc)

    assert error_entry['exception_message'] == expected_message

    # Verify traceback is a non-empty string containing the stack trace
    tb = error_entry['traceback']
    assert isinstance(tb, str)
    assert len(tb) > 0
    assert 'Traceback' in tb

    # Verify session_id is included
    assert error_entry.get('session_id') == session_id

    # Verify session status was set to error
    assert session.info.last_agent_status == 'error'


@given(
    exc_type=exception_types,
    exc_msg=exception_messages,
    session_id=session_ids,
)
@settings(max_examples=50)
def test_structured_error_logs_to_session_not_just_stderr(exc_type, exc_msg, session_id):
    """Property 8: Errors are logged to the session's structured JSON logger,
    not only printed to stderr via traceback.print_exc().

    **Validates: Requirement 9.4**
    """
    config = ServiceConfig()
    runner = AgentRunner(config)

    session, captured_errors = _create_session_with_capturing_logger(session_id)

    def failing_agent():
        raise exc_type(exc_msg)

    session.agent = failing_agent
    queue_service = Mock()

    runner.run_agent_in_thread(session, queue_service)

    # The session's log_error must have been called (not just traceback.print_exc)
    assert session.log_error.called, (
        "log_error should be called on the session for structured logging"
    )

    # Verify the log_error was called with log_type='Error'
    call_args = session.log_error.call_args_list[0]
    assert call_args[1].get('log_type') == 'Error' or (
        len(call_args[0]) > 1 and call_args[0][1] == 'Error'
    ), "log_error should be called with log_type='Error'"
