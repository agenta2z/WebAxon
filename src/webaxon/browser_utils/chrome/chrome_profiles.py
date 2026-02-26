"""
Chrome profile discovery and management utilities.

Cross-platform support for Windows, macOS, and Linux.
Provides functions to discover and enumerate Chrome profiles.
"""
import os
import platform
import json
from typing import List, Dict, Optional
from pathlib import Path


def get_chrome_user_data_dir() -> Optional[str]:
    """
    Get the Chrome user data directory based on the operating system.
    
    Returns:
        Path to Chrome user data directory, or None if not found.
        
    Platform-specific paths:
        - Windows: %LOCALAPPDATA%\\Google\\Chrome\\User Data
        - macOS: ~/Library/Application Support/Google/Chrome
        - Linux: ~/.config/google-chrome
    """
    system = platform.system()
    
    if system == "Windows":
        profile_path = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
    elif system == "Darwin":  # macOS
        profile_path = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:  # Linux
        profile_path = os.path.expanduser("~/.config/google-chrome")
    
    return profile_path if os.path.exists(profile_path) else None


def get_chrome_profile_name(profile_dir: str) -> str:
    """
    Get the user-friendly name for a profile from its Preferences file.
    
    Args:
        profile_dir: Path to the profile directory
        
    Returns:
        Profile name or directory name as fallback
    """
    try:
        prefs_file = os.path.join(profile_dir, "Preferences")
        if os.path.exists(prefs_file):
            with open(prefs_file, 'r', encoding='utf-8') as f:
                prefs = json.load(f)
                
                # Try to get the profile name
                profile_info = prefs.get('profile', {})
                name = profile_info.get('name', '')
                
                if name:
                    return name
                
                # Fallback to account info
                account_info = prefs.get('account_info', [])
                if account_info and len(account_info) > 0:
                    email = account_info[0].get('email', '')
                    if email:
                        return email
    
    except Exception:
        pass
    
    # Fallback to directory name
    return os.path.basename(profile_dir)


def get_available_chrome_profiles() -> List[Dict[str, str]]:
    """
    Discover all available Chrome profiles.
    
    Returns:
        List of profile dictionaries with 'name' and 'directory' keys.
        Example:
            [
                {'name': 'Default', 'directory': 'Default'},
                {'name': 'Profile 1 (Work)', 'directory': 'Profile 1'},
                {'name': 'New Profile', 'directory': ''}  # Temp profile option
            ]
    """
    profiles = []
    user_data_dir = get_chrome_user_data_dir()
    
    if not user_data_dir:
        # No Chrome installation found, only offer temp profile
        return [{'name': '🆕 New Temporary Profile', 'directory': ''}]
    
    try:
        # Check for Default profile
        default_profile = os.path.join(user_data_dir, "Default")
        if os.path.exists(default_profile):
            profile_name = get_chrome_profile_name(default_profile)
            profiles.append({
                'name': f'👤 {profile_name}',
                'directory': 'Default'
            })
        
        # Check for numbered profiles (Profile 1, Profile 2, etc.)
        for item in os.listdir(user_data_dir):
            item_path = os.path.join(user_data_dir, item)
            if os.path.isdir(item_path) and item.startswith("Profile "):
                profile_name = get_chrome_profile_name(item_path)
                profiles.append({
                    'name': f'👤 {profile_name}',
                    'directory': item
                })
    
    except Exception as e:
        print(f"Warning: Could not enumerate Chrome profiles: {e}")
    
    # Always add temp profile option at the end
    profiles.append({'name': '🆕 New Temporary Profile', 'directory': ''})
    
    return profiles


def get_chrome_profile_options_for_dropdown() -> List[Dict[str, str]]:
    """
    Get profile options formatted for Dash dropdown or similar UI components.
    
    Returns:
        List of dicts with 'label' and 'value' keys for dropdown options.
        Example:
            [
                {'label': '👤 Person 1', 'value': 'Default'},
                {'label': '👤 Work Profile', 'value': 'Profile 1'},
                {'label': '🆕 New Temporary Profile', 'value': ''}
            ]
    """
    profiles = get_available_chrome_profiles()
    return [
        {'label': profile['name'], 'value': profile['directory']}
        for profile in profiles
    ]
