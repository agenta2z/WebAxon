"""
Chrome profile discovery and management utilities.

Cross-platform support for Windows, macOS, and Linux.
Provides functions to discover, enumerate, and copy Chrome profiles.
"""
import json
import logging
import os
import platform
import shutil
import tempfile
from typing import List, Dict, Optional, Set
from pathlib import Path

_logger = logging.getLogger(__name__)

# Heavy directories that are not needed for preserving login sessions.
# Skipping these reduces a typical 1.6 GB profile copy to ~300 MB.
PROFILE_COPY_SKIP_DIRS: Set[str] = {
    "Cache",
    "Code Cache",
    "CacheStorage",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "File System",
    "GPUCache",
    "GrShaderCache",
    "IndexedDB",
    "Service Worker",
    "blob_storage",
}

# Lock files that Chrome places in the user-data-dir (parent of profiles).
_CHROME_LOCK_FILES = ("SingletonLock", "SingletonSocket", "SingletonCookie")

# #region agent log
_AGENT_DEBUG_LOG = "/Users/tchen7/MyProjects/.cursor/debug-deb179.log"
_AGENT_SESSION_ID = "deb179"


def _agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: Optional[dict] = None,
    run_id: str = "pre-fix",
) -> None:
    try:
        import time

        line = (
            json.dumps(
                {
                    "sessionId": _AGENT_SESSION_ID,
                    "timestamp": int(time.time() * 1000),
                    "hypothesisId": hypothesis_id,
                    "location": location,
                    "message": message,
                    "data": data or {},
                    "runId": run_id,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        with open(_AGENT_DEBUG_LOG, "a", encoding="utf-8") as _f:
            _f.write(line)
    except Exception:
        pass


# #endregion


def remove_chrome_user_data_singleton_locks(
    user_data_dir: str,
    profile_directory: Optional[str] = None,
) -> None:
    """Remove Chrome singleton lock artifacts so a new browser instance can start.

    Chrome creates ``SingletonLock``, ``SingletonSocket``, and ``SingletonCookie``
    under the user-data directory root. After a crash, kill, or failed automation
    launch, these can linger and block the next start (e.g. Selenium
    ``cannot connect to chrome`` / chrome not reachable).

    If *profile_directory* is set (e.g. ``\"Default\"``), the same filenames are
    removed under that profile subfolder when present, since some setups leave
    stale artifacts there.

    Safe to call repeatedly. Missing paths are ignored.

    Args:
        user_data_dir: Chrome user-data directory path.
        profile_directory: Optional profile folder name inside *user_data_dir*.
    """
    # #region agent log
    _agent_debug_log(
        "H2",
        "chrome_profiles.remove_chrome_user_data_singleton_locks:entry",
        "lock_cleanup_entered",
        {
            "raw_user_data_dir": user_data_dir,
            "profile_directory": profile_directory,
            "chrome_profiles_file": __file__,
        },
    )
    # #endregion
    if not user_data_dir:
        # #region agent log
        _agent_debug_log(
            "H1",
            "chrome_profiles.remove_chrome_user_data_singleton_locks:early",
            "skip_empty_user_data_dir",
            {},
        )
        # #endregion
        return
    try:
        user_data_dir = os.path.abspath(os.path.expanduser(user_data_dir))
    except OSError as e:
        # #region agent log
        _agent_debug_log(
            "H1",
            "chrome_profiles.remove_chrome_user_data_singleton_locks:early",
            "abspath_oserror",
            {"error": str(e)},
        )
        # #endregion
        return
    if not os.path.isdir(user_data_dir):
        # #region agent log
        _agent_debug_log(
            "H1",
            "chrome_profiles.remove_chrome_user_data_singleton_locks:early",
            "not_a_directory",
            {"resolved": user_data_dir},
        )
        # #endregion
        return

    bases: List[str] = [user_data_dir]
    if profile_directory:
        sub = os.path.join(user_data_dir, profile_directory)
        if os.path.isdir(sub):
            bases.append(sub)

    # #region agent log
    locks_before: dict = {}
    for base in bases:
        locks_before[base] = {
            name: os.path.lexists(os.path.join(base, name))
            for name in _CHROME_LOCK_FILES
        }
    extra_singletonish: List[str] = []
    try:
        for name in os.listdir(user_data_dir):
            if "Singleton" in name or name.lower().startswith("lock"):
                extra_singletonish.append(name)
    except OSError:
        pass
    _agent_debug_log(
        "H2",
        "chrome_profiles.remove_chrome_user_data_singleton_locks:before_remove",
        "lock_state",
        {
            "bases": bases,
            "locks_before": locks_before,
            "extra_singletonish_in_root": extra_singletonish[:20],
        },
    )
    # #endregion

    remove_errors: List[str] = []
    for base in bases:
        for lock_name in _CHROME_LOCK_FILES:
            lock_path = os.path.join(base, lock_name)
            try:
                if os.path.lexists(lock_path):
                    os.remove(lock_path)
            except OSError as exc:
                _logger.debug(
                    "Could not remove Chrome lock file %s: %s", lock_path, exc
                )
                remove_errors.append(f"{lock_path}:{exc!s}")

    # #region agent log
    locks_after: dict = {}
    for base in bases:
        locks_after[base] = {
            name: os.path.lexists(os.path.join(base, name))
            for name in _CHROME_LOCK_FILES
        }
    _agent_debug_log(
        "H3",
        "chrome_profiles.remove_chrome_user_data_singleton_locks:after_remove",
        "lock_state",
        {
            "locks_after": locks_after,
            "remove_errors": remove_errors,
        },
    )
    # #endregion


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


def copy_chrome_profile(
    user_data_dir: str,
    profile_directory: str = "Default",
    dest_user_data_dir: Optional[str] = None,
) -> str:
    """Copy a Chrome profile to a separate directory for isolated automation.

    This avoids Chrome's single-process lock by giving the WebDriver its own
    copy of the profile while preserving cookies, local storage, and other
    session data needed to stay logged in.

    Heavy, non-essential directories (caches, Service Worker, IndexedDB, etc.)
    are skipped to keep the copy fast. See ``PROFILE_COPY_SKIP_DIRS``.

    Args:
        user_data_dir: Source Chrome user-data directory
            (e.g. ``~/Library/Application Support/Google/Chrome``).
        profile_directory: Profile folder name inside *user_data_dir*
            (e.g. ``"Default"``, ``"Profile 1"``).
        dest_user_data_dir: Destination user-data directory.
            - ``None`` (default): create a new ``tempfile.mkdtemp()``.
            - A path string: use that directory. If the profile subfolder
              already exists inside it the copy is **skipped** (reuse).

    Returns:
        The *dest_user_data_dir* path (caller should pass this as the
        ``user_data_dir`` when launching Chrome/WebDriver).

    Raises:
        FileNotFoundError: If the source profile directory does not exist.
    """
    src_profile = os.path.join(user_data_dir, profile_directory)
    if not os.path.isdir(src_profile):
        raise FileNotFoundError(
            f"Source profile directory does not exist: {src_profile}"
        )

    if dest_user_data_dir is None:
        dest_user_data_dir = tempfile.mkdtemp(prefix="webaxon_chrome_")
        _logger.info("Created temp user-data-dir: %s", dest_user_data_dir)

    dest_profile = os.path.join(dest_user_data_dir, profile_directory)

    if os.path.isdir(dest_profile):
        print(f"[Profile Copy] Reusing existing copy at {dest_profile}")
        _logger.info("Reusing existing profile copy at %s", dest_profile)
        remove_chrome_user_data_singleton_locks(
            dest_user_data_dir, profile_directory
        )
        return dest_user_data_dir

    print(f"[Profile Copy] Copying '{profile_directory}' profile...")
    print(f"  Source: {src_profile}")
    print(f"  Dest:   {dest_profile}")

    skipped_dirs: List[str] = []

    def _ignore_heavy_dirs(directory: str, contents: List[str]) -> List[str]:
        if os.path.normpath(directory) == os.path.normpath(src_profile):
            ignored = [c for c in contents if c in PROFILE_COPY_SKIP_DIRS]
            skipped_dirs.extend(ignored)
            return ignored
        return []

    import time as _time
    t0 = _time.monotonic()

    shutil.copytree(
        src_profile,
        dest_profile,
        symlinks=True,
        ignore=_ignore_heavy_dirs,
        ignore_dangling_symlinks=True,
    )

    elapsed = _time.monotonic() - t0

    # Calculate copied size
    copied_bytes = 0
    for dirpath, _, filenames in os.walk(dest_profile):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp) and not os.path.islink(fp):
                copied_bytes += os.path.getsize(fp)

    if skipped_dirs:
        print(f"  Skipped heavy dirs: {', '.join(sorted(skipped_dirs))}")
    print(f"  Copied {copied_bytes / 1e6:.1f} MB in {elapsed:.1f}s")

    remove_chrome_user_data_singleton_locks(
        dest_user_data_dir, profile_directory
    )

    # Fix exit_type in Preferences to suppress "Chrome didn't shut down
    # correctly" restore bar.  Same fixup that undetected_chromedriver does.
    prefs_path = os.path.join(dest_profile, "Preferences")
    try:
        if os.path.exists(prefs_path):
            with open(prefs_path, "r", encoding="latin1") as f:
                prefs = json.load(f)
            if prefs.get("profile", {}).get("exit_type") is not None:
                prefs["profile"]["exit_type"] = None
                with open(prefs_path, "w", encoding="latin1") as f:
                    json.dump(prefs, f)
    except Exception as exc:
        _logger.debug("Could not fix exit_type in copied Preferences: %s", exc)

    print(f"[Profile Copy] Done -> {dest_user_data_dir}")
    _logger.info("Profile copy complete (%s)", dest_profile)
    return dest_user_data_dir


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
