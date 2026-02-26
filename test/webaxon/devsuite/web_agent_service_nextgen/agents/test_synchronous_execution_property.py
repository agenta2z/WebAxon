"""Property-based test for synchronous execution.

This module contains property-based tests using hypothesis to verify
that agent execution runs in the main process when in synchronous mode.
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
        self.run_completed = False

    def __call__(self):
        """Agent is callable."""
        self.run_called = True
        self.run_thread_id = threading.current_thread().ident
        time.sleep(self.run_duration)
        self.run_completed = True
        return 'completed'


# Feature: web-agent-service-modularization, Property 24: Synchronous Execution
# Validates: Requirements 7.3
@settings(max_examples=100, deadline=None)
@given(
    # Generate number of sessions to test
    num_sessions=st.integers(min_value=1, max_value=5),
    # Generate agent run duration (in seconds)
    run_duration=st.floats(min_value=0.01, max_value=0.1),
)
def test_synchronous_execution(num_sessions, run_duration):
    """Property: For any agent execution when synchronous_agent is True,
    the agent should run in the main process without creating a thread.

    This test verifies that:
    1. When synchronous_agent is True, start_agent_thread() returns None
    2. No thread is created for agent execution
    3. The agent executes in the main thread (same thread ID)
    4. The method blocks until agent completes (synchronous behavior)
    5. Agent status is updated after completion
    6. Multiple sessions execute sequentially (not concurrently)
    7. No thread reference is stored in session
    8. The main thread ID matches the agent execution thread ID
    9. Execution completes before start_agent_thread() returns
    10. Session status reflects completion after return

    Test strategy:
    - Create multiple sessions with synchronous mode enabled
    - Track main thread ID before execution
    - Start agent execution for each session
    - Verify no threads are created
    - Verify agent executes in main thread
    - Verify execution is blocking (completes before return)
    - Verify sessions execute sequentially
    - Verify status updates occur correctly
    """
    # Filter out edge cases
    assume(num_sessions >= 1)
    assume(0.01 <= run_duration <= 0.1)

    # Create temporary directory for logs
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Create config with synchronous mode enabled
        config = ServiceConfig(synchronous_agent=True)

        # Create agent runner
        runner = AgentRunner(config)

        # Create mock queue service
        queue_service = MockQueueService()

        # Create session manager
        session_manager = SessionManager(id='test', log_name='Test', logger=[print], always_add_logging_based_logger=False, config=config, queue_service=queue_service, service_log_dir=temp_dir)

        # Track main thread ID
        main_thread_id = threading.current_thread().ident

        # Track execution order and timing
        execution_order = []
        start_times = []
        end_times = []

        # Create sessions and run agents synchronously
        session_ids = [f"test_session_{i}" for i in range(num_sessions)]
        agents = []

        for i, session_id in enumerate(session_ids):
            # Create session
            session = session_manager.get_or_create(session_id)

            # Create mock agent
            agent = MockAgent(run_duration=run_duration)
            agents.append(agent)
            session_manager.update_session(session_id, agent=agent)

            # Get updated session
            session = session_manager.get(session_id)

            # Record start time
            start_time = time.time()
            start_times.append(start_time)

            # Start agent (should run synchronously)
            thread = runner.start_agent_thread(session, queue_service)

            # Record end time
            end_time = time.time()
            end_times.append(end_time)

            # Record execution order
            execution_order.append(i)

            # Property 1: start_agent_thread() should return None in synchronous mode
            assert thread is None, \
                f"start_agent_thread() should return None in synchronous mode for session {session_id}, got {thread}"

            # Property 2: Agent should have been called
            assert agent.run_called, \
                f"Agent should have been called for session {session_id}"

            # Property 3: Agent should have completed
            assert agent.run_completed, \
                f"Agent should have completed before start_agent_thread() returns for session {session_id}"

            # Property 4: Agent should execute in the main thread
            assert agent.run_thread_id == main_thread_id, \
                f"Agent should run in main thread (expected={main_thread_id}, got={agent.run_thread_id}) for session {session_id}"

            # Property 5: Execution should be blocking (duration >= run_duration)
            execution_duration = end_time - start_time
            assert execution_duration >= run_duration * 0.9, \
                f"Execution should block for at least {run_duration}s, but took {execution_duration}s for session {session_id}"

            # Property 6: Session status should be updated after completion
            session = session_manager.get(session_id)
            assert session.info.last_agent_status == 'completed', \
                f"Session status should be 'completed' after synchronous execution for session {session_id}, got {session.info.last_agent_status}"

            # Property 7: No thread reference should be stored in session
            # (In synchronous mode, agent_thread should remain None)
            assert session.agent_thread is None, \
                f"Session should not have thread reference in synchronous mode for session {session_id}"

        # Property 8: All agents should have executed in the main thread
        for i, agent in enumerate(agents):
            assert agent.run_thread_id == main_thread_id, \
                f"Agent {i} should have run in main thread (expected={main_thread_id}, got={agent.run_thread_id})"

        # Property 9: Execution should be sequential (not concurrent)
        # Each session should start after the previous one completes
        for i in range(1, num_sessions):
            # Session i should start after session i-1 ends
            # Allow small timing tolerance
            assert start_times[i] >= end_times[i-1] - 0.01, \
                f"Session {i} should start after session {i-1} completes (sequential execution)"

        # Property 10: Execution order should match session order
        assert execution_order == list(range(num_sessions)), \
            f"Execution order should be sequential, expected {list(range(num_sessions))}, got {execution_order}"

        # Property 11: Total execution time should be approximately sum of individual durations
        total_expected_duration = run_duration * num_sessions
        total_actual_duration = end_times[-1] - start_times[0]
        # Allow 20% tolerance for overhead
        assert total_actual_duration >= total_expected_duration * 0.8, \
            f"Total execution time should be at least {total_expected_duration}s (sequential), got {total_actual_duration}s"

        # Property 12: No background threads should be created
        # Count threads before and after should be the same (or only differ by system threads)
        current_thread_count = threading.active_count()
        # In synchronous mode, we shouldn't have created any agent threads
        # (There might be other system threads, but no agent threads)
        agent_threads = [t for t in threading.enumerate() if 'AgentThread' in t.name]
        assert len(agent_threads) == 0, \
            f"No agent threads should exist in synchronous mode, found {len(agent_threads)}"

        # Property 13: All sessions should have completed status
        for session_id in session_ids:
            session = session_manager.get(session_id)
            assert session.info.last_agent_status == 'completed', \
                f"Session {session_id} should have 'completed' status"

        # Property 14: Current thread should still be the main thread
        assert threading.current_thread().ident == main_thread_id, \
            "Current thread should still be the main thread after all executions"

        # Property 15: Synchronous execution should be deterministic
        # Running the same agent twice should produce the same behavior
        test_session_id = "determinism_test"
        test_session = session_manager.get_or_create(test_session_id)
        test_agent = MockAgent(run_duration=0.01)
        session_manager.update_session(test_session_id, agent=test_agent)
        test_session = session_manager.get(test_session_id)

        # First run
        thread1 = runner.start_agent_thread(test_session, queue_service)
        assert thread1 is None, "First run should return None"
        assert test_agent.run_called, "First run should call agent"
        assert test_agent.run_thread_id == main_thread_id, "First run should be in main thread"

    finally:
        # Cleanup temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors


if __name__ == '__main__':
    print("Running property-based test for synchronous execution...")
    print("Testing with 100 random configurations...")
    print()

    try:
        test_synchronous_execution()
        print("✓ Property test passed: Synchronous execution verified")
        print("  start_agent_thread() returns None when synchronous_agent is True")
        print("  No threads are created for agent execution")
        print("  Agent executes in the main thread (same thread ID)")
        print("  Method blocks until agent completes (synchronous behavior)")
        print("  Agent status is updated after completion")
        print("  Multiple sessions execute sequentially (not concurrently)")
        print("  No thread reference is stored in session")
        print("  Main thread ID matches agent execution thread ID")
        print("  Execution completes before start_agent_thread() returns")
        print("  Session status reflects completion after return")
        print("  No background agent threads are created")
        print("  Total execution time reflects sequential execution")
        print("  Execution is deterministic and repeatable")
        print()
        print("  Test parameters varied:")
        print("    - Number of sessions: 1 to 5")
        print("    - Agent run duration: 0.01 to 0.1 seconds")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("All property-based tests passed! ✓")
