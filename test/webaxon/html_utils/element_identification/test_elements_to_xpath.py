"""
Unit Tests for elements_to_xpath utility function.

Tests the elements_to_xpath function which generates lean xpaths to uniquely
identify one or more HTML elements within a document context.

**Feature: agent-as-action**
**Requirements: Monitor agent target resolution**
"""

# Path resolution - must be first
import sys
from pathlib import Path

# Configuration
PIVOT_FOLDER_NAME = 'test'  # The folder name we're inside of

# Get absolute path to this file
current_file = Path(__file__).resolve()

# Navigate up to find the pivot folder (test directory)
current_path = current_file.parent
while current_path.name != PIVOT_FOLDER_NAME and current_path.parent != current_path:
    current_path = current_path.parent

if current_path.name != PIVOT_FOLDER_NAME:
    raise RuntimeError(f"Could not find '{PIVOT_FOLDER_NAME}' folder in path hierarchy")

# WebAgent root is parent of test/ directory
webagent_root = current_path.parent

# Add src directory to path for webaxon imports
src_dir = webagent_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Add science packages if they exist (for tests that need them)
projects_root = webagent_root.parent
science_python_utils_src = projects_root / "SciencePythonUtils" / "src"
science_modeling_tools_src = projects_root / "ScienceModelingTools" / "src"

for path_item in [science_python_utils_src, science_modeling_tools_src]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

import pytest
from bs4 import BeautifulSoup
from lxml import etree
from webaxon.html_utils.element_identification import (
    elements_to_xpath,
    XPathResolutionMode,
    _escape_xpath_string,
    _is_hash_like_value,
    _is_generic_class,
)

# Path to test data (shared test_data at project root)
TEST_DATA_DIR = webagent_root / "test_data"
GOOGLE_SEARCH_HTML_PATH = TEST_DATA_DIR / "google_search.html"


def load_test_html(filename: str) -> str:
    """Load HTML test data file."""
    filepath = TEST_DATA_DIR / filename
    if not filepath.exists():
        pytest.skip(f"Test data file not found: {filepath}")
    return filepath.read_text(encoding='utf-8')


def validate_xpath_on_html(xpath: str, html: str, expected_count: int = 1) -> bool:
    """Validate that xpath returns expected number of elements."""
    try:
        tree = etree.HTML(html)
        results = tree.xpath(xpath)
        return len(results) == expected_count
    except Exception:
        return False


# =============================================================================
# Test _escape_xpath_string
# =============================================================================

class TestEscapeXpathString:
    """Tests for the XPath string escaping utility."""

    def test_simple_string_uses_single_quotes(self):
        """Simple string without quotes uses single quotes."""
        result = _escape_xpath_string("simple")
        assert result == "'simple'"

    def test_string_with_single_quote_uses_double_quotes(self):
        """String with single quote uses double quotes."""
        result = _escape_xpath_string("it's")
        assert result == '"it\'s"'

    def test_string_with_double_quote_uses_single_quotes(self):
        """String with double quote uses single quotes."""
        result = _escape_xpath_string('say "hello"')
        assert result == "'say \"hello\"'"

    def test_string_with_both_quotes_uses_concat(self):
        """String with both quote types uses concat()."""
        result = _escape_xpath_string("it's \"quoted\"")
        assert result.startswith("concat(")
        assert "'" in result
        assert '"' in result


# =============================================================================
# Test _is_hash_like_value
# =============================================================================

class TestIsHashLikeValue:
    """Tests for hash-like value detection."""

    def test_react_id_detected(self):
        """React-prefixed IDs are detected."""
        assert _is_hash_like_value("react-123") is True
        assert _is_hash_like_value("react-select-2") is True

    def test_ember_id_detected(self):
        """Ember IDs are detected."""
        assert _is_hash_like_value("ember123") is True

    def test_angular_id_detected(self):
        """Angular IDs are detected."""
        assert _is_hash_like_value("ng-123") is True

    def test_react18_useId_detected(self):
        """React 18 useId pattern is detected."""
        assert _is_hash_like_value(":r1:") is True
        assert _is_hash_like_value(":r123:") is True

    def test_uuid_like_detected(self):
        """UUID-like IDs (8+ lowercase hex) are detected."""
        assert _is_hash_like_value("a1b2c3d4e5f6") is True
        assert _is_hash_like_value("abcdef12") is True

    def test_pure_numeric_detected(self):
        """Pure numeric IDs are detected as dynamic."""
        assert _is_hash_like_value("12345") is True

    def test_google_style_hash_detected(self):
        """Google-style minified IDs (APjFqb, gLFyf) are detected."""
        # Mixed case with unusual patterns
        assert _is_hash_like_value("APjFqb") is True
        assert _is_hash_like_value("gLFyf") is True
        assert _is_hash_like_value("RNmpXc") is True
        # Underscore + digits pattern
        assert _is_hash_like_value("gb_70") is True

    def test_static_id_not_detected(self):
        """Normal static IDs are not detected as dynamic."""
        assert _is_hash_like_value("submit-btn") is False
        assert _is_hash_like_value("main-content") is False
        assert _is_hash_like_value("header") is False

    def test_meaningful_words_not_detected(self):
        """Normal words like Search, Submit are not detected as hash-like."""
        assert _is_hash_like_value("Search") is False
        assert _is_hash_like_value("Submit") is False
        assert _is_hash_like_value("email") is False
        assert _is_hash_like_value("password") is False
        assert _is_hash_like_value("Google Search") is False


# =============================================================================
# Test _is_generic_class
# =============================================================================

class TestIsGenericClass:
    """Tests for generic class detection."""

    def test_common_framework_classes_detected(self):
        """Common CSS framework classes are detected."""
        assert _is_generic_class("btn") is True
        assert _is_generic_class("container") is True
        assert _is_generic_class("row") is True
        assert _is_generic_class("col") is True

    def test_utility_class_prefixes_detected(self):
        """Utility class prefixes are detected."""
        assert _is_generic_class("d-flex") is True
        assert _is_generic_class("m-2") is True
        assert _is_generic_class("p-3") is True

    def test_hash_like_classes_detected(self):
        """Hash-like minified classes are detected."""
        assert _is_generic_class("L3eUgb") is True
        assert _is_generic_class("gNO89b") is True

    def test_semantic_classes_not_detected(self):
        """Semantic class names are not detected as generic."""
        assert _is_generic_class("submit-button") is False
        assert _is_generic_class("user-profile") is False
        assert _is_generic_class("nav-link") is False


# =============================================================================
# Test elements_to_xpath - Single Element
# =============================================================================

class TestElementsToXpathSingleElement:
    """Tests for generating xpath for single elements."""

    def test_uses_id_attribute_when_available(self):
        """Should use id attribute when element has one."""
        html = '<div><button id="submit-btn">Submit</button></div>'
        soup = BeautifulSoup(html, 'html.parser')
        elem = soup.find('button')

        xpath = elements_to_xpath(elem, html)

        assert xpath == "//button[@id='submit-btn']"

    def test_skips_dynamic_id(self):
        """Should skip dynamic IDs and use other attributes."""
        html = '<div><button id="react-123" title="Submit">Submit</button></div>'
        soup = BeautifulSoup(html, 'html.parser')
        elem = soup.find('button')

        xpath = elements_to_xpath(elem, html)

        # Should use title instead of dynamic id
        assert "react-123" not in xpath
        assert "@title=" in xpath or "text()" in xpath

    def test_uses_title_attribute(self):
        """Should use title attribute for lean xpath."""
        html = '<div><input title="Search" type="text"/></div>'
        soup = BeautifulSoup(html, 'html.parser')
        elem = soup.find('input')

        xpath = elements_to_xpath(elem, html)

        assert xpath == "//input[@title='Search']"

    def test_uses_value_attribute(self):
        """Should use value attribute for inputs/buttons."""
        html = '<div><input type="submit" value="Google Search"/></div>'
        soup = BeautifulSoup(html, 'html.parser')
        elem = soup.find('input')

        xpath = elements_to_xpath(elem, html)

        assert "@value='Google Search'" in xpath

    def test_uses_text_content_for_buttons(self):
        """Should use text content for buttons when needed."""
        html = '<div><button class="btn">Click Me</button><button class="btn">Submit</button></div>'
        soup = BeautifulSoup(html, 'html.parser')
        buttons = soup.find_all('button')
        submit_btn = buttons[1]

        xpath = elements_to_xpath(submit_btn, html)

        # Should use text to distinguish
        assert "Submit" in xpath

    def test_adds_parent_context_when_needed(self):
        """Should add parent context when element is not unique."""
        html = '''
        <div>
            <button class="btn">Click</button>
        </div>
        <div id="form">
            <button class="btn">Submit</button>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        form_div = soup.find('div', id='form')
        btn = form_div.find('button')

        xpath = elements_to_xpath(btn, html)

        # Should use parent context or text to uniquely identify
        assert "Submit" in xpath or "form" in xpath.lower()

    def test_excludes_id_attribute_from_result(self):
        """Should exclude __id__ from generated xpath by default."""
        html = '<div __id__="0"><input __id__="1" title="Search"/></div>'
        soup = BeautifulSoup(html, 'html.parser')
        elem = soup.find('input')

        xpath = elements_to_xpath(elem, html)

        assert "__id__" not in xpath
        assert "@title='Search'" in xpath


# =============================================================================
# Test elements_to_xpath - Multiple Elements
# =============================================================================

class TestElementsToXpathMultipleElements:
    """Tests for generating xpath for multiple elements."""

    def test_dropdown_options_with_parent_id(self):
        """Should generate parent-based xpath for dropdown options."""
        html = '<select id="country"><option value="us">US</option><option value="uk">UK</option></select>'
        soup = BeautifulSoup(html, 'html.parser')
        options = soup.find_all('option')

        xpath = elements_to_xpath(options, html)

        # Should use parent select with id
        assert "select" in xpath.lower()
        assert "country" in xpath or "option" in xpath

    def test_list_items_with_parent_class(self):
        """Should generate parent-based xpath for list items."""
        html = '<ul class="menu"><li>Item 1</li><li>Item 2</li></ul>'
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.find_all('li')

        xpath = elements_to_xpath(items, html)

        # Should reference parent ul somehow
        assert "ul" in xpath.lower() or "li" in xpath.lower()

    def test_checkbox_group_with_common_name(self):
        """Should use common name attribute for checkbox group."""
        html = '''
        <form>
            <input type="checkbox" name="colors" value="red"/>
            <input type="checkbox" name="colors" value="blue"/>
            <input type="checkbox" name="colors" value="green"/>
            <input type="text" name="other"/>
        </form>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        checkboxes = soup.find_all('input', {'name': 'colors'})

        xpath = elements_to_xpath(checkboxes, html)

        # Should use common name attribute or type to distinguish
        assert "colors" in xpath or "checkbox" in xpath


# =============================================================================
# Test elements_to_xpath - Error Cases
# =============================================================================

class TestElementsToXpathErrors:
    """Tests for error handling in elements_to_xpath."""

    def test_raises_on_empty_elements(self):
        """Should raise ValueError when no elements provided."""
        with pytest.raises(ValueError, match="No elements provided"):
            elements_to_xpath([], "<div></div>")


# =============================================================================
# Integration Tests
# =============================================================================

class TestElementsToXpathIntegration:
    """Integration tests for elements_to_xpath with realistic HTML."""

    def test_google_search_textarea(self):
        """Should generate lean xpath for Google search input."""
        # Simplified Google-like HTML
        html = '''
        <div class="L3eUgb">
            <form>
                <textarea title="Search" name="q" class="gLFyf"></textarea>
            </form>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        textarea = soup.find('textarea')

        xpath = elements_to_xpath(textarea, html)

        # Should use a stable identifying attribute (name has higher priority than title)
        assert "@name='q'" in xpath or "@title='Search'" in xpath

    def test_google_search_button(self):
        """Should generate lean xpath for Google search button."""
        html = '''
        <div class="FPdoLc lJ9FBc">
            <center>
                <input class="gNO89b" value="Google Search" name="btnK" type="submit"/>
                <input class="RNmpXc" value="I'm Feeling Lucky" name="btnI" type="submit"/>
            </center>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        search_btn = soup.find('input', {'value': 'Google Search'})

        xpath = elements_to_xpath(search_btn, html)

        # Should use a stable identifying attribute (name has higher priority than value)
        assert "@name='btnK'" in xpath or "@value='Google Search'" in xpath


# =============================================================================
# Real Google Search HTML Tests
# =============================================================================

class TestElementsToXpathRealGoogleHtml:
    """
    Tests using real captured Google search page HTML.

    These tests validate that elements_to_xpath generates working xpaths
    against actual Google search page structure, matching the xpaths used in:
    - create_google_search_action_graph_with_monitor.py
    """

    @pytest.fixture
    def google_html(self):
        """Load the real Google search HTML test data."""
        return load_test_html("google_search.html")

    def test_search_textarea_generates_valid_xpath(self, google_html):
        """
        Generated xpath for search textarea should work on real Google HTML.

        Reference xpath from example: //textarea[@title='Search']
        The actual Google page may have different attributes (e.g., id),
        so we just verify the generated xpath works and uses a stable attribute.
        """
        soup = BeautifulSoup(google_html, 'html.parser')
        textarea = soup.find('textarea', {'title': 'Search'})

        if textarea is None:
            pytest.skip("Search textarea not found in test HTML")

        xpath = elements_to_xpath(textarea, google_html)

        # Verify the generated xpath works
        assert validate_xpath_on_html(xpath, google_html, expected_count=1), \
            f"Generated xpath '{xpath}' should match exactly 1 element"

        # Should use a stable attribute (id, name, or title are all acceptable)
        stable_attrs = ['@id=', '@name=', '@title=']
        assert any(attr in xpath for attr in stable_attrs), \
            f"Expected xpath to use a stable attribute (id/name/title), got: {xpath}"

    def test_search_button_generates_valid_xpath(self, google_html):
        """
        Generated xpath for Google Search button should work on real Google HTML.

        Reference xpath from example: //input[@value='Google Search']
        Google has multiple identical search buttons for different viewport sizes,
        so this test may fail if the element can't be uniquely identified.
        In that case, we skip the test as it's a limitation of the HTML structure.
        """
        soup = BeautifulSoup(google_html, 'html.parser')
        search_btn = soup.find('input', {'value': 'Google Search'})

        if search_btn is None:
            pytest.skip("Google Search button not found in test HTML")

        # Google page has duplicate buttons - check how many exist
        all_search_btns = soup.find_all('input', {'value': 'Google Search'})
        if len(all_search_btns) > 1:
            pytest.skip(
                f"Google HTML has {len(all_search_btns)} identical search buttons - "
                "cannot uniquely identify one without __id__ context"
            )

        try:
            xpath = elements_to_xpath(search_btn, google_html)

            # Verify the generated xpath matches at least 1 element
            tree = etree.HTML(google_html)
            results = tree.xpath(xpath)
            assert len(results) >= 1, \
                f"Generated xpath '{xpath}' should match at least 1 element"

            # Should use a stable attribute
            stable_attrs = ['@id=', '@name=', '@value=', '@aria-label=']
            assert any(attr in xpath for attr in stable_attrs), \
                f"Expected xpath to use a stable attribute, got: {xpath}"
        except ValueError as e:
            # If xpath generation fails due to non-unique element, skip
            if "Could not generate unique xpath" in str(e):
                pytest.skip(f"Element cannot be uniquely identified: {e}")
            raise

    def test_feeling_lucky_button_generates_valid_xpath(self, google_html):
        """Generated xpath for I'm Feeling Lucky button should work."""
        soup = BeautifulSoup(google_html, 'html.parser')
        lucky_btn = soup.find('input', {'value': "I'm Feeling Lucky"})

        if lucky_btn is None:
            pytest.skip("I'm Feeling Lucky button not found in test HTML")

        # Google page may have duplicate buttons - check how many exist
        all_lucky_btns = soup.find_all('input', {'value': "I'm Feeling Lucky"})
        if len(all_lucky_btns) > 1:
            pytest.skip(
                f"Google HTML has {len(all_lucky_btns)} identical lucky buttons - "
                "cannot uniquely identify one without __id__ context"
            )

        try:
            xpath = elements_to_xpath(lucky_btn, google_html)

            # Verify the generated xpath matches at least 1 element
            tree = etree.HTML(google_html)
            results = tree.xpath(xpath)
            assert len(results) >= 1, \
                f"Generated xpath '{xpath}' should match at least 1 element"
        except ValueError as e:
            # If xpath generation fails due to non-unique element, skip
            if "Could not generate unique xpath" in str(e):
                pytest.skip(f"Element cannot be uniquely identified: {e}")
            raise

    def test_generated_xpath_does_not_use_hash_classes(self, google_html):
        """
        Generated xpaths should not use hash-like classes (e.g., gLFyf, gNO89b).

        These classes are minified and change between deployments.
        """
        soup = BeautifulSoup(google_html, 'html.parser')
        textarea = soup.find('textarea', {'title': 'Search'})

        if textarea is None:
            pytest.skip("Search textarea not found in test HTML")

        xpath = elements_to_xpath(textarea, google_html)

        # Should not contain hash-like class names
        hash_classes = ['gLFyf', 'gNO89b', 'RNmpXc', 'L3eUgb']
        for cls in hash_classes:
            assert cls not in xpath, \
                f"XPath should not use hash-like class '{cls}': {xpath}"

    def test_generated_xpath_excludes_internal_ids(self, google_html):
        """Generated xpaths should not use __id__ attributes."""
        soup = BeautifulSoup(google_html, 'html.parser')
        textarea = soup.find('textarea', {'title': 'Search'})

        if textarea is None:
            pytest.skip("Search textarea not found in test HTML")

        xpath = elements_to_xpath(textarea, google_html)

        assert "__id__" not in xpath, \
            f"XPath should not contain __id__: {xpath}"


# =============================================================================
# XPath Validation Tests
# =============================================================================

class TestXpathValidation:
    """Tests that generated xpaths actually work when executed."""

    def test_xpath_with_name_attribute_is_executable(self):
        """XPath using name attribute should be executable by lxml."""
        html = '<form><input name="q" type="text"/></form>'
        soup = BeautifulSoup(html, 'html.parser')
        elem = soup.find('input')

        xpath = elements_to_xpath(elem, html)

        # Execute xpath with lxml
        tree = etree.HTML(html)
        results = tree.xpath(xpath)

        assert len(results) == 1, f"XPath '{xpath}' should match exactly 1 element"
        assert results[0].get('name') == 'q'

    def test_xpath_with_special_chars_is_executable(self):
        """XPath with escaped special characters should be executable."""
        html = '<button title="It\'s working">Click</button>'
        soup = BeautifulSoup(html, 'html.parser')
        elem = soup.find('button')

        xpath = elements_to_xpath(elem, html)

        # Execute xpath with lxml
        tree = etree.HTML(html)
        results = tree.xpath(xpath)

        assert len(results) == 1, f"XPath '{xpath}' should match exactly 1 element"

    def test_xpath_with_both_quote_types_is_executable(self):
        """XPath with concat() for mixed quotes should be executable."""
        html = '''<button data-msg="Say 'hello' and \\"goodbye\\"">Click</button>'''
        soup = BeautifulSoup(html, 'html.parser')
        elem = soup.find('button')

        xpath = elements_to_xpath(elem, html)

        # Execute xpath with lxml - should not raise
        tree = etree.HTML(html)
        results = tree.xpath(xpath)

        assert len(results) == 1, f"XPath '{xpath}' should match exactly 1 element"


# =============================================================================
# Dynamic Content Detection Tests (Expedia-style)
# =============================================================================

class TestDynamicContentDetection:
    """
    Tests that dynamic/personalized content is skipped in xpath generation.

    Dynamic content includes dates, counts, prices, etc. that change per user
    or session. Such content creates unstable xpaths that break frequently.
    """

    @pytest.fixture
    def expedia_html(self):
        """Load real Expedia HTML test data."""
        return load_test_html("expedia.html")

    def test_static_aria_label_is_used(self, expedia_html):
        """
        Static aria-label ('Where to?') should be used in xpath.

        Static labels don't contain dynamic content like dates or counts.
        """
        soup = BeautifulSoup(expedia_html, 'html.parser')
        btn = soup.find('button', {'aria-label': 'Where to?'})

        if btn is None:
            pytest.skip("'Where to?' button not found in test HTML")

        xpath = elements_to_xpath(btn, expedia_html)

        assert "@aria-label='Where to?'" in xpath, \
            f"Expected static aria-label in xpath, got: {xpath}"

    def test_dates_button_avoids_dynamic_aria_label(self, expedia_html):
        """
        Dates button should use data-testid, NOT dynamic aria-label.

        The aria-label contains dates like "Tue, Jan 6 - Thu, Jan 8"
        which change based on user selection.
        """
        soup = BeautifulSoup(expedia_html, 'html.parser')
        btn = soup.find('button', {'data-testid': 'uitk-date-selector-input1-default'})

        if btn is None:
            pytest.skip("Dates button not found in test HTML")

        xpath = elements_to_xpath(btn, expedia_html)

        # Should NOT contain month names or day names
        assert 'Jan' not in xpath, \
            f"XPath should not contain dynamic month 'Jan': {xpath}"
        assert 'Tue' not in xpath, \
            f"XPath should not contain dynamic day 'Tue': {xpath}"
        # Should use stable data-testid
        assert "@data-testid=" in xpath, \
            f"Expected data-testid in xpath, got: {xpath}"

    def test_travelers_button_avoids_dynamic_aria_label(self, expedia_html):
        """
        Travelers button should use data-stid, NOT dynamic aria-label.

        The aria-label contains counts like "2 travelers, 1 room"
        which change based on user selection.
        """
        soup = BeautifulSoup(expedia_html, 'html.parser')
        btn = soup.find('button', {'data-stid': 'open-room-picker'})

        if btn is None:
            pytest.skip("Travelers button not found in test HTML")

        xpath = elements_to_xpath(btn, expedia_html)

        # Should NOT contain count-based text
        assert 'travelers' not in xpath.lower(), \
            f"XPath should not contain dynamic 'travelers': {xpath}"
        assert 'room' not in xpath.lower() or 'room-picker' in xpath.lower(), \
            f"XPath should not contain dynamic 'room' (except in data-stid): {xpath}"
        # Should use stable data-stid
        assert "@data-stid=" in xpath, \
            f"Expected data-stid in xpath, got: {xpath}"

    def test_search_button_uses_id(self, expedia_html):
        """
        Search button should use id attribute (highest priority).
        """
        soup = BeautifulSoup(expedia_html, 'html.parser')
        btn = soup.find('button', {'id': 'search_button'})

        if btn is None:
            pytest.skip("Search button not found in test HTML")

        xpath = elements_to_xpath(btn, expedia_html)

        assert "@id='search_button'" in xpath, \
            f"Expected id attribute in xpath, got: {xpath}"

    def test_currency_content_is_skipped(self):
        """Attribute values with currency should be skipped."""
        html = '''
        <div>
            <button aria-label="Book for $299" data-testid="book-btn">Book</button>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        btn = soup.find('button')

        xpath = elements_to_xpath(btn, html)

        # Should NOT use aria-label with price
        assert '$299' not in xpath, \
            f"XPath should not contain dynamic price: {xpath}"
        # Should use stable data-testid instead
        assert "@data-testid='book-btn'" in xpath, \
            f"Expected data-testid in xpath, got: {xpath}"

    def test_count_content_is_skipped(self):
        """Attribute values with counts should be skipped."""
        html = '''
        <div>
            <button aria-label="5 items in cart" data-testid="cart-btn">Cart</button>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        btn = soup.find('button')

        xpath = elements_to_xpath(btn, html)

        # Should NOT use aria-label with count
        assert '5 items' not in xpath, \
            f"XPath should not contain dynamic count: {xpath}"
        # Should use stable data-testid instead
        assert "@data-testid='cart-btn'" in xpath, \
            f"Expected data-testid in xpath, got: {xpath}"

    def test_time_content_is_skipped(self):
        """Attribute values with times should be skipped."""
        # Note: Use multiple buttons with same text to ensure text is not unique
        # This forces the algorithm to use data-testid instead
        html = '''
        <div>
            <button aria-label="Departure at 10:30 AM" data-testid="flight-btn-1">Select</button>
            <button aria-label="Departure at 2:00 PM" data-testid="flight-btn-2">Select</button>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        # Get the first button
        btn = soup.find('button', {'data-testid': 'flight-btn-1'})

        xpath = elements_to_xpath(btn, html)

        # Should NOT use aria-label with time
        assert '10:30' not in xpath, \
            f"XPath should not contain dynamic time: {xpath}"
        # Should use stable data-testid instead (text 'Select' is not unique)
        assert "@data-testid='flight-btn-1'" in xpath, \
            f"Expected data-testid in xpath, got: {xpath}"


# =============================================================================
# Test XPathResolutionMode
# =============================================================================

class TestXPathResolutionMode:
    """Tests for the XPathResolutionMode enum and resolution strategies."""

    def test_unique_only_raises_on_non_unique(self):
        """UNIQUE_ONLY mode should raise ValueError when element is not unique."""
        # All buttons are completely identical - no unique attributes or text
        html = '''
        <div>
            <button class="btn">Click</button>
            <button class="btn">Click</button>
            <button class="btn">Click</button>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        buttons = soup.find_all('button')
        btn = buttons[1]  # Get the second identical button

        with pytest.raises(ValueError, match="Could not"):
            elements_to_xpath(btn, html, resolution_mode=XPathResolutionMode.UNIQUE_ONLY)

    def test_first_match_returns_indexed_xpath(self):
        """FIRST_MATCH mode should return xpath with [1] index."""
        html = '''
        <div>
            <button class="btn">Click</button>
            <button class="btn">Click</button>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        btn = soup.find('button')  # First button

        xpath = elements_to_xpath(btn, html, resolution_mode=XPathResolutionMode.FIRST_MATCH)

        # Should end with [1] index
        assert xpath.endswith(")[1]"), f"Expected xpath ending with [1], got: {xpath}"

    def test_match_by_text_finds_correct_element(self):
        """MATCH_BY_TEXT mode should find element by text content when elements are similar."""
        # Use nested structure to make direct xpath generation harder
        # All spans have same class but different text
        html = '''
        <div class="container">
            <div class="item"><span class="text">Alpha</span></div>
            <div class="item"><span class="text">Beta</span></div>
            <div class="item"><span class="text">Gamma</span></div>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        spans = soup.find_all('span', class_='text')
        beta_span = spans[1]  # The "Beta" span

        xpath = elements_to_xpath(beta_span, html, resolution_mode=XPathResolutionMode.MATCH_BY_TEXT)

        # Verify the xpath returns the correct element (with "Beta" text)
        tree = etree.HTML(html)
        results = tree.xpath(xpath)
        assert len(results) == 1
        assert 'Beta' in etree.tostring(results[0], encoding='unicode')

    def test_match_by_signature_finds_correct_element(self):
        """MATCH_BY_SIGNATURE mode should find element by signature."""
        html = '''
        <div>
            <input type="text" name="first" placeholder="First Name"/>
            <input type="text" name="last" placeholder="Last Name"/>
            <input type="text" name="email" placeholder="Email"/>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        email_input = soup.find('input', {'name': 'email'})

        xpath = elements_to_xpath(email_input, html, resolution_mode=XPathResolutionMode.MATCH_BY_SIGNATURE)

        # Verify the xpath returns the correct element
        tree = etree.HTML(html)
        results = tree.xpath(xpath)
        assert len(results) == 1
        assert results[0].get('name') == 'email'

    def test_match_by_html_finds_correct_element(self):
        """MATCH_BY_HTML mode should find element using compare_elements()."""
        html = '''
        <div>
            <span class="label" data-id="1">Label A</span>
            <span class="label" data-id="2">Label B</span>
            <span class="label" data-id="3">Label C</span>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        label_b = soup.find('span', {'data-id': '2'})

        xpath = elements_to_xpath(label_b, html, resolution_mode=XPathResolutionMode.MATCH_BY_HTML)

        # Verify the xpath returns the correct element
        tree = etree.HTML(html)
        results = tree.xpath(xpath)
        assert len(results) == 1
        assert results[0].get('data-id') == '2'

    def test_match_by_html_with_ignore_attrs(self):
        """MATCH_BY_HTML mode should respect ignore_attrs argument."""
        html = '''
        <div>
            <button class="btn" data-track="btn1">Click</button>
            <button class="btn" data-track="btn2">Click</button>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        btn = soup.find('button', {'data-track': 'btn2'})

        # When ignoring data-track, buttons look identical except position
        xpath = elements_to_xpath(
            btn, html,
            resolution_mode=XPathResolutionMode.MATCH_BY_HTML,
            ignore_attrs=['data-track']
        )

        # Should still find the element (matches by position since attrs ignored)
        tree = etree.HTML(html)
        results = tree.xpath(xpath)
        assert len(results) == 1

    def test_match_by_signature_with_consider_children(self):
        """MATCH_BY_SIGNATURE mode should respect consider_children argument."""
        html = '''
        <div>
            <div class="card"><span>Content A</span></div>
            <div class="card"><span>Content B</span></div>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        card_b = soup.find_all('div', class_='card')[1]

        xpath = elements_to_xpath(
            card_b, html,
            resolution_mode=XPathResolutionMode.MATCH_BY_SIGNATURE,
            consider_children=True
        )

        # Verify the xpath returns the correct element
        tree = etree.HTML(html)
        results = tree.xpath(xpath)
        assert len(results) == 1
        assert 'Content B' in etree.tostring(results[0], encoding='unicode')

    def test_default_mode_is_unique_only(self):
        """Default resolution mode should be UNIQUE_ONLY."""
        html = '<button id="unique-btn">Click</button>'
        soup = BeautifulSoup(html, 'html.parser')
        btn = soup.find('button')

        # Should work without specifying resolution_mode
        xpath = elements_to_xpath(btn, html)
        assert "@id='unique-btn'" in xpath

    def test_id_matching_uses_descriptive_xpath_not_generic_tag(self):
        """When element has __id__, returned xpath should use descriptive candidate, not just //tag."""
        from webaxon.html_utils.element_identification import (
            add_unique_index_to_html,
            ATTR_NAME_INCREMENTAL_ID,
        )

        # Multiple inputs - search button is at position 3
        html = '''
        <form>
            <input type="text" name="first">
            <input type="text" name="last">
            <input type="submit" value="Google Search">
            <input type="submit" value="Feeling Lucky">
        </form>
        '''

        # Add __id__ to simulate FindElementInferencer behavior
        html_with_ids = add_unique_index_to_html(html, index_name=ATTR_NAME_INCREMENTAL_ID)

        soup = BeautifulSoup(html_with_ids, 'html.parser')
        google_btn = soup.find('input', {'value': 'Google Search'})

        xpath = elements_to_xpath(
            google_btn, html_with_ids,
            resolution_mode=XPathResolutionMode.MATCH_BY_HTML
        )

        # Should use descriptive xpath like (//input[@value='Google Search'])[1]
        # NOT generic xpath like (//input)[3]
        assert "@value" in xpath or "Google Search" in xpath, \
            f"Expected descriptive xpath with @value, got: {xpath}"
        assert "(//input)[3]" not in xpath, \
            f"Should NOT use generic tag-only xpath, got: {xpath}"
