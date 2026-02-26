"""Template manager wrapper for version tracking.

This module provides a wrapper around the existing TemplateManager to add
version tracking capabilities for per-session template versioning.
"""
from pathlib import Path
from typing import Optional

from rich_python_utils.string_utils.formatting.template_manager import TemplateManager


class TemplateManagerWrapper:
    """Wrapper for TemplateManager with version tracking.
    
    This class wraps the existing TemplateManager to provide:
    - Version tracking for debugging and logging
    - Simplified version switching interface
    - Access to underlying TemplateManager functionality
    
    The wrapper delegates all template operations to the underlying
    TemplateManager while maintaining state about the current version.
    
    Example:
        >>> wrapper = TemplateManagerWrapper(Path('templates'))
        >>> wrapper.switch_version('v2.1')
        >>> print(wrapper.get_current_version())
        'v2.1'
        >>> tm = wrapper.get_template_manager()
    """
    
    def __init__(self, template_dir: Path, template_formatter):
        """Initialize the template manager wrapper.
        
        Args:
            template_dir: Path to the directory containing template files
            template_formatter: Template formatting function (e.g., handlebars_template_format)
        """
        self._template_manager = TemplateManager(
            templates=str(template_dir),
            template_formatter=template_formatter
        )
        self._current_version = ""
    
    def switch_version(self, template_version: str) -> TemplateManager:
        """Switch to specified template version.
        
        This method switches the underlying TemplateManager to use the
        specified template version and updates the internal version tracking.
        
        Args:
            template_version: Version identifier to switch to (e.g., 'v2.1', 'experimental')
                            Empty string means use default version
            
        Returns:
            The underlying TemplateManager instance for chaining
            
        Example:
            >>> wrapper.switch_version('v2.1')
            >>> # Now all template operations use v2.1 templates
        """
        if template_version:
            self._template_manager.switch(template_version=template_version)
            self._current_version = template_version
        else:
            # Empty string means default version - reset tracking
            self._current_version = ""
        
        return self._template_manager
    
    def get_current_version(self) -> str:
        """Get current template version.
        
        Returns:
            Current template version identifier, or empty string if using default
            
        Example:
            >>> wrapper.switch_version('v2.1')
            >>> print(wrapper.get_current_version())
            'v2.1'
        """
        return self._current_version
    
    def get_template_manager(self) -> TemplateManager:
        """Get underlying TemplateManager instance.
        
        This provides direct access to the wrapped TemplateManager for
        operations that need the full TemplateManager interface.
        
        Returns:
            The underlying TemplateManager instance
            
        Example:
            >>> tm = wrapper.get_template_manager()
            >>> tm.switch(active_template_type='reflection')
        """
        return self._template_manager
    
    def switch(self, **kwargs) -> TemplateManager:
        """Delegate switch calls to underlying TemplateManager.
        
        This convenience method allows direct switching of template
        parameters without explicitly getting the underlying manager.
        
        Args:
            **kwargs: Arguments to pass to TemplateManager.switch()
            
        Returns:
            The underlying TemplateManager instance for chaining
            
        Example:
            >>> wrapper.switch(active_template_root_space='response_agent')
            >>> wrapper.switch(active_template_type='reflection')
        """
        return self._template_manager.switch(**kwargs)
