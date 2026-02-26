"""
XPath validation script for GoodTime template selection workflow.

This script tests the XPath selectors against the dev_data HTML files
to verify they correctly locate the target elements.

Usage:
    python xpath_dev.py
"""

import os
import sys
from lxml import etree
from bs4 import BeautifulSoup

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", "..", "..", ".."))
projects_root = os.path.abspath(os.path.join(project_root, ".."))
sys.path.insert(0, os.path.join(project_root, "src"))
for pkg in ["SciencePythonUtils", "ScienceModelingTools"]:
    pkg_src = os.path.join(projects_root, pkg, "src")
    if os.path.exists(pkg_src) and pkg_src not in sys.path:
        sys.path.insert(0, pkg_src)

from webaxon.html_utils.element_identification import elements_to_xpath, XPathResolutionMode

# Get paths
script_dir = os.path.dirname(os.path.abspath(__file__))
dev_data_dir = os.path.join(script_dir, "dev_data")

# HTML files
step1_html_path = os.path.join(dev_data_dir, "step1_entry_page.html")
step2_html_path = os.path.join(dev_data_dir, "step2_select_template_based_on_notes.html")

# XPath selectors from create_goodtime_template_selection_graph.py
XPATHS = {
    "step1": {
        "Katie Meringolo candidate": "//a[contains(@class, '_Interview_1kmia_9') and .//span[@class='_GuestName_1kmia_148' and text()='Katie Meringolo']]"
    },
    "step2": {
        "Select Template button": "//button[.//span[text()='Select Template']]",
        "Notes button": "//button[contains(@class, '_OpenFloatingNotesButton')]",
        "Template options": "//div[@data-test='template-option']",
        "Continue/Done button (original)": "//a[contains(@class, '_buttonTitle_yjkez_24') and contains(., 'Continue')]",
        "Continue/Done button (fixed)": "//a[contains(@class, '_buttonTitle_yjkez_24') and (contains(., 'Continue') or contains(., 'Done'))]"
    }
}


def truncate_html(html_str: str, max_len: int = 300) -> str:
    """Truncate HTML string for display."""
    if len(html_str) > max_len:
        return html_str[:max_len] + "..."
    return html_str


def test_xpath(tree: etree._Element, xpath: str, name: str) -> None:
    """Test an XPath against the HTML tree and print results."""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"XPath: {xpath}")
    print('='*70)

    try:
        elements = tree.xpath(xpath)
        print(f"Found: {len(elements)} element(s)")

        if elements:
            for i, elem in enumerate(elements[:3]):  # Show max 3 elements
                html_str = etree.tostring(elem, encoding='unicode', pretty_print=True)
                print(f"\n--- Element {i+1} ---")
                print(f"Tag: <{elem.tag}>")

                # Show key attributes
                if elem.attrib:
                    attrs = dict(elem.attrib)
                    # Truncate long class names
                    if 'class' in attrs and len(attrs['class']) > 80:
                        attrs['class'] = attrs['class'][:80] + "..."
                    print(f"Attributes: {attrs}")

                # Show text content if any
                text = elem.text_content().strip() if hasattr(elem, 'text_content') else (elem.text or '').strip()
                if text:
                    text_preview = text[:100] + "..." if len(text) > 100 else text
                    print(f"Text: {text_preview}")

                print(f"HTML preview:\n{truncate_html(html_str)}")

            if len(elements) > 3:
                print(f"\n... and {len(elements) - 3} more elements")
        else:
            print("NO ELEMENTS FOUND - XPath may be incorrect!")

    except Exception as e:
        print(f"ERROR: {e}")


def main():
    print("="*70)
    print("XPath Validation for GoodTime Template Selection Workflow")
    print("="*70)

    # Load HTML files
    print(f"\nLoading step1: {step1_html_path}")
    with open(step1_html_path, 'r', encoding='utf-8') as f:
        step1_html = f.read()
    step1_tree = etree.HTML(step1_html)
    print(f"  Loaded ({len(step1_html):,} bytes)")

    print(f"\nLoading step2: {step2_html_path}")
    with open(step2_html_path, 'r', encoding='utf-8') as f:
        step2_html = f.read()
    step2_tree = etree.HTML(step2_html)
    print(f"  Loaded ({len(step2_html):,} bytes)")

    # Test Step 1 XPaths
    print("\n" + "#"*70)
    print("# STEP 1: Entry Page - Candidate Selection")
    print("#"*70)

    for name, xpath in XPATHS["step1"].items():
        test_xpath(step1_tree, xpath, name)

    # Test Step 2 XPaths
    print("\n" + "#"*70)
    print("# STEP 2: Template Selection Page")
    print("#"*70)

    for name, xpath in XPATHS["step2"].items():
        test_xpath(step2_tree, xpath, name)

    # Show template names for reference
    print("\n" + "#"*70)
    print("# TEMPLATE NAMES (for FindElementInferencer reference)")
    print("#"*70)
    template_elements = step2_tree.xpath("//div[@data-test='template-option']")
    for i, elem in enumerate(template_elements):
        # Try to find template name - look for title/header text
        name_elem = elem.xpath(".//div[contains(@class, '_title_') or contains(@class, 'title')]//text()")
        if not name_elem:
            # Fallback: get first substantial text
            all_text = elem.xpath(".//text()")
            name_elem = [t.strip() for t in all_text if t.strip() and len(t.strip()) > 3][:1]
        name = name_elem[0].strip() if name_elem else f"(Template {i+1})"
        print(f"  {i+1}. {name[:80]}")

    # Test elements_to_xpath on Katie Meringolo elements
    print("\n" + "#"*70)
    print("# elements_to_xpath TEST (Katie Meringolo)")
    print("#"*70)

    # Use BeautifulSoup to find elements and generate xpath
    soup1 = BeautifulSoup(step1_html, 'html.parser')
    katie_elements = soup1.select('a._Interview_1kmia_9')
    katie_elements = [e for e in katie_elements if 'Katie Meringolo' in e.get_text()]

    print(f"\nFound {len(katie_elements)} Katie Meringolo elements via BeautifulSoup")

    for i, elem in enumerate(katie_elements):
        print(f"\n--- Element {i+1} ---")
        # Show href for identification
        href = elem.get('href', 'N/A')
        print(f"href: ...{href[-50:]}" if len(href) > 50 else f"href: {href}")

        try:
            # Try UNIQUE_ONLY first
            xpath = elements_to_xpath(elem, step1_html, max_depth=5)
            print(f"elements_to_xpath (UNIQUE_ONLY): {xpath}")
        except ValueError as e:
            print(f"elements_to_xpath (UNIQUE_ONLY): FAILED - {e}")
            # Try with FIRST_MATCH mode
            try:
                xpath = elements_to_xpath(
                    elem, step1_html, max_depth=5,
                    resolution_mode=XPathResolutionMode.FIRST_MATCH
                )
                print(f"elements_to_xpath (FIRST_MATCH): {xpath}")
            except Exception as e2:
                print(f"elements_to_xpath (FIRST_MATCH): FAILED - {e2}")

    # Summary
    print("\n" + "="*70)
    print("VALIDATION COMPLETE")
    print("="*70)
    print("\nReview the output above to verify:")
    print("1. Each XPath found at least 1 element")
    print("2. The found elements match the expected UI components")
    print("3. Text content and attributes look correct")


if __name__ == "__main__":
    main()
