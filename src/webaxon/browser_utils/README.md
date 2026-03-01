# Browser Utilities

Common utilities for browser management and configuration in webaxon

## Modules

### `chrome_profiles.py`

Cross-platform utilities for discovering and managing Chrome profiles.

#### Functions

##### `get_chrome_user_data_dir() -> Optional[str]`

Get the Chrome user data directory based on the operating system.

**Returns:** Path to Chrome user data directory, or None if not found.

**Platform-specific paths:**
- **Windows**: `%LOCALAPPDATA%\Google\Chrome\User Data`
- **macOS**: `~/Library/Application Support/Google/Chrome`
- **Linux**: `~/.config/google-chrome`

**Example:**

```python
from webaxon.browser_utils import get_chrome_user_data_dir

user_data_dir = get_chrome_user_data_dir()
if user_data_dir:
    print(f"Chrome found at: {user_data_dir}")
```

---

##### `get_chrome_profile_name(profile_dir: str) -> str`

Get the user-friendly name for a profile from its Preferences file.

**Args:**
- `profile_dir`: Path to the profile directory

**Returns:** Profile name or directory name as fallback

**Example:**

```python
from webaxon.browser_utils import get_chrome_profile_name

profile_name = get_chrome_profile_name("/path/to/Chrome/User Data/Default")
print(f"Profile name: {profile_name}")
```

---

##### `get_available_chrome_profiles() -> List[Dict[str, str]]`

Discover all available Chrome profiles on the system.

**Returns:** List of profile dictionaries with 'name' and 'directory' keys.

**Example:**

```python
from webaxon.browser_utils import get_available_chrome_profiles

profiles = get_available_chrome_profiles()
for profile in profiles:
    print(f"{profile['name']} -> {profile['directory']}")

# Output:
# 👤 Person 1 -> Default
# 👤 Work Profile -> Profile 1
# 🆕 New Temporary Profile -> 
```

---

##### `get_chrome_profile_options_for_dropdown() -> List[Dict[str, str]]`

Get profile options formatted for UI dropdown components (e.g., Dash).

**Returns:** List of dicts with 'label' and 'value' keys for dropdown options.

**Example:**

```python
from webaxon.browser_utils import get_chrome_profile_options_for_dropdown

options = get_chrome_profile_options_for_dropdown()
# Use in Dash dropdown:
# dcc.Dropdown(options=options, value='Default')
```

## Usage Examples

### Basic Profile Discovery

```python
from webaxon.browser_utils import (
    get_chrome_user_data_dir,
    get_available_chrome_profiles
)

# Check if Chrome is installed
user_data_dir = get_chrome_user_data_dir()
if not user_data_dir:
    print("Chrome not installed")
    exit(1)

# Get all profiles
profiles = get_available_chrome_profiles()
print(f"Found {len(profiles)} profiles")

for profile in profiles:
    print(f"  - {profile['name']}")
    print(f"    Directory: {profile['directory']}")
```

### Using with Selenium/undetected_chromedriver

```python
import undetected_chromedriver as uc
from webaxon.browser_utils import get_chrome_user_data_dir

# Launch Chrome with a specific profile
options = uc.ChromeOptions()
user_data_dir = get_chrome_user_data_dir()

if user_data_dir:
    options.add_argument(f'--user-data-dir={user_data_dir}')
    options.add_argument('--profile-directory=Default')

driver = uc.Chrome(options=options)
```

### Creating a Profile Selector UI

```python
from dash import dcc, html
from webaxon.browser_utils import get_chrome_profile_options_for_dropdown

layout = html.Div([
    html.Label('Select Chrome Profile:'),
    dcc.Dropdown(
        id='profile-selector',
        options=get_chrome_profile_options_for_dropdown(),
        value='Default',  # Default selection
        placeholder='Choose a profile...'
    )
])
```

## Features

- ✅ **Cross-platform**: Works on Windows, macOS, and Linux
- ✅ **User-friendly names**: Extracts profile names from Chrome preferences
- ✅ **Automatic discovery**: Finds all Chrome profiles automatically
- ✅ **Temporary profile option**: Includes option for clean temporary profiles
- ✅ **UI-ready**: Provides dropdown-formatted options for easy integration

## Notes

- Profile names are extracted from Chrome's `Preferences` file
- Falls back to directory name if profile name cannot be determined
- Handles missing Chrome installations gracefully
- Temporary profile option (empty directory string) creates a clean browser instance

## Migration from Old Location

If you were using the old location:

```python
# OLD (deprecated)
from webaxon.devsuite.agent_debugger_nextgen.action_tester.chrome_profiles import ChromeProfileManager

profiles = ChromeProfileManager.get_available_profiles()

# NEW (recommended)
from webaxon.browser_utils import get_available_chrome_profiles

profiles = get_available_chrome_profiles()
```

The old `ChromeProfileManager` class is kept for backward compatibility but is deprecated.
