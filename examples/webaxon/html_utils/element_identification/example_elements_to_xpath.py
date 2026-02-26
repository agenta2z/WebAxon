"""
Example: Using elements_to_xpath to generate lean xpaths for HTML elements.

This example demonstrates how to use elements_to_xpath to generate unique,
stable xpaths for HTML elements found via BeautifulSoup.

Usage:
    python example_elements_to_xpath.py
"""

import os
import sys

# Add project root to path for local imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

from bs4 import BeautifulSoup
from lxml import etree

from webaxon.html_utils.element_identification import elements_to_xpath, XPathResolutionMode

# Load test HTML file
html_path = os.path.join(project_root, "test_data", "google_search.html")
with open(html_path, "r", encoding="utf-8") as f:
    html_content = f.read()

# Parse HTML with BeautifulSoup
soup = BeautifulSoup(html_content, 'html.parser')

# Find Google search button
search_btn = soup.find('input', {'value': 'Google Search'})
if search_btn:
    xpath = elements_to_xpath(
        search_btn, html_content, max_depth=-1,
        resolution_mode=XPathResolutionMode.MATCH_BY_HTML
    )
    print(f"Google Search button XPath: {xpath}")

    # Validate xpath
    tree = etree.HTML(html_content)
    elements = tree.xpath(xpath)
    print(f"Found {len(elements)} element(s)")
    if elements:
        print(f"Element HTML: {etree.tostring(elements[0], encoding='unicode')}")
