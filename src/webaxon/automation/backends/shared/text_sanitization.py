"""
Text sanitization utilities for Selenium WebDriver input operations.

ChromeDriver only supports characters in the Basic Multilingual Plane (BMP),
which includes Unicode code points from U+0000 to U+FFFF. Characters outside
this range (like emoji, certain CJK characters, and special symbols) will
cause WebDriverException errors.

This module provides utilities to sanitize text before sending to WebDriver.
"""

import re
import unicodedata
from enum import StrEnum
from typing import Optional, Callable


class NonBMPHandling(StrEnum):
    """How to handle non-BMP characters (code points > U+FFFF)."""
    KEEP = "keep"               # Keep non-BMP characters as-is (only works with JavaScript implementation)
    REMOVE = "remove"           # Remove non-BMP characters entirely
    REPLACE = "replace"         # Replace with a placeholder character
    TRANSLITERATE = "transliterate"  # Attempt to transliterate (e.g., emoji to text)
    RAISE = "raise"             # Raise an exception if non-BMP found


class NewlineHandling(StrEnum):
    """How to handle newline characters."""
    KEEP = "keep"               # Keep newlines as-is
    SPACE = "space"             # Replace with single space
    REMOVE = "remove"           # Remove entirely
    NORMALIZE = "normalize"     # Normalize to \n only (remove \r)


class WhitespaceHandling(StrEnum):
    """How to handle whitespace."""
    KEEP = "keep"               # Keep as-is
    NORMALIZE = "normalize"     # Collapse multiple spaces to single
    STRIP = "strip"             # Strip leading/trailing only
    FULL = "full"               # Both normalize and strip


# Common emoji descriptions for transliteration
_EMOJI_TRANSLITERATIONS = {
    # Faces
    '\U0001F600': ':grinning:',
    '\U0001F601': ':beaming:',
    '\U0001F602': ':joy:',
    '\U0001F603': ':smiley:',
    '\U0001F604': ':smile:',
    '\U0001F605': ':sweat_smile:',
    '\U0001F606': ':laughing:',
    '\U0001F607': ':innocent:',
    '\U0001F608': ':smiling_imp:',
    '\U0001F609': ':wink:',
    '\U0001F60A': ':blush:',
    '\U0001F60B': ':yum:',
    '\U0001F60C': ':relieved:',
    '\U0001F60D': ':heart_eyes:',
    '\U0001F60E': ':sunglasses:',
    '\U0001F60F': ':smirk:',
    '\U0001F610': ':neutral_face:',
    '\U0001F611': ':expressionless:',
    '\U0001F612': ':unamused:',
    '\U0001F613': ':sweat:',
    '\U0001F614': ':pensive:',
    '\U0001F615': ':confused:',
    '\U0001F616': ':confounded:',
    '\U0001F617': ':kissing:',
    '\U0001F618': ':kissing_heart:',
    '\U0001F619': ':kissing_smiling_eyes:',
    '\U0001F61A': ':kissing_closed_eyes:',
    '\U0001F61B': ':stuck_out_tongue:',
    '\U0001F61C': ':stuck_out_tongue_winking_eye:',
    '\U0001F61D': ':stuck_out_tongue_closed_eyes:',
    '\U0001F61E': ':disappointed:',
    '\U0001F61F': ':worried:',
    '\U0001F620': ':angry:',
    '\U0001F621': ':rage:',
    '\U0001F622': ':cry:',
    '\U0001F623': ':persevere:',
    '\U0001F624': ':triumph:',
    '\U0001F625': ':disappointed_relieved:',
    '\U0001F626': ':frowning:',
    '\U0001F627': ':anguished:',
    '\U0001F628': ':fearful:',
    '\U0001F629': ':weary:',
    '\U0001F62A': ':sleepy:',
    '\U0001F62B': ':tired_face:',
    '\U0001F62C': ':grimacing:',
    '\U0001F62D': ':sob:',
    '\U0001F62E': ':open_mouth:',
    '\U0001F62F': ':hushed:',
    '\U0001F630': ':cold_sweat:',
    '\U0001F631': ':scream:',
    '\U0001F632': ':astonished:',
    '\U0001F633': ':flushed:',
    '\U0001F634': ':sleeping:',
    '\U0001F635': ':dizzy_face:',
    '\U0001F636': ':no_mouth:',
    '\U0001F637': ':mask:',
    # Gestures
    '\U0001F44D': ':thumbsup:',
    '\U0001F44E': ':thumbsdown:',
    '\U0001F44B': ':wave:',
    '\U0001F44F': ':clap:',
    '\U0001F64F': ':pray:',
    # Hearts
    '\u2764': ':heart:',
    '\U0001F494': ':broken_heart:',
    '\U0001F495': ':two_hearts:',
    '\U0001F496': ':sparkling_heart:',
    '\U0001F497': ':heartpulse:',
    '\U0001F498': ':cupid:',
    '\U0001F499': ':blue_heart:',
    '\U0001F49A': ':green_heart:',
    '\U0001F49B': ':yellow_heart:',
    '\U0001F49C': ':purple_heart:',
    # Common symbols
    '\U0001F4A1': ':bulb:',
    '\U0001F4A5': ':boom:',
    '\U0001F4AF': ':100:',
    '\U0001F525': ':fire:',
    '\u2B50': ':star:',
    '\U0001F31F': ':star2:',
    '\U0001F389': ':tada:',
    '\U0001F388': ':balloon:',
    '\U0001F381': ':gift:',
    '\U0001F3C6': ':trophy:',
    # Checks and marks
    '\u2705': ':white_check_mark:',
    '\u274C': ':x:',
    '\u2714': ':heavy_check_mark:',
    '\u2716': ':heavy_multiplication_x:',
    '\u26A0': ':warning:',
    # Arrows
    '\u27A1': ':arrow_right:',
    '\u2B05': ':arrow_left:',
    '\u2B06': ':arrow_up:',
    '\u2B07': ':arrow_down:',
}


def is_bmp_character(char: str) -> bool:
    """
    Check if a character is within the Basic Multilingual Plane (BMP).

    The BMP contains code points from U+0000 to U+FFFF.

    Args:
        char: A single character to check

    Returns:
        True if the character is in BMP, False otherwise
    """
    return ord(char) <= 0xFFFF


def contains_non_bmp(text: str) -> bool:
    """
    Check if text contains any non-BMP characters.

    Args:
        text: The text to check

    Returns:
        True if text contains non-BMP characters, False otherwise
    """
    return any(ord(c) > 0xFFFF for c in text)


def get_non_bmp_characters(text: str) -> list:
    """
    Extract all non-BMP characters from text.

    Args:
        text: The text to scan

    Returns:
        List of tuples (character, position, code_point, unicode_name)
    """
    non_bmp = []
    for i, char in enumerate(text):
        if ord(char) > 0xFFFF:
            try:
                name = unicodedata.name(char, 'UNKNOWN')
            except ValueError:
                name = 'UNKNOWN'
            non_bmp.append((char, i, ord(char), name))
    return non_bmp


def remove_non_bmp(text: str) -> str:
    """
    Remove all non-BMP characters from text.

    Args:
        text: The text to sanitize

    Returns:
        Text with non-BMP characters removed
    """
    return ''.join(c for c in text if ord(c) <= 0xFFFF)


def replace_non_bmp(text: str, replacement: str = '\uFFFD') -> str:
    """
    Replace non-BMP characters with a placeholder.

    Args:
        text: The text to sanitize
        replacement: The replacement character (default: U+FFFD REPLACEMENT CHARACTER)

    Returns:
        Text with non-BMP characters replaced
    """
    return ''.join(c if ord(c) <= 0xFFFF else replacement for c in text)


def transliterate_non_bmp(text: str, fallback: str = '') -> str:
    """
    Attempt to transliterate non-BMP characters to ASCII-safe text representations.

    Uses known emoji mappings and falls back to Unicode character names.

    Args:
        text: The text to transliterate
        fallback: Fallback text for unknown characters (default: empty string)

    Returns:
        Text with non-BMP characters transliterated
    """
    result = []
    for char in text:
        if ord(char) <= 0xFFFF:
            result.append(char)
        elif char in _EMOJI_TRANSLITERATIONS:
            result.append(_EMOJI_TRANSLITERATIONS[char])
        else:
            # Try to get Unicode name as fallback
            try:
                name = unicodedata.name(char, None)
                if name:
                    # Convert name to a shorter form
                    short_name = name.lower().replace(' ', '_')
                    result.append(f':{short_name}:')
                else:
                    result.append(fallback)
            except ValueError:
                result.append(fallback)
    return ''.join(result)


def handle_non_bmp(
    text: str,
    handling: NonBMPHandling = NonBMPHandling.REMOVE,
    replacement: str = '\uFFFD',
    transliterate_fallback: str = ''
) -> str:
    """
    Handle non-BMP characters according to the specified strategy.

    Args:
        text: The text to process
        handling: How to handle non-BMP characters
        replacement: Replacement character for REPLACE handling
        transliterate_fallback: Fallback for unknown chars in TRANSLITERATE handling

    Returns:
        Processed text

    Raises:
        ValueError: If handling is RAISE and non-BMP characters are found
    """
    if handling == NonBMPHandling.KEEP:
        return text
    elif handling == NonBMPHandling.REMOVE:
        return remove_non_bmp(text)
    elif handling == NonBMPHandling.REPLACE:
        return replace_non_bmp(text, replacement)
    elif handling == NonBMPHandling.TRANSLITERATE:
        return transliterate_non_bmp(text, transliterate_fallback)
    elif handling == NonBMPHandling.RAISE:
        non_bmp = get_non_bmp_characters(text)
        if non_bmp:
            char_info = ', '.join(
                f"'{c}' (U+{cp:04X}, {name})"
                for c, _, cp, name in non_bmp[:5]
            )
            if len(non_bmp) > 5:
                char_info += f", ... and {len(non_bmp) - 5} more"
            raise ValueError(
                f"Text contains {len(non_bmp)} non-BMP character(s) that ChromeDriver "
                f"cannot handle: {char_info}"
            )
        return text
    else:
        raise ValueError(f"Unknown NonBMPHandling: {handling}")


def handle_newlines(
    text: str,
    handling: NewlineHandling = NewlineHandling.SPACE
) -> str:
    """
    Handle newline characters according to the specified strategy.

    Args:
        text: The text to process
        handling: How to handle newlines

    Returns:
        Processed text
    """
    if handling == NewlineHandling.KEEP:
        return text
    elif handling == NewlineHandling.SPACE:
        # Replace all newline variants with space
        return re.sub(r'[\r\n]+', ' ', text)
    elif handling == NewlineHandling.REMOVE:
        return re.sub(r'[\r\n]+', '', text)
    elif handling == NewlineHandling.NORMALIZE:
        # Convert \r\n and \r to just \n
        return text.replace('\r\n', '\n').replace('\r', '\n')
    else:
        raise ValueError(f"Unknown NewlineHandling: {handling}")


def handle_whitespace(
    text: str,
    handling: WhitespaceHandling = WhitespaceHandling.NORMALIZE
) -> str:
    """
    Handle whitespace according to the specified strategy.

    Args:
        text: The text to process
        handling: How to handle whitespace

    Returns:
        Processed text
    """
    if handling == WhitespaceHandling.KEEP:
        return text
    elif handling == WhitespaceHandling.NORMALIZE:
        # Collapse multiple spaces/tabs to single space (preserving newlines)
        return re.sub(r'[^\S\n]+', ' ', text)
    elif handling == WhitespaceHandling.STRIP:
        return text.strip()
    elif handling == WhitespaceHandling.FULL:
        # Both normalize and strip
        text = re.sub(r'[^\S\n]+', ' ', text)
        return text.strip()
    else:
        raise ValueError(f"Unknown WhitespaceHandling: {handling}")


def remove_control_characters(text: str, keep_whitespace: bool = True) -> str:
    """
    Remove control characters from text.

    Args:
        text: The text to process
        keep_whitespace: If True, preserve space, tab, and newline characters

    Returns:
        Text with control characters removed
    """
    if keep_whitespace:
        # Remove control chars except space, tab, newline, carriage return
        return ''.join(
            c for c in text
            if not unicodedata.category(c).startswith('C') or c in ' \t\n\r'
        )
    else:
        return ''.join(
            c for c in text
            if not unicodedata.category(c).startswith('C')
        )


def sanitize_input_text_for_webdriver(
    text: str,
    non_bmp_handling: NonBMPHandling = NonBMPHandling.REMOVE,
    newline_handling: NewlineHandling = NewlineHandling.SPACE,
    whitespace_handling: WhitespaceHandling = WhitespaceHandling.NORMALIZE,
    remove_control_chars: bool = True,
    non_bmp_replacement: str = '\uFFFD',
    transliterate_fallback: str = '',
    custom_sanitizer: Optional[Callable[[str], str]] = None
) -> str:
    """
    Comprehensive text sanitization for WebDriver input.

    Applies multiple sanitization steps to ensure text is compatible with
    ChromeDriver's send_keys method.

    Args:
        text: The text to sanitize
        non_bmp_handling: How to handle non-BMP characters (default: remove)
        newline_handling: How to handle newlines (default: replace with space)
        whitespace_handling: How to handle whitespace (default: normalize)
        remove_control_chars: Whether to remove control characters (default: True)
        non_bmp_replacement: Replacement char for non-BMP when using REPLACE handling
        transliterate_fallback: Fallback for TRANSLITERATE handling
        custom_sanitizer: Optional custom sanitization function to apply last

    Returns:
        Sanitized text safe for WebDriver input

    Example:
        >>> text = "Hello\\n\\nWorld! \\U0001F600"  # Contains emoji
        >>> sanitize_input_text_for_webdriver(text)
        'Hello World!'

        >>> sanitize_input_text_for_webdriver(text, non_bmp_handling=NonBMPHandling.TRANSLITERATE)
        'Hello World! :grinning:'
    """
    if not text:
        return text

    # Step 1: Handle non-BMP characters (must be first for ChromeDriver compatibility)
    text = handle_non_bmp(
        text,
        handling=non_bmp_handling,
        replacement=non_bmp_replacement,
        transliterate_fallback=transliterate_fallback
    )

    # Step 2: Remove control characters (if enabled)
    if remove_control_chars:
        text = remove_control_characters(text, keep_whitespace=True)

    # Step 3: Handle newlines
    text = handle_newlines(text, handling=newline_handling)

    # Step 4: Handle whitespace
    text = handle_whitespace(text, handling=whitespace_handling)

    # Step 5: Apply custom sanitizer (if provided)
    if custom_sanitizer is not None:
        text = custom_sanitizer(text)

    return text


def sanitize_input_text_for_webdriver_strict(text: str) -> str:
    """
    Strict sanitization: removes non-BMP, replaces newlines, normalizes whitespace.

    This is a convenience function with strict defaults suitable for single-line
    text inputs like search boxes.

    Args:
        text: The text to sanitize

    Returns:
        Strictly sanitized text
    """
    return sanitize_input_text_for_webdriver(
        text,
        non_bmp_handling=NonBMPHandling.REMOVE,
        newline_handling=NewlineHandling.SPACE,
        whitespace_handling=WhitespaceHandling.FULL,
        remove_control_chars=True
    )


def sanitize_input_text_for_webdriver_preserve_formatting(text: str) -> str:
    """
    Sanitization that preserves newlines and whitespace structure.

    This is a convenience function suitable for multi-line text areas where
    formatting matters.

    Args:
        text: The text to sanitize

    Returns:
        Sanitized text with formatting preserved
    """
    return sanitize_input_text_for_webdriver(
        text,
        non_bmp_handling=NonBMPHandling.REMOVE,
        newline_handling=NewlineHandling.NORMALIZE,
        whitespace_handling=WhitespaceHandling.KEEP,
        remove_control_chars=True
    )
