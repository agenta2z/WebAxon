"""
Pytest fixtures and helper functions for clean_html tests.

This module provides shared fixtures and utilities for testing the clean_html function,
particularly focusing on activation flag behavior and container preservation.
"""

import pytest
from pathlib import Path
from bs4 import BeautifulSoup
import re


@pytest.fixture
def slack_test_html():
    """
    Load slack_test_page.html for testing.

    This fixture loads the real Slack application HTML that contains ~75 div elements
    with 'scroll', 'list', or 'view' in their class/name/title attributes.

    Returns:
        str: Complete HTML content of slack_test_page.html
    """
    # Load from test_data folder in the same directory
    test_file_dir = Path(__file__).parent
    input_path = test_file_dir / 'test_data' / 'slack_test_page.html'

    if not input_path.exists():
        pytest.skip(f"Test HTML file not found: {input_path}")

    return input_path.read_text(encoding='utf-8')


def count_divs_with_pattern(html: str, pattern: str) -> int:
    """
    Count div elements where class, name, or title attributes match the given pattern.

    This helper function searches for divs that have the specified pattern in:
    - class attribute (checks all classes in the list)
    - name, data-name, aria-name attributes
    - title, aria-title attributes

    Args:
        html: HTML string to search
        pattern: Regular expression pattern to match (e.g., r'scroll|list|view')

    Returns:
        int: Count of matching div elements

    Examples:
        >>> html = '<div class="scrollable-view"><p>Content</p></div><div>Other</div>'
        >>> count_divs_with_pattern(html, r'scroll')
        1
    """
    soup = BeautifulSoup(html, 'html.parser')
    count = 0

    for div in soup.find_all('div'):
        # Check class attribute (can be list or string)
        classes = div.get('class', [])
        if isinstance(classes, list):
            if any(re.search(pattern, cls, re.IGNORECASE) for cls in classes):
                count += 1
                continue
        elif isinstance(classes, str):
            if re.search(pattern, classes, re.IGNORECASE):
                count += 1
                continue

        # Check name-like attributes
        for attr in ['name', 'data-name', 'aria-name', 'title', 'aria-title']:
            val = div.get(attr)
            if val and re.search(pattern, str(val), re.IGNORECASE):
                count += 1
                break

    return count


def has_div_with_class(html: str, class_substring: str) -> bool:
    """
    Check if any div element has a class containing the specified substring.

    Args:
        html: HTML string to search
        class_substring: Substring to search for in class names (case-sensitive)

    Returns:
        bool: True if at least one matching div is found, False otherwise

    Examples:
        >>> html = '<div class="p-view_contents--sidebar">Content</div>'
        >>> has_div_with_class(html, 'view')
        True
        >>> has_div_with_class(html, 'nonexistent')
        False
    """
    soup = BeautifulSoup(html, 'html.parser')

    for div in soup.find_all('div'):
        classes = div.get('class', [])
        if isinstance(classes, list):
            if any(class_substring in cls for cls in classes):
                return True
        elif isinstance(classes, str):
            if class_substring in classes:
                return True

    return False


def extract_text_content(html: str) -> str:
    """
    Extract all text content from HTML for comparison purposes.

    This function strips all HTML tags and returns only the text content,
    useful for verifying that text is preserved even when container structure changes.

    Args:
        html: HTML string to extract text from

    Returns:
        str: Extracted text with spaces as separators, stripped of extra whitespace

    Examples:
        >>> html = '<div><p>Hello</p><p>World</p></div>'
        >>> extract_text_content(html)
        'Hello World'
    """
    soup = BeautifulSoup(html, 'html.parser')
    return soup.get_text(separator=' ', strip=True)


def count_total_divs(html: str) -> int:
    """
    Count total number of div elements in HTML.

    Args:
        html: HTML string to count divs in

    Returns:
        int: Total count of div elements
    """
    soup = BeautifulSoup(html, 'html.parser')
    return len(soup.find_all('div'))
