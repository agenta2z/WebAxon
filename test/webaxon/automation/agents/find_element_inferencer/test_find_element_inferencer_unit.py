"""Mocked, deterministic characterization tests for FindElementInferencer.

These tests exist to pin down the wrapper-era behavior so the migration off
``TemplatedInferencer`` (composition wrapper) onto ``TemplatedInferencerBase``
(inheritance) can be verified to be a no-op for callers. Every test here must
pass both BEFORE and AFTER the migration.

Mock strategy:
- ``base_inferencer`` is a ``MagicMock`` returning canned ``<TargetElementID>``
  responses; this is the boundary where we don't want to spend money or hit
  network in unit tests.
- ``template_manager`` is the **real** ``TemplateManager`` constructed against
  the bundled ``find_element.hbs`` (handlebars formatter) — template format
  compatibility is itself a migration risk, so we exercise the real renderer.
- WebDriver tests use a tiny stand-in object exposing the surface the
  inferencer actually touches (``page_source`` + ``_backend._driver``) and
  patch ``add_unique_index_to_elements`` (the only real-Selenium escape hatch).
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from webaxon.automation.agents.find_element_inferencer import (
    FindElementInferencer,
    FindElementInferenceConfig,
    _parse_element_id,
)
from webaxon.html_utils.element_identification import ATTR_NAME_INCREMENTAL_ID
from rich_python_utils.string_utils.formatting.template_manager.template_manager import (
    TemplateManager,
)
from rich_python_utils.string_utils.formatting.handlebars_format import (
    format_template as handlebars_format,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Synthetic HTML with elements that survive `clean_html` (input/button/a have
# attribute classes preserved; div/body/etc are stripped). These are what the
# LLM would actually see at the prompt.
_SAMPLE_HTML = (
    "<html><body>"
    '<div class="container">'
    '<input type="text" name="q" />'
    '<button type="submit" class="search-btn">Search</button>'
    '<a href="https://example.com" class="lucky-link">Feeling Lucky</a>'
    "</div>"
    "</body></html>"
)


@pytest.fixture
def real_template_manager():
    """Real TemplateManager with the bundled find_element.hbs template."""
    templates_dir = os.path.join(
        "WebAxon", "src", "webaxon", "automation", "agents", "prompt_templates"
    )
    return TemplateManager(
        templates=templates_dir,
        template_formatter=handlebars_format,
    )


@pytest.fixture
def mock_base_inferencer():
    """MagicMock base inferencer returning a canned LLM response.

    Default response targets element ``__id__=2`` which (under the synthetic
    HTML above) maps to the ``<input>`` element after ``add_unique_index_to_html``.
    Tests that need a different ID override ``return_value`` directly.
    """
    inf = MagicMock()
    inf.return_value = "<TargetElementID>2</TargetElementID>"
    return inf


@pytest.fixture
def make_find_element_inferencer(real_template_manager, mock_base_inferencer):
    """Factory that builds a FindElementInferencer with the supplied (or default)
    base_inferencer + real template_manager. Pass ``base_inferencer=`` to inject
    a custom mock for tests that assert on call args.
    """
    def _factory(*, base_inferencer=None, max_html_length=None):
        kwargs = dict(
            base_inferencer=base_inferencer or mock_base_inferencer,
            template_manager=real_template_manager,
        )
        if max_html_length is not None:
            kwargs["max_html_length"] = max_html_length
        return FindElementInferencer(**kwargs)
    return _factory


class _FakeWebDriver:
    """Minimal WebDriver stand-in matching the surface ``FindElementInferencer``
    actually touches: ``page_source`` (str) + ``_backend._driver`` (anything,
    handed to the patched ``add_unique_index_to_elements``).
    """
    def __init__(self, html: str):
        self.page_source = html
        self._backend = MagicMock()
        self._backend._driver = MagicMock()


# ---------------------------------------------------------------------------
# Tests 1–2: constructor
# ---------------------------------------------------------------------------

def test_constructor_minimal(real_template_manager, mock_base_inferencer):
    """FindElementInferencer constructs cleanly with just (base, template_manager)."""
    inf = FindElementInferencer(
        base_inferencer=mock_base_inferencer,
        template_manager=real_template_manager,
    )
    assert inf.base_inferencer is mock_base_inferencer
    assert inf.template_manager is real_template_manager
    # Default field values that callers rely on:
    assert inf.max_html_length is None


def test_constructor_with_max_html_length(real_template_manager, mock_base_inferencer):
    """max_html_length is stored on the instance."""
    inf = FindElementInferencer(
        base_inferencer=mock_base_inferencer,
        template_manager=real_template_manager,
        max_html_length=1000,
    )
    assert inf.max_html_length == 1000


# ---------------------------------------------------------------------------
# Tests 3–5: routing between dom-injection vs xpath-mapping branches
# ---------------------------------------------------------------------------

def test_call_with_html_string_routes_to_xpath_mapping(make_find_element_inferencer):
    """HTML string input → _find_with_xpath_mapping → returns xpath."""
    inf = make_find_element_inferencer()
    result = inf(html_source=_SAMPLE_HTML, description="search input")
    # xpath_mapping returns an xpath string (NOT just a numeric __id__).
    assert isinstance(result, str)
    assert result.startswith("/") or result.startswith("(")  # xpath syntax


def test_call_with_webdriver_dom_inject_true_routes_to_dom_injection(
    make_find_element_inferencer,
):
    """WebDriver + inject_unique_index_to_elements=True → DOM injection branch.

    Returns the raw __id__ from the LLM response (not an xpath), because under
    DOM injection the live DOM has __id__ available for direct lookup.
    """
    inf = make_find_element_inferencer()
    fake_driver = _FakeWebDriver(_SAMPLE_HTML)
    cfg = FindElementInferenceConfig(inject_unique_index_to_elements=True)

    with patch(
        "webaxon.automation.agents.find_element_inferencer.add_unique_index_to_elements"
    ) as mock_inject:
        result = inf(html_source=fake_driver, description="search input", inference_config=cfg)

    # DOM injection mutated the live driver
    mock_inject.assert_called_once_with(fake_driver._backend._driver, index_name=ATTR_NAME_INCREMENTAL_ID)
    # Returned the parsed __id__ verbatim
    assert result == "2"


def test_call_with_webdriver_dom_inject_false_routes_to_xpath_mapping(
    make_find_element_inferencer,
):
    """WebDriver + inject_unique_index_to_elements=False → xpath-mapping branch
    (uses driver.page_source as a string, no live-DOM mutation)."""
    inf = make_find_element_inferencer()
    fake_driver = _FakeWebDriver(_SAMPLE_HTML)
    cfg = FindElementInferenceConfig(inject_unique_index_to_elements=False)

    with patch(
        "webaxon.automation.agents.find_element_inferencer.add_unique_index_to_elements"
    ) as mock_inject:
        result = inf(html_source=fake_driver, description="search input", inference_config=cfg)

    # Critical: we did NOT mutate the live DOM
    mock_inject.assert_not_called()
    # We got an xpath string back (not a bare integer)
    assert isinstance(result, str)
    assert "/" in result


# ---------------------------------------------------------------------------
# Test 6: max_html_length truncation
# ---------------------------------------------------------------------------

def test_max_html_length_truncates(real_template_manager):
    """When sanitized HTML > max_html_length, it is truncated with the
    ``"\\n... [truncated]"`` suffix before being fed to the template."""
    captured = {}

    def _capture(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return "<TargetElementID>3</TargetElementID>"

    base_mock = MagicMock(side_effect=_capture)

    inf = FindElementInferencer(
        base_inferencer=base_mock,
        template_manager=real_template_manager,
        max_html_length=120,
    )

    # Build HTML that comfortably exceeds 120 chars after sanitization.
    big_html = (
        "<html><body>"
        + "".join(f'<button class="b{i}">x</button>' for i in range(50))
        + "</body></html>"
    )
    inf(html_source=big_html, description="anything")

    rendered_prompt = captured["prompt"]
    # The truncation marker must appear in the rendered prompt; the html
    # block must end with the marker (sanitized html is truncated, then placed
    # inside <PageHTML>).
    assert "... [truncated]" in rendered_prompt


# ---------------------------------------------------------------------------
# Tests 7–10: _parse_element_id helper (module-level function)
# ---------------------------------------------------------------------------

def test_parse_element_id_from_target_tag():
    """Standard tag form returns the numeric content."""
    assert _parse_element_id("<TargetElementID>42</TargetElementID>") == "42"


def test_parse_element_id_takes_last_match():
    """When multiple <TargetElementID> tags appear, the LAST one wins
    (this matches the parser's intent: LLMs sometimes echo the example
    response and then give the real answer last)."""
    response = (
        "<TargetElementID>1</TargetElementID> some chatter "
        "<TargetElementID>42</TargetElementID>"
    )
    assert _parse_element_id(response) == "42"


def test_parse_element_id_not_found_raises():
    """NOT_FOUND inside the tag → ValueError."""
    with pytest.raises(ValueError, match="not found"):
        _parse_element_id("<TargetElementID>NOT_FOUND</TargetElementID>")


def test_parse_element_id_unparseable_raises():
    """Garbage with no number anywhere → ValueError."""
    with pytest.raises(ValueError, match="Could not parse"):
        _parse_element_id("completely garbage no digits anywhere")


# ---------------------------------------------------------------------------
# Test 11: template feed shape
# ---------------------------------------------------------------------------

def test_template_feed_shape(real_template_manager, mock_base_inferencer):
    """The template_manager is invoked with template_key="find_element" and
    a feed dict carrying exactly ``{html, description, options}``.

    Wraps the real TemplateManager in a MagicMock side_effect so we can
    inspect the call args while still letting the real renderer produce a
    string for downstream code.
    """
    tm_spy = MagicMock(side_effect=real_template_manager)
    # Preserve attributes the inferencer might read on TemplateManager directly.
    inf = FindElementInferencer(
        base_inferencer=mock_base_inferencer,
        template_manager=tm_spy,
    )
    inf(html_source=_SAMPLE_HTML, description="the search input box")

    assert tm_spy.call_count == 1
    args, kwargs = tm_spy.call_args
    # First positional is the template key
    assert args[0] == "find_element"
    # Feed dict carries the three documented keys + nothing else
    feed = kwargs.get("feed")
    assert isinstance(feed, dict)
    assert set(feed.keys()) == {"html", "description", "options"}
    assert feed["description"] == "the search input box"
    assert feed["options"] == []
    assert isinstance(feed["html"], str) and feed["html"]


# ---------------------------------------------------------------------------
# Test 12: xpath does not include __id__
# ---------------------------------------------------------------------------

def test_xpath_excludes_unique_id_attr(make_find_element_inferencer):
    """Generated xpath uses class/text/etc — never the synthetic ``__id__``
    attribute (it doesn't exist in the live DOM under the xpath-mapping branch)."""
    inf = make_find_element_inferencer()
    xpath = inf(html_source=_SAMPLE_HTML, description="submit button")
    assert ATTR_NAME_INCREMENTAL_ID not in xpath, (
        f"xpath must not reference {ATTR_NAME_INCREMENTAL_ID!r} (it doesn't "
        f"exist in the live DOM); got: {xpath}"
    )


# ---------------------------------------------------------------------------
# Tests 13–14: required-arg validation
# ---------------------------------------------------------------------------

def test_missing_html_source_raises(make_find_element_inferencer):
    """Calling without html_source (and without ``feed['html_source']``/``feed['html']``)
    raises ValueError."""
    inf = make_find_element_inferencer()
    with pytest.raises(ValueError, match="html_source"):
        inf(description="anything")


def test_missing_description_raises(make_find_element_inferencer):
    """Calling without description (and without ``feed['description']``) raises
    ValueError."""
    inf = make_find_element_inferencer()
    with pytest.raises(ValueError, match="description"):
        inf(html_source=_SAMPLE_HTML)
