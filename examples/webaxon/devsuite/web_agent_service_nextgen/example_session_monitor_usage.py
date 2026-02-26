"""Example usage of SessionMonitor.

This script demonstrates how to use the SessionMonitor class for
background monitoring of agent sessions.
"""
import resolve_path  # Sets up Python path for webaxon imports
import time
from unittest.mock import Mock

from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager, AgentSession, AgentSessionInfo
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.session.agent_session_monitor import AgentSessionMonitor


def example_basic_usage():
    """Example: Basic SessionMonitor usage."""
    print("=" * 60)
    print("Example 1: Basic SessionMonitor Usage")
    print("=" * 60)
    
    # Create dependencies (mocked for example)
    session_manager = Mock(spec=SessionManager)
    session_manager.get_all_sessions.return_value = {}
    queue_service = Mock()
    config = ServiceConfig()
    agent_factory = Mock(spec=AgentFactory)
    
    # Create SessionMonitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory
    )
    
    print("✓ SessionMonitor created")
    print(f"  - Cleanup interval: {config.cleanup_check_interval}s")
    print(f"  - Session idle timeout: {config.session_idle_timeout}s")
    print(f"  - Lazy agent creation: {config.new_agent_on_first_submission}")
    
    # Run monitoring cycle
    print("\nRunning monitoring cycle...")
    monitor.run_monitoring_cycle()
    print("✓ Monitoring cycle completed")


def example_status_change_detection():
    """Example: Status change detection."""
    print("\n" + "=" * 60)
    print("Example 2: Status Change Detection")
    print("=" * 60)
    
    # Create dependencies
    session_manager = Mock(spec=SessionManager)
    queue_service = Mock()
    config = ServiceConfig()
    agent_factory = Mock(spec=AgentFactory)
    
    # Create mock session with agent
    session = Mock(spec=AgentSession)
    session.session_id = 'example_session'
    session.info = Mock(spec=AgentSessionInfo)
    session.info.agent_created = True
    session.agent = Mock()
    session.agent_thread = Mock()
    session.agent_thread.is_alive.return_value = True
    session.info.last_agent_status = None

    session_manager.get_all_sessions.return_value = {
        'example_session': session
    }

    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory
    )

    print("Session state:")
    print(f"  - Session ID: {session.session_id}")
    print(f"  - Agent created: {session.info.agent_created}")
    print(f"  - Last status: {session.info.last_agent_status}")
    
    # Check for status changes
    print("\nChecking for status changes...")
    monitor.check_status_changes()
    
    # Verify status was updated
    if session_manager.update_session.called:
        print("✓ Status change detected and acknowledged")
        print(f"  - New status: running")
    else:
        print("✓ No status changes detected")


def example_periodic_cleanup():
    """Example: Periodic cleanup."""
    print("\n" + "=" * 60)
    print("Example 3: Periodic Cleanup")
    print("=" * 60)
    
    # Create dependencies
    session_manager = Mock(spec=SessionManager)
    queue_service = Mock()
    config = ServiceConfig()
    config.cleanup_check_interval = 2  # 2 seconds for demo
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory
    )
    
    print(f"Cleanup interval: {config.cleanup_check_interval}s")
    print(f"Last cleanup: {monitor._last_cleanup_time}")
    
    # First check - should not cleanup (just initialized)
    print("\nFirst check (just initialized)...")
    monitor.periodic_cleanup()
    if not session_manager.cleanup_idle_sessions.called:
        print("✓ Cleanup skipped (interval not elapsed)")
    
    # Wait for interval to elapse
    print(f"\nWaiting {config.cleanup_check_interval + 1}s for interval to elapse...")
    monitor._last_cleanup_time = time.time() - (config.cleanup_check_interval + 1)
    
    # Second check - should cleanup
    print("Second check (interval elapsed)...")
    monitor.periodic_cleanup()
    if session_manager.cleanup_idle_sessions.called:
        print("✓ Cleanup executed")
        print(f"  - New last cleanup time: {monitor._last_cleanup_time}")


def example_error_resilience():
    """Example: Error resilience."""
    print("\n" + "=" * 60)
    print("Example 4: Error Resilience")
    print("=" * 60)
    
    # Create dependencies with error-throwing session manager
    session_manager = Mock(spec=SessionManager)
    session_manager.get_all_sessions.side_effect = Exception("Simulated error")
    queue_service = Mock()
    config = ServiceConfig()
    agent_factory = Mock(spec=AgentFactory)
    
    # Create monitor
    monitor = AgentSessionMonitor(
        session_manager=session_manager,
        queue_service=queue_service,
        config=config,
        agent_factory=agent_factory
    )
    
    print("Simulating error in session manager...")
    
    # Try to check status changes - should not crash
    try:
        monitor.check_status_changes()
        print("✓ Error handled gracefully")
        print("  - Service continues operation")
        print("  - Error logged but not raised")
    except Exception as e:
        print(f"✗ Error not handled: {e}")


def example_integration_pattern():
    """Example: Integration pattern for main service."""
    print("\n" + "=" * 60)
    print("Example 5: Integration Pattern")
    print("=" * 60)
    
    print("""
Integration pattern for WebAgentService:

```python
class WebAgentService:
    def __init__(self, testcase_root: Path, config: Optional[ServiceConfig] = None):
        # ... initialize other components ...
        
        # Create SessionMonitor
        self._session_monitor = SessionMonitor(
            session_manager=self._session_manager,
            queue_service=queue_service,
            config=self._config,
            agent_factory=self._agent_factory
        )
    
    def run(self):
        # Main service loop
        while not self._shutdown_requested:
            try:
                # Process control messages
                control_msg = queue_service.get(
                    self._config.client_control_queue_id,
                    blocking=False
                )
                if control_msg:
                    self._message_handlers.dispatch(control_msg)
                
                # Run monitoring cycle
                self._session_monitor.run_monitoring_cycle()
                
                # Small sleep to prevent tight loop
                time.sleep(0.1)
                
            except Exception as e:
                self._global_debugger.log_error(f'Error in main loop: {e}')
                time.sleep(1)
```

Key points:
1. Create SessionMonitor in __init__() with all dependencies
2. Call run_monitoring_cycle() in main service loop
3. Monitor handles all errors gracefully
4. Service continues operation despite monitoring failures
    """)


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("SessionMonitor Usage Examples")
    print("=" * 60)
    
    example_basic_usage()
    example_status_change_detection()
    example_periodic_cleanup()
    example_error_resilience()
    example_integration_pattern()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
