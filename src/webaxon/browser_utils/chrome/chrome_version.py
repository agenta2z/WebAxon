"""
Chrome version detection utilities.

Cross-platform support for Windows, macOS, and Linux.
Provides functions to detect the installed Chrome browser version.
"""
import logging
import platform
import re
import subprocess
from typing import Optional, Tuple

_logger = logging.getLogger(__name__)


def _find_chrome_executable() -> Optional[str]:
    """Find the Chrome executable path using undetected_chromedriver or common locations.

    Returns:
        Path to Chrome executable, or None if not found.
    """
    try:
        import undetected_chromedriver as uc
        return uc.find_chrome_executable()
    except ImportError:
        pass

    # Fallback: check common installation paths
    system = platform.system()
    import os

    if system == "Windows":
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        ]
    elif system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    else:  # Linux
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def get_chrome_version(chrome_path: Optional[str] = None) -> Optional[str]:
    """Detect the installed Chrome browser version string.

    Tries multiple detection methods in order:
    1. PowerShell Get-Item on the Chrome executable (Windows)
    2. Windows registry HKCU BLBeacon key (Windows fallback)
    3. ``chrome --version`` command (macOS/Linux)

    Args:
        chrome_path: Explicit path to the Chrome executable.
            If None, auto-detects using ``undetected_chromedriver``
            or common installation paths.

    Returns:
        Full version string (e.g. ``"145.0.7632.117"``), or None if
        detection fails.
    """
    if chrome_path is None:
        chrome_path = _find_chrome_executable()

    system = platform.system()

    if chrome_path and system == "Windows":
        # Method 1: PowerShell Get-Item
        try:
            ps_cmd = f'(Get-Item \"{chrome_path}\").VersionInfo.ProductVersion'
            ver_str = subprocess.check_output(
                ["powershell", "-Command", ps_cmd],
                stderr=subprocess.DEVNULL, timeout=10,
            ).decode().strip()
            if ver_str and re.match(r"\d+\.\d+\.\d+\.\d+", ver_str):
                _logger.debug("Detected Chrome version via PowerShell: %s", ver_str)
                return ver_str
        except Exception:
            pass

        # Method 2: Windows registry fallback
        try:
            reg_cmd = 'reg query "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon" /v version'
            output = subprocess.check_output(
                reg_cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5,
            ).decode().strip()
            if output:
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
                if m:
                    ver_str = m.group(1)
                    _logger.debug("Detected Chrome version via registry: %s", ver_str)
                    return ver_str
        except Exception:
            pass

    elif chrome_path:
        # macOS / Linux: run chrome --version
        try:
            output = subprocess.check_output(
                [chrome_path, "--version"], stderr=subprocess.DEVNULL, timeout=5,
            ).decode().strip()
            if output:
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
                if m:
                    ver_str = m.group(1)
                    _logger.debug("Detected Chrome version via CLI: %s", ver_str)
                    return ver_str
        except Exception:
            pass

    _logger.debug("Could not detect Chrome version")
    return None


def get_chrome_major_version(chrome_path: Optional[str] = None) -> Optional[int]:
    """Detect the installed Chrome major version number.

    Convenience wrapper around :func:`get_chrome_version` that returns
    only the major version as an integer.

    Args:
        chrome_path: Explicit path to Chrome executable (auto-detected if None).

    Returns:
        Major version integer (e.g. ``145``), or None if detection fails.
    """
    version = get_chrome_version(chrome_path)
    if version:
        m = re.match(r"(\d+)", version)
        if m:
            return int(m.group(1))
    return None
