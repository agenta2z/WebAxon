# Chrome Profile Selection - Quick Start Guide

## 🚀 Quick Start (30 seconds)

1. Open the **Action Tester** tab
2. Find the **"Chrome Profile:"** dropdown
3. Select your profile (or "New Temporary Profile")
4. Click **"🚀 Launch Browser"**
5. Done! Browser opens with your selected profile

## 📋 Profile Options

| Option | Description | Use When |
|--------|-------------|----------|
| 👤 **Default** | Your main Chrome profile | You want to stay logged in |
| 👤 **Profile 1, 2, etc.** | Additional profiles | Testing with different accounts |
| 🆕 **New Temporary Profile** | Clean browser | You need a fresh start |

## 💡 Common Use Cases

### Stay Logged In
```
Select: Default (or your main profile)
Benefit: No need to log in to Gmail, GitHub, etc.
```

### Test Different Users
```
Select: Profile 1, Profile 2, etc.
Benefit: Switch between work/personal accounts
```

### Clean Testing
```
Select: New Temporary Profile
Benefit: No cookies, cache, or login sessions
```

## 🎯 What You Get

✅ **Persistent Sessions** - Stay logged in across test runs  
✅ **Bookmarks** - Access your saved bookmarks  
✅ **Extensions** - Use your installed extensions  
✅ **Settings** - Keep your browser preferences  
✅ **Fast Testing** - No repeated logins  

## 🔧 Troubleshooting

**Profile not showing?**
- Make sure Chrome is installed
- Check that you have created profiles in Chrome

**"Profile in use" error?**
- Close other Chrome windows using that profile
- Wait a few seconds and try again

**Want a clean browser?**
- Select "🆕 New Temporary Profile"
- No persistent data or logins

## 📝 Code Example

```python
from webaxon.devsuite.agent_debugger_nextgen.action_tester.manager import ActionTesterManager

manager = ActionTesterManager()

# Use your main profile (stay logged in)
manager.launch_browser(profile_directory='Default')

# Use a specific profile
manager.launch_browser(profile_directory='Profile 1')

# Use temporary profile (clean slate)
manager.launch_browser(profile_directory='')
```

## 🌟 Pro Tips

1. **Default Profile** is selected by default for convenience
2. **Temporary Profile** is great for testing without affecting your data
3. **Multiple Profiles** let you test different user scenarios
4. **Profile names** are extracted from your Chrome settings
5. **Cross-platform** - works on Windows, macOS, and Linux

## 📚 More Information

For detailed documentation, see:
- `CHROME_PROFILE_FEATURE.md` - Complete feature documentation
- `CHROME_PROFILE_IMPLEMENTATION_SUMMARY.md` - Technical details

---

**That's it!** You're ready to use Chrome profiles in the Action Tester. 🎉
