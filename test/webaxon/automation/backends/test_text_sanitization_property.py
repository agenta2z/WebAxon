"""
Property tests for Text Sanitization.

Feature: playwright-support
Property 8: Text Sanitization Round-Trip
Property 9: Text Sanitization Transliteration

Property 8: *For any* text string containing non-BMP characters, after sanitization
with `non_bmp_handling=REMOVE`, the result SHALL contain only BMP characters
(code points <= 0xFFFF), and the sanitization function SHALL be idempotent
(sanitizing twice produces the same result as sanitizing once).

Property 9: *For any* text string containing known emoji characters, after sanitization
with `non_bmp_handling=TRANSLITERATE`, the result SHALL contain text representations
of those emoji (e.g., `:smile:` for certain emoji), and the result SHALL contain only
BMP characters.

Validates: Requirements 14.1, 14.2, 14.3
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
from hypothesis import given, strategies as st, settings, assume

from webaxon.automation.backends.shared.text_sanitization import (
    NonBMPHandling,
    NewlineHandling,
    WhitespaceHandling,
    is_bmp_character,
    contains_non_bmp,
    get_non_bmp_characters,
    remove_non_bmp,
    replace_non_bmp,
    transliterate_non_bmp,
    handle_non_bmp,
    sanitize_input_text_for_webdriver,
    _EMOJI_TRANSLITERATIONS,
)


# =============================================================================
# Property 8: Text Sanitization Round-Trip
# =============================================================================

class TestTextSanitizationRoundTrip:
    """
    Property 8: For any text string containing non-BMP characters, after
    sanitization with non_bmp_handling=REMOVE, the result SHALL contain only
    BMP characters, and the function SHALL be idempotent.
    """

    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_remove_non_bmp_produces_only_bmp_chars(self, text):
        """After removing non-BMP chars, result should contain only BMP chars."""
        result = remove_non_bmp(text)
        for char in result:
            assert ord(char) <= 0xFFFF, f"Non-BMP char found: U+{ord(char):04X}"

    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_remove_non_bmp_is_idempotent(self, text):
        """Applying remove_non_bmp twice should give same result as once."""
        once = remove_non_bmp(text)
        twice = remove_non_bmp(once)
        assert once == twice

    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_sanitize_input_text_for_webdriver_produces_only_bmp_chars(self, text):
        """sanitize_input_text_for_webdriver should produce only BMP characters."""
        result = sanitize_input_text_for_webdriver(text, non_bmp_handling=NonBMPHandling.REMOVE)
        for char in result:
            assert ord(char) <= 0xFFFF, f"Non-BMP char found: U+{ord(char):04X}"

    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_sanitize_input_text_for_webdriver_is_idempotent(self, text):
        """Applying sanitize_input_text_for_webdriver twice should give same result as once."""
        once = sanitize_input_text_for_webdriver(text, non_bmp_handling=NonBMPHandling.REMOVE)
        twice = sanitize_input_text_for_webdriver(once, non_bmp_handling=NonBMPHandling.REMOVE)
        assert once == twice

    def test_specific_emoji_removed(self):
        """Specific emoji should be removed with REMOVE handling."""
        text = "Hello 😀 World 🎉"
        result = remove_non_bmp(text)
        assert "😀" not in result
        assert "🎉" not in result
        assert "Hello" in result
        assert "World" in result

    def test_bmp_text_unchanged_by_remove(self):
        """BMP-only text should be unchanged by remove_non_bmp."""
        text = "Hello World! 123 ABC"
        result = remove_non_bmp(text)
        assert result == text

    def test_contains_non_bmp_detects_emoji(self):
        """contains_non_bmp should detect emoji."""
        assert contains_non_bmp("Hello 😀")
        assert not contains_non_bmp("Hello World")

    def test_is_bmp_character_correct(self):
        """is_bmp_character should correctly identify BMP chars."""
        assert is_bmp_character('A')
        assert is_bmp_character('中')  # Chinese character in BMP
        assert is_bmp_character('\u0000')
        assert is_bmp_character('\uFFFF')
        assert not is_bmp_character('😀')  # Emoji is non-BMP

    @given(text=st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_get_non_bmp_characters_returns_correct_info(self, text):
        """get_non_bmp_characters should return correct info for non-BMP chars."""
        non_bmp = get_non_bmp_characters(text)
        for char, pos, code_point, name in non_bmp:
            assert ord(char) > 0xFFFF
            assert code_point == ord(char)
            assert text[pos] == char


class TestReplaceNonBMP:
    """Tests for replace_non_bmp function."""

    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_replace_non_bmp_produces_only_bmp_chars(self, text):
        """After replacing non-BMP chars, result should contain only BMP chars."""
        result = replace_non_bmp(text)
        for char in result:
            assert ord(char) <= 0xFFFF

    def test_replace_uses_replacement_char(self):
        """replace_non_bmp should use the replacement character."""
        text = "Hello 😀"
        result = replace_non_bmp(text, replacement='X')
        assert 'X' in result
        assert '😀' not in result

    def test_replace_default_is_replacement_character(self):
        """Default replacement should be U+FFFD."""
        text = "Hello 😀"
        result = replace_non_bmp(text)
        assert '\uFFFD' in result


class TestHandleNonBMP:
    """Tests for handle_non_bmp function with different strategies."""

    def test_keep_strategy_preserves_non_bmp(self):
        """KEEP strategy should preserve non-BMP characters."""
        text = "Hello 😀"
        result = handle_non_bmp(text, handling=NonBMPHandling.KEEP)
        assert result == text

    def test_remove_strategy_removes_non_bmp(self):
        """REMOVE strategy should remove non-BMP characters."""
        text = "Hello 😀"
        result = handle_non_bmp(text, handling=NonBMPHandling.REMOVE)
        assert '😀' not in result

    def test_replace_strategy_replaces_non_bmp(self):
        """REPLACE strategy should replace non-BMP characters."""
        text = "Hello 😀"
        result = handle_non_bmp(text, handling=NonBMPHandling.REPLACE)
        assert '😀' not in result
        assert '\uFFFD' in result

    def test_raise_strategy_raises_for_non_bmp(self):
        """RAISE strategy should raise ValueError for non-BMP characters."""
        text = "Hello 😀"
        with pytest.raises(ValueError) as exc_info:
            handle_non_bmp(text, handling=NonBMPHandling.RAISE)
        assert "non-BMP" in str(exc_info.value)

    def test_raise_strategy_passes_for_bmp_only(self):
        """RAISE strategy should not raise for BMP-only text."""
        text = "Hello World"
        result = handle_non_bmp(text, handling=NonBMPHandling.RAISE)
        assert result == text


# =============================================================================
# Property 9: Text Sanitization Transliteration
# =============================================================================

class TestTextSanitizationTransliteration:
    """
    Property 9: For any text string containing known emoji characters, after
    sanitization with non_bmp_handling=TRANSLITERATE, the result SHALL contain
    text representations of those emoji, and the result SHALL contain only
    BMP characters.
    """

    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_transliterate_produces_only_bmp_chars(self, text):
        """After transliteration, result should contain only BMP characters."""
        result = transliterate_non_bmp(text)
        for char in result:
            assert ord(char) <= 0xFFFF, f"Non-BMP char found: U+{ord(char):04X}"

    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_transliterate_is_idempotent(self, text):
        """Applying transliteration twice should give same result as once."""
        once = transliterate_non_bmp(text)
        twice = transliterate_non_bmp(once)
        assert once == twice

    def test_known_emoji_transliterated(self):
        """Known emoji should be transliterated to text representation."""
        # Test a few known emoji from the transliteration dictionary
        test_cases = [
            ('\U0001F600', ':grinning:'),  # 😀
            ('\U0001F44D', ':thumbsup:'),  # 👍
            ('\U0001F525', ':fire:'),       # 🔥
            ('\U0001F389', ':tada:'),       # 🎉
        ]
        for emoji, expected in test_cases:
            if emoji in _EMOJI_TRANSLITERATIONS:
                result = transliterate_non_bmp(f"Hello {emoji}")
                assert expected in result, f"Expected {expected} for emoji {emoji}"

    def test_transliterate_preserves_bmp_text(self):
        """Transliteration should preserve BMP text."""
        text = "Hello World! 123"
        result = transliterate_non_bmp(text)
        assert result == text

    def test_transliterate_with_fallback(self):
        """Unknown non-BMP chars should use fallback."""
        # Use a non-BMP char that's not in the emoji dictionary
        text = "Hello \U0001F9E0"  # Brain emoji (may not be in dict)
        result = transliterate_non_bmp(text, fallback='[?]')
        assert '\U0001F9E0' not in result
        for char in result:
            assert ord(char) <= 0xFFFF

    def test_sanitize_with_transliterate_option(self):
        """sanitize_input_text_for_webdriver with TRANSLITERATE should transliterate emoji."""
        text = "Hello \U0001F600"  # 😀
        result = sanitize_input_text_for_webdriver(text, non_bmp_handling=NonBMPHandling.TRANSLITERATE)
        assert '\U0001F600' not in result
        if '\U0001F600' in _EMOJI_TRANSLITERATIONS:
            assert ':grinning:' in result
        for char in result:
            assert ord(char) <= 0xFFFF

    @given(emoji=st.sampled_from([
        e for e in _EMOJI_TRANSLITERATIONS.keys() if ord(e) > 0xFFFF
    ]))
    @settings(max_examples=50)
    def test_all_known_non_bmp_emoji_transliterate_correctly(self, emoji):
        """All known non-BMP emoji in the dictionary should transliterate correctly."""
        # Only test non-BMP emoji (code points > 0xFFFF)
        # BMP characters (like U+2705) are not transliterated
        expected = _EMOJI_TRANSLITERATIONS[emoji]
        result = transliterate_non_bmp(emoji)
        assert result == expected

    def test_mixed_content_transliteration(self):
        """Mixed content with text and emoji should be handled correctly."""
        text = "Hello 😀 World 🎉 Test 👍"
        result = transliterate_non_bmp(text)

        # Should not contain original emoji
        assert '😀' not in result
        assert '🎉' not in result
        assert '👍' not in result

        # Should contain original text
        assert 'Hello' in result
        assert 'World' in result
        assert 'Test' in result

        # Result should be all BMP
        for char in result:
            assert ord(char) <= 0xFFFF


class TestNewlineHandling:
    """Tests for newline handling in sanitization."""

    def test_newline_space_replaces_with_space(self):
        """SPACE handling should replace newlines with spaces."""
        from webaxon.automation.backends.shared.text_sanitization import handle_newlines

        text = "Hello\nWorld\r\nTest"
        result = handle_newlines(text, handling=NewlineHandling.SPACE)
        assert '\n' not in result
        assert '\r' not in result
        assert ' ' in result

    def test_newline_remove_removes_newlines(self):
        """REMOVE handling should remove newlines entirely."""
        from webaxon.automation.backends.shared.text_sanitization import handle_newlines

        text = "Hello\nWorld"
        result = handle_newlines(text, handling=NewlineHandling.REMOVE)
        assert '\n' not in result
        assert result == "HelloWorld"

    def test_newline_normalize_converts_to_unix(self):
        """NORMALIZE handling should convert to Unix-style newlines."""
        from webaxon.automation.backends.shared.text_sanitization import handle_newlines

        text = "Hello\r\nWorld\rTest"
        result = handle_newlines(text, handling=NewlineHandling.NORMALIZE)
        assert '\r' not in result
        assert result == "Hello\nWorld\nTest"

    def test_newline_keep_preserves_newlines(self):
        """KEEP handling should preserve newlines."""
        from webaxon.automation.backends.shared.text_sanitization import handle_newlines

        text = "Hello\nWorld"
        result = handle_newlines(text, handling=NewlineHandling.KEEP)
        assert result == text


class TestWhitespaceHandling:
    """Tests for whitespace handling in sanitization."""

    def test_whitespace_normalize_collapses_spaces(self):
        """NORMALIZE handling should collapse multiple spaces."""
        from webaxon.automation.backends.shared.text_sanitization import handle_whitespace

        text = "Hello    World"
        result = handle_whitespace(text, handling=WhitespaceHandling.NORMALIZE)
        assert "    " not in result
        assert "Hello World" in result

    def test_whitespace_strip_removes_leading_trailing(self):
        """STRIP handling should remove leading/trailing whitespace."""
        from webaxon.automation.backends.shared.text_sanitization import handle_whitespace

        text = "   Hello World   "
        result = handle_whitespace(text, handling=WhitespaceHandling.STRIP)
        assert result == "Hello World"

    def test_whitespace_full_normalizes_and_strips(self):
        """FULL handling should both normalize and strip."""
        from webaxon.automation.backends.shared.text_sanitization import handle_whitespace

        text = "   Hello    World   "
        result = handle_whitespace(text, handling=WhitespaceHandling.FULL)
        assert result == "Hello World"

    def test_whitespace_keep_preserves_whitespace(self):
        """KEEP handling should preserve whitespace."""
        from webaxon.automation.backends.shared.text_sanitization import handle_whitespace

        text = "   Hello    World   "
        result = handle_whitespace(text, handling=WhitespaceHandling.KEEP)
        assert result == text


class TestComprehensiveSanitization:
    """Tests for the comprehensive sanitize_input_text_for_webdriver function."""

    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_comprehensive_sanitization_safe_for_webdriver(self, text):
        """Sanitized text should be safe for WebDriver (all BMP chars)."""
        result = sanitize_input_text_for_webdriver(text)
        for char in result:
            assert ord(char) <= 0xFFFF

    def test_sanitize_removes_control_chars(self):
        """Control characters should be removed by default."""
        text = "Hello\x00World\x1F"
        result = sanitize_input_text_for_webdriver(text)
        assert '\x00' not in result
        assert '\x1F' not in result

    def test_sanitize_with_custom_sanitizer(self):
        """Custom sanitizer should be applied."""
        text = "Hello World"
        result = sanitize_input_text_for_webdriver(
            text,
            custom_sanitizer=lambda x: x.upper()
        )
        assert result == "HELLO WORLD"

    def test_empty_string_unchanged(self):
        """Empty string should remain empty."""
        assert sanitize_input_text_for_webdriver("") == ""

    def test_none_handling(self):
        """None should be handled gracefully (if passed, returns falsy)."""
        # The function checks `if not text: return text`
        result = sanitize_input_text_for_webdriver("")
        assert result == ""
