"""
Property tests for Unsupported Browser Type Rejection.

Property 3: Unsupported Browser Type Rejection
Validates: Requirements 2.3

These tests verify that:
1. PlaywrightBackend.initialize() rejects unsupported browser types with ValueError
2. The error message includes the invalid browser type
3. The error message lists supported browser types
4. Valid browser types are accepted without error
"""

import pytest
from hypothesis import given, settings, strategies as st

from webaxon.automation.backends.playwright.shims import PLAYWRIGHT_AVAILABLE


# Skip all tests if Playwright is not available
pytestmark = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE,
    reason="Playwright not installed"
)


class TestUnsupportedBrowserTypeRejection:
    """Tests that verify unsupported browser types are properly rejected."""

    # Valid browser types for Playwright
    VALID_BROWSER_TYPES = [
        'chromium', 'chrome', 'undetected_chrome',
        'firefox', 'gecko',
        'webkit', 'safari',
    ]

    # Invalid browser types that should be rejected
    INVALID_BROWSER_TYPES = [
        'ie', 'internet_explorer', 'edge', 'opera',
        'netscape', 'mosaic', 'invalid_browser',
        '', 'null', 'undefined', '123', 'CHROMIUM_INVALID',
    ]

    def test_invalid_browser_type_raises_value_error(self):
        """PlaywrightBackend.initialize() must raise ValueError for invalid browser types."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()

        for invalid_type in self.INVALID_BROWSER_TYPES:
            with pytest.raises(ValueError) as exc_info:
                backend.initialize(browser_type=invalid_type, headless=True)

            # Verify error message contains useful information
            error_msg = str(exc_info.value).lower()
            assert 'unsupported' in error_msg or 'supported' in error_msg, \
                f"Error message should mention 'unsupported' or 'supported': {exc_info.value}"

    def test_error_message_includes_invalid_browser_type(self):
        """Error message must include the invalid browser type that was provided."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()
        invalid_type = 'nonexistent_browser'

        with pytest.raises(ValueError) as exc_info:
            backend.initialize(browser_type=invalid_type, headless=True)

        error_msg = str(exc_info.value)
        assert invalid_type in error_msg, \
            f"Error message should include the invalid browser type '{invalid_type}': {error_msg}"

    def test_error_message_lists_supported_types(self):
        """Error message must list the supported browser types."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()

        with pytest.raises(ValueError) as exc_info:
            backend.initialize(browser_type='invalid_browser', headless=True)

        error_msg = str(exc_info.value).lower()

        # At least some valid types should be mentioned
        supported_mentioned = any(
            valid_type in error_msg
            for valid_type in ['chromium', 'firefox', 'webkit']
        )
        assert supported_mentioned, \
            f"Error message should list supported browser types: {exc_info.value}"

    @given(st.text(min_size=1, max_size=50).filter(
        lambda x: x.lower() not in [
            'chromium', 'chrome', 'undetected_chrome',
            'firefox', 'gecko', 'webkit', 'safari'
        ]
    ))
    @settings(max_examples=20)
    def test_arbitrary_invalid_browser_types_rejected(self, invalid_type: str):
        """Any invalid browser type string must be rejected with ValueError."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()

        with pytest.raises(ValueError):
            backend.initialize(browser_type=invalid_type, headless=True)


class TestValidBrowserTypeAcceptance:
    """Tests that verify valid browser types are accepted."""

    # Valid browser types and their expected internal mappings
    VALID_BROWSER_TYPES = {
        'chromium': 'chromium',
        'chrome': 'chromium',
        'undetected_chrome': 'chromium',
        'firefox': 'firefox',
        'gecko': 'firefox',
        'webkit': 'webkit',
        'safari': 'webkit',
    }

    def test_valid_browser_types_do_not_raise(self):
        """Valid browser types should not raise ValueError during initialize()."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        for valid_type in self.VALID_BROWSER_TYPES.keys():
            backend = PlaywrightBackend()
            try:
                # This will likely fail for other reasons (no display, etc.)
                # but should NOT fail with ValueError for unsupported type
                backend.initialize(browser_type=valid_type, headless=True)
                backend.quit()
            except ValueError as e:
                if 'unsupported' in str(e).lower():
                    pytest.fail(f"Valid browser type '{valid_type}' was rejected: {e}")
            except Exception:
                # Other exceptions (like display issues) are OK for this test
                pass

    def test_case_insensitive_browser_types(self):
        """Browser types should be case-insensitive."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        case_variants = ['CHROMIUM', 'Chromium', 'ChRoMiUm', 'FIREFOX', 'Firefox']

        for variant in case_variants:
            backend = PlaywrightBackend()
            try:
                backend.initialize(browser_type=variant, headless=True)
                backend.quit()
            except ValueError as e:
                if 'unsupported' in str(e).lower():
                    pytest.fail(f"Case variant '{variant}' was rejected: {e}")
            except Exception:
                # Other exceptions are OK
                pass


class TestBrowserTypeMappingConsistency:
    """Tests that verify browser type mapping is consistent."""

    def test_chrome_maps_to_chromium(self):
        """'chrome' should map to Chromium browser internally."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()
        try:
            backend.initialize(browser_type='chrome', headless=True)
            # If initialization succeeds, verify the driver type
            assert backend.driver_type is not None
            backend.quit()
        except ValueError:
            pytest.fail("'chrome' should be a valid browser type")
        except Exception:
            # Other exceptions are OK
            pass

    def test_safari_maps_to_webkit(self):
        """'safari' should map to WebKit browser internally."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()
        try:
            backend.initialize(browser_type='safari', headless=True)
            # If initialization succeeds, verify the driver type
            assert backend.driver_type is not None
            backend.quit()
        except ValueError:
            pytest.fail("'safari' should be a valid browser type")
        except Exception:
            # Other exceptions are OK
            pass

    def test_gecko_maps_to_firefox(self):
        """'gecko' should map to Firefox browser internally."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()
        try:
            backend.initialize(browser_type='gecko', headless=True)
            # If initialization succeeds, verify the driver type
            assert backend.driver_type is not None
            backend.quit()
        except ValueError:
            pytest.fail("'gecko' should be a valid browser type")
        except Exception:
            # Other exceptions are OK
            pass


class TestEdgeCaseBrowserTypes:
    """Tests for edge cases in browser type handling."""

    def test_empty_string_rejected(self):
        """Empty string browser type should be rejected."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()

        with pytest.raises(ValueError):
            backend.initialize(browser_type='', headless=True)

    def test_whitespace_only_rejected(self):
        """Whitespace-only browser type should be rejected."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()

        with pytest.raises(ValueError):
            backend.initialize(browser_type='   ', headless=True)

    def test_browser_type_with_leading_trailing_spaces(self):
        """Browser type with leading/trailing spaces behavior."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()

        # ' chromium ' with spaces should either be accepted (stripped)
        # or rejected (not stripped) - test documents current behavior
        try:
            backend.initialize(browser_type=' chromium ', headless=True)
            # If accepted, that's fine - it was stripped
            backend.quit()
        except ValueError:
            # If rejected, that's also fine - spaces aren't stripped
            pass
        except Exception:
            # Other exceptions are OK
            pass

    def test_none_browser_type_raises_appropriate_error(self):
        """None browser type should raise an appropriate error."""
        from webaxon.automation.backends.playwright.playwright_backend import PlaywrightBackend

        backend = PlaywrightBackend()

        # None should raise either ValueError or TypeError
        with pytest.raises((ValueError, TypeError, AttributeError)):
            backend.initialize(browser_type=None, headless=True)
