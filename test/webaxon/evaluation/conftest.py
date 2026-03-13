"""
Hypothesis strategies and shared fixtures for evaluation module tests.

Provides reusable strategies for generating random instances of:
- EvalResult
- EvaluationTask
- EvaluationConfig

Used by property-based tests across the evaluation module.
Settings: @settings(max_examples=100) as per spec.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# Path resolution for imports
_current_file = Path(__file__).resolve()
_current_path = _current_file.parent
while _current_path.name != "test" and _current_path.parent != _current_path:
    _current_path = _current_path.parent
_src_dir = _current_path.parent / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

# Also add RichPythonUtils src to path (provides rich_python_utils.mp_utils for evaluator)
_rpu_src = Path(__file__).resolve().parents[4] / "RichPythonUtils" / "src"
if _rpu_src.exists() and str(_rpu_src) not in sys.path:
    sys.path.insert(0, str(_rpu_src))

import pytest
from hypothesis import strategies as st

from webaxon.evaluation.protocol import EvalResult
from webaxon.evaluation.tasks import EvaluationTask
from webaxon.evaluation.config import EvaluationConfig


# ── Shared helper strategies ─────────────────────────────────────────────────

# Non-empty text (must have non-whitespace chars)
_non_empty_text = st.text(min_size=1).filter(lambda s: s.strip())

# Windows reserved device names that cannot be used as directory names
_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})

# Simple identifier text (excluding Windows reserved device names)
_identifier_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.upper() not in _WINDOWS_RESERVED)

# URL strategy — generates plausible URLs
_url_strategy = st.from_regex(
    r"https://[a-z]{3,12}\.(com|org|net)/[a-z0-9/]{0,30}",
    fullmatch=True,
)

# Confidence in [0.0, 1.0]
_confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Duration in seconds (positive)
_duration_strategy = st.floats(
    min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False,
)

# Difficulty levels matching load_tasks() expectations
_level_strategy = st.sampled_from(["easy", "medium", "hard"])

# Screenshot path strategy
_screenshot_path_strategy = st.builds(
    lambda n: Path(f"{n}_screenshot.png"),
    st.integers(min_value=0, max_value=99),
)

# Action history entry (JSON-like string)
_action_entry_strategy = st.one_of(
    st.just('{"source": "https://example.com", "action_skipped": false}'),
    st.builds(
        lambda t, tgt: f'{{"type": "{t}", "target": "{tgt}"}}',
        st.sampled_from(["click", "input_text", "scroll", "visit_url", "wait"]),
        st.integers(min_value=1, max_value=200).map(str),
    ),
)

# Readable action entry
_readable_action_strategy = st.one_of(
    st.just("CLICK [target=42]"),
    st.builds(
        lambda t, n: f"{t} [target={n}]",
        st.sampled_from(["CLICK", "INPUT", "SCROLL", "NAVIGATE"]),
        st.integers(min_value=1, max_value=200),
    ),
)


# ── EvalResult strategy ─────────────────────────────────────────────────────


@st.composite
def eval_result_strategy(draw, with_error=False):
    """Generate a random EvalResult instance.

    Parameters
    ----------
    with_error:
        If True, always include an error message.
        If False, error is randomly None or a string.
    """
    num_steps = draw(st.integers(min_value=0, max_value=10))

    answer = draw(_non_empty_text)
    confidence = draw(_confidence_strategy)
    action_history = draw(st.lists(_action_entry_strategy, min_size=num_steps, max_size=num_steps))
    action_history_readable = draw(
        st.lists(_readable_action_strategy, min_size=num_steps, max_size=num_steps)
    )
    thoughts = draw(st.lists(st.text(max_size=100), max_size=num_steps))
    raw_generations = draw(st.lists(st.text(max_size=200), max_size=num_steps))
    screenshot_paths = draw(
        st.lists(_screenshot_path_strategy, min_size=num_steps, max_size=num_steps)
    )
    duration_seconds = draw(_duration_strategy)

    if with_error:
        error = draw(_non_empty_text)
    else:
        error = draw(st.one_of(st.none(), _non_empty_text))

    metadata = draw(
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(max_size=50), st.integers(), st.booleans()),
            max_size=3,
        )
    )

    return EvalResult(
        answer=answer,
        confidence=confidence,
        action_history=action_history,
        action_history_readable=action_history_readable,
        thoughts=thoughts,
        raw_generations=raw_generations,
        screenshot_paths=screenshot_paths,
        duration_seconds=duration_seconds,
        error=error,
        metadata=metadata,
    )


# ── EvaluationTask strategy ─────────────────────────────────────────────────


@st.composite
def evaluation_task_strategy(draw):
    """Generate a random EvaluationTask instance.

    Fields match the JSONL format expected by load_tasks():
    - task_id: non-empty identifier
    - task: non-empty description
    - start_url: valid-looking URL
    - reference_length: non-negative int
    - level: one of easy/medium/hard
    """
    task_id = draw(_identifier_text)
    task = draw(_non_empty_text)
    start_url = draw(_url_strategy)
    reference_length = draw(st.integers(min_value=0, max_value=100))
    level = draw(_level_strategy)

    return EvaluationTask(
        task_id=task_id,
        task=task,
        start_url=start_url,
        reference_length=reference_length,
        level=level,
    )


# ── EvaluationConfig strategy ───────────────────────────────────────────────


@st.composite
def evaluation_config_strategy(draw):
    """Generate a random EvaluationConfig instance.

    - adapter_name: simple string
    - adapter_config: small dict of JSON-serializable values
    - max_steps: positive int
    - agent_timeout: positive int
    - stay_on_start_url: bool
    - output_dir: Path
    """
    adapter_name = draw(st.sampled_from(["webaxon", "custom", "test_adapter"]))
    adapter_config = draw(
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(max_size=50), st.integers(), st.booleans()),
            max_size=3,
        )
    )
    max_steps = draw(st.integers(min_value=1, max_value=200))
    agent_timeout = draw(st.integers(min_value=1, max_value=3600))
    stay_on_start_url = draw(st.booleans())
    output_dir = Path(draw(st.sampled_from(["runs", "output", "eval_runs", "tmp/runs"])))

    return EvaluationConfig(
        adapter_name=adapter_name,
        adapter_config=adapter_config,
        max_steps=max_steps,
        agent_timeout=agent_timeout,
        stay_on_start_url=stay_on_start_url,
        output_dir=output_dir,
    )


# ── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_task() -> EvaluationTask:
    """A fixed EvaluationTask for deterministic unit tests."""
    return EvaluationTask(
        task_id="task_001",
        task="Find the price of item X",
        start_url="https://example.com",
        reference_length=5,
        level="easy",
    )


@pytest.fixture
def sample_result() -> EvalResult:
    """A fixed EvalResult for deterministic unit tests."""
    return EvalResult(
        answer="done",
        confidence=0.9,
        action_history=['{"type": "click", "target": "1"}'],
        action_history_readable=["CLICK [target=1]"],
        thoughts=["thinking"],
        raw_generations=["raw output"],
        screenshot_paths=[Path("0_screenshot.png")],
        duration_seconds=10.0,
    )


@pytest.fixture
def sample_config() -> EvaluationConfig:
    """A fixed EvaluationConfig for deterministic unit tests."""
    return EvaluationConfig(
        adapter_name="webaxon",
        max_steps=50,
        agent_timeout=600,
    )


# ── E2E test options and markers ────────────────────────────────────────────


def pytest_addoption(parser):
    """Add CLI options for e2e tests."""
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run real end-to-end agent tests (slow, requires browser + API keys)",
    )
    parser.addoption(
        "--webaxon-workspace",
        default=None,
        help="WebAxon workspace (testcase_root) directory",
    )
    parser.addoption(
        "--eval-inferencer",
        choices=["openai", "claude"],
        default="openai",
        help="Inferencer backend for evaluation (default: openai)",
    )
    parser.addoption(
        "--eval-model",
        default=None,
        help="Model ID for evaluation inferencer",
    )
    parser.addoption(
        "--agent-type",
        default="DefaultAgent",
        help="WebAxon agent type (default: DefaultAgent)",
    )
    parser.addoption(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: real end-to-end test (needs browser + API keys)")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-e2e"):
        skip_e2e = pytest.mark.skip(reason="need --run-e2e option to run")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)
