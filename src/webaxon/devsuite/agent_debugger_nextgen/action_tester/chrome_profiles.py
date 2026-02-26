"""
Chrome profile discovery and management utilities.

DEPRECATED: This module is kept for backward compatibility.
Use webaxon.browser_utils.chrome_profiles instead.
"""
from webaxon.browser_utils.chrome.chrome_profiles import (
    get_chrome_user_data_dir,
    get_available_chrome_profiles,
    get_chrome_profile_options_for_dropdown
)


class ChromeProfileManager:
    """
    Manages Chrome profile discovery and configuration.
    
    DEPRECATED: Use functions from webaxon.browser_utils.chrome_profiles directly.
    This class is kept for backward compatibility.
    """
    
    @staticmethod
    def get_chrome_user_data_dir():
        """Get the Chrome user data directory. See webaxon.browser_utils.chrome_profiles.get_chrome_user_data_dir()"""
        return get_chrome_user_data_dir()
    
    @staticmethod
    def get_available_profiles():
        """Get available Chrome profiles. See webaxon.browser_utils.chrome_profiles.get_available_chrome_profiles()"""
        return get_available_chrome_profiles()
    
    @staticmethod
    def get_profile_options_for_dropdown():
        """Get profile options for dropdown. See webaxon.browser_utils.chrome_profiles.get_chrome_profile_options_for_dropdown()"""
        return get_chrome_profile_options_for_dropdown()
