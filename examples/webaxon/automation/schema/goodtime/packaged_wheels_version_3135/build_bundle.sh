#!/bin/bash
# Build script for GoodTime Automation Bundle
# Creates a single compiled wheel from three packages: SciencePythonUtils, ScienceModelingTools, WebAgent

set -e  # Exit on any error

echo "================================================================================"
echo "  GoodTime Automation Bundle Builder"
echo "================================================================================"
echo ""

# Define Python version to use
PYTHON="/opt/anaconda3/bin/python"

# Verify Python version
echo "Using Python: $PYTHON"
$PYTHON --version
echo ""

# Define paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$SCRIPT_DIR/bundle_workspace"
BUNDLE_DIR="$WORKSPACE_DIR/goodtime_automation_bundle"
SRC_DIR="$BUNDLE_DIR/src/goodtime_automation_bundle"
DIST_DIR="$SCRIPT_DIR/release"

PROJECTS_ROOT="/Users/zgchen/PycharmProjects/MyProjects"
GOODTIME_DIR="/Users/zgchen/PycharmProjects/MyProjects/WebAgent/examples/automation/schema/goodtime"

# Step 1: Install Cython if needed
echo "[1/10] Checking Cython installation..."
if ! $PYTHON -c "import Cython" 2>/dev/null; then
    echo "Installing Cython..."
    $PYTHON -m pip install Cython
else
    echo "Cython already installed"
fi
echo ""

# Step 2: Clean previous builds
echo "[2/10] Cleaning previous builds..."
if [ -d "$WORKSPACE_DIR" ]; then
    echo "Removing old workspace..."
    rm -rf "$WORKSPACE_DIR"
fi
if [ -d "$DIST_DIR" ]; then
    echo "Removing old distribution..."
    rm -rf "$DIST_DIR"
fi
echo ""

# Step 3: Create directory structure
echo "[3/10] Creating workspace directory structure..."
mkdir -p "$SRC_DIR"
mkdir -p "$DIST_DIR"
echo "Created: $SRC_DIR"
echo "Created: $DIST_DIR"
echo ""

# Step 4: Copy source code from the three packages
echo "[4/10] Copying source code from packages..."

echo "  - Copying SciencePythonUtils (127 files)..."
cp -r "$PROJECTS_ROOT/SciencePythonUtils/src/science_python_utils" "$SRC_DIR/"

echo "  - Copying ScienceModelingTools (103 files)..."
cp -r "$PROJECTS_ROOT/ScienceModelingTools/src/science_modeling_tools" "$SRC_DIR/"

echo "  - Copying WebAgent (132 files + templates)..."
cp -r "$PROJECTS_ROOT/WebAgent/src/webagent" "$SRC_DIR/"

echo "Source code copied successfully"
echo ""

# Step 5: Generate setup.py with Cython configuration
echo "[5/10] Generating setup.py with Cython configuration..."
cat > "$BUNDLE_DIR/setup.py" << 'SETUP_PY'
from setuptools import setup, find_packages
from Cython.Build import cythonize
from Cython.Compiler.Errors import CompileError
from setuptools.extension import Extension
import os
import sys

# Collect all .py files to compile (excluding __init__.py)
py_files = []
pydantic_files = []  # Track Pydantic model files to skip

for root, dirs, files in os.walk("src"):
    for file in files:
        if file.endswith(".py") and file != "__init__.py":
            filepath = os.path.join(root, file)

            # Check if file contains Pydantic BaseModel
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Skip files with Pydantic models - they don't work with Cython
                    if 'BaseModel' in content and ('from pydantic' in content or 'import pydantic' in content):
                        pydantic_files.append(filepath)
                        continue
            except Exception:
                pass

            py_files.append(filepath)

print(f"Found {len(py_files)} Python modules to compile")
print(f"Skipping {len(pydantic_files)} Pydantic model files (incompatible with Cython)")
print(f"Compiling files individually to skip problematic files...")

# Compile each file individually to handle errors gracefully
successful_extensions = []
failed_files = []

for i, py_file in enumerate(py_files, 1):
    module_name = py_file.replace("src/", "").replace("/", ".").replace(".py", "")
    ext = Extension(name=module_name, sources=[py_file])

    try:
        # Try to compile this single file
        result = cythonize(
            [ext],
            compiler_directives={
                'language_level': "3",
                'embedsignature': True,
                'annotation_typing': False,  # Treat type hints as documentation only
            },
            force=False,
            quiet=True,  # Suppress per-file output
        )
        successful_extensions.extend(result)
        if i % 50 == 0:
            print(f"  Progress: {i}/{len(py_files)} files processed, {len(successful_extensions)} compiled successfully")
    except (CompileError, Exception) as e:
        # Skip this file and continue
        failed_files.append((py_file, str(e)[:100]))

print(f"\n=== Compilation Summary ===")
print(f"Total Python files found: {len(py_files) + len(pydantic_files)}")
print(f"Pydantic models skipped: {len(pydantic_files)} (left as .py for runtime compatibility)")
print(f"Files attempted: {len(py_files)}")
print(f"Successfully compiled: {len(successful_extensions)}")
print(f"Failed: {len(failed_files)}")
total_protected = len(successful_extensions)
total_files = len(py_files) + len(pydantic_files)
print(f"Protection rate: {total_protected*100//total_files}% compiled to native code")

if failed_files and len(failed_files) <= 20:
    print(f"\nFailed files:")
    for file, error in failed_files[:20]:
        print(f"  - {file}")

setup(
    name="goodtime_automation_bundle",
    version="1.0.2",
    description="Compiled bundle of SciencePythonUtils, ScienceModelingTools, and WebAgent",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    ext_modules=successful_extensions,
    # Explicit package_data for non-Python files (more reliable than MANIFEST.in for wheels)
    package_data={
        '': ['*.hbs', '*.json', '*.md', '*.pkl'],  # Include these extensions in all packages
    },
    include_package_data=True,
    python_requires=">=3.8",
    zip_safe=False,
)
SETUP_PY

echo "Generated setup.py"
echo ""

# Step 6: Generate MANIFEST.in for resource files
echo "[6/10] Generating MANIFEST.in for resource files..."
cat > "$BUNDLE_DIR/MANIFEST.in" << 'MANIFEST_IN'
# Include all resource files from the packages
# Note: recursive-include handles recursion - no need for **/ prefix
recursive-include src/goodtime_automation_bundle/science_python_utils *.md *.pkl *.json
recursive-include src/goodtime_automation_bundle/science_modeling_tools *.json
recursive-include src/goodtime_automation_bundle/webagent *.hbs
MANIFEST_IN

echo "Generated MANIFEST.in"
echo ""

# Step 7: Generate __init__.py with package re-exports
echo "[7/10] Generating __init__.py with package re-exports..."
cat > "$SRC_DIR/__init__.py" << 'INIT_PY'
"""
GoodTime Automation Bundle

This package bundles three packages into a single compiled wheel:
- SciencePythonUtils
- ScienceModelingTools
- WebAgent

The packages are re-exported under their original names for import compatibility.
"""

import sys

# Import the bundled packages
try:
    from goodtime_automation_bundle import science_python_utils
    from goodtime_automation_bundle import science_modeling_tools
    from goodtime_automation_bundle import webagent
except ImportError:
    # During build, these imports might not work yet
    pass
else:
    # Register them under their original names in sys.modules
    # This allows imports like "from science_python_utils.string_utils import ..."
    sys.modules['science_python_utils'] = science_python_utils
    sys.modules['science_modeling_tools'] = science_modeling_tools
    sys.modules['webagent'] = webagent

__version__ = "1.0.2"
__all__ = ['science_python_utils', 'science_modeling_tools', 'webagent']
INIT_PY

echo "Generated __init__.py"
echo ""

# Step 8: Build the wheel with Cython compilation
echo "[8/10] Building wheel with Cython compilation..."
echo "This will take 5-10 minutes to compile 362 Python modules..."
cd "$BUNDLE_DIR"
$PYTHON setup.py bdist_wheel
echo ""
echo "Wheel built successfully!"
echo ""

# Step 9: Copy output files to distribution directory
echo "[9/10] Copying files to distribution directory..."

# Copy the wheel
WHEEL_FILE=$(ls "$BUNDLE_DIR/dist"/*.whl | head -1)
if [ -f "$WHEEL_FILE" ]; then
    cp "$WHEEL_FILE" "$DIST_DIR/"
    echo "  - Copied wheel: $(basename $WHEEL_FILE)"
else
    echo "ERROR: Wheel file not found!"
    exit 1
fi

# Copy launcher scripts
cp "$GOODTIME_DIR/run_goodtime_template_selection_graph_with_monitor.py" "$DIST_DIR/"
echo "  - Copied: run_goodtime_template_selection_graph_with_monitor.py"

# Patch the runner script to import goodtime_automation_bundle FIRST
# This is required because the bundle registers modules in sys.modules
# Without this, 'import webaxon' will fail when using the bundle
cat > "$DIST_DIR/_patch_imports.py" << 'PATCH_SCRIPT'
import re
import sys

filepath = sys.argv[1]
with open(filepath, 'r') as f:
    content = f.read()

# The bundle import block to insert
bundle_import = '''# =============================================================================
# Import goodtime_automation_bundle first (for bundle wheel mode)
# This registers science_python_utils, science_modeling_tools, webagent in sys.modules
# =============================================================================
try:
    import goodtime_automation_bundle
    print("✓ Imported goodtime_automation_bundle (modules registered in sys.modules)")
except ImportError:
    # Bundle not installed - will try to import from source or installed packages
    pass


'''

# Find the import section header and insert bundle import before it
# Pattern matches the "Import packages - fail fast" section
pattern = r'(# =+\n# Import packages - fail fast with clear error\n# =+\ntry:)'
if re.search(pattern, content):
    content = re.sub(pattern, bundle_import + r'\1', content)
    print("  ✓ Patched: Added goodtime_automation_bundle import before package imports")
else:
    print("  ⚠ Warning: Could not find import section pattern to patch")

with open(filepath, 'w') as f:
    f.write(content)
PATCH_SCRIPT

$PYTHON "$DIST_DIR/_patch_imports.py" "$DIST_DIR/run_goodtime_template_selection_graph_with_monitor.py"
rm "$DIST_DIR/_patch_imports.py"

cp "$GOODTIME_DIR/create_goodtime_template_selection_graph_with_monitor.py" "$DIST_DIR/"
echo "  - Copied: create_goodtime_template_selection_graph_with_monitor.py"

cp "$GOODTIME_DIR/path_utils.py" "$DIST_DIR/"
echo "  - Copied: path_utils.py"

# Generate launch.sh with correct version and dependencies
# Generate launch.sh using the dedicated script (for fast iterations without full rebuild)
# The create_launch.sh script can also be run independently to update launch.sh only
"$SCRIPT_DIR/create_launch.sh" | tail -n 5  # Show only the success message

# Generate README.md
BUILD_DATE=$(date '+%Y-%m-%d %H:%M')
cat > "$DIST_DIR/README.md" << README_EOF
# GoodTime Automation Bundle

**Version:** 1.0.2
**Platform:** macOS 11.0+ (ARM64/Apple Silicon)
**Python:** 3.13.5
**Build Date:** $BUILD_DATE

**v1.0.2 Updates:**
- ✅ Added BrowserConfig dataclass for type-safe browser configuration
- ✅ Support for browser version specification (Chrome 144.0.7559.109)
- ✅ Support for browser binary location (Chrome Beta/Canary)
- ✅ Fixed user_data_dir for Chrome/Firefox/Edge
- ✅ Added Firefox preferences support
- ✅ EdgeOptions best practice improvement
- ✅ Added webdriver-manager dependency

**Technical Note:** This bundle uses Cython's \`annotation_typing=False\` directive, which tells Cython to treat type hints as documentation rather than C type declarations.

## What's Inside

This bundle contains a compiled Python wheel that packages three components into one:

- **SciencePythonUtils** - Core utilities and algorithms
- **ScienceModelingTools** - LLM APIs and agent framework
- **WebAgent** - Browser automation framework

**Protection Level:** 98% of source code is compiled to native ARM64 machine code (.so files).

## Quick Start

### Option 1: Use the Launch Script (Recommended)

\`\`\`bash
chmod +x launch.sh
./launch.sh
\`\`\`

### Option 2: Manual Installation

\`\`\`bash
# Install dependencies (note: webdriver-manager is new in v1.0.2)
pip install attrs pydantic anthropic boto3 selenium playwright beautifulsoup4 lxml pybars3 jinja2 undetected_chromedriver webdriver-manager

# NOTE: Ensure ai_gateway is installed on your system before running

# Install the wheel
pip install goodtime_automation_bundle-1.0.2-cp313-cp313-macosx_11_0_arm64.whl --force-reinstall

# Run the automation
python run_goodtime_template_selection_graph_with_monitor.py
\`\`\`

## Requirements

- **Operating System:** macOS 11.0 or later
- **Architecture:** ARM64 (Apple Silicon M1/M2/M3/M4)
- **Python:** 3.13.x
- **pip:** Latest version recommended

## Troubleshooting

### Import errors / ModuleNotFoundError
- Install dependencies: \`pip install attrs pydantic anthropic boto3 selenium playwright beautifulsoup4 lxml pybars3 jinja2 undetected_chromedriver webdriver-manager\`
- Ensure ai_gateway is installed on your system
- Reinstall wheel: \`pip install goodtime_automation_bundle-*.whl --force-reinstall\`

### Permission denied for launch.sh
- Run: \`chmod +x launch.sh\`

---

**Built with:** Python 3.13.5 + Cython compilation for source code protection
**Bundle created:** $BUILD_DATE
README_EOF

echo "  - Generated: README.md (v1.0.2)"
echo ""

# Step 10: Display success message and instructions
echo "[10/10] Build complete!"
echo ""
echo "================================================================================"
echo "  Build Successful!"
echo "================================================================================"
echo ""
echo "Distribution files are in: $DIST_DIR"
echo ""
ls -lh "$DIST_DIR"
echo ""
echo "To install and run:"
echo ""
echo "  cd $DIST_DIR"
echo "  $PYTHON -m pip install $(basename $WHEEL_FILE) --force-reinstall"
echo "  $PYTHON run_goodtime_template_selection_graph_with_monitor.py"
echo ""
echo "To verify source protection:"
echo ""
echo "  $PYTHON -c \"import science_python_utils; print(science_python_utils.__file__)\""
echo ""
echo "Expected: Path should end with .so (compiled native code)"
echo ""
echo "================================================================================"
