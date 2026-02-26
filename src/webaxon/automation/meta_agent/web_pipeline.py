"""Factory for creating a web-configured MetaAgentPipeline.

Provides :func:`create_web_meta_agent_pipeline`, which injects
:class:`WebTargetConverter` and :data:`WEB_ACTION_TYPE_MAP` so that
``__id__`` targets are converted to stable web selectors and
``ElementInteraction.*`` types are mapped to canonical action types.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from science_modeling_tools.automation.meta_agent.evaluator import EvaluationRule
from science_modeling_tools.automation.meta_agent.models import PipelineConfig
from science_modeling_tools.automation.meta_agent.pipeline import MetaAgentPipeline
from science_modeling_tools.automation.meta_agent.synthetic_data import (
    SyntheticDataProvider,
)

from webaxon.automation.meta_agent.web_normalizer_config import WEB_ACTION_TYPE_MAP
from webaxon.automation.meta_agent.web_target_converter import WebTargetConverter


def create_web_meta_agent_pipeline(
    agent: Any,
    action_executor: Any,
    config: Optional[PipelineConfig] = None,
    *,
    synthetic_data_provider: Optional[SyntheticDataProvider] = None,
    action_metadata: Optional[Any] = None,
    inferencer: Optional[Any] = None,
    evaluation_rules: Optional[List[EvaluationRule]] = None,
    output_dir: Optional[Path] = None,
    stage_hook: Optional[Callable[[str, dict], None]] = None,
) -> MetaAgentPipeline:
    """Create a :class:`MetaAgentPipeline` pre-configured for WebAgent.

    Injects :class:`WebTargetConverter` and :data:`WEB_ACTION_TYPE_MAP`
    into the pipeline config so that:

    * ``__id__`` targets are converted to stable web selectors
      (CSS, XPath, aria, data attributes)
    * ``ElementInteraction.*`` action types are mapped to canonical types
      (``click``, ``input_text``, etc.)

    Parameters
    ----------
    agent:
        The web agent instance (e.g. ``WebAgent``).
    action_executor:
        The action executor for running synthesized graphs.
    config:
        Optional pipeline config.  If ``target_converter`` or
        ``custom_type_map`` are ``None``, web defaults are injected.
    synthetic_data_provider:
        Optional provider for synthetic test data.
    action_metadata:
        Optional action metadata for the normalizer / synthesizer.
    inferencer:
        Optional LLM inferencer (required for ``llm`` or ``hybrid``
        synthesis strategies).
    evaluation_rules:
        Optional list of evaluation rules for trace evaluation.

    Returns
    -------
    MetaAgentPipeline
        A pipeline instance ready for ``pipeline.run(task_description)``.
    """
    if config is None:
        config = PipelineConfig()

    if config.target_converter is None:
        config.target_converter = WebTargetConverter()

    if config.custom_type_map is None:
        config.custom_type_map = WEB_ACTION_TYPE_MAP

    return MetaAgentPipeline(
        agent=agent,
        action_executor=action_executor,
        config=config,
        synthetic_data_provider=synthetic_data_provider,
        action_metadata=action_metadata,
        inferencer=inferencer,
        evaluation_rules=evaluation_rules,
        output_dir=output_dir,
        stage_hook=stage_hook,
    )
