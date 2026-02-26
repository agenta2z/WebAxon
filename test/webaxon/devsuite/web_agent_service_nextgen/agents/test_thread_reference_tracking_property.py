"""Property-based test for thread reference tracking.

This module contains property-based tests using hypothesis to verify
that agent thread references are properly stored in session info.
"""
import sys
import resolve_path  # Setup import paths

import threading
import time
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock

# Add parent directory to path
from hypothesis import given, strategies as st, settings, assume
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager, AgentSession
from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import AgentRunner


# Mock classes for testing
class MockQueueService:
    """Mock queue service for testing."""
    pass


class MockAgent:
    """Mock agent for testing."""
    def __init__(self, run_duration=0.1):
        self.run_duration = run_duration
        self.run_called = False
        self.run_thread_id = None

    def __call__(self):
        """Agent is callable."""
        self.run_called = True
        self.run_thread_id = threading.current_thread().ident
        time.sleep(self.run_duration)
        return 'completed'


# Feature: web-agent-service-modularization, Property 25: Thread Reference Tracking
# Validates: Requirements 7.4
@settings(max_examples=100, deadline=None)
@given(
    # Generate number of sessions to test
    num_sessions=st.integers(min_value=1, max_value=10),
    # Generate agent run duration (in seconds)
    run_duration=st.floats(min_value=0.05, max_value=0.3),
    # Generate whether to use async or sync mode
    use_async_mode=st.booleans(),
)
def test_thread_reference_tracking(num_sessions, run_duration, use_async_mode):
    """Property: For any agent thread that is started, the thread reference
    should be stored in session.agent_thread.

    This test verifies that:
    1. When an agent thread is started in async mode, the thread reference is returned
    2. The returned thread reference can be stored in session.agent_thread
    3. The stored thread reference matches the actual running thread
    4. The thread reference persists in session after storage
    5. The thread reference can be retrieved from session
    6. Multiple sessions can have independent thread references
    7. Each session's thread reference is unique and correct
    8. Thread references remain valid while threads are running
    9. Thread references can be used to check thread status (is_alive())
    10. Thread references can be used to join threads
    11. In synchronous mode, no thread reference is stored (None)
    12. Thread references are properly typed (threading.Thread or None)

    Test strategy:
    - Create multiple sessions with async or sync mode
    - Start agent threads for each session
    - Store thread references in session
    - Verify thread references are correct and accessible
    - Verify thread references match actual running threads
    - Verify thread references can be used for thread operations
    - Verify synchronous mode has no thread references
    """
    # Filter out edge cases
    assume(num_sessions >= 1)
    assume(0.05 <= run_duration <= 0.3)

    # Create temporary directory for logs
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Create config with specified mode
        config = ServiceConfig(synchronous_agent=not use_async_mode)

        # Create agent runner
        runner = AgentRunner(config)

        # Create mock queue service
        queue_service = MockQueueService()

        # Create session manager
        session_manager = SessionManager(id='test', log_name='Test', logger=[print], always_add_logging_based_logger=False, config=config, queue_service=queue_service, service_log_dir=temp_dir)

        # Create sessions and start agent threads
        session_ids = [f"test_session_{i}" for i in range(num_sessions)]
        threads = []
        agents = []

        for session_id in session_ids:
            # Create session
            session = session_manager.get_or_create(session_id)

            # Property 1: Initially, agent_thread should be None
            assert session.agent_thread is None, \
                f"Session {session_id} should have no thread reference initially"

            # Create mock agent
            agent = MockAgent(run_duration=run_duration)
            agents.append(agent)
            session_manager.update_session(session_id, agent=agent)

            # Get updated session
            session = session_manager.get(session_id)

            # Start agent thread
            thread = runner.start_agent_thread(session, queue_service)
            threads.append(thread)

            if use_async_mode:
                # Property 2: In async mode, thread should be returned
                assert thread is not None, \
                    f"start_agent_thread() should return a thread in async mode for session {session_id}"

                # Property 3: Returned thread should be a threading.Thread instance
                assert isinstance(thread, threading.Thread), \
                    f"Returned thread should be a threading.Thread instance for session {session_id}, got {type(thread)}"

                # Property 4: Store thread reference in session
                session_manager.update_session(session_id, agent_thread=thread)

                # Property 5: Thread reference should be stored in session
                session = session_manager.get(session_id)
                assert session.agent_thread is not None, \
                    f"Session {session_id} should have thread reference stored after update"

                # Property 6: Stored thread reference should match returned thread
                assert session.agent_thread == thread, \
                    f"Stored thread reference should match returned thread for session {session_id}"

                # Property 7: Stored thread reference should be the same object
                assert session.agent_thread is thread, \
                    f"Stored thread reference should be the same object (identity) for session {session_id}"

                # Property 8: Thread reference should have correct properties
                assert session.agent_thread.name == thread.name, \
                    f"Thread name should match for session {session_id}"
                assert session.agent_thread.ident == thread.ident, \
                    f"Thread ident should match for session {session_id}"
                assert session.agent_thread.daemon == thread.daemon, \
                    f"Thread daemon flag should match for session {session_id}"

                # Property 9: Thread reference can be used to check status
                # Give thread a moment to start
                time.sleep(0.01)
                is_alive = session.agent_thread.is_alive()
                assert isinstance(is_alive, bool), \
                    f"is_alive() should return a boolean for session {session_id}"
                # Thread should be alive shortly after start
                assert is_alive, \
                    f"Thread should be alive after start for session {session_id}"

                # Property 10: Thread reference persists across multiple retrievals
                session_2 = session_manager.get(session_id)
                assert session_2.agent_thread is thread, \
                    f"Thread reference should persist across retrievals for session {session_id}"

            else:
                # Synchronous mode
                # Property 11: In sync mode, no thread should be returned
                assert thread is None, \
                    f"start_agent_thread() should return None in synchronous mode for session {session_id}"

                # Property 12: Session should not have thread reference in sync mode
                session = session_manager.get(session_id)
                assert session.agent_thread is None, \
                    f"Session {session_id} should not have thread reference in synchronous mode"

        if use_async_mode:
            # Property 13: All sessions should have unique thread references
            stored_threads = []
            for session_id in session_ids:
                session = session_manager.get(session_id)
                stored_threads.append(session.agent_thread)

            # All thread references should be non-None
            assert all(t is not None for t in stored_threads), \
                "All sessions should have non-None thread references in async mode"

            # All thread references should be unique (different objects)
            thread_ids = [id(t) for t in stored_threads]
            unique_thread_ids = set(thread_ids)
            assert len(unique_thread_ids) == num_sessions, \
                f"Each session should have unique thread reference, expected {num_sessions}, got {len(unique_thread_ids)}"

            # Property 14: Thread references should match the threads list
            for i, session_id in enumerate(session_ids):
                session = session_manager.get(session_id)
                assert session.agent_thread is threads[i], \
                    f"Session {session_id} thread reference should match threads list"

            # Property 15: Thread references can be used for thread operations
            for i, session_id in enumerate(session_ids):
                session = session_manager.get(session_id)
                thread_ref = session.agent_thread

                # Can check if alive
                is_alive = thread_ref.is_alive()
                assert isinstance(is_alive, bool), \
                    f"Thread reference should support is_alive() for session {session_id}"

                # Can get thread name
                thread_name = thread_ref.name
                assert isinstance(thread_name, str), \
                    f"Thread reference should support name property for session {session_id}"
                assert session_id in thread_name, \
                    f"Thread name should contain session_id for session {session_id}"

                # Can get thread ident
                thread_ident = thread_ref.ident
                assert isinstance(thread_ident, int), \
                    f"Thread reference should support ident property for session {session_id}"

            # Property 16: Thread references remain valid while threads run
            # Check that all thread references are still valid
            for session_id in session_ids:
                session = session_manager.get(session_id)
                assert session.agent_thread is not None, \
                    f"Thread reference should remain valid for session {session_id}"
                assert isinstance(session.agent_thread, threading.Thread), \
                    f"Thread reference should remain a Thread instance for session {session_id}"

            # Property 17: Thread references can be used to join threads
            for i, session_id in enumerate(session_ids):
                session = session_manager.get(session_id)
                thread_ref = session.agent_thread

                # Join with timeout
                thread_ref.join(timeout=run_duration + 1.0)

                # After join, thread should not be alive
                assert not thread_ref.is_alive(), \
                    f"Thread should not be alive after join for session {session_id}"

            # Property 18: Thread references persist after thread completion
            for session_id in session_ids:
                session = session_manager.get(session_id)
                assert session.agent_thread is not None, \
                    f"Thread reference should persist after completion for session {session_id}"
                assert isinstance(session.agent_thread, threading.Thread), \
                    f"Thread reference should still be a Thread instance after completion for session {session_id}"

        else:
            # Synchronous mode
            # Property 19: No sessions should have thread references in sync mode
            for session_id in session_ids:
                session = session_manager.get(session_id)
                assert session.agent_thread is None, \
                    f"Session {session_id} should not have thread reference in synchronous mode"

            # Property 20: All threads list entries should be None in sync mode
            assert all(t is None for t in threads), \
                "All thread references should be None in synchronous mode"

        # Cleanup: wait for any remaining threads
        if use_async_mode:
            for thread in threads:
                if thread and thread.is_alive():
                    thread.join(timeout=run_duration + 1.0)

    finally:
        # Cleanup temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors


if __name__ == '__main__':
    print("Running property-based test for thread reference tracking...")
    print("Testing with 100 random configurations...")
    print()

    try:
        test_thread_reference_tracking()
        print("✓ Property test passed: Thread reference tracking verified")
        print("  Thread references are returned when threads are started")
        print("  Thread references can be stored in session.agent_thread")
        print("  Stored thread references match actual running threads")
        print("  Thread references persist in session after storage")
        print("  Thread references can be retrieved from session")
        print("  Multiple sessions have independent thread references")
        print("  Each session's thread reference is unique and correct")
        print("  Thread references remain valid while threads are running")
        print("  Thread references can be used to check thread status (is_alive())")
        print("  Thread references can be used to join threads")
        print("  In synchronous mode, no thread reference is stored (None)")
        print("  Thread references are properly typed (threading.Thread or None)")
        print("  Thread references persist after thread completion")
        print()
        print("  Test parameters varied:")
        print("    - Number of sessions: 1 to 10")
        print("    - Agent run duration: 0.05 to 0.3 seconds")
        print("    - Execution mode: async (True) or sync (False)")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("All property-based tests passed! ✓")
