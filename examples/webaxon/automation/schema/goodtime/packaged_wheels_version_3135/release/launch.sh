#!/bin/bash
# Launch script for GoodTime Automation Bundle
# This script installs dependencies, installs the wheel, and runs the automation

set -e  # Exit on any error

# =============================================================================
# CONFIGURATION
# =============================================================================
# Set to "true" to use local source code instead of the bundled wheel.
# This is useful for development/testing when you have the source repositories.
# When enabled, the script will:
#   - Always uninstall any existing bundle (to avoid import conflicts)
#   - Check for local source directories (WebAgent, SciencePythonUtils, ScienceModelingTools)
#   - Use PYTHONPATH to load from local sources instead of installing the wheel
ENABLE_LOCAL_CODE="false"

# =============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Determine project paths for local code mode
# wheels/ is inside: WebAgent/examples/automation/schema/goodtime/packaged_wheels_version_3135/wheels/
# Navigate up to find the source directories
WEBAGENT_ROOT="$(cd "$SCRIPT_DIR/../../../.." 2>/dev/null && pwd)" || WEBAGENT_ROOT=""
PROJECTS_ROOT="$(cd "$WEBAGENT_ROOT/.." 2>/dev/null && pwd)" || PROJECTS_ROOT=""

# Define local source paths
WEBAGENT_SRC="$WEBAGENT_ROOT/src"
SCIENCE_PYTHON_UTILS_SRC="$PROJECTS_ROOT/SciencePythonUtils/src"
SCIENCE_MODELING_TOOLS_SRC="$PROJECTS_ROOT/ScienceModelingTools/src"

# Define file names
WHEEL_FILE=$(ls goodtime_automation_bundle-*.whl 2>/dev/null | head -1)
LAUNCHER_SCRIPT="run_goodtime_template_selection_graph_with_monitor.py"

echo "================================================================================"
echo "  GoodTime Automation Bundle - Launch Script"
echo "  Version: 1.0.2 - Browser Configuration Enhancement"
if [ "$ENABLE_LOCAL_CODE" = "true" ]; then
    echo "  Mode: LOCAL CODE (development)"
else
    echo "  Mode: BUNDLED WHEEL (production)"
fi
echo "================================================================================"
echo ""

# =============================================================================
# LOCAL CODE MODE HANDLING
# =============================================================================
USE_LOCAL_CODE="false"

if [ "$ENABLE_LOCAL_CODE" = "true" ]; then
    echo "[0/5] LOCAL CODE MODE - Checking for local source directories..."
    echo ""

    # Always uninstall bundle first to avoid import conflicts
    echo "  Uninstalling any existing bundle (to avoid conflicts)..."
    pip uninstall goodtime-automation-bundle goodtime_automation_bundle -y 2>/dev/null || true
    echo ""

    # Check if all required source directories exist
    LOCAL_CODE_FOUND="true"

    if [ -d "$WEBAGENT_SRC" ]; then
        echo "  ✓ Found: WebAgent/src"
        echo "    Path: $WEBAGENT_SRC"
    else
        echo "  ✗ NOT FOUND: WebAgent/src"
        echo "    Expected: $WEBAGENT_SRC"
        LOCAL_CODE_FOUND="false"
    fi

    if [ -d "$SCIENCE_PYTHON_UTILS_SRC" ]; then
        echo "  ✓ Found: SciencePythonUtils/src"
        echo "    Path: $SCIENCE_PYTHON_UTILS_SRC"
    else
        echo "  ✗ NOT FOUND: SciencePythonUtils/src"
        echo "    Expected: $SCIENCE_PYTHON_UTILS_SRC"
        LOCAL_CODE_FOUND="false"
    fi

    if [ -d "$SCIENCE_MODELING_TOOLS_SRC" ]; then
        echo "  ✓ Found: ScienceModelingTools/src"
        echo "    Path: $SCIENCE_MODELING_TOOLS_SRC"
    else
        echo "  ✗ NOT FOUND: ScienceModelingTools/src"
        echo "    Expected: $SCIENCE_MODELING_TOOLS_SRC"
        LOCAL_CODE_FOUND="false"
    fi

    echo ""

    if [ "$LOCAL_CODE_FOUND" = "true" ]; then
        echo "  ✓ All local source directories found!"
        echo "  Using LOCAL CODE instead of bundled wheel."
        echo ""

        # Set PYTHONPATH to use local sources (prepend so they take priority)
        export PYTHONPATH="$WEBAGENT_SRC:$SCIENCE_PYTHON_UTILS_SRC:$SCIENCE_MODELING_TOOLS_SRC:$PYTHONPATH"
        echo "  PYTHONPATH configured for local sources."
        USE_LOCAL_CODE="true"
    else
        echo "  ✗ ERROR: ENABLE_LOCAL_CODE is true but not all source directories found."
        echo ""
        echo "  Options:"
        echo "    1. Set ENABLE_LOCAL_CODE=\"false\" in this script to use the bundled wheel"
        echo "    2. Ensure all three source repositories exist in the expected locations:"
        echo "       - $WEBAGENT_SRC"
        echo "       - $SCIENCE_PYTHON_UTILS_SRC"
        echo "       - $SCIENCE_MODELING_TOOLS_SRC"
        echo ""
        exit 1
    fi
    echo ""
fi

# =============================================================================
# STANDARD LAUNCH STEPS
# =============================================================================

# Step 1: Check if wheel file exists (always needed for reference, even in local mode)
echo "[1/5] Checking wheel file..."
if [ -z "$WHEEL_FILE" ] || [ ! -f "$WHEEL_FILE" ]; then
    if [ "$USE_LOCAL_CODE" = "true" ]; then
        echo "⚠ Wheel file not found (OK in local code mode)"
    else
        echo "✗ ERROR: Wheel file not found"
        echo "  Please ensure you're running this script from the wheels directory."
        exit 1
    fi
else
    echo "✓ Found wheel file: $WHEEL_FILE"
fi
echo ""

# Step 2: Check launcher script
echo "[2/5] Checking launcher script..."
if [ ! -f "$LAUNCHER_SCRIPT" ]; then
    echo "✗ ERROR: Launcher script not found: $LAUNCHER_SCRIPT"
    exit 1
fi
echo "✓ Found launcher script"
echo ""

# Step 3: Install dependencies (includes webdriver-manager for v1.0.2)
echo "[3/5] Installing dependencies..."
echo "  Installing: attrs, pydantic, anthropic, boto3, selenium, playwright,"
echo "              beautifulsoup4, lxml, pybars3, jinja2, undetected_chromedriver,"
echo "              webdriver-manager"
pip install attrs pydantic anthropic boto3 selenium playwright beautifulsoup4 lxml pybars3 jinja2 undetected_chromedriver webdriver-manager --quiet
echo "✓ Dependencies installed"
echo ""

# Step 3a: Check if ai_gateway is installed
echo "[3a/5] Checking for ai_gateway package..."
if python -c "import ai_gateway" 2>/dev/null; then
    echo "✓ ai_gateway is installed"
else
    echo "✗ ERROR: ai_gateway is not installed"
    echo "  The application requires ai_gateway to function"
    echo "  Please install ai_gateway before running this script"
    exit 1
fi
echo ""

# Step 4: Install wheel (skip if using local code)
if [ "$USE_LOCAL_CODE" = "true" ]; then
    echo "[4/5] Skipping wheel installation (using local code)..."
    echo "✓ Local code mode - no wheel installation needed"
else
    echo "[4/5] Force reinstalling wheel..."
    echo "  Uninstalling any existing version..."
    pip uninstall goodtime-automation-bundle goodtime_automation_bundle -y 2>/dev/null || true
    echo "  Installing fresh wheel: $WHEEL_FILE"
    pip install "$WHEEL_FILE" --force-reinstall --no-cache-dir --quiet
    echo "✓ Wheel installed successfully"
fi
echo ""

# Step 5: Verify installation
echo "[5/5] Verifying installation..."

if [ "$USE_LOCAL_CODE" = "true" ]; then
    # Verify local code imports
    echo "  Mode: Local code verification"
    python -c "
import sys
print(f'  PYTHONPATH includes local sources: OK')

import science_python_utils
import science_modeling_tools
import webagent
print('✓ All packages imported successfully from LOCAL CODE')

# Show where imports are coming from
print(f'  webagent loaded from: {webagent.__file__}')
print(f'  science_python_utils loaded from: {science_python_utils.__file__}')
print(f'  science_modeling_tools loaded from: {science_modeling_tools.__file__}')
"
else
    # Verify bundle installation
    echo "  Mode: Bundle verification"
    echo "  Wheel file built: $(stat -f "%Sm" "$WHEEL_FILE" 2>/dev/null || stat -c "%y" "$WHEEL_FILE" 2>/dev/null || echo "unknown")"

    python -c "
import goodtime_automation_bundle
import science_python_utils
import science_modeling_tools
import webagent
print('✓ All packages imported successfully')
print(f'✓ Bundle version: {goodtime_automation_bundle.__version__}')

# Check if code is compiled
from science_python_utils.string_utils import common
if common.__file__.endswith('.so'):
    print('✓ Source code is compiled (protected)')
    print(f'  Installed at: {common.__file__}')
else:
    print('⚠ Warning: Source code is not compiled')

# Show when the installed file was created
import os
import time
mtime = os.path.getmtime(common.__file__)
print(f'  Installed file timestamp: {time.strftime(\"%Y-%m-%d %H:%M:%S\", time.localtime(mtime))}')
"
fi

if [ $? -eq 0 ]; then
    echo "✓ Installation verified"
else
    echo "✗ Verification failed - missing dependencies?"
    echo "  Try: pip install attrs pydantic anthropic boto3 selenium playwright beautifulsoup4 lxml pybars3 jinja2 undetected_chromedriver webdriver-manager"
    exit 1
fi

echo ""
echo "================================================================================"
echo "  Installation Complete - Launching Automation"
echo "================================================================================"
echo ""
echo "The automation will now prompt for your consent before proceeding."
echo ""

# Launch the automation
exec python "$LAUNCHER_SCRIPT"
