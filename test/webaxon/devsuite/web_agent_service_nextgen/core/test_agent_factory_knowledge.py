"""Unit tests for AgentFactory knowledge integration.

Tests that the AgentFactory correctly creates and manages a KnowledgeProvider
when a knowledge_data_file is configured, and falls back to MOCK_USER_PROFILE
when not configured.

Requirements: 3.1, 3.4, 7.1, 7.2
"""
import sys
import tempfile
import pytest
from unittest.mock import MagicMock
from pathlib import Path

import resolve_path  # Setup import paths

from webaxon.devsuite.web_agent_service_nextgen.core.config import ServiceConfig
from webaxon.devsuite.web_agent_service_nextgen.core.agent_factory import AgentFactory
from agent_foundation.knowledge import KnowledgeProvider


# Path to the grocery store knowledge data file
GROCERY_DATA_FILE = str(
    Path(__file__).resolve().parent.parent.parent.parent
    / 'webaxon' / 'webaxon' / 'grocery_store_testcase' / 'knowledge_data.json'
)


@pytest.fixture
def mock_template_manager():
    """Create a mock TemplateManager for AgentFactory tests."""
    tm = MagicMock()
    tm.switch = MagicMock(return_value=tm)
    return tm


class TestAgentFactoryKnowledge:
    """Tests for AgentFactory knowledge integration."""

    def test_create_knowledge_provider_with_config(self, mock_template_manager, tmp_path):
        """Test _create_knowledge_provider returns KnowledgeProvider when configured.

        Requirements: 3.1
        """
        config = ServiceConfig(knowledge_data_file=GROCERY_DATA_FILE)
        factory = AgentFactory(mock_template_manager, config, testcase_root=tmp_path)
        assert factory._provider is not None
        assert isinstance(factory._provider, KnowledgeProvider)
        factory.close()

    def test_create_knowledge_provider_without_config(self, mock_template_manager, tmp_path):
        """Test _create_knowledge_provider always creates a provider even without config.

        The provider is always created with file-based stores at
        testcase_root/_runtime/knowledge_store/.

        Requirements: 3.4
        """
        config = ServiceConfig()  # knowledge_data_file defaults to None
        factory = AgentFactory(mock_template_manager, config, testcase_root=tmp_path)
        assert factory._provider is not None
        factory.close()

    def test_user_profile_none_when_provider_active(self, mock_template_manager, tmp_path):
        """Test _load_user_profile returns None when provider is active.

        When a KnowledgeProvider is configured, user_profile should be None
        because the provider supplies it via the knowledge_provider attribute.

        Requirements: 3.1
        """
        config = ServiceConfig(knowledge_data_file=GROCERY_DATA_FILE)
        factory = AgentFactory(mock_template_manager, config, testcase_root=tmp_path)
        assert factory._user_profile is None
        factory.close()

    def test_user_profile_loaded_when_no_provider(self, mock_template_manager, tmp_path):
        """Test _load_user_profile returns None because provider is always created.

        Since _create_knowledge_provider() now always creates a KnowledgeProvider
        (with file-based stores at testcase_root/_runtime/knowledge_store/),
        _load_user_profile() returns None when the provider exists.

        Requirements: 3.4
        """
        config = ServiceConfig()
        factory = AgentFactory(mock_template_manager, config, testcase_root=tmp_path)
        assert factory._user_profile is None
        factory.close()

    def test_close_calls_provider_close(self, mock_template_manager, tmp_path):
        """Test close() calls provider.close().

        Requirements: 7.1, 7.2
        """
        config = ServiceConfig(knowledge_data_file=GROCERY_DATA_FILE)
        factory = AgentFactory(mock_template_manager, config, testcase_root=tmp_path)
        # Replace provider with a mock to verify close() is called
        mock_provider = MagicMock()
        factory._provider = mock_provider
        factory.close()
        mock_provider.close.assert_called_once()

    def test_close_safe_when_no_provider(self, mock_template_manager, tmp_path):
        """Test close() is safe when no provider exists.

        Since _create_knowledge_provider() always creates a provider now,
        we explicitly set it to None to verify close() handles that case.

        Requirements: 7.2
        """
        config = ServiceConfig()
        factory = AgentFactory(mock_template_manager, config, testcase_root=tmp_path)
        factory._provider = None
        factory.close()  # Should not raise
