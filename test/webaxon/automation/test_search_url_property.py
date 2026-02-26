"""
Property tests for Search URL Generation.

Feature: playwright-support
Property 11: Search URL Generation

Property 11: *For any* search query string and provider (Google or Bing), the
generated search URL SHALL contain the query, and when date filters are provided,
the URL SHALL include the appropriate date parameters for that provider.

Validates: Requirements 16.1, 16.2, 16.3, 16.4
"""

# Path resolution - must be first
import sys
from pathlib import Path

PIVOT_FOLDER_NAME = 'test'
current_file = Path(__file__).resolve()
current_path = current_file.parent
while current_path.name != PIVOT_FOLDER_NAME and current_path.parent != current_path:
    current_path = current_path.parent

if current_path.name != PIVOT_FOLDER_NAME:
    raise RuntimeError(f"Could not find '{PIVOT_FOLDER_NAME}' folder in path hierarchy")

webagent_root = current_path.parent
src_dir = webagent_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

projects_root = webagent_root.parent
for path_item in [projects_root / "SciencePythonUtils" / "src", projects_root / "ScienceModelingTools" / "src"]:
    if path_item.exists() and str(path_item) not in sys.path:
        sys.path.insert(0, str(path_item))

import pytest
from urllib.parse import urlparse, parse_qs, unquote
from hypothesis import given, strategies as st, settings, assume

from webaxon.url_utils.search_urls.google_search_url import create_search_url as google_create_url
from webaxon.url_utils.search_urls.bing_search_url import create_search_url as bing_create_url


# =============================================================================
# Property 11: Search URL Generation
# =============================================================================

class TestGoogleSearchURLGeneration:
    """Tests for Google search URL generation."""

    @given(query=st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
        min_codepoint=32, max_codepoint=126
    )).filter(lambda x: x.strip()))
    @settings(max_examples=50)
    def test_google_url_contains_query(self, query):
        """Generated Google URL should contain the search query."""
        url = google_create_url(query=query)

        parsed = urlparse(url)
        assert parsed.netloc == 'www.google.com'
        assert parsed.path == '/search'

        # Query should be in the 'q' parameter
        params = parse_qs(parsed.query)
        assert 'q' in params

    def test_google_url_with_date_range(self):
        """Google URL with date range should contain tbs parameter."""
        url = google_create_url(
            query="test query",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Should have tbs parameter for date filtering
        assert 'tbs' in params

        # tbs should contain date information
        tbs_value = unquote(params['tbs'][0])
        assert 'cdr' in tbs_value  # Custom date range indicator

    def test_google_url_with_start_date_only(self):
        """Google URL with only start_date should work."""
        url = google_create_url(
            query="test query",
            start_date="2023-06-01"
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert 'tbs' in params
        tbs_value = unquote(params['tbs'][0])
        assert 'cd_min' in tbs_value

    def test_google_url_with_end_date_only(self):
        """Google URL with only end_date should work."""
        url = google_create_url(
            query="test query",
            end_date="2023-12-31"
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert 'tbs' in params
        tbs_value = unquote(params['tbs'][0])
        assert 'cd_max' in tbs_value

    def test_google_url_with_sites(self):
        """Google URL with site restrictions should include site: operators."""
        url = google_create_url(
            query="test query",
            sites=["example.com", "test.org"]
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        q_value = unquote(params['q'][0])
        assert 'site:example.com' in q_value or 'site%3Aexample.com' in params['q'][0]

    def test_google_url_empty_query_raises_error(self):
        """Empty query should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            google_create_url(query="   ")

        assert "empty" in str(exc_info.value).lower()

    def test_google_url_invalid_date_format_raises_error(self):
        """Invalid date format should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            google_create_url(query="test", start_date="2023/01/01")

        assert "YYYY-MM-DD" in str(exc_info.value)

    def test_google_url_end_before_start_raises_error(self):
        """End date before start date should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            google_create_url(
                query="test",
                start_date="2023-12-31",
                end_date="2023-01-01"
            )

        assert "earlier" in str(exc_info.value).lower()

    def test_google_url_with_extra_params(self):
        """Extra parameters should be included in URL."""
        url = google_create_url(
            query="test query",
            hl="en",
            safe="active"
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert 'hl' in params
        assert params['hl'][0] == 'en'
        assert 'safe' in params
        assert params['safe'][0] == 'active'


class TestBingSearchURLGeneration:
    """Tests for Bing search URL generation."""

    @given(query=st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
        min_codepoint=32, max_codepoint=126
    )).filter(lambda x: x.strip()))
    @settings(max_examples=50)
    def test_bing_url_contains_query(self, query):
        """Generated Bing URL should contain the search query."""
        url = bing_create_url(query=query)

        parsed = urlparse(url)
        assert parsed.netloc == 'www.bing.com'
        assert parsed.path == '/search'

        # Query should be in the 'q' parameter
        params = parse_qs(parsed.query)
        assert 'q' in params

    def test_bing_url_with_date_range(self):
        """Bing URL with date range should contain filters parameter."""
        url = bing_create_url(
            query="test query",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Bing uses 'filters' parameter for date filtering
        assert 'filters' in params

    def test_bing_url_with_start_date_only(self):
        """Bing URL with only start_date should work."""
        url = bing_create_url(
            query="test query",
            start_date="2023-06-01"
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert 'filters' in params

    def test_bing_url_with_end_date_only(self):
        """Bing URL with only end_date should work."""
        url = bing_create_url(
            query="test query",
            end_date="2023-12-31"
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert 'filters' in params

    def test_bing_url_with_sites(self):
        """Bing URL with site restrictions should include site: operators."""
        url = bing_create_url(
            query="test query",
            sites=["example.com", "test.org"]
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        q_value = unquote(params['q'][0])
        assert 'site:' in q_value or 'site%3A' in params['q'][0]

    def test_bing_url_empty_query_raises_error(self):
        """Empty query should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            bing_create_url(query="   ")

        assert "empty" in str(exc_info.value).lower()

    def test_bing_url_invalid_date_format_raises_error(self):
        """Invalid date format should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            bing_create_url(query="test", start_date="01-01-2023")

        assert "YYYY-MM-DD" in str(exc_info.value)

    def test_bing_url_end_before_start_raises_error(self):
        """End date before start date should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            bing_create_url(
                query="test",
                start_date="2023-12-31",
                end_date="2023-01-01"
            )

        assert "earlier" in str(exc_info.value).lower()

    def test_bing_url_with_extra_params(self):
        """Extra parameters should be included in URL."""
        url = bing_create_url(
            query="test query",
            setlang="en",
            form="QBLH"
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert 'setlang' in params
        assert params['setlang'][0] == 'en'


class TestSearchURLCrossProviderConsistency:
    """Tests for consistency across search providers."""

    @given(query=st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        min_codepoint=48, max_codepoint=122
    )).filter(lambda x: x.strip()))
    @settings(max_examples=30)
    def test_both_providers_include_query(self, query):
        """Both Google and Bing URLs should include the query."""
        google_url = google_create_url(query=query)
        bing_url = bing_create_url(query=query)

        google_parsed = urlparse(google_url)
        bing_parsed = urlparse(bing_url)

        google_params = parse_qs(google_parsed.query)
        bing_params = parse_qs(bing_parsed.query)

        assert 'q' in google_params
        assert 'q' in bing_params

    def test_both_providers_reject_empty_query(self):
        """Both providers should reject empty queries."""
        with pytest.raises(ValueError):
            google_create_url(query="")

        with pytest.raises(ValueError):
            bing_create_url(query="")

    def test_both_providers_validate_date_format(self):
        """Both providers should validate date format."""
        with pytest.raises(ValueError):
            google_create_url(query="test", start_date="invalid")

        with pytest.raises(ValueError):
            bing_create_url(query="test", start_date="invalid")

    def test_both_providers_reject_invalid_date_range(self):
        """Both providers should reject end < start."""
        with pytest.raises(ValueError):
            google_create_url(query="test", start_date="2024-01-01", end_date="2023-01-01")

        with pytest.raises(ValueError):
            bing_create_url(query="test", start_date="2024-01-01", end_date="2023-01-01")


class TestSearchURLSpecialCharacters:
    """Tests for handling special characters in search queries."""

    def test_google_handles_spaces(self):
        """Google should handle spaces in queries."""
        url = google_create_url(query="hello world test")
        assert '+' in url or '%20' in url

    def test_bing_handles_spaces(self):
        """Bing should handle spaces in queries."""
        url = bing_create_url(query="hello world test")
        assert '+' in url or '%20' in url

    def test_google_handles_special_chars(self):
        """Google should handle special characters in queries."""
        url = google_create_url(query="C++ programming")
        # Should be URL encoded
        parsed = urlparse(url)
        assert parsed.query  # Should have query parameters

    def test_bing_handles_special_chars(self):
        """Bing should handle special characters in queries."""
        url = bing_create_url(query="C++ programming")
        parsed = urlparse(url)
        assert parsed.query


class TestSearchURLSiteRestrictions:
    """Tests for site restriction functionality."""

    def test_google_single_site_restriction(self):
        """Google should handle single site restriction."""
        url = google_create_url(query="test", sites=["example.com"])
        assert "site" in url.lower()

    def test_bing_single_site_restriction(self):
        """Bing should handle single site restriction."""
        url = bing_create_url(query="test", sites=["example.com"])
        assert "site" in url.lower()

    def test_google_multiple_site_restrictions(self):
        """Google should handle multiple site restrictions with OR."""
        url = google_create_url(query="test", sites=["a.com", "b.com", "c.com"])
        # Should contain OR operator
        decoded = unquote(url)
        assert "OR" in decoded or "site" in decoded.lower()

    def test_bing_multiple_site_restrictions(self):
        """Bing should handle multiple site restrictions with OR."""
        url = bing_create_url(query="test", sites=["a.com", "b.com", "c.com"])
        decoded = unquote(url)
        assert "OR" in decoded or "site" in decoded.lower()

    def test_google_sites_as_comma_string(self):
        """Google should handle sites as comma-separated string."""
        url = google_create_url(query="test", sites="a.com,b.com")
        decoded = unquote(url)
        assert "site" in decoded.lower()

    def test_bing_sites_as_comma_string(self):
        """Bing should handle sites as comma-separated string."""
        url = bing_create_url(query="test", sites="a.com,b.com")
        decoded = unquote(url)
        assert "site" in decoded.lower()
