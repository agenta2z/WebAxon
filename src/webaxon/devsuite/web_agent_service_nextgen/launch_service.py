"""
Launch Script for Web Agent Service

Entry point for starting the modular web agent service.
This script initializes the service with proper configuration and starts
the main service loop.
"""
import sys
import argparse
from pathlib import Path

# Add source paths if needed
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent.parent

# Add project root
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add science packages
rich_python_utils_src = project_root / "SciencePythonUtils" / "src"
agent_foundation_src = project_root / "ScienceModelingTools" / "src"
webagent_src = project_root / "WebAgent" / "src"

for path_item in [rich_python_utils_src, agent_foundation_src, webagent_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

# Import service components
from webaxon.devsuite.web_agent_service_nextgen.service import WebAgentService
from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig


def parse_arguments():
    """Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Web Agent Service - Modular queue-based agent service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start service with default workspace (_workspace/)
  python launch_service.py

  # Start service with custom workspace
  python launch_service.py /path/to/workspace

  # Start service with custom timeout
  WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=3600 python launch_service.py

  # Start service in synchronous mode for debugging
  WEBAGENT_SERVICE_SYNCHRONOUS_AGENT=true python launch_service.py

Environment Variables:
  WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT      Session idle timeout in seconds (default: 1800)
  WEBAGENT_SERVICE_CLEANUP_CHECK_INTERVAL    Cleanup check interval in seconds (default: 300)
  WEBAGENT_SERVICE_DEBUG_MODE_SERVICE        Enable debug logging (default: true)
  WEBAGENT_SERVICE_SYNCHRONOUS_AGENT         Run agents synchronously (default: false)
  WEBAGENT_SERVICE_NEW_AGENT_ON_FIRST_SUBMISSION  Create agents lazily (default: true)
  WEBAGENT_SERVICE_DEFAULT_AGENT_TYPE        Default agent type (default: DefaultAgent)
  WEBAGENT_SERVICE_INPUT_QUEUE_ID            Input queue ID (default: user_input)
  WEBAGENT_SERVICE_RESPONSE_QUEUE_ID         Response queue ID (default: agent_response)
  WEBAGENT_SERVICE_CLIENT_CONTROL_QUEUE_ID   Client control queue ID (default: client_control)
  WEBAGENT_SERVICE_SERVER_CONTROL_QUEUE_ID   Server control queue ID (default: server_control)
  WEBAGENT_SERVICE_QUEUE_ROOT_PATH           Custom queue root path (optional)
  WEBAGENT_SERVICE_LOG_ROOT_PATH             Log root path (default: _runtime)
  WEBAGENT_SERVICE_TEMPLATE_DIR              Prompt templates directory name (default: prompt_templates)

For more information, see README.md
        """
    )
    
    # Default workspace: _workspace/ next to this script
    default_workspace = Path(__file__).resolve().parent / '_workspace'

    parser.add_argument(
        'testcase_root',
        nargs='?',
        type=Path,
        default=default_workspace,
        help=f'Workspace root directory (default: {default_workspace})'
    )
    
    parser.add_argument(
        '--config-file',
        type=Path,
        help='Path to configuration file (optional, environment variables take precedence)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode (overrides environment variable)'
    )
    
    parser.add_argument(
        '--synchronous',
        action='store_true',
        help='Run agents synchronously for debugging (overrides environment variable)'
    )
    
    return parser.parse_args()


def main():
    """Run the web agent service.
    
    This function:
    1. Parses command line arguments
    2. Loads configuration from environment variables
    3. Applies command line overrides
    4. Creates and runs the service
    """
    # Parse arguments
    args = parse_arguments()
    
    # Validate testcase root
    if not args.testcase_root.exists():
        print(f"Error: Testcase root does not exist: {args.testcase_root}")
        sys.exit(1)
    
    if not args.testcase_root.is_dir():
        print(f"Error: Testcase root is not a directory: {args.testcase_root}")
        sys.exit(1)
    
    # Load configuration from environment
    config = ServiceConfig.from_env()
    
    # Apply command line overrides
    if args.debug:
        config.debug_mode_service = True
    
    if args.synchronous:
        config.synchronous_agent = True
    
    # Print startup banner
    print("=" * 80)
    print("WEB AGENT SERVICE - Modular Queue-Based Architecture")
    print("=" * 80)
    print(f"Testcase Root: {args.testcase_root}")
    print(f"Debug Mode: {config.debug_mode_service}")
    print(f"Synchronous Agent: {config.synchronous_agent}")
    print(f"Session Idle Timeout: {config.session_idle_timeout}s")
    print(f"Cleanup Check Interval: {config.cleanup_check_interval}s")
    print(f"New Agent on First Submission: {config.new_agent_on_first_submission}")
    print(f"Default Agent Type: {config.default_agent_type}")
    print(f"Template Directory: {args.testcase_root / config.template_dir}")
    print("-" * 80)
    print("Queue Configuration:")
    print(f"  Input Queue: {config.input_queue_id}")
    print(f"  Response Queue: {config.response_queue_id}")
    print(f"  Client Control Queue: {config.client_control_queue_id}")
    print(f"  Server Control Queue: {config.server_control_queue_id}")
    print("-" * 80)
    print("Starting service... (Press Ctrl+C to stop)")
    print("=" * 80)
    print()
    
    try:
        # Create and run service
        service = WebAgentService(args.testcase_root, config)
        service.run()
    
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\nService stopped")


if __name__ == '__main__':
    main()
