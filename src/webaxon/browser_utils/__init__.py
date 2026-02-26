"""
Browser utilities for WebAgent.

Provides cross-platform utilities for browser management and configuration.
"""

from webaxon.browser_utils.chrome.chrome_profiles import (
    get_chrome_user_data_dir,
    get_available_chrome_profiles,
    get_chrome_profile_name,
    get_chrome_profile_options_for_dropdown
)
from webaxon.browser_utils.chrome.chrome_version import (
    get_chrome_version,
    get_chrome_major_version,
)

__all__ = [
    'get_chrome_user_data_dir',
    'get_available_chrome_profiles',
    'get_chrome_profile_name',
    'get_chrome_profile_options_for_dropdown',
    'get_chrome_version',
    'get_chrome_major_version',
]
