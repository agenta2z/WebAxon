"""
Debug script for FindElementInferencer with GoodTime HTML.

Usage:
    python debug_find_element.py
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

from science_modeling_tools.common.inferencers.api_inferencers.ag.ag_claude_api_inferencer import AgClaudeApiInferencer as ClaudeApiInferencer
from rich_python_utils.string_utils.formatting.template_manager import TemplateManager
from rich_python_utils.string_utils.formatting.handlebars_format import format_template as handlebars_format

from webaxon.automation.agents import FindElementInferencer

# =============================================================================
# PASTE YOUR SANITIZED HTML HERE (between the triple quotes)
# =============================================================================
HTML_CONTENT = """
<head __id__="1">
<title __id__="28">✏️ Katie Meringolo - Create Interview - GoodTime</title>
</head>
<div __id__="1625">
TEMPLATES
<div __id__="1636" class="_avatar_twdin_6">2</div><span __id__="1639">2 way sync PTECH Testing</span><button __id__="1642" class="_moreIcon_1ju00_1833"></button>
<div __id__="1652" class="_avatar_twdin_6">B</div><span __id__="1655">Back End Code Design Reverse Shadow Template</span><button __id__="1658" class="_moreIcon_1ju00_1833"></button>
<div __id__="1796" class="_avatar_twdin_6">S</div><span __id__="1799">S/RS_UAT_Q4FY25_Backend Coding - Code Design P40</span><button __id__="1802" class="_moreIcon_1ju00_1833"></button>
<div __id__="1812" class="_avatar_twdin_6">S</div><span __id__="1815">S/RS_UAT_Q4FY25_Backend Coding - Code Design P50</span><button __id__="1818" class="_moreIcon_1ju00_1833"></button>
<div __id__="1828" class="_avatar_twdin_6">S</div><span __id__="1831">S/RS_UAT_Q4FY25_Backend Coding - Code Design P60</span><button __id__="1834" class="_moreIcon_1ju00_1833"></button>
</div>
<div __id__="1547" class="_DrawerNotesHeaderTitle_16upe_15">ACTIVITY</div>
<textarea __id__="1589" class="_mentions__input_1hgvt_19" disabled="">
Level of Job
P40
Job Family Group
Engineering
Select the Engineering interview types that need to be scheduled in this round.
Backend Coding - Code Design
</textarea>
"""

# =============================================================================
# SETUP INFERENCER
# =============================================================================
print("Setting up FindElementInferencer...")

reasoner = ClaudeApiInferencer(
    max_retry=3,
    min_retry_wait=1.0,
    max_retry_wait=5.0,
)

templates_path = os.path.join(project_root, "src", "webaxon", "automation", "agents", "prompt_templates")
template_manager = TemplateManager(
    templates=templates_path,
    template_formatter=handlebars_format,
)

find_element_inferencer = FindElementInferencer(
    base_inferencer=reasoner,
    template_manager=template_manager,
)

# =============================================================================
# QUERY QUERIES
# =============================================================================

def run_query(description: str):
    """Run a query and show the result."""
    print(f"\n{'='*70}")
    print(f"QUERY: {description[:100]}...")
    print('='*70)

    try:
        result = find_element_inferencer(
            html_source=HTML_CONTENT,
            description=description,
        )
        print(f"RESULT: {result}")
        return result
    except Exception as e:
        print(f"ERROR: {e}")
        return None


# Query 1: Simple query - find a specific template
print("\n" + "#"*70)
print("# QUERY 1: Simple template query")
print("#"*70)
run_query("Find the template named 'S/RS_UAT_Q4FY25_Backend Coding - Code Design P40'")

# Query 2: The actual query from create_goodtime_template_selection_graph.py
print("\n" + "#"*70)
print("# QUERY 2: Full matching query (from workflow)")
print("#"*70)
run_query("""Find the template that best matches the candidate notes in the ACTIVITY section.
The notes contain TWO key pieces of information to match:
1. Interview type (look for 'Select the Engineering interview types' - e.g., 'Backend Coding - Code Design')
2. Job level (look for 'Level of Job' - e.g., 'P40')

Templates are listed in the 'TEMPLATES' section as <span> elements with names like
'S/RS_UAT_Q4FY25_Backend Coding - Code Design P40'.

Select the <span> element containing the template name that matches BOTH the interview type AND the level.
For example, if notes say 'Backend Coding - Code Design' and 'P40', select the template
'S/RS_UAT_Q4FY25_Backend Coding - Code Design P40'.""")

# Query 3: Simpler version of the query
print("\n" + "#"*70)
print("# QUERY 3: Simplified query")
print("#"*70)
run_query("""Find the <span> element containing the template that matches:
- Interview type: 'Backend Coding - Code Design' (from ACTIVITY section)
- Level: 'P40' (from ACTIVITY section)
The matching template should be 'S/RS_UAT_Q4FY25_Backend Coding - Code Design P40'.""")

print("\n" + "="*70)
print("DEBUG COMPLETE")
print("="*70)
print("\nExpected result: 1799 (the __id__ of the P40 template span)")
