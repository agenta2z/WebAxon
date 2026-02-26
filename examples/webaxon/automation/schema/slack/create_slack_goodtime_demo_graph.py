"""Factory function to create an ActionGraph for Google search operations."""

from science_modeling_tools.automation.schema import ActionGraph, TargetSpec
from science_modeling_tools.automation.schema.action_metadata import ActionMetadataRegistry


def create_slack_good_time_demo_graph(
    action_executor,
    search_query: str = "test query",
    url: str = "https://app.slack.com/client/EE8HJA7RS/C097JUKSEQJ"
):
    """
    Create an ActionGraph that visits Google, inputs text, and clicks search button.

    Args:
        action_executor: The action executor (e.g., WebDriver instance)
        search_query: The search query to input
        url: The Google URL to visit (default: https://www.google.com)

    Returns:
        ActionGraph configured with visit_url, input_text, and click actions
    """

    graph = ActionGraph(
        action_executor=action_executor,
        action_metadata=ActionMetadataRegistry()
    )

    graph.action(
        "wait",
        target=5
    )

    # Action 1: Visit Goodtime dashboard
    graph.action(
        "visit_url",
        target='https://eu.goodtime.io/dashboard'
    )

    # Action 2: Click on reschedule
    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//a[contains(@class, '_Interview_1kmia_9') and contains(., 'Anakin')]")
    )

    graph.action(
        "wait",
        target=5
    )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//button[contains(., 'Set Availability')]")
    )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//td[@title='December 23, 2025']")
    )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//div[contains(@class,'gui-modal-footer')]//button[contains(., 'Set Availability')]")
    )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//a[contains(@class, '_buttonTitle_yjkez_24') and contains(., 'Reschedule')]")
    )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//div[contains(@class,'_footer_6daik_188')]//button[contains(., 'Reschedule')]")
    )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//a[contains(@class, '_buttonTitle_yjkez_24') and contains(., 'Continue')]")
    )

    graph.action(
        "wait",
        target=5
    )

    # _TimeListItem_1mfa3_1784
    # svg-inline--fa fa-xmark

    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class, '_TimeListItem_1mfa3_1784') and contains(., 'Dec 19')]//div[contains(@class, '_TimeListItemCloseIcon_1mfa3_1843)]")
    # )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//div[contains(@class, '_TimeListItem_1mfa3_1784') and contains(., 'Dec 19')]//div[contains(@class, '_TimeListItemCloseIcon_1mfa3_1843')]")
    )


    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//button[contains(., 'Add Another Day and Time')]")
    # )
    #
    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class,'_AddTimeCard_9lymr_1784')]//input[contains(@class, '_datePickerInput_1ws63_16')]")
    # )
    #
    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class,'_calendar_1ws63_29')]//div[contains(@class,'_main_1ws63_98')]//div[contains(@class, '_day_1ws63_41') and contains(., '23')]")
    # )

    # graph.action(
    #     "input",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class,'_AddTimeCard_9lymr_1784')]//div[contains(@div, '_RainTimeRangePickerStart_qd3f8_1784')//input[contains(@class, 'ant-select-selection-search-input')]")
    # )
    #
    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class,'_AddTimeCard_9lymr_1784')]//div[contains(@div, '_RainTimeRangePickerStart_qd3f8_1784')//div[contains(@class, 'ant-select-item-option-content') and contains(., '11:00 AM')]")
    # )
    #
    # graph.action(
    #     "input",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class,'_AddTimeCard_9lymr_1784')]//div[contains(@class, '_RainTimeRangePickerEnd_qd3f8_1799')]//input[contains(@class, 'ant-select-selection-search-input')")
    # )
    #
    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class,'_AddTimeCard_9lymr_1784')]//div[contains(@div, '_RainTimeRangePickerEnd_qd3f8_1799')//div[contains(@class, 'ant-select-item-option-content') and contains(., '12:00 PM')]")
    # )

    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//button[contains(@class, '_AddTimeCardButton_9lymr_1828') and contains(., 'Save')]")
    # )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//div[contains(@class,'_toast_90z3e_6')]//button[contains(., 'Refresh')]")
    )

    graph.action(
        "wait",
        target=15
    )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//div[contains(@class,'_timelineContainer_1ghxd_1889') and contains(., '11:00 AM - 12:00 PM (PST)')]//button[contains(., 'Select this option')]")
    )

    graph.action(
        action_type='scroll_up_to_element',
        target=TargetSpec(strategy='xpath', value="//div[contains(@class, '_labelText_1qicp_28') and contains(., 'Candidate Email')]")
    )

    graph.action(
        "wait",
        target=5
    )

    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class, '_box_1ba76_91') and contains (., 'Email Templates')]//span[contains(@class, 'Select-value')]")
    # )
    #
    # graph.action(
    #     "wait",
    #     timeout=5
    # )

    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class,'Select-menu-outer')/*[last()]")
    # )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//a[contains(., 'Schedule Now')]")
    )

    graph.action(
        "wait",
        target=5
    )

    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//div[contains(@class, 'ant-select-item ant-select-item-option') and contains(., 'Calendar Conflict')]")
    # )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//button[contains(@class, 'ant-btn') and contains(., 'Skip')]")
    )

    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//input[contains(@class, 'ant-select-selection-search-input')]")
    # )

    graph.action(
        "wait",
        target=5
    )

    graph.action(
        "visit_url",
        target='https://app.slack.com/client/EE8HJA7RS/C097JUKSEQJ'
    )

    graph.action(
        "wait",
        target=5
    )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//div[contains(@class, 'p-channel_sidebar__channel') and contains(., 'goodtime-demo')]")
    )

    graph.action(
        "input_text",
        target=TargetSpec(strategy="xpath", value="//div[contains(@class, 'ql-editor')]"),
        args={"text": "✅ Interview rescheduled for Anakin\n\n• New time: Dec 23, 2025 @ 11:00 AM - 12:00 PM (PST)\n• Previous slot (Dec 19) removed\n• Candidate email notification sent"}
    )

    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//button[contains(@class, 'c-wysiwyg_container__button--send') and contains(@aria-label, 'Send now')]")
    )




    # # Action 3: Click the Google Search button
    # # XPath: find input tag with value='Google Search' (semantic & stable)
    # graph.action(
    #     "click",
    #     target=TargetSpec(strategy="xpath", value="//input[@value='Google Search']")
    # )

    return graph
