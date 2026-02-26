from os import path

from webaxon.integrated_tests.action_sequence_reproduce.test_data_example import DATA_EXAMPLE
from webaxon.automation.web_driver import WebDriver, WebAutomationDrivers

if __name__ == '__main__':
    output_path_recordings_root = 'test_case_recordings'
    test_case = DATA_EXAMPLE
    test_case_id = test_case['test_case_id']
    turn_index = 1
    output_path_recordings_test_case = path.join(
        output_path_recordings_root,
        test_case_id,
        f'turn_{turn_index}'
    )

    driver = WebDriver(headless=False, driver_type=WebAutomationDrivers.UndetectedChrome)
    driver.execute_actions(
        actions=DATA_EXAMPLE['turns'][1]['actions'][:16],
        output_path_action_records=output_path_recordings_test_case
    )
