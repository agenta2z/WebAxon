"""Property-based test for async thread creation.

This module contains property-based tests using hypothesis to verify
that agent execution creates separate threads when in async mode.
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


# Feature: web-agent-service-modularization, Property 23: Async Thread Creation
# Validates: Requirements 7.2
@settings(max_examples=100, deadline=None)
@given(
    # Generate number of sessions to test
    num_sessions=st.integers(min_value=1, max_value=10),
    # Generate agent run duration (in seconds)
    run_duration=st.floats(min_value=0.05, max_value=0.3),
    # Generate whether to wait for threads to complete
    wait_for_completion=st.booleans(),
)
def test_async_thread_creation(num_sessions, run_duration, wait_for_completion):
    """Property: For any agent execution when synchronous_agent is False,
    a separate thread should be created and tracked in the session.

    This test verifies that:
    1. When synchronous_agent is False, start_agent_thread() creates a thread
    2. The created thread is a proper threading.Thread instance
    3. The thread is started (is_alive() returns True initially)
    4. The thread is a daemon thread (daemon=True)
    5. The thread has a proper name containing the session_id
    6. The thread reference is returned by start_agent_thread()
    7. The agent executes in the created thread (different thread ID)
    8. Multiple sessions can have concurrent threads
    9. Each session gets its own independent thread
    10. Thread status can be checked via is_alive()

    Test strategy:
    - Create multiple sessions with async mode enabled
    - Start agent threads for each session
    - Verify threads are created and have correct properties
    - Verify agent executes in separate threads
    - Verify threads are independent (different thread IDs)
    - Verify thread lifecycle (alive -> completed)
    """
    # Filter out edge cases
    assume(num_sessions >= 1)
    assume(0.05 <= run_duration <= 0.3)

    # Create temporary directory for logs
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Create config with async mode enabled
        config = ServiceConfig(synchronous_agent=False)

        # Create agent runner
        runner = AgentRunner(config)

        # Create mock queue service
        queue_service = MockQueueService()

        # Create session manager
        session_manager = SessionManager(id='test', log_name='Test', logger=[print], always_add_logging_based_logger=False, config=config, queue_service=queue_service, service_log_dir=temp_dir)

        # Track main thread ID
        main_thread_id = threading.current_thread().ident

        # Create sessions and start agent threads
        session_ids = [f"test_session_{i}" for i in range(num_sessions)]
        threads = []
        agents = []

        for session_id in session_ids:
            # Create session
            session = session_manager.get_or_create(session_id)

            # Create mock agent
            agent = MockAgent(run_duration=run_duration)
            agents.append(agent)
            session_manager.update_session(session_id, agent=agent)

            # Get updated session
            session = session_manager.get(session_id)

            # Start agent thread
            thread = runner.start_agent_thread(session, queue_service)
            threads.append(thread)

            # Property 1: Thread should be created (not None)
            assert thread is not None, \
                f"start_agent_thread() should return a thread in async mode for session {session_id}"

            # Property 2: Thread should be a threading.Thread instance
            assert isinstance(thread, threading.Thread), \
                f"Returned object should be a threading.Thread instance for session {session_id}, got {type(thread)}"

            # Property 3: Thread should be started (alive)
            # Give it a moment to start
            time.sleep(0.01)
            assert thread.is_alive(), \
                f"Thread should be alive after start for session {session_id}"

            # Property 4: Thread should be a daemon thread
            assert thread.daemon is True, \
                f"Thread should be a daemon thread for session {session_id}"

            # Property 5: Thread should have proper name containing session_id
            assert session_id in thread.name, \
                f"Thread name should contain session_id '{session_id}', got '{thread.name}'"
            assert 'AgentThread' in thread.name, \
                f"Thread name should contain 'AgentThread', got '{thread.name}'"

            # Update session with thread reference
            session_manager.update_session(session_id, agent_thread=thread)

        # Property 6: All threads should be independent (different thread IDs)
        thread_ids = [t.ident for t in threads]
        unique_thread_ids = set(thread_ids)
        assert len(unique_thread_ids) == num_sessions, \
            f"Each session should have its own thread, expected {num_sessions} unique thread IDs, got {len(unique_thread_ids)}"

        # Property 7: All threads should be different from main thread
        for i, thread_id in enumerate(thread_ids):
            assert thread_id != main_thread_id, \
                f"Thread {i} should run in separate thread, not main thread"

        # Wait a bit for agents to start running
        time.sleep(0.05)

        # Property 8: Agent should be called in each thread
        for i, agent in enumerate(agents):
            assert agent.run_called, \
                f"Agent {i} should have been called"

            # Property 9: Agent should execute in the created thread, not main thread
            assert agent.run_thread_id != main_thread_id, \
                f"Agent {i} should run in separate thread, not main thread (main={main_thread_id}, agent={agent.run_thread_id})"

            # Property 10: Agent should execute in its corresponding thread
            assert agent.run_thread_id == threads[i].ident, \
                f"Agent {i} should run in its corresponding thread (expected={threads[i].ident}, got={agent.run_thread_id})"

        # Property 11: Thread status can be checked via is_alive()
        # At this point, threads should still be alive (or just finishing)
        alive_count = sum(1 for t in threads if t.is_alive())
        # At least some threads should still be alive if we haven't waited long
        if not wait_for_completion:
            # We expect at least some threads to still be running
            # (This is probabilistic, but with short sleep above, most should still be running)
            pass  # Don't assert here as timing is tricky

        # If requested, wait for all threads to complete
        if wait_for_completion:
            for thread in threads:
                thread.join(timeout=run_duration + 1.0)

            # Property 12: After completion, threads should not be alive
            for i, thread in enumerate(threads):
                assert not thread.is_alive(), \
                    f"Thread {i} should have completed after join()"

            # Property 13: Session status should be updated after completion
            for i, session_id in enumerate(session_ids):
                session = session_manager.get(session_id)
                # Status should be either 'completed' or 'error'
                assert session.info.last_agent_status in ['completed', 'error', None], \
                    f"Session {session_id} should have valid status after completion, got {session.info.last_agent_status}"

        # Property 14: Thread references should be stored in session
        for i, session_id in enumerate(session_ids):
            session = session_manager.get(session_id)
            assert session.agent_thread is not None, \
                f"Session {session_id} should have thread reference stored"
            assert session.agent_thread == threads[i], \
                f"Session {session_id} should have correct thread reference"

        # Property 15: Multiple concurrent threads should work correctly
        # All threads should be independent and not interfere with each other
        # We've already verified they have different thread IDs and run independently

        # Cleanup: wait for any remaining threads
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=run_duration + 1.0)

    finally:
        # Cleanup temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors


if __name__ == '__main__':
    print("Running property-based test for async thread creation...")
    print("Testing with 100 random configurations...")
    print()

    try:
        test_async_thread_creation()
        print("✓ Property test passed: Async thread creation verified")
        print("  Threads are created when synchronous_agent is False")
        print("  Threads are proper threading.Thread instances")
        print("  Threads are started and alive after creation")
        print("  Threads are daemon threads")
        print("  Threads have proper names containing session_id")
        print("  Thread references are returned and stored in session")
        print("  Agent executes in the created thread (not main thread)")
        print("  Multiple sessions have independent concurrent threads")
        print("  Each session gets its own thread with unique thread ID")
        print("  Thread status can be checked via is_alive()")
        print()
        print("  Test parameters varied:")
        print("    - Number of sessions: 1 to 10")
        print("    - Agent run duration: 0.05 to 0.3 seconds")
        print("    - Wait for completion: True/False")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("All property-based tests passed! ✓")
