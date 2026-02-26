"""
Example: Using FindElementInferencer to find elements in Google Search HTML.

This example demonstrates how to use FindElementInferencer with Google Search HTML
to find elements like the search input and search button using natural language.

Prerequisites:
1. Set ANTHROPIC_API_KEY environment variable

Usage:
    python example_find_element_google_search.py
"""

import os
import sys

# Add project root to path for local imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", "..", "..", ".."))
projects_root = os.path.abspath(os.path.join(project_root, ".."))

# Add WebAgent src
sys.path.insert(0, os.path.join(project_root, "src"))

# Add science packages if they exist
for pkg in ["SciencePythonUtils", "ScienceModelingTools"]:
    pkg_src = os.path.join(projects_root, pkg, "src")
    if os.path.exists(pkg_src) and pkg_src not in sys.path:
        sys.path.insert(0, pkg_src)

from science_modeling_tools.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_format

from webaxon.automation.agents import FindElementInferencer

# Load test HTML file
html_path = os.path.join(project_root, "test_data", "google_search.html")
with open(html_path, "r", encoding="utf-8") as f:
    html_content = f.read()

# Create the base inferencer (LLM client)
reasoner = ClaudeApiInferencer(
    max_retry=3,
    min_retry_wait=1.0,
    max_retry_wait=5.0,
)

# Create template manager pointing to bundled templates
templates_path = os.path.join(project_root, "src", "webaxon", "automation", "agents", "prompt_templates")
template_manager = TemplateManager(
    templates=templates_path,
    template_formatter=handlebars_format,
)

# Create FindElementInferencer
find_element_inferencer = FindElementInferencer(
    base_inferencer=reasoner,
    template_manager=template_manager,
)

from lxml import etree

def find_and_validate(description: str):
    """Find element and validate the xpath."""
    print(f"\n{'='*60}")
    print(f"Finding: {description}")
    print('='*60)

    xpath = find_element_inferencer(
        html_source=html_content,
        description=description,
    )
    print(f"XPath: {xpath}")

    # Validate xpath by finding the element in HTML
    tree = etree.HTML(html_content)
    elements = tree.xpath(xpath)
    print(f"Found {len(elements)} element(s)")
    if elements:
        html_str = etree.tostring(elements[0], encoding='unicode')
        # Truncate long HTML for display
        if len(html_str) > 200:
            html_str = html_str[:200] + "..."
        print(f"Element HTML: {html_str}")
    return xpath

# Example 1: Find the search input box
find_and_validate("the search input box where users type their query")

# Example 2: Find the Google Search button
find_and_validate("the Google Search button")

# Example 3: Find the I'm Feeling Lucky button
find_and_validate("the I'm Feeling Lucky button")
