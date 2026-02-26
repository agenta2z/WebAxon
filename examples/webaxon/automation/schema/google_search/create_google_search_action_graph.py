"""Factory function to create an ActionGraph for Google search operations."""

from science_modeling_tools.automation.schema import ActionGraph, TargetSpec
from science_modeling_tools.automation.schema.action_metadata import ActionMetadataRegistry


def create_google_search_action_graph(
    action_executor,
    search_query: str = "test query",
    url: str = "https://www.google.com"
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

    # Action 1: Visit Google homepage
    graph.action(
        "visit_url",
        target=url
    )

    graph.action(
        "wait",
        target=20
    )

    # Action 2: Input text into search textarea
    # XPath: find textarea tag with title='Search' (semantic & stable)
    graph.action(
        "input_text",
        target=TargetSpec(strategy="xpath", value="//textarea[@title='Search']"),
        args={"text": search_query}
    )

    # Action 3: Click the Google Search button
    # XPath: find input tag with value='Google Search' (semantic & stable)
    graph.action(
        "click",
        target=TargetSpec(strategy="xpath", value="//input[@value='Google Search']")
    )

    return graph
