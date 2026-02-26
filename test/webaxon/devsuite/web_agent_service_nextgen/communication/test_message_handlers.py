"""Test message handlers implementation.

This test verifies that the MessageHandlers class correctly processes
different types of control messages and sends appropriate responses.
"""
import sys
import resolve_path  # Setup import paths

from pathlib import Path

# Add parent directory to path for imports
from rich_python_utils.service_utils.queue_service.storage_based_queue_service import StorageBasedQueueService
from rich_python_utils.datetime_utils.common import timestamp
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_template_format
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager

from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.session import SessionManager
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from webaxon.devsuite.web_agent_service_nextgen.communication.message_handlers import MessageHandlers


def test_message_handlers():
    """Test message handlers with mock queue service."""
    print("=" * 80)
    print("Testing Message Handlers")
    print("=" * 80)
    
    # Setup
    testcase_root = Path(__file__).parent / '_test_runtime'
    testcase_root.mkdir(exist_ok=True)
    
    # Create config
    config = ServiceConfig()
    
    # Create queue service
    queue_root = testcase_root / 'queues' / timestamp()
    queue_root.mkdir(parents=True, exist_ok=True)
    queue_service = StorageBasedQueueService(
        root_path=str(queue_root),
        archive_popped_items=True
    )
    
    # Create required queues
    queue_service.create_queue(config.input_queue_id)
    queue_service.create_queue(config.response_queue_id)
    queue_service.create_queue(config.client_control_queue_id)
    queue_service.create_queue(config.server_control_queue_id)
    
    # Create session manager
    service_log_dir = testcase_root / '_runtime'
    session_manager = SessionManager(
        id='test', log_name='Test', logger=[print],
        always_add_logging_based_logger=False,
        config=config, queue_service=queue_service,
        service_log_dir=service_log_dir,
    )
    
    # Create template manager
    template_dir = Path(__file__).parent.parent.parent.parent.parent.parent / 'test' / 'webaxon' / 'webaxon' / 'grocery_store_testcase' / 'prompt_templates'
    if not template_dir.exists():
        print(f"Warning: Template directory not found: {template_dir}")
        print("Creating minimal template manager...")
        template_dir = testcase_root / 'templates'
        template_dir.mkdir(exist_ok=True)
        # Create proper subdirectory structure for TemplateManager
        for subdir in ['planning_agent', 'action_agent', 'response_agent', 'reflection']:
            (template_dir / subdir).mkdir(parents=True, exist_ok=True)
            (template_dir / subdir / 'default.hbs').write_text('{{input}}')
    
    template_manager = TemplateManager(
        templates=str(template_dir),
        template_formatter=handlebars_template_format
    )
    
    # Create agent factory
    agent_factory = AgentFactory(template_manager, config, testcase_root=testcase_root)
    
    # Create message handlers
    message_handlers = MessageHandlers(
        session_manager=session_manager,
        agent_factory=agent_factory,
        queue_service=queue_service,
        config=config
    )
    
    print("\n✓ Message handlers initialized")
    
    # Test 1: sync_active_sessions
    print("\n" + "-" * 80)
    print("Test 1: sync_active_sessions")
    print("-" * 80)
    
    sync_message = {
        'type': 'sync_active_sessions',
        'message': {
            'active_sessions': ['session1', 'session2']
        },
        'timestamp': timestamp()
    }
    
    message_handlers.dispatch(sync_message)
    
    # Check response
    response = queue_service.get(config.client_control_queue_id, blocking=False)
    if response:
        print(f"✓ Response received: {response['type']}")
        print(f"  Active sessions: {response.get('active_sessions', [])}")
    else:
        print("✗ No response received")
    
    # Test 2: sync_session_agent
    print("\n" + "-" * 80)
    print("Test 2: sync_session_agent")
    print("-" * 80)
    
    agent_sync_message = {
        'type': 'sync_session_agent',
        'message': {
            'session_id': 'test_session_1',
            'agent_type': 'DefaultAgent'
        },
        'timestamp': timestamp()
    }
    
    message_handlers.dispatch(agent_sync_message)
    
    # Check response
    response = queue_service.get(config.client_control_queue_id, blocking=False)
    if response:
        print(f"✓ Response received: {response['type']}")
        print(f"  Session ID: {response.get('session_id')}")
        print(f"  Agent type: {response.get('agent_type')}")
        print(f"  Agent status: {response.get('agent_status')}")
        print(f"  Agent created: {response.get('agent_created')}")
    else:
        print("✗ No response received")
    
    # Test 3: sync_session_template_version
    print("\n" + "-" * 80)
    print("Test 3: sync_session_template_version")
    print("-" * 80)
    
    template_sync_message = {
        'type': 'sync_session_template_version',
        'message': {
            'session_id': 'test_session_1',
            'template_version': 'v2.1'
        },
        'timestamp': timestamp()
    }
    
    message_handlers.dispatch(template_sync_message)
    
    # Check response
    response = queue_service.get(config.client_control_queue_id, blocking=False)
    if response:
        print(f"✓ Response received: {response['type']}")
        print(f"  Session ID: {response.get('session_id')}")
        print(f"  Template version: {response.get('template_version')}")
    else:
        print("✗ No response received")
    
    # Test 4: agent_control (without actual agent)
    print("\n" + "-" * 80)
    print("Test 4: agent_control")
    print("-" * 80)
    
    control_message = {
        'type': 'agent_control',
        'message': {
            'session_id': 'test_session_1',
            'control': 'pause'
        },
        'timestamp': timestamp()
    }
    
    message_handlers.dispatch(control_message)
    
    # Check response
    response = queue_service.get(config.client_control_queue_id, blocking=False)
    if response:
        print(f"✓ Response received: {response['type']}")
        print(f"  Session ID: {response.get('session_id')}")
        print(f"  Control: {response.get('control')}")
        print(f"  Success: {response.get('success')}")
    else:
        print("✗ No response received")
    
    # Test 5: Unknown message type
    print("\n" + "-" * 80)
    print("Test 5: Unknown message type")
    print("-" * 80)
    
    unknown_message = {
        'type': 'unknown_message_type',
        'message': {},
        'timestamp': timestamp()
    }
    
    message_handlers.dispatch(unknown_message)
    print("✓ Unknown message handled gracefully (no crash)")
    
    # Test 6: Verify session was created
    print("\n" + "-" * 80)
    print("Test 6: Verify session state")
    print("-" * 80)
    
    session = session_manager.get('test_session_1')
    if session:
        print(f"✓ Session exists: test_session_1")
        print(f"  Agent type: {session.info.session_type}")
        print(f"  Template version: {session.info.template_version}")
        print(f"  Agent created: {session.info.initialized}")
    else:
        print("✗ Session not found")
    
    # Cleanup
    queue_service.close()
    
    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == '__main__':
    test_message_handlers()
