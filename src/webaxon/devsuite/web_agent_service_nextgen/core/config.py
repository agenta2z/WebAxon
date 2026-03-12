"""Configuration management for web agent service.

This module provides centralized configuration with environment variable support.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ServiceConfig:
    """Configuration for web agent service.
    
    This class centralizes all configuration values for the service,
    supporting both default values and environment variable overrides.
    
    Attributes:
        session_idle_timeout: Seconds before idle session cleanup (default: 30 minutes)
        cleanup_check_interval: Seconds between cleanup checks (default: 5 minutes)
        debug_mode_service: Enable debug logging for service
        synchronous_agent: Run agents synchronously for debugging
        new_agent_on_first_submission: Create agents lazily on first message
        default_agent_type: Default agent type for new sessions
        input_queue_id: Queue ID for user input messages
        response_queue_id: Queue ID for agent response messages
        client_control_queue_id: Queue ID for client control messages
        server_control_queue_id: Queue ID for server control messages
        queue_root_path: Optional custom queue root path
        log_root_path: Root path for log files
        template_dir: Directory name for prompt templates (relative to testcase_root)
        knowledge_data_file: Optional path to knowledge data JSON file for knowledge provider
        chrome_version: Chrome major version to pin ChromeDriver (e.g. 145). None = auto-detect.
    """
    # Session management
    session_idle_timeout: int = 30 * 60  # 30 minutes in seconds
    cleanup_check_interval: int = 5 * 60  # 5 minutes in seconds
    
    # Debug modes
    debug_mode_service: bool = True
    synchronous_agent: bool = False
    
    # Agent behavior
    new_agent_on_first_submission: bool = True
    default_agent_type: str = 'DefaultAgent'

    # Browser
    chrome_version: Optional[int] = None  # Chrome major version (e.g. 145) to pin ChromeDriver
    
    # Queue IDs
    input_queue_id: str = 'user_input'
    response_queue_id: str = 'agent_response'
    client_control_queue_id: str = 'client_control'
    server_control_queue_id: str = 'server_control'
    
    # Paths
    queue_root_path: Optional[str] = None
    log_root_path: str = '_runtime'
    template_dir: str = 'prompt_templates'
    knowledge_data_file: Optional[str] = None

    # Knowledge consolidation
    knowledge_consolidation_mode: str = "disabled"  # "enabled", "disabled", "disabled_for_short_knowledge"
    knowledge_consolidation_short_threshold: int = 200  # tokens (count_tokens units, ~800 chars)

    @classmethod
    def from_env(cls, prefix: str = 'WEBAGENT_SERVICE_') -> 'ServiceConfig':
        """Load configuration from environment variables.
        
        Environment variables are prefixed with the given prefix (default: WEBAGENT_SERVICE_).
        For example, to set session_idle_timeout, use WEBAGENT_SERVICE_SESSION_IDLE_TIMEOUT=3600.
        
        Args:
            prefix: Prefix for environment variable names
            
        Returns:
            ServiceConfig instance with values from environment or defaults
        """
        def get_env_int(key: str, default: int) -> int:
            """Get int from environment or return default."""
            value = os.getenv(f'{prefix}{key.upper()}')
            return int(value) if value is not None else default
        
        def get_env_bool(key: str, default: bool) -> bool:
            """Get bool from environment or return default."""
            value = os.getenv(f'{prefix}{key.upper()}')
            if value is None:
                return default
            return value.lower() in ('true', '1', 'yes', 'on')
        
        def get_env_str(key: str, default: str) -> str:
            """Get string from environment or return default."""
            return os.getenv(f'{prefix}{key.upper()}', default)
        
        def get_env_optional_str(key: str) -> Optional[str]:
            """Get optional string from environment."""
            return os.getenv(f'{prefix}{key.upper()}')
        
        return cls(
            session_idle_timeout=get_env_int('session_idle_timeout', 30 * 60),
            cleanup_check_interval=get_env_int('cleanup_check_interval', 5 * 60),
            debug_mode_service=get_env_bool('debug_mode_service', True),
            synchronous_agent=get_env_bool('synchronous_agent', False),
            new_agent_on_first_submission=get_env_bool('new_agent_on_first_submission', True),
            default_agent_type=get_env_str('default_agent_type', 'DefaultAgent'),
            input_queue_id=get_env_str('input_queue_id', 'user_input'),
            response_queue_id=get_env_str('response_queue_id', 'agent_response'),
            client_control_queue_id=get_env_str('client_control_queue_id', 'client_control'),
            server_control_queue_id=get_env_str('server_control_queue_id', 'server_control'),
            queue_root_path=get_env_optional_str('queue_root_path'),
            log_root_path=get_env_str('log_root_path', '_runtime'),
            template_dir=get_env_str('template_dir', 'prompt_templates'),
            knowledge_data_file=get_env_optional_str('knowledge_data_file'),
            chrome_version=get_env_int('chrome_version', 0) or None,
            knowledge_consolidation_mode=get_env_str('knowledge_consolidation_mode', 'disabled'),
            knowledge_consolidation_short_threshold=get_env_int('knowledge_consolidation_short_threshold', 200),
        )
    
    def validate(self) -> None:
        """Validate configuration values.
        
        Raises:
            ValueError: If any configuration value is invalid
        """
        # Validate timeouts are positive
        if self.session_idle_timeout <= 0:
            raise ValueError(
                f"session_idle_timeout must be positive, got {self.session_idle_timeout}"
            )
        
        if self.cleanup_check_interval <= 0:
            raise ValueError(
                f"cleanup_check_interval must be positive, got {self.cleanup_check_interval}"
            )
        
        # Validate queue IDs are non-empty
        queue_ids = [
            ('input_queue_id', self.input_queue_id),
            ('response_queue_id', self.response_queue_id),
            ('client_control_queue_id', self.client_control_queue_id),
            ('server_control_queue_id', self.server_control_queue_id),
        ]
        
        for name, value in queue_ids:
            if not value or not value.strip():
                raise ValueError(f"{name} cannot be empty")
        
        # Validate agent type is non-empty
        if not self.default_agent_type or not self.default_agent_type.strip():
            raise ValueError("default_agent_type cannot be empty")
        
        # Validate log root path is non-empty
        if not self.log_root_path or not self.log_root_path.strip():
            raise ValueError("log_root_path cannot be empty")
