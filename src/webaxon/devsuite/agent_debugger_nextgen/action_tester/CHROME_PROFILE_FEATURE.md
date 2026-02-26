# Chrome Profile Selection Feature

## Overview

The Action Tester now supports launching Chrome with your existing profiles, allowing you to stay logged into websites and use your bookmarks, extensions, and settings during testing.

## Features

### 1. **Automatic Profile Discovery**
- Detects all Chrome profiles on your system
- Works cross-platform (Windows, macOS, Linux)
- Extracts user-friendly profile names from Chrome preferences

### 2. **Profile Selection Dropdown**
- Visual dropdown in the UI showing all available profiles
- Displays profile names with icons:
  - 👤 for existing user profiles
  - 🆕 for temporary profile option
- Default selection is your main "Default" profile

### 3. **Profile Options**

#### Existing Profiles
- **Default**: Your main Chrome profile
- **Profile 1, Profile 2, etc.**: Additional Chrome profiles you've created
- Each profile maintains:
  - Saved passwords and login sessions
  - Bookmarks and browsing history
  - Extensions and settings
  - Cookies and site data

#### Temporary Profile
- **New Temporary Profile**: Clean browser instance
- No saved data or login sessions
- Useful for testing in a fresh environment
- Data is discarded when browser closes

## Usage

### In the UI

1. **Select Profile**:
   - Open the Action Tester tab
   - Find the "Chrome Profile:" dropdown under Browser Controls
   - Select your desired profile from the list

2. **Launch Browser**:
   - Click "🚀 Launch Browser"
   - Browser opens with the selected profile
   - Status indicator shows which profile is active

3. **Switch Profiles**:
   - Close the current browser
   - Select a different profile from dropdown
   - Launch browser again

### Programmatically

```python
from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager

manager = ActionTesterManager()

# Launch with default profile
manager.launch_browser(profile_directory='Default')

# Launch with specific profile
manager.launch_browser(profile_directory='Profile 1')

# Launch with temporary profile
manager.launch_browser(profile_directory='')
```

## Implementation Details

### Files Modified

1. **chrome_profiles.py** (NEW)
   - `ChromeProfileManager` class
   - Profile discovery and enumeration
   - Cross-platform path resolution
   - Profile name extraction from Chrome preferences

2. **manager.py**
   - Updated `launch_browser()` to accept `profile_directory` parameter
   - Integrated with `ChromeProfileManager`
   - Profile-specific Chrome options configuration

3. **action_tester_tab.py**
   - Added profile selection dropdown
   - Styled to match existing UI theme

4. **app.py**
   - Added callback to populate dropdown on page load
   - Updated launch callback to use selected profile
   - Profile selection state management

5. **action_tester_styles.css**
   - Custom dropdown styling
   - Hover effects and transitions
   - Dark theme integration

### Profile Detection Logic

#### Windows
```
%LOCALAPPDATA%\Google\Chrome\User Data
```

#### macOS
```
~/Library/Application Support/Google/Chrome
```

#### Linux
```
~/.config/google-chrome
```

### Profile Name Resolution

The system attempts to extract user-friendly names in this order:
1. Profile name from `Preferences` file (`profile.name`)
2. Email address from account info
3. Directory name as fallback

## Benefits

### For Development
- ✅ No repeated logins to test sites
- ✅ Access to authenticated APIs
- ✅ Test with real user data
- ✅ Use browser extensions during testing

### For Testing
- ✅ Test different user scenarios with different profiles
- ✅ Isolate test data in separate profiles
- ✅ Clean slate testing with temporary profiles
- ✅ Reproduce user-specific issues

### For Productivity
- ✅ Faster test iterations (no login delays)
- ✅ Seamless workflow integration
- ✅ Familiar browser environment
- ✅ Persistent session state

## Technical Notes

### Profile Locking
- Chrome profiles can only be used by one browser instance at a time
- If a profile is already in use, Chrome will show an error
- Close other Chrome windows using that profile before launching

### Data Safety
- Profile data is read-only during automation
- No modifications to your actual Chrome profile
- Temporary profiles are automatically cleaned up

### Compatibility
- Requires Chrome browser installed
- Works with `undetected_chromedriver`
- Compatible with all Chrome profile types

## Troubleshooting

### Profile Not Found
- Ensure Chrome is installed
- Check that profiles exist in the expected location
- Try selecting "New Temporary Profile" as fallback

### Profile In Use Error
- Close all Chrome windows using that profile
- Wait a few seconds for Chrome to release the lock
- Try launching again

### Profile Data Not Loading
- Verify the profile directory exists
- Check Chrome preferences file is valid JSON
- Ensure you have read permissions for the profile directory

## Future Enhancements

Potential improvements for future versions:
- Profile creation from within the UI
- Profile usage statistics
- Recent profiles quick-select
- Profile-specific settings override
- Multi-profile testing support
