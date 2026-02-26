"""
Web-specific normalizer configuration for the Meta Agent Workflow pipeline.

Contains action type mappings from WebAgent-internal action type strings
to canonical ActionGraph action type strings.
"""

from __future__ import annotations

from typing import Dict

WEB_ACTION_TYPE_MAP: Dict[str, str] = {
    "ElementInteraction.Click": "click",
    "ElementInteraction.InputText": "input_text",
    "ElementInteraction.AppendText": "append_text",
    "ElementInteraction.Scroll": "scroll",
    "ElementInteraction.ScrollUpToElement": "scroll_up_to_element",
    "ElementInteraction.InputAndSubmit": "input_and_submit",
    "UserInputsRequired": "wait",
}
