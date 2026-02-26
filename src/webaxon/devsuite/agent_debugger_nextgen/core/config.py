"""Configuration management for agent debugger.

This module provides centralized configuration with environment variable support.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DebuggerConfig:
    """Configuration for agent debugger.
    
    This class centralizes all configuration values for the debugger UI,
    supporting both default values and environment variable overrides.
    
    Attributes:
        queue_check_interval: Seconds between queue service checks
        log_monitor_interval: Seconds between log file checks
        max_monitor_messages: Maximum number of monitor messages to keep
        ui_port: Port for Dash web server
        ui_debug: Enable Dash debug mode
        ui_title: Title for the web UI
        debug_mode_debugger: Enable debug logging for debugger
        default_agent_type: Default agent type for new sessions
        console_display_rate_limit: Seconds between console messages (0 = no limit)
        enable_console_update: Enable in-place console updates
    """
    # Queue settings
    queue_check_interval: float = 5.0

    # Monitoring settings
    log_monitor_interval: float = 2.0
    max_monitor_messages: int = 10

    # UI settings
    ui_port: int = 8050
    ui_debug: bool = True
    ui_title: str = "Web Agent Debugger"

    # Debug modes
    debug_mode_debugger: bool = True

    # Agent defaults
    default_agent_type: str = 'DefaultAgent'

    # Console logging settings
    console_display_rate_limit: float = 2.0
    enable_console_update: bool = True
    
    @classmethod
    def from_env(cls, prefix: str = 'WEBAGENT_DEBUGGER_') -> 'DebuggerConfig':
        """Load configuration from environment variables.
        
        Environment variables are prefixed with the given prefix (default: WEBAGENT_DEBUGGER_).
        For example, to set ui_port, use WEBAGENT_DEBUGGER_UI_PORT=8080.
        
        Args:
            prefix: Prefix for environment variable names
            
        Returns:
            DebuggerConfig instance with values from environment or defaults
        """
        def get_env_float(key: str, default: float) -> float:
            """Get float from environment or return default."""
            value = os.getenv(f'{prefix}{key.upper()}')
            return float(value) if value is not None else default
        
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
        
        return cls(
            queue_check_interval=get_env_float('queue_check_interval', 5.0),
            log_monitor_interval=get_env_float('log_monitor_interval', 2.0),
            max_monitor_messages=get_env_int('max_monitor_messages', 10),
            ui_port=get_env_int('ui_port', 8050),
            ui_debug=get_env_bool('ui_debug', True),
            ui_title=get_env_str('ui_title', "Web Agent Debugger"),
            debug_mode_debugger=get_env_bool('debug_mode_debugger', True),
            default_agent_type=get_env_str('default_agent_type', 'DefaultAgent'),
            console_display_rate_limit=get_env_float('console_display_rate_limit', 2.0),
            enable_console_update=get_env_bool('enable_console_update', True)
        )
    
    def validate(self) -> None:
        """Validate configuration values.
        
        Raises:
            ValueError: If any configuration value is invalid
        """
        if not (1 <= self.ui_port <= 65535):
            raise ValueError(f"ui_port must be between 1 and 65535, got {self.ui_port}")
        
        if self.queue_check_interval <= 0:
            raise ValueError(f"queue_check_interval must be positive, got {self.queue_check_interval}")
        
        if self.log_monitor_interval <= 0:
            raise ValueError(f"log_monitor_interval must be positive, got {self.log_monitor_interval}")
        
        if self.max_monitor_messages < 1:
            raise ValueError(f"max_monitor_messages must be at least 1, got {self.max_monitor_messages}")
        
        if not self.default_agent_type:
            raise ValueError("default_agent_type cannot be empty")
