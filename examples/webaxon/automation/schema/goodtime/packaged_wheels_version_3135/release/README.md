# GoodTime Automation Bundle

**Version:** 1.0.2
**Platform:** macOS 11.0+ (ARM64/Apple Silicon)
**Python:** 3.13.5
**Build Date:** 2026-02-01 23:27

**v1.0.2 Updates:**
- ✅ Added BrowserConfig dataclass for type-safe browser configuration
- ✅ Support for browser version specification (Chrome 144.0.7559.109)
- ✅ Support for browser binary location (Chrome Beta/Canary)
- ✅ Fixed user_data_dir for Chrome/Firefox/Edge
- ✅ Added Firefox preferences support
- ✅ EdgeOptions best practice improvement
- ✅ Added webdriver-manager dependency

**Technical Note:** This bundle uses Cython's `annotation_typing=False` directive, which tells Cython to treat type hints as documentation rather than C type declarations.

## What's Inside

This bundle contains a compiled Python wheel that packages three components into one:

- **SciencePythonUtils** - Core utilities and algorithms
- **ScienceModelingTools** - LLM APIs and agent framework
- **WebAgent** - Browser automation framework

**Protection Level:** 98% of source code is compiled to native ARM64 machine code (.so files).

## Quick Start

### Option 1: Use the Launch Script (Recommended)

```bash
chmod +x launch.sh
./launch.sh
```

### Option 2: Manual Installation

```bash
# Install dependencies (note: webdriver-manager is new in v1.0.2)
pip install attrs pydantic anthropic boto3 selenium playwright beautifulsoup4 lxml pybars3 jinja2 undetected_chromedriver webdriver-manager

# NOTE: Ensure ai_gateway is installed on your system before running

# Install the wheel
pip install goodtime_automation_bundle-1.0.2-cp313-cp313-macosx_11_0_arm64.whl --force-reinstall

# Run the automation
python run_goodtime_template_selection_graph_with_monitor.py
```

## Requirements

- **Operating System:** macOS 11.0 or later
- **Architecture:** ARM64 (Apple Silicon M1/M2/M3/M4)
- **Python:** 3.13.x
- **pip:** Latest version recommended

## Troubleshooting

### Import errors / ModuleNotFoundError
- Install dependencies: `pip install attrs pydantic anthropic boto3 selenium playwright beautifulsoup4 lxml pybars3 jinja2 undetected_chromedriver webdriver-manager`
- Ensure ai_gateway is installed on your system
- Reinstall wheel: `pip install goodtime_automation_bundle-*.whl --force-reinstall`

### Permission denied for launch.sh
- Run: `chmod +x launch.sh`

---

**Built with:** Python 3.13.5 + Cython compilation for source code protection
**Bundle created:** 2026-02-01 23:27
