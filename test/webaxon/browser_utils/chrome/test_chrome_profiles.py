"""
Cross-validation tests for Chrome profile detection.

Uses two independent methods to discover profiles and verifies they agree:
  Method 1 (directory scanning): get_available_chrome_profiles()
      Scans user-data-dir for "Default" and "Profile N" folders, reads
      each profile's Preferences file for the display name.
  Method 2 (Local State): Chrome's own profile registry at
      {user_data_dir}/Local State -> profile.info_cache
      This is the canonical source Chrome itself uses.

If both methods find the same set of profile directories, we have high
confidence the detection logic is correct.
"""
import resolve_path  # noqa: F401 — must be first

import json
import os
import shutil
import tempfile
import pytest
from typing import Dict, List, Optional, Set

from webaxon.browser_utils.chrome.chrome_profiles import (
    copy_chrome_profile,
    get_available_chrome_profiles,
    get_chrome_profile_name,
    get_chrome_user_data_dir,
    PROFILE_COPY_SKIP_DIRS,
    remove_chrome_user_data_singleton_locks,
)


# ---------------------------------------------------------------------------
# Method 2: read Chrome's Local State file directly
# ---------------------------------------------------------------------------

def _get_profiles_from_local_state(user_data_dir: str) -> List[Dict[str, str]]:
    """Parse Chrome's Local State JSON to extract the profile list.

    Chrome stores a profile cache at:
        {user_data_dir}/Local State -> {"profile": {"info_cache": { ... }}}

    Each key in info_cache is the profile directory name (e.g. "Default",
    "Profile 1") and each value contains metadata including "name".
    """
    local_state_path = os.path.join(user_data_dir, "Local State")
    if not os.path.exists(local_state_path):
        return []

    with open(local_state_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    info_cache = data.get("profile", {}).get("info_cache", {})
    profiles = []
    for directory, meta in info_cache.items():
        profiles.append({
            "directory": directory,
            "name": meta.get("name", directory),
        })
    return profiles


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def user_data_dir() -> Optional[str]:
    """Get the Chrome user data directory, skip if Chrome isn't installed."""
    path = get_chrome_user_data_dir()
    if path is None:
        pytest.skip("Chrome user data directory not found on this machine")
    return path


class TestChromeProfileDetection:
    """Verify that profile detection works on the current machine."""

    def test_user_data_dir_exists(self, user_data_dir):
        """The detected user data directory should actually exist on disk."""
        assert os.path.isdir(user_data_dir)

    def test_at_least_one_profile_detected(self):
        """get_available_chrome_profiles should find at least one real profile
        (plus the synthetic 'New Temporary Profile' entry)."""
        profiles = get_available_chrome_profiles()
        real_profiles = [p for p in profiles if p["directory"]]
        assert len(real_profiles) >= 1, (
            f"Expected at least one real Chrome profile, got: {profiles}"
        )

    def test_default_profile_exists(self, user_data_dir):
        """Every Chrome installation should have a 'Default' profile."""
        default_dir = os.path.join(user_data_dir, "Default")
        assert os.path.isdir(default_dir), (
            f"Expected 'Default' profile directory at {default_dir}"
        )

    def test_profile_name_resolution(self, user_data_dir):
        """get_chrome_profile_name should return a non-empty string."""
        default_dir = os.path.join(user_data_dir, "Default")
        if not os.path.isdir(default_dir):
            pytest.skip("No Default profile directory")
        name = get_chrome_profile_name(default_dir)
        assert isinstance(name, str) and len(name) > 0


class TestCrossValidation:
    """Cross-check directory scanning (method 1) against Local State (method 2)."""

    def test_directory_sets_match(self, user_data_dir):
        """The set of profile directories found by directory scanning should
        match the set found in Chrome's Local State info_cache."""
        # Method 1: our utility
        method1_profiles = get_available_chrome_profiles()
        method1_dirs: Set[str] = {
            p["directory"] for p in method1_profiles if p["directory"]
        }

        # Method 2: Local State
        method2_profiles = _get_profiles_from_local_state(user_data_dir)
        if not method2_profiles:
            pytest.skip(
                "Local State file not found or has no info_cache — "
                "cannot cross-validate"
            )
        method2_dirs: Set[str] = {p["directory"] for p in method2_profiles}

        # Filter method 2 to only dirs that actually exist on disk,
        # since Local State may reference profiles that were deleted
        method2_dirs_existing = {
            d for d in method2_dirs
            if os.path.isdir(os.path.join(user_data_dir, d))
        }

        assert method1_dirs == method2_dirs_existing, (
            f"Profile directory mismatch!\n"
            f"  Directory scanning (method 1): {sorted(method1_dirs)}\n"
            f"  Local State, existing on disk (method 2): {sorted(method2_dirs_existing)}\n"
            f"  Local State, all entries:  {sorted(method2_dirs)}"
        )

    def test_both_methods_return_names_for_all_profiles(self, user_data_dir):
        """Both methods should return a non-empty display name for every
        profile they find.

        Note: the names may legitimately differ because method 1 reads
        ``profile.name`` from each profile's Preferences file (user-chosen
        display name), while method 2 reads the Local State ``info_cache``
        (often the account email or org).  We verify both return *something*
        for every shared directory.
        """
        method1_profiles = get_available_chrome_profiles()
        method1_by_dir = {
            p["directory"]: p["name"] for p in method1_profiles if p["directory"]
        }

        method2_profiles = _get_profiles_from_local_state(user_data_dir)
        if not method2_profiles:
            pytest.skip("Local State file not available")
        method2_by_dir = {p["directory"]: p["name"] for p in method2_profiles}

        common_dirs = set(method1_by_dir) & set(method2_by_dir)
        assert len(common_dirs) > 0, "No common profiles to compare"

        for d in sorted(common_dirs):
            m1_name = method1_by_dir[d].lstrip("👤 ").strip()
            m2_name = method2_by_dir[d]
            assert m1_name, f"Method 1 returned empty name for profile '{d}'"
            assert m2_name, f"Method 2 returned empty name for profile '{d}'"


class TestCopyProfile:
    """Tests for copy_chrome_profile()."""

    @pytest.fixture(autouse=True)
    def _cleanup_temp_dirs(self):
        """Track and clean up temp directories created during tests."""
        self._temp_dirs: List[str] = []
        yield
        for d in self._temp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _track(self, path: str) -> str:
        self._temp_dirs.append(path)
        return path

    def test_copy_creates_profile_in_temp_dir(self, user_data_dir):
        """copy_chrome_profile(dest=None) should create a temp dir with the
        profile subfolder inside it."""
        dest = copy_chrome_profile(user_data_dir, "Default")
        self._track(dest)

        assert os.path.isdir(dest)
        assert os.path.isdir(os.path.join(dest, "Default"))

    def test_essential_files_preserved(self, user_data_dir):
        """Cookies, Preferences, and Local Storage should be copied."""
        dest = copy_chrome_profile(user_data_dir, "Default")
        self._track(dest)

        profile = os.path.join(dest, "Default")
        for name in ("Cookies", "Preferences"):
            path = os.path.join(profile, name)
            if os.path.exists(os.path.join(user_data_dir, "Default", name)):
                assert os.path.exists(path), f"Essential file missing: {name}"

        ls_dir = os.path.join(profile, "Local Storage")
        if os.path.isdir(os.path.join(user_data_dir, "Default", "Local Storage")):
            assert os.path.isdir(ls_dir), "Local Storage directory missing"

    def test_heavy_dirs_skipped(self, user_data_dir):
        """Cache and Service Worker directories should NOT be copied."""
        dest = copy_chrome_profile(user_data_dir, "Default")
        self._track(dest)

        profile = os.path.join(dest, "Default")
        for skip_name in PROFILE_COPY_SKIP_DIRS:
            src_path = os.path.join(user_data_dir, "Default", skip_name)
            if os.path.isdir(src_path):
                dest_path = os.path.join(profile, skip_name)
                assert not os.path.exists(dest_path), (
                    f"Heavy directory should have been skipped: {skip_name}"
                )

    def test_lock_files_removed(self, user_data_dir):
        """SingletonLock/Socket/Cookie should not exist in the copy."""
        dest = copy_chrome_profile(user_data_dir, "Default")
        self._track(dest)

        for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            assert not os.path.exists(os.path.join(dest, lock_name)), (
                f"Lock file should have been removed: {lock_name}"
            )

    def test_exit_type_fixed(self, user_data_dir):
        """The copied Preferences should have exit_type set to null."""
        dest = copy_chrome_profile(user_data_dir, "Default")
        self._track(dest)

        prefs_path = os.path.join(dest, "Default", "Preferences")
        if not os.path.exists(prefs_path):
            pytest.skip("No Preferences file in Default profile")

        with open(prefs_path, "r", encoding="latin1") as f:
            prefs = json.load(f)
        exit_type = prefs.get("profile", {}).get("exit_type")
        assert exit_type is None, f"exit_type should be None, got {exit_type!r}"

    def test_reuse_existing_dest(self, user_data_dir):
        """When dest already has the profile subfolder, copy is skipped."""
        dest = tempfile.mkdtemp(prefix="webaxon_test_reuse_")
        self._track(dest)

        # First copy
        result1 = copy_chrome_profile(user_data_dir, "Default", dest)
        assert result1 == dest

        # Place a marker file to detect if the directory gets overwritten
        marker = os.path.join(dest, "Default", "_test_marker")
        with open(marker, "w") as f:
            f.write("marker")

        # Second call — should reuse, not re-copy
        result2 = copy_chrome_profile(user_data_dir, "Default", dest)
        assert result2 == dest
        assert os.path.exists(marker), (
            "Marker file was deleted — copy_chrome_profile re-copied instead of reusing"
        )

    def test_explicit_dest_path(self, user_data_dir):
        """copy_chrome_profile with an explicit dest path should use it."""
        dest = tempfile.mkdtemp(prefix="webaxon_test_explicit_")
        self._track(dest)
        # Remove the dir so copy_chrome_profile creates the profile inside it
        shutil.rmtree(dest)
        os.makedirs(dest)

        result = copy_chrome_profile(user_data_dir, "Default", dest)
        assert result == dest
        assert os.path.isdir(os.path.join(dest, "Default"))

    def test_nonexistent_source_raises(self):
        """Copying from a nonexistent source should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            copy_chrome_profile("/nonexistent/path", "Default")

    def test_copy_size_much_smaller(self, user_data_dir):
        """The copy should be significantly smaller than the original due to
        skipping caches. This is a sanity check, not a strict assertion."""
        dest = copy_chrome_profile(user_data_dir, "Default")
        self._track(dest)

        def _dir_size(path):
            total = 0
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.isfile(fp) and not os.path.islink(fp):
                        total += os.path.getsize(fp)
            return total

        src_size = _dir_size(os.path.join(user_data_dir, "Default"))
        dest_size = _dir_size(os.path.join(dest, "Default"))

        if src_size > 100 * 1024 * 1024:  # Only assert if source > 100 MB
            assert dest_size < src_size * 0.8, (
                f"Copy ({dest_size / 1e6:.1f} MB) should be significantly "
                f"smaller than source ({src_size / 1e6:.1f} MB)"
            )


class TestRemoveSingletonLocks:
    """remove_chrome_user_data_singleton_locks clears root and profile locks."""

    _LOCK_NAMES = ("SingletonLock", "SingletonSocket", "SingletonCookie")

    def test_removes_locks_from_user_data_root(self):
        root = tempfile.mkdtemp(prefix="webaxon_lock_test_")
        try:
            for name in self._LOCK_NAMES:
                open(os.path.join(root, name), "w").close()
            remove_chrome_user_data_singleton_locks(root)
            for name in self._LOCK_NAMES:
                assert not os.path.lexists(os.path.join(root, name))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_removes_locks_from_profile_subdirectory(self):
        root = tempfile.mkdtemp(prefix="webaxon_lock_test_")
        prof = os.path.join(root, "Default")
        try:
            os.makedirs(prof)
            for name in self._LOCK_NAMES:
                open(os.path.join(root, name), "w").close()
                open(os.path.join(prof, name), "w").close()
            remove_chrome_user_data_singleton_locks(root, "Default")
            for name in self._LOCK_NAMES:
                assert not os.path.lexists(os.path.join(root, name))
                assert not os.path.lexists(os.path.join(prof, name))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_no_op_for_missing_paths(self):
        remove_chrome_user_data_singleton_locks("")
        remove_chrome_user_data_singleton_locks("/nonexistent/path/webaxon_chrome_xyz")


class TestPrintProfiles:
    """Diagnostic test that prints all detected profiles (always passes).

    Run with ``pytest -s`` to see the output.
    """

    def test_print_detected_profiles(self, user_data_dir):
        print("\n" + "=" * 60)
        print("METHOD 1: Directory scanning (get_available_chrome_profiles)")
        print("=" * 60)
        for p in get_available_chrome_profiles():
            print(f"  directory={p['directory']!r:20s}  name={p['name']}")

        print("\n" + "=" * 60)
        print("METHOD 2: Chrome Local State (info_cache)")
        print("=" * 60)
        profiles_ls = _get_profiles_from_local_state(user_data_dir)
        if profiles_ls:
            for p in profiles_ls:
                print(f"  directory={p['directory']!r:20s}  name={p['name']}")
        else:
            print("  (Local State not available)")
        print()
