"""Real-LLM characterization tests for FindElementInferencer.

These tests hit the real Claude API and so are gated behind:

- ``@pytest.mark.integration`` — opt-in via ``-m integration``.
- ``ANTHROPIC_API_KEY`` env var — auto-skip if absent.

They use the bundled ``google_search.html`` corpus (a captured Google homepage)
and the real Handlebars-formatted ``find_element.hbs`` template. The
assertions are **behavioral**, not byte-equality, because LLM output is
non-deterministic. We assert that:

1. The returned xpath is a non-empty string.
2. The xpath resolves to ≥1 element when evaluated against the source HTML.

**Important characterization note.** Descriptions are chosen for elements that
survive ``clean_html`` aggressive sanitization. Notably the actual Google
search ``<textarea>`` is stripped out, so descriptions like "the search input
box" reliably yield ``NOT_FOUND`` under the current implementation — those are
not useful characterization targets. The tests below target ``<input>``,
``<a>``, and ``<button>`` elements that DO appear in the sanitized prompt.

Run cost: ~$0.05–$0.20 per call × 3 tests ≈ $0.15–$0.60 per run. Manual only.
"""
import os

import pytest

from webaxon.automation.agents.find_element_inferencer import (
    FindElementInferencer,
    FindElementInferenceConfig,
)
from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import (
    ClaudeApiInferencer,
)
from rich_python_utils.string_utils.formatting.template_manager.template_manager import (
    TemplateManager,
)
from rich_python_utils.string_utils.formatting.handlebars_format import (
    format_template as handlebars_format,
)


# Skip the whole module if the API key is missing — these are real-LLM tests.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY env var required for real-LLM tests",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def google_search_html(webaxon_root):
    """Load the bundled google_search.html corpus.

    Verified path: ``WebAxon/examples/webaxon/automation/schema/google_search/google_search.html``.
    The example file ``example_find_element_google_search.py:38`` references a
    different (broken) path — we deliberately use the real one.
    """
    fixture_path = (
        webaxon_root
        / "examples"
        / "webaxon"
        / "automation"
        / "schema"
        / "google_search"
        / "google_search.html"
    )
    if not fixture_path.exists():
        pytest.skip(f"google_search.html fixture not found at {fixture_path}")
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def real_template_manager():
    templates_dir = os.path.join(
        "WebAxon", "src", "webaxon", "automation", "agents", "prompt_templates"
    )
    return TemplateManager(
        templates=templates_dir,
        template_formatter=handlebars_format,
    )


@pytest.fixture(scope="module")
def real_find_element_inferencer(real_template_manager):
    """Real FindElementInferencer wired to the live Claude API."""
    reasoner = ClaudeApiInferencer(
        max_retry=3,
        min_retry_wait=1.0,
        max_retry_wait=5.0,
    )
    return FindElementInferencer(
        base_inferencer=reasoner,
        template_manager=real_template_manager,
        max_html_length=50000,  # match the example's truncation for fairness
    )


def _xpath_resolves(html: str, xpath: str) -> int:
    """Return the number of elements ``xpath`` matches in ``html``."""
    from lxml import etree

    tree = etree.HTML(html)
    return len(tree.xpath(xpath))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_real_find_google_search_submit_button(
    real_find_element_inferencer, google_search_html, request
):
    """LLM must return a usable xpath for the Google Search submit button.

    Targets ``<input name="btnK" type="submit" aria-label="Google Search">`` —
    survives ``clean_html`` (kept ``name`` and ``type`` attrs), so reliably
    findable end-to-end.
    """
    xpath = real_find_element_inferencer(
        html_source=google_search_html,
        description="the Google Search submit button",
    )
    assert isinstance(xpath, str) and xpath, "xpath must be a non-empty string"
    matches = _xpath_resolves(google_search_html, xpath)
    request.node.user_properties.append(("xpath", xpath))
    request.node.user_properties.append(("matches", matches))
    assert matches >= 1, f"xpath {xpath!r} resolved to 0 elements"


def test_real_find_im_feeling_lucky_button(
    real_find_element_inferencer, google_search_html, request
):
    """LLM must return a usable xpath for the I'm Feeling Lucky button.

    Targets ``<input name="btnI" type="submit" aria-label="I'm Feeling Lucky">``.
    """
    xpath = real_find_element_inferencer(
        html_source=google_search_html,
        description="the I'm Feeling Lucky button",
    )
    assert isinstance(xpath, str) and xpath
    matches = _xpath_resolves(google_search_html, xpath)
    request.node.user_properties.append(("xpath", xpath))
    request.node.user_properties.append(("matches", matches))
    assert matches >= 1, f"xpath {xpath!r} resolved to 0 elements"


def test_real_find_with_options_hint(
    real_find_element_inferencer, google_search_html, request
):
    """Same query (Google Search submit button), but with ``options=['static']``
    propagated through the template. Verifies options round-trip end-to-end —
    the option string must reach the rendered prompt without breaking the
    inference path.
    """
    cfg = FindElementInferenceConfig(options=["static"])
    xpath = real_find_element_inferencer(
        html_source=google_search_html,
        description="the Google Search submit button",
        inference_config=cfg,
    )
    assert isinstance(xpath, str) and xpath
    matches = _xpath_resolves(google_search_html, xpath)
    request.node.user_properties.append(("xpath", xpath))
    request.node.user_properties.append(("matches", matches))
    assert matches >= 1, f"xpath {xpath!r} resolved to 0 elements"
