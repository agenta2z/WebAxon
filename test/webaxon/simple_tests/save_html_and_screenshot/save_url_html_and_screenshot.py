from rich_python_utils.io_utils.text_io import write_all_text
from webaxon.automation.web_driver import WebDriver, WebAutomationDrivers
from os import path

url_lsit = [
    'https://www.forbes.com/lists/americas-best-startup-employers/?sh=9e35d362ad72',
    'https://www.microsoft.com/en-us/ai/ai-customer-stories',
    'https://www.microsoft.com/en-us/startups'
]

output_path = 'test_case_recordings'
driver = WebDriver(headless=False, user_agent='default', driver_type=WebAutomationDrivers.UndetectedChrome)

for url_index, url in enumerate(url_lsit):
    output_path_test_case = path.join(output_path, str(url_index))
    driver.open_url(url)
    driver.wait_for_page_loading()
    write_all_text(driver.get_body_html(), path.join(output_path_test_case, 'source.html'))
    driver.capture_full_page_screenshot(path.join(output_path_test_case, 'screenshot.png'), use_cdp_cmd_for_chrome=True)
