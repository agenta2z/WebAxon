"""HTML tag sanitization for action history cleaning.

Copied from _dev/external/evaluation_framework/evaluators/online_mind2web/src/clean_html.py
"""

from typing import Iterable

from bs4 import BeautifulSoup

SALIENT_ATTRIBUTES = (
    "alt",
    "aria-describedby",
    "aria-label",
    "aria-role",
    "aria-controls",
    "input-checked",
    "label",
    "name",
    "option_selected",
    "placeholder",
    "readonly",
    "text-value",
    "title",
    "value",
    "data-gtm-label",
    "href",
    "role",
)


def process_element_tag(element: str, salient_attributes: Iterable[str]) -> str:
    if not element.endswith(">"):
        element += "'>"

    soup = BeautifulSoup(element, "html.parser")
    for tag in soup.find_all(True):
        # Keep only salient attributes
        filtered_attrs = {k: tag.attrs[k] for k in tag.attrs if k in salient_attributes}
        name_val = filtered_attrs.pop("name", None)
        new_tag = soup.new_tag(tag.name, **filtered_attrs)
        if name_val:
            new_tag["name"] = name_val
        return str(new_tag).split(f"</{tag.name}>")[0]
    return element
