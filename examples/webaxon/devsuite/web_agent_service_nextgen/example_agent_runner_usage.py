"""Example usage of AgentRunner.

This script demonstrates how AgentRunner will be used in the service.
"""
import resolve_path  # Sets up Python path for webaxon imports
from unittest.mock import Mock

from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import AgentSession, AgentSessionInfo
from webaxon.devsuite.web_agent_service_nextgen.agents.agent_runner import AgentRunner


def example_production_mode():
    """Example: Running agent in production mode (async threads)."""
    print("\n=== Production Mode Example ===\n")
    
    # Create config for production (async mode)
    config = ServiceConfig(
        synchronous_agent=False,
        debug_mode_service=True
    )
    
    # Create agent runner
    runner = AgentRunner(config)
    
    # Create mock session (in real service, this comes from SessionManager)
    session = Mock(spec=AgentSession)
    session.session_id = 'prod_session_123'
    session.info = Mock(spec=AgentSessionInfo)
    session.info.agent_type = 'DefaultAgent'
    session.agent = Mock()
    session.agent.run = Mock(return_value='completed')
    session.interactive = Mock()

    # Create mock queue service
    queue_service = Mock()

    # Start agent in thread
    print("Starting agent in separate thread...")
    thread = runner.start_agent_thread(session, queue_service)
    
    if thread:
        print(f"✓ Agent thread created: {thread.name}")
        print(f"  Thread is alive: {thread.is_alive()}")
        print(f"  Thread is daemon: {thread.daemon}")
        print("  Service can continue processing other requests...")
        
        # Wait for completion
        thread.join(timeout=2.0)
        print(f"✓ Agent thread completed")
    else:
        print("✗ No thread created (unexpected in async mode)")


def example_debug_mode():
    """Example: Running agent in debug mode (synchronous)."""
    print("\n=== Debug Mode Example ===\n")
    
    # Create config for debugging (sync mode)
    config = ServiceConfig(
        synchronous_agent=True,
        debug_mode_service=True
    )
    
    # Create agent runner
    runner = AgentRunner(config)
    
    # Create mock session
    session = Mock(spec=AgentSession)
    session.session_id = 'debug_session_456'
    session.info = Mock(spec=AgentSessionInfo)
    session.info.agent_type = 'DefaultAgent'
    session.agent = Mock()
    session.agent.run = Mock(return_value='completed')
    session.interactive = Mock()
    session.info.last_agent_status = None

    # Create mock queue service
    queue_service = Mock()

    # Start agent synchronously
    print("Running agent synchronously (blocks until complete)...")
    thread = runner.start_agent_thread(session, queue_service)

    if thread is None:
        print("✓ No thread created (expected in sync mode)")
        print("✓ Agent ran synchronously in main process")
        print(f"  Final status: {session.info.last_agent_status}")
        print("  This mode enables debugger attachment and step-through debugging")
    else:
        print("✗ Thread created (unexpected in sync mode)")


def example_error_handling():
    """Example: Error handling during agent execution."""
    print("\n=== Error Handling Example ===\n")
    
    # Create config
    config = ServiceConfig(synchronous_agent=False)
    
    # Create agent runner
    runner = AgentRunner(config)
    
    # Create mock session with failing agent
    session = Mock(spec=AgentSession)
    session.session_id = 'error_session_789'
    session.info = Mock(spec=AgentSessionInfo)
    session.info.agent_type = 'DefaultAgent'
    session.agent = Mock()
    session.agent.run = Mock(side_effect=RuntimeError('Simulated error'))
    session.interactive = Mock()
    session.info.last_agent_status = None

    # Create mock queue service
    queue_service = Mock()

    # Start agent (will fail)
    print("Starting agent that will fail...")
    thread = runner.start_agent_thread(session, queue_service)

    if thread:
        print(f"✓ Agent thread created: {thread.name}")

        # Wait for completion
        thread.join(timeout=2.0)

        print(f"✓ Error handled gracefully")
        print(f"  Final status: {session.info.last_agent_status}")
        print(f"  Error response sent: {session.interactive.send_response.called}")


def example_service_integration():
    """Example: How AgentRunner integrates with the service."""
    print("\n=== Service Integration Example ===\n")
    
    print("In the WebAgentService main loop:")
    print("""
    # 1. SessionMonitor detects message waiting
    if message_waiting and not session.agent:
        # 2. AgentFactory creates agent
        agent = agent_factory.create_agent(
            interactive=session.interactive,
            logger=session.logger,
            agent_type=session.agent_type
        )
        session.agent = agent
        
        # 3. AgentRunner starts agent
        thread = agent_runner.start_agent_thread(
            session_info=session,
            queue_service=queue_service
        )
        
        # 4. Store thread reference
        if thread:
            session.agent_thread = thread
            print(f"Agent started in thread: {thread.name}")
        else:
            print("Agent running synchronously (debug mode)")
    """)
    
    print("\nKey benefits:")
    print("  • Clean separation of concerns")
    print("  • Easy to test in isolation")
    print("  • Flexible execution modes")
    print("  • Comprehensive error handling")


def main():
    """Run all examples."""
    print("=" * 70)
    print("AgentRunner Usage Examples")
    print("=" * 70)
    
    example_production_mode()
    example_debug_mode()
    example_error_handling()
    example_service_integration()
    
    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
