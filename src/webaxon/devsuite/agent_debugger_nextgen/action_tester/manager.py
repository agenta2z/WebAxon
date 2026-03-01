"""
Action Tester Manager.

Global singleton manager for action testing with multi-test support.
Manages ONE global WebDriver instance with multiple tests (each test = one browser tab).
"""
import os
import sys
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime
import traceback
import uuid
import atexit

# Add paths for webaxon imports
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.chrome.webdriver import WebDriver as SeleniumWebDriver
    from webaxon.automation.web_driver import WebDriver, WebAutomationDrivers
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    uc = None
    SeleniumWebDriver = None
    WebDriver = None
    WebAutomationDrivers = None

from webaxon.devsuite.agent_debugger_nextgen.action_tester.models import (
    Test,
    TestInfo,
    BrowserStatus,
    SequenceValidationResult,
    ActionStepResult,
    ElementIDResult
)


class ActionTesterManager:
    """
    Global manager for action testing with multi-test support.
    
    Manages ONE global WebDriver instance with multiple tests.
    Each test corresponds to one browser tab and maintains its own state.
    """
    
    def __init__(self):
        """Initialize the action tester manager."""
        self.tests: Dict[str, Test] = {}
        self.active_test_id: Optional[str] = None
        self.driver: Optional[WebDriver] = None
        self.is_browser_active: bool = False
        self.action_metadata = None  # Will be initialized when needed
        
        # Load action metadata from schema system (uses Python defaults as source of truth)
        try:
            from agent_foundation.automation.schema.action_metadata import ActionMetadataRegistry
            self.action_metadata = ActionMetadataRegistry()  # Uses Python defaults
        except Exception as e:
            print(f"Warning: Could not load action metadata: {e}")
        
        # Register cleanup handler to terminate browser on application exit
        atexit.register(self._cleanup)
    
    def launch_browser(self, profile_directory: str = 'Default', copy_profile: bool = True) -> Dict:
        """
        Launch global browser instance.

        Args:
            profile_directory: Chrome profile directory name (e.g., 'Default', 'Profile 1').
                             Empty string '' means use a clean temporary profile.
            copy_profile: If True, copies the profile to temp dir (allows launching while Chrome is open).
                         If False, uses the original profile directly (requires closing Chrome first).

        Returns:
            Dict with {success: bool, message: str}
        """
        if not SELENIUM_AVAILABLE:
            return {
                'success': False,
                'message': (
                    '❌ Browser Launch Failed: Missing Dependencies\n\n'
                    'Selenium and undetected_chromedriver are not installed.\n\n'
                    '📋 Action Required:\n'
                    '1. Install required packages:\n'
                    '   pip install undetected-chromedriver selenium\n'
                    '2. Restart the debugger\n'
                    '3. Try launching the browser again'
                )
            }
        
        try:
            # Clean up any existing browser state (handles externally closed browsers too)
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass  # Browser may already be closed
            self._reset_browser_state()
            
            # Build options list for WebDriver
            browser_options = ['--start-maximized']
            chrome_user_data_dir = None

            # Add profile support if requested
            if profile_directory:  # Non-empty means use existing profile
                from webaxon.browser_utils import get_chrome_user_data_dir

                original_user_data_dir = get_chrome_user_data_dir()
                if original_user_data_dir:
                    original_profile_path = os.path.join(original_user_data_dir, profile_directory)
                    if os.path.exists(original_profile_path):
                        if copy_profile:
                            # Copy profile to temp location to avoid Chrome profile lock conflicts
                            # This allows launching even when main Chrome is running
                            import shutil
                            import tempfile
                            temp_user_data_dir = tempfile.mkdtemp(prefix='chrome_profile_')
                            temp_profile_path = os.path.join(temp_user_data_dir, profile_directory)
                            print(f'Copying profile from {original_profile_path} to {temp_profile_path}')
                            # Exclude lock files and session restore files to start fresh
                            shutil.copytree(original_profile_path, temp_profile_path,
                                           ignore=shutil.ignore_patterns(
                                               'lockfile', 'SingletonLock', 'SingletonSocket', 'SingletonCookie',
                                               'Current Session', 'Current Tabs', 'Last Session', 'Last Tabs',
                                               'Session Storage', 'Sessions'
                                           ))
                            chrome_user_data_dir = temp_user_data_dir
                        else:
                            # Use original profile directly (requires Chrome to be closed)
                            chrome_user_data_dir = original_user_data_dir
                        browser_options.append(f'--profile-directory={profile_directory}')

            # Use WebDriver wrapper class which has __call__ for ActionFlow
            print(f'checkpoint 101 - browser_options: {browser_options}, user_data_dir: {chrome_user_data_dir}')
            self.driver = WebDriver(
                driver_type=WebAutomationDrivers.UndetectedChrome,
                headless=False,
                timeout=120,
                options=browser_options,
                user_data_dir=chrome_user_data_dir
            )
            print('checkpoint 102')
            # Note: uc.Chrome already opens with an initial tab, no need for get("about:blank")
            self.is_browser_active = True
            
            profile_msg = f" (profile: {profile_directory})" if profile_directory else " (temporary profile)"
            return {
                'success': True,
                'message': f'✅ Browser launched successfully{profile_msg}'
            }
            
        except FileNotFoundError as e:
            self.is_browser_active = False
            error_msg = str(e).lower()
            if 'chromedriver' in error_msg:
                return {
                    'success': False,
                    'message': (
                        '❌ Browser Launch Failed: ChromeDriver Not Found\n\n'
                        'The ChromeDriver executable could not be located.\n\n'
                        '📋 Action Required:\n'
                        '1. Ensure Chrome browser is installed on your system\n'
                        '2. ChromeDriver will be downloaded automatically on first run\n'
                        '3. If the issue persists, manually download ChromeDriver from:\n'
                        '   https://chromedriver.chromium.org/downloads\n'
                        '4. Place it in your system PATH or project directory'
                    )
                }
            elif 'chrome' in error_msg or 'google' in error_msg:
                return {
                    'success': False,
                    'message': (
                        '❌ Browser Launch Failed: Chrome Browser Not Found\n\n'
                        'Google Chrome is not installed or not in the expected location.\n\n'
                        '📋 Action Required:\n'
                        '1. Install Google Chrome from: https://www.google.com/chrome/\n'
                        '2. Restart the debugger\n'
                        '3. Try launching the browser again'
                    )
                }
            else:
                return {
                    'success': False,
                    'message': (
                        f'❌ Browser Launch Failed: File Not Found\n\n'
                        f'Error: {str(e)}\n\n'
                        '📋 Action Required:\n'
                        '1. Ensure Google Chrome is installed\n'
                        '2. Check that all required files are accessible\n'
                        '3. Try restarting the debugger'
                    )
                }
        except PermissionError as e:
            self.is_browser_active = False
            return {
                'success': False,
                'message': (
                    '❌ Browser Launch Failed: Permission Denied\n\n'
                    f'Error: {str(e)}\n\n'
                    '📋 Action Required:\n'
                    '1. Close any existing Chrome instances\n'
                    '2. Check file permissions in the working directory\n'
                    '3. Try running the debugger with appropriate permissions\n'
                    '4. On Windows, try running as Administrator if necessary'
                )
            }
        except OSError as e:
            self.is_browser_active = False
            error_msg = str(e).lower()
            if 'address already in use' in error_msg or 'port' in error_msg:
                return {
                    'success': False,
                    'message': (
                        '❌ Browser Launch Failed: Port Already In Use\n\n'
                        'Another browser instance or process is using the required port.\n\n'
                        '📋 Action Required:\n'
                        '1. Close any existing Chrome or ChromeDriver instances\n'
                        '2. Check for zombie processes:\n'
                        '   - Windows: Task Manager → End "chrome.exe" and "chromedriver.exe"\n'
                        '   - Linux/Mac: killall chrome chromedriver\n'
                        '3. Wait a few seconds and try again'
                    )
                }
            else:
                return {
                    'success': False,
                    'message': (
                        f'❌ Browser Launch Failed: System Error\n\n'
                        f'Error: {str(e)}\n\n'
                        '📋 Action Required:\n'
                        '1. Check system resources (memory, disk space)\n'
                        '2. Close unnecessary applications\n'
                        '3. Restart the debugger and try again'
                    )
                }
        except Exception as e:
            self.is_browser_active = False
            self._reset_browser_state()
            error_type = type(e).__name__
            error_msg = str(e).lower()
            
            # Handle SessionNotCreatedException - usually means profile is locked
            if 'session' in error_type.lower() or 'session' in error_msg:
                return {
                    'success': False,
                    'message': (
                        f'❌ Browser Launch Failed: {error_type}\n\n'
                        'The Chrome profile may be in use by another browser instance.\n\n'
                        '📋 Action Required:\n'
                        '1. Close all Chrome browser windows\n'
                        '2. Wait a few seconds for Chrome to fully close\n'
                        '3. Try launching again\n'
                        '4. Or select "New Temporary Profile" from the dropdown'
                    )
                }
            
            # Handle profile-related errors
            if 'user data' in error_msg or 'profile' in error_msg:
                return {
                    'success': False,
                    'message': (
                        f'❌ Browser Launch Failed: Profile Error\n\n'
                        f'Error: {str(e)}\n\n'
                        '📋 Action Required:\n'
                        '1. The selected Chrome profile may be in use\n'
                        '2. Close all Chrome windows using that profile\n'
                        '3. Try selecting "New Temporary Profile" instead\n'
                        '4. Or wait a few seconds and try again'
                    )
                }
            
            return {
                'success': False,
                'message': (
                    f'❌ Browser Launch Failed: {error_type}\n\n'
                    f'Error: {str(e)}\n\n'
                    '📋 Action Required:\n'
                    '1. Check the error message above for specific details\n'
                    '2. Ensure Chrome and ChromeDriver are properly installed\n'
                    '3. Try closing all Chrome instances and restarting\n'
                    '4. If the issue persists, check the debugger logs for more details'
                )
            }
    
    def close_browser(self) -> None:
        """Close global browser instance and all tests."""
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            print(f"Error closing browser: {e}")
        finally:
            self._reset_browser_state()
    
    def _reset_browser_state(self) -> None:
        """Reset internal browser state. Called when browser is closed (manually or externally)."""
        self.driver = None
        self.is_browser_active = False
        self.tests.clear()
        self.active_test_id = None
    
    def get_browser_status(self) -> Dict:
        """
        Get browser status including active state, window count, active tab, URL.
        
        Also detects if browser was closed externally and resets internal state.
        
        Returns:
            Dict with browser status information
        """
        if not self.is_browser_active or not self.driver:
            return {
                'active': False,
                'status_indicator': '🔴 Not Active',
                'window_count': 0,
                'window_count_text': '0 tab(s) open',
                'active_window': 'None',
                'current_url': '—',
                'page_title': '—'
            }
        
        try:
            window_handles = self.driver.window_handles
            window_count = len(window_handles)
            
            # If no windows, browser was closed externally
            if window_count == 0:
                self._reset_browser_state()
                return {
                    'active': False,
                    'status_indicator': '🔴 Not Active',
                    'window_count': 0,
                    'window_count_text': '0 tab(s) open',
                    'active_window': 'None',
                    'current_url': '—',
                    'page_title': '—'
                }
            
            current_handle = self.driver.current_window_handle()

            # Find which tab number is active
            tab_number = window_handles.index(current_handle) + 1 if current_handle in window_handles else 0
            
            current_url = self.driver.current_url
            page_title = self.driver.title
            
            return {
                'active': True,
                'status_indicator': '🟢 Active',
                'window_count': window_count,
                'window_count_text': f'{window_count} tab(s) open',
                'active_window': f'Tab {tab_number} - "{page_title}"' if page_title else f'Tab {tab_number}',
                'current_url': current_url,
                'page_title': page_title
            }
        except Exception as e:
            # Browser was likely closed externally - reset state
            self._reset_browser_state()
            return {
                'active': False,
                'status_indicator': '🔴 Not Active',
                'window_count': 0,
                'window_count_text': '0 tab(s) open',
                'active_window': 'None',
                'current_url': '—',
                'page_title': '—'
            }
    
    def create_test(self, test_name: str = None) -> str:
        """
        Create new test with browser tab.
        
        Args:
            test_name: Optional name for the test
            
        Returns:
            test_id of the created test
            
        Raises:
            RuntimeError: If browser is not active or test creation fails
        """
        if not self.is_browser_active or not self.driver:
            raise RuntimeError(
                "❌ Test Creation Failed: No Active Browser\n\n"
                "A browser must be running to create a test.\n\n"
                "📋 Action Required:\n"
                "1. Click the '🚀 Launch Browser' button\n"
                "2. Wait for the browser to open\n"
                "3. Try creating a test again"
            )
        
        try:
            # Generate unique test ID and name
            test_id = str(uuid.uuid4())
            if not test_name:
                test_name = f"Test {len(self.tests) + 1}"
            
            # Open new browser tab
            self.driver.execute_script("window.open('about:blank', '_blank');")
            window_handles = self.driver.window_handles
            tab_handle = window_handles[-1]  # Get the newly opened tab
            
            # Create test object
            test = Test(
                test_id=test_id,
                test_name=test_name,
                tab_handle=tab_handle
            )
            
            self.tests[test_id] = test
            self.active_test_id = test_id
            
            # Switch to the new tab
            self.driver.switch_to.window(tab_handle)
            
            return test_id
            
        except Exception as e:
            error_type = type(e).__name__
            raise RuntimeError(
                f"❌ Test Creation Failed: {error_type}\n\n"
                f"Error: {str(e)}\n\n"
                "📋 Action Required:\n"
                "1. Check if the browser is still responsive\n"
                "2. Try closing and relaunching the browser\n"
                "3. If the issue persists, restart the debugger"
            )
    
    def close_test(self, test_id: str) -> None:
        """
        Close test and its browser tab.
        
        Args:
            test_id: Test identifier
            
        Raises:
            RuntimeError: If test closure fails critically
        """
        if test_id not in self.tests:
            # Silently ignore if test doesn't exist (already closed)
            return
        
        test = self.tests[test_id]
        
        # Close browser tab
        if self.driver and self.is_browser_active:
            try:
                self.driver.switch_to.window(test.tab_handle)
                self.driver.close()
                
                # Switch to another tab if available
                remaining_handles = self.driver.window_handles
                if remaining_handles:
                    self.driver.switch_to.window(remaining_handles[0])
                    # Find test with this handle
                    for tid, t in self.tests.items():
                        if t.tab_handle == remaining_handles[0]:
                            self.active_test_id = tid
                            break
                else:
                    self.active_test_id = None
            except Exception as e:
                # Log the error but continue with cleanup
                print(f"⚠️ Warning: Error closing browser tab: {e}")
                print("The test will be removed from the list, but the browser tab may still be open.")
        
        # Remove test from internal state
        try:
            del self.tests[test_id]
        except KeyError:
            pass  # Already removed
        
        # If this was the active test, clear it
        if self.active_test_id == test_id:
            self.active_test_id = None
    
    def switch_to_test(self, test_id: str) -> None:
        """
        Switch active test and focus its browser tab.
        
        Args:
            test_id: Test identifier
            
        Raises:
            RuntimeError: If test switching fails critically
        """
        if test_id not in self.tests:
            raise RuntimeError(
                f"❌ Test Switch Failed: Test Not Found\n\n"
                f"Test ID '{test_id}' does not exist.\n\n"
                "📋 Action Required:\n"
                "1. The test may have been closed\n"
                "2. Refresh the test list\n"
                "3. Select a different test or create a new one"
            )
        
        test = self.tests[test_id]
        self.active_test_id = test_id
        
        # Focus browser tab
        if self.driver and self.is_browser_active:
            try:
                self.driver.switch_to.window(test.tab_handle)
            except Exception as e:
                error_msg = str(e).lower()
                if 'no such window' in error_msg or 'invalid window handle' in error_msg:
                    raise RuntimeError(
                        f"❌ Test Switch Failed: Browser Tab Closed\n\n"
                        f"The browser tab for test '{test.test_name}' was closed externally.\n\n"
                        "📋 Action Required:\n"
                        "1. Close this test from the test list\n"
                        "2. Create a new test\n"
                        "3. Avoid manually closing browser tabs - use the test close button instead"
                    )
                else:
                    raise RuntimeError(
                        f"❌ Test Switch Failed: {type(e).__name__}\n\n"
                        f"Error: {str(e)}\n\n"
                        "📋 Action Required:\n"
                        "1. Check if the browser is still responsive\n"
                        "2. Try refreshing the test list\n"
                        "3. If the issue persists, close and relaunch the browser"
                    )
    
    def get_test_list(self) -> List[Dict]:
        """
        Get list of all tests with their names and active status.
        
        Returns:
            List of test info dicts
        """
        return [
            {
                'test_id': test.test_id,
                'test_name': test.test_name,
                'is_active': test.test_id == self.active_test_id,
                'created_at': test.created_at.isoformat()
            }
            for test in self.tests.values()
        ]
    
    def update_test_content(self, test_id: str, json_content: str) -> None:
        """
        Update test's JSON editor content.
        
        Args:
            test_id: Test identifier
            json_content: JSON content string
        """
        if test_id in self.tests:
            self.tests[test_id].update_content(json_content)
    
    def get_test_content(self, test_id: str) -> str:
        """
        Get test's JSON editor content.
        
        Args:
            test_id: Test identifier
            
        Returns:
            JSON content string
        """
        if test_id in self.tests:
            return self.tests[test_id].json_content
        return ""
    
    def add_element_ids(self) -> Dict:
        """
        Inject __id__ attributes to all HTML elements in active tab.
        
        Uses the existing add_unique_index_to_elements() function from
        webaxon.automation.selenium.element_selection for consistency.
        
        Returns:
            Dict with {success: bool, elements_tagged: int, error: str}
        """
        if not self.is_browser_active or not self.driver:
            return {
                'success': False,
                'elements_tagged': 0,
                'error': (
                    '❌ ID Injection Failed: No Active Browser\n\n'
                    'A browser must be running to inject element IDs.\n\n'
                    '📋 Action Required:\n'
                    '1. Click the "🚀 Launch Browser" button\n'
                    '2. Navigate to a webpage\n'
                    '3. Try injecting IDs again'
                )
            }
        
        try:
            # Check if page is loaded
            current_url = self.driver.current_url
            if current_url == 'about:blank' or not current_url:
                return {
                    'success': False,
                    'elements_tagged': 0,
                    'error': (
                        '⚠️ ID Injection Warning: No Page Loaded\n\n'
                        'The current tab is blank or has no content.\n\n'
                        '📋 Action Required:\n'
                        '1. Navigate to a webpage first\n'
                        '2. Wait for the page to fully load\n'
                        '3. Try injecting IDs again'
                    )
                }
            
            # Use the existing utility function from element_selection
            from webaxon.automation.backends.selenium.element_selection import add_unique_index_to_elements
            from webaxon.html_utils.element_identification import ATTR_NAME_INCREMENTAL_ID
            
            # Add __id__ attributes to all elements
            add_unique_index_to_elements(self.driver, index_name=ATTR_NAME_INCREMENTAL_ID)
            
            # Count elements with __id__ attribute
            elements_tagged = self.driver.execute_script(f"""
                return document.querySelectorAll('[{ATTR_NAME_INCREMENTAL_ID}]').length;
            """)
            
            if elements_tagged == 0:
                return {
                    'success': True,
                    'elements_tagged': 0,
                    'error': (
                        'ℹ️ All elements already have __id__ attributes.\n\n'
                        'No new IDs were added. This is normal if you\'ve already run this operation on this page.'
                    )
                }
            
            return {
                'success': True,
                'elements_tagged': elements_tagged,
                'error': None
            }
            
        except Exception as e:
            error_msg = str(e).lower()
            error_type = type(e).__name__
            
            if 'javascript error' in error_msg or 'script' in error_msg:
                return {
                    'success': False,
                    'elements_tagged': 0,
                    'error': (
                        f'❌ ID Injection Failed: JavaScript Execution Error\n\n'
                        f'Error: {str(e)}\n\n'
                        '📋 Action Required:\n'
                        '1. The page may have security restrictions\n'
                        '2. Try navigating to a different page\n'
                        '3. Some pages (like chrome://, file://) block JavaScript execution'
                    )
                }
            elif 'no such window' in error_msg or 'invalid window' in error_msg:
                return {
                    'success': False,
                    'elements_tagged': 0,
                    'error': (
                        '❌ ID Injection Failed: Browser Tab Closed\n\n'
                        'The active browser tab was closed.\n\n'
                        '📋 Action Required:\n'
                        '1. Switch to a different test\n'
                        '2. Or create a new test\n'
                        '3. Avoid manually closing browser tabs'
                    )
                }
            elif 'timeout' in error_msg:
                return {
                    'success': False,
                    'elements_tagged': 0,
                    'error': (
                        '❌ ID Injection Failed: Operation Timeout\n\n'
                        'The page took too long to respond.\n\n'
                        '📋 Action Required:\n'
                        '1. Wait for the page to finish loading\n'
                        '2. Check if the page is responsive\n'
                        '3. Try refreshing the page and injecting IDs again'
                    )
                }
            else:
                return {
                    'success': False,
                    'elements_tagged': 0,
                    'error': (
                        f'❌ ID Injection Failed: {error_type}\n\n'
                        f'Error: {str(e)}\n\n'
                        '📋 Action Required:\n'
                        '1. Check if the browser is still responsive\n'
                        '2. Try refreshing the page\n'
                        '3. If the issue persists, close and relaunch the browser'
                    )
                }
    
    def validate_sequence_json(self, json_str: str) -> Dict:
        """
        Validate action sequence JSON.
        
        Args:
            json_str: JSON string to validate
            
        Returns:
            Dict with {valid: bool, sequence_id: str, action_count: int, error: str}
        """
        if not json_str or not json_str.strip():
            return {
                'valid': False,
                'sequence_id': None,
                'action_count': None,
                'error': (
                    '❌ Validation Failed: Empty Input\n\n'
                    'The JSON editor is empty.\n\n'
                    '📋 Action Required:\n'
                    '1. Click "📄 Load Template" to load an example sequence\n'
                    '2. Or paste your own action sequence JSON\n'
                    '3. Then try validating again'
                )
            }
        
        try:
            from webaxon.automation.schema import load_sequence_from_string
            
            sequence = load_sequence_from_string(json_str)
            
            # Additional validation checks
            if not sequence.actions or len(sequence.actions) == 0:
                return {
                    'valid': False,
                    'sequence_id': sequence.id,
                    'action_count': 0,
                    'error': (
                        '⚠️ Validation Warning: No Actions Defined\n\n'
                        'The sequence is valid but contains no actions.\n\n'
                        '📋 Action Required:\n'
                        '1. Add at least one action to the "actions" array\n'
                        '2. See the Action Reference panel for available actions\n'
                        '3. Validate again after adding actions'
                    )
                }
            
            return {
                'valid': True,
                'sequence_id': sequence.id,
                'action_count': len(sequence.actions),
                'error': None
            }
            
        except ImportError as e:
            return {
                'valid': False,
                'sequence_id': None,
                'action_count': None,
                'error': (
                    '❌ Validation Failed: Missing Schema System\n\n'
                    f'Error: {str(e)}\n\n'
                    '📋 Action Required:\n'
                    '1. Ensure the webaxon automation schema is properly installed\n'
                    '2. Check that all required modules are available\n'
                    '3. Restart the debugger if necessary'
                )
            }
        except ValueError as e:
            error_msg = str(e)
            return {
                'valid': False,
                'sequence_id': None,
                'action_count': None,
                'error': (
                    f'❌ Validation Failed: Invalid JSON Structure\n\n'
                    f'Error: {error_msg}\n\n'
                    '📋 Action Required:\n'
                    '1. Check that your JSON has the required fields:\n'
                    '   - "version": string (e.g., "1.0")\n'
                    '   - "id": string (unique identifier)\n'
                    '   - "actions": array of action objects\n'
                    '2. Each action must have:\n'
                    '   - "id": string\n'
                    '   - "type": string (valid action type)\n'
                    '3. See the Action Reference panel for examples'
                )
            }
        except KeyError as e:
            return {
                'valid': False,
                'sequence_id': None,
                'action_count': None,
                'error': (
                    f'❌ Validation Failed: Missing Required Field\n\n'
                    f'Missing field: {str(e)}\n\n'
                    '📋 Action Required:\n'
                    '1. Ensure all required fields are present\n'
                    '2. Common required fields:\n'
                    '   - Sequence: version, id, actions\n'
                    '   - Action: id, type\n'
                    '   - Target (if required): strategy, value\n'
                    '3. Click "📄 Load Template" to see a valid example'
                )
            }
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Check for common JSON syntax errors
            if 'json' in error_msg.lower() or 'parse' in error_msg.lower():
                return {
                    'valid': False,
                    'sequence_id': None,
                    'action_count': None,
                    'error': (
                        f'❌ Validation Failed: JSON Syntax Error\n\n'
                        f'Error: {error_msg}\n\n'
                        '📋 Action Required:\n'
                        '1. Check for common JSON syntax issues:\n'
                        '   - Missing or extra commas\n'
                        '   - Unclosed brackets or braces\n'
                        '   - Unquoted strings\n'
                        '   - Trailing commas (not allowed in JSON)\n'
                        '2. Use a JSON validator to find the exact issue\n'
                        '3. Click "📄 Load Template" to see valid JSON syntax'
                    )
                }
            else:
                return {
                    'valid': False,
                    'sequence_id': None,
                    'action_count': None,
                    'error': (
                        f'❌ Validation Failed: {error_type}\n\n'
                        f'Error: {error_msg}\n\n'
                        '📋 Action Required:\n'
                        '1. Review the error message above\n'
                        '2. Check the Action Reference panel for valid action types\n'
                        '3. Ensure your JSON follows the expected schema\n'
                        '4. Click "📄 Load Template" to see a working example'
                    )
                }
    
    def execute_sequence(self, test_id: str, json_str: str) -> List[Dict]:
        """
        Execute action sequence for test.
        
        Args:
            test_id: Test identifier
            json_str: JSON sequence string
            
        Returns:
            List of step results
        """
        if not self.is_browser_active or not self.driver:
            return [{
                'action_id': 'error',
                'action_type': 'error',
                'success': False,
                'error': (
                    '❌ Execution Failed: No Active Browser\n\n'
                    'A browser must be running to execute sequences.\n\n'
                    '📋 Action Required:\n'
                    '1. Click the "🚀 Launch Browser" button\n'
                    '2. Wait for the browser to open\n'
                    '3. Try running the sequence again'
                )
            }]
        
        if test_id not in self.tests:
            return [{
                'action_id': 'error',
                'action_type': 'error',
                'success': False,
                'error': (
                    f'❌ Execution Failed: Test Not Found\n\n'
                    f'Test ID "{test_id}" does not exist.\n\n'
                    '📋 Action Required:\n'
                    '1. The test may have been closed\n'
                    '2. Create a new test\n'
                    '3. Try running the sequence again'
                )
            }]
        
        if not json_str or not json_str.strip():
            return [{
                'action_id': 'error',
                'action_type': 'error',
                'success': False,
                'error': (
                    '❌ Execution Failed: Empty Sequence\n\n'
                    'The JSON editor is empty.\n\n'
                    '📋 Action Required:\n'
                    '1. Click "📄 Load Template" to load an example\n'
                    '2. Or paste your action sequence JSON\n'
                    '3. Click "✓ Validate JSON" to check it\n'
                    '4. Then try running again'
                )
            }]
        
        try:
            from webaxon.automation.schema import load_sequence_from_string, ActionFlow
            
            # Parse sequence
            try:
                sequence = load_sequence_from_string(json_str)
            except Exception as parse_error:
                error_msg = str(parse_error)
                return [{
                    'action_id': 'parse_error',
                    'action_type': 'parse',
                    'success': False,
                    'error': (
                        f'❌ Execution Failed: JSON Parse Error\n\n'
                        f'Error: {error_msg}\n\n'
                        '📋 Action Required:\n'
                        '1. Click "✓ Validate JSON" to see detailed validation errors\n'
                        '2. Fix any JSON syntax or structure issues\n'
                        '3. Ensure all required fields are present\n'
                        '4. Try running again after fixing'
                    )
                }]
            
            if not sequence.actions or len(sequence.actions) == 0:
                return [{
                    'action_id': 'no_actions',
                    'action_type': 'validation',
                    'success': False,
                    'error': (
                        '⚠️ Execution Warning: No Actions to Execute\n\n'
                        'The sequence contains no actions.\n\n'
                        '📋 Action Required:\n'
                        '1. Add actions to the "actions" array\n'
                        '2. See the Action Reference panel for available actions\n'
                        '3. Try running again after adding actions'
                    )
                }]
            
            # Switch to test's tab
            try:
                self.switch_to_test(test_id)
            except Exception as switch_error:
                return [{
                    'action_id': 'switch_error',
                    'action_type': 'setup',
                    'success': False,
                    'error': str(switch_error)
                }]
            
            # Execute sequence using ActionFlow
            # WebDriver class implements __call__ which provides the action_executor interface
            executor = ActionFlow(
                action_executor=self.driver,
                action_metadata=self.action_metadata
            )
            
            # Execute the entire sequence
            exec_result = executor.execute(sequence)
            
            # Build step-by-step results from execution context
            results = []
            for action in sequence.actions:
                action_result = exec_result.context.get_result(action.id)
                
                if action_result and action_result.success:
                    results.append({
                        'action_id': action.id,
                        'action_type': action.type,
                        'success': True,
                        'value': str(action_result.value) if action_result.value else None,
                        'error': None
                    })
                else:
                    # Get error message and enhance it
                    error_msg = str(action_result.error) if action_result and action_result.error else 'Unknown error'
                    error_type = type(action_result.error).__name__ if action_result and action_result.error else 'Error'
                    
                    # Provide context-specific error messages
                    if 'no such element' in error_msg.lower() or 'unable to locate element' in error_msg.lower():
                        enhanced_error = (
                            f'❌ Action Failed: Element Not Found\n\n'
                            f'Could not locate element for action "{action.id}" ({action.type})\n\n'
                            f'Original error: {error_msg}\n\n'
                            '📋 Action Required:\n'
                            '1. Check that the element exists on the page\n'
                            '2. Try using "🏷️ Assign __id__" to add IDs to elements\n'
                            '3. Verify your target selector is correct\n'
                            '4. Ensure the page has fully loaded before running\n'
                            '5. Use browser DevTools to test your selector'
                        )
                    elif 'timeout' in error_msg.lower():
                        enhanced_error = (
                            f'❌ Action Failed: Timeout\n\n'
                            f'Action "{action.id}" ({action.type}) timed out\n\n'
                            f'Original error: {error_msg}\n\n'
                            '📋 Action Required:\n'
                            '1. The element may be loading slowly\n'
                            '2. Add a "wait" action before this action\n'
                            '3. Check if the page is responsive\n'
                            '4. Increase timeout if needed'
                        )
                    elif 'stale element' in error_msg.lower():
                        enhanced_error = (
                            f'❌ Action Failed: Stale Element\n\n'
                            f'Element for action "{action.id}" ({action.type}) is no longer valid\n\n'
                            f'Original error: {error_msg}\n\n'
                            '📋 Action Required:\n'
                            '1. The page may have refreshed or changed\n'
                            '2. Re-run "🏷️ Assign __id__" after page changes\n'
                            '3. Add wait actions between steps\n'
                            '4. Check if previous actions modified the page'
                        )
                    elif 'not clickable' in error_msg.lower() or 'not interactable' in error_msg.lower():
                        enhanced_error = (
                            f'❌ Action Failed: Element Not Interactable\n\n'
                            f'Cannot interact with element for action "{action.id}" ({action.type})\n\n'
                            f'Original error: {error_msg}\n\n'
                            '📋 Action Required:\n'
                            '1. The element may be hidden or covered\n'
                            '2. Try scrolling to the element first\n'
                            '3. Wait for animations or overlays to complete\n'
                            '4. Check if the element is disabled'
                        )
                    elif 'invalid argument' in error_msg.lower() or 'invalid selector' in error_msg.lower():
                        enhanced_error = (
                            f'❌ Action Failed: Invalid Selector or Argument\n\n'
                            f'Action "{action.id}" ({action.type}) has invalid configuration\n\n'
                            f'Original error: {error_msg}\n\n'
                            '📋 Action Required:\n'
                            '1. Check your target selector syntax\n'
                            '2. Verify all required arguments are provided\n'
                            '3. See the Action Reference panel for correct format\n'
                            '4. Validate your JSON structure'
                        )
                    else:
                        enhanced_error = (
                            f'❌ Action Failed: {error_type}\n\n'
                            f'Action "{action.id}" ({action.type}) failed\n\n'
                            f'Error: {error_msg}\n\n'
                            '📋 Action Required:\n'
                            '1. Review the error message above\n'
                            '2. Check the Action Reference for correct usage\n'
                            '3. Verify the page state before this action\n'
                            '4. Try running previous actions individually to isolate the issue'
                        )
                    
                    results.append({
                        'action_id': action.id,
                        'action_type': action.type,
                        'success': False,
                        'value': None,
                        'error': enhanced_error
                    })
                    
                    # Stop processing if this action failed (sequence executor stops on first error)
                    if exec_result.failed_action_id == action.id:
                        break
            
            # Store results in test
            self.tests[test_id].set_results(results)
            
            return results
            
        except ImportError as e:
            error_result = [{
                'action_id': 'import_error',
                'action_type': 'setup',
                'success': False,
                'error': (
                    f'❌ Execution Failed: Missing Dependencies\n\n'
                    f'Error: {str(e)}\n\n'
                    '📋 Action Required:\n'
                    '1. Ensure the webaxon automation schema is installed\n'
                    '2. Check that all required modules are available\n'
                    '3. Restart the debugger\n'
                    '4. If the issue persists, reinstall dependencies'
                )
            }]
            if test_id in self.tests:
                self.tests[test_id].set_results(error_result)
            return error_result
            
        except Exception as e:
            error_type = type(e).__name__
            error_result = [{
                'action_id': 'execution_error',
                'action_type': 'system',
                'success': False,
                'error': (
                    f'❌ Execution Failed: {error_type}\n\n'
                    f'Error: {str(e)}\n\n'
                    '📋 Action Required:\n'
                    '1. Check if the browser is still responsive\n'
                    '2. Try validating your JSON first\n'
                    '3. Review the sequence for any issues\n'
                    '4. If the issue persists, close and relaunch the browser'
                )
            }]
            if test_id in self.tests:
                self.tests[test_id].set_results(error_result)
            return error_result
    
    def get_available_actions(self) -> List[Dict]:
        """
        Get all available actions with metadata for reference panel.
        
        Returns:
            List of action metadata dicts
        """
        if not self.action_metadata:
            return []
        
        try:
            actions = []
            for action_name in self.action_metadata.list_actions():
                metadata = self.action_metadata.get_metadata(action_name)
                if metadata:
                    actions.append({
                        'name': action_name,
                        'description': metadata.description,
                        'target_required': metadata.requires_target,
                        'supported_args': metadata.supported_args
                    })
            return actions
        except Exception as e:
            print(f"Error getting available actions: {e}")
            return []
    
    def _cleanup(self) -> None:
        """
        Cleanup handler to terminate browser on application exit.
        
        This method is registered with atexit and will be called automatically
        when the Python interpreter exits. It ensures the browser is properly
        closed even if the application terminates unexpectedly.
        """
        if self.driver:
            try:
                # Attempt graceful shutdown
                self.driver.quit()
                print("✓ Action Tester: Browser terminated successfully")
            except Exception as e:
                # If graceful shutdown fails, try to force kill
                try:
                    # Try to kill the process if quit() failed
                    if hasattr(self.driver, 'service') and hasattr(self.driver.service, 'process'):
                        process = self.driver.service.process
                        if process and process.poll() is None:  # Process is still running
                            process.terminate()
                            # Give it a moment to terminate
                            import time
                            time.sleep(1)
                            # Force kill if still running
                            if process.poll() is None:
                                process.kill()
                    print(f"⚠ Action Tester: Browser terminated with force (error during graceful shutdown: {e})")
                except Exception as force_error:
                    # Even force kill failed, but we tried our best
                    print(f"⚠ Action Tester: Could not terminate browser cleanly: {force_error}")
            finally:
                # Clear state regardless of success
                self.driver = None
                self.is_browser_active = False
                self.tests.clear()
                self.active_test_id = None


# Global singleton instance
_action_tester_manager = None

def get_action_tester_manager() -> ActionTesterManager:
    """Get or create the global ActionTesterManager instance."""
    global _action_tester_manager
    if _action_tester_manager is None:
        _action_tester_manager = ActionTesterManager()
    return _action_tester_manager
