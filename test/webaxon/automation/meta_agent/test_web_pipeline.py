"""Tests for create_web_meta_agent_pipeline factory."""

from __future__ import annotations

from unittest.mock import MagicMock

from science_modeling_tools.automation.meta_agent.models import PipelineConfig
from science_modeling_tools.automation.meta_agent.pipeline import MetaAgentPipeline

from webaxon.automation.meta_agent.web_normalizer_config import WEB_ACTION_TYPE_MAP
from webaxon.automation.meta_agent.web_pipeline import create_web_meta_agent_pipeline
from webaxon.automation.meta_agent.web_target_converter import WebTargetConverter


class TestCreateWebMetaAgentPipeline:
    """Tests for the create_web_meta_agent_pipeline factory function."""

    def test_returns_pipeline_instance(self):
        pipeline = create_web_meta_agent_pipeline(
            agent=MagicMock(),
            action_executor=MagicMock(),
        )
        assert isinstance(pipeline, MetaAgentPipeline)

    def test_injects_web_target_converter_by_default(self):
        config = PipelineConfig()
        create_web_meta_agent_pipeline(
            agent=MagicMock(),
            action_executor=MagicMock(),
            config=config,
        )
        assert isinstance(config.target_converter, WebTargetConverter)

    def test_injects_web_action_type_map_by_default(self):
        config = PipelineConfig()
        create_web_meta_agent_pipeline(
            agent=MagicMock(),
            action_executor=MagicMock(),
            config=config,
        )
        assert config.custom_type_map is WEB_ACTION_TYPE_MAP

    def test_preserves_existing_target_converter(self):
        custom_converter = MagicMock()
        config = PipelineConfig(target_converter=custom_converter)
        create_web_meta_agent_pipeline(
            agent=MagicMock(),
            action_executor=MagicMock(),
            config=config,
        )
        assert config.target_converter is custom_converter

    def test_preserves_existing_custom_type_map(self):
        custom_map = {"MyAction": "my_action"}
        config = PipelineConfig(custom_type_map=custom_map)
        create_web_meta_agent_pipeline(
            agent=MagicMock(),
            action_executor=MagicMock(),
            config=config,
        )
        assert config.custom_type_map is custom_map

    def test_creates_default_config_when_none(self):
        pipeline = create_web_meta_agent_pipeline(
            agent=MagicMock(),
            action_executor=MagicMock(),
            config=None,
        )
        assert isinstance(pipeline, MetaAgentPipeline)

    def test_passes_kwargs_through(self):
        mock_provider = MagicMock()
        mock_metadata = MagicMock()
        pipeline = create_web_meta_agent_pipeline(
            agent=MagicMock(),
            action_executor=MagicMock(),
            synthetic_data_provider=mock_provider,
            action_metadata=mock_metadata,
        )
        assert isinstance(pipeline, MetaAgentPipeline)

    def test_custom_config_values_preserved(self):
        config = PipelineConfig(
            run_count=10,
            validate=True,
            synthesis_strategy="rule_based",
        )
        create_web_meta_agent_pipeline(
            agent=MagicMock(),
            action_executor=MagicMock(),
            config=config,
        )
        assert config.run_count == 10
        assert config.validate is True
        assert config.synthesis_strategy == "rule_based"
        # Web defaults should still be injected
        assert isinstance(config.target_converter, WebTargetConverter)
        assert config.custom_type_map is WEB_ACTION_TYPE_MAP
