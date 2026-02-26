from os import path

from rich_python_utils.common_utils.arg_utils.arg_parse import get_parsed_args
from rich_python_utils.io_utils.text_io import write_all_text, read_all_text
from rich_python_utils.path_utils.common import resolve_path, sanitize_filename
from rich_python_utils.string_utils import remove_any_prefix, add_suffix
from webaxon.html_utils.sanitization import DEFAULT_HTML_CLEAN_TAGS_TO_KEEP, DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE, \
    DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP, clean_html
from webaxon.html_utils.element_identification import ATTR_NAME_INCREMENTAL_ID

args = get_parsed_args(
    default_input_path='input/rovo.html',
    # default_url='https://lifeboostcoffee.com/blogs/lifeboost/25-best-starbucks-chocolate-drinks-to-try-including-secret-menu-items?srsltid=AfmBOopwF-v9ecNmIK1lMDk0r__Uk2qU3tN1AjA8tEfXDarUE-qKm0aO',
    default_output_path='output'
)

# region STEP1: resolve arguments
input_path = args.input_path
if input_path:
    resolved_input_path = resolve_path(
        input_path, 'input_path', __file__
    )
    output_filename = path.basename(resolved_input_path)
    load_from_file = True
else:
    url = args.url
    if not url:
        raise ValueError("At least one of 'input_path' or 'url' is required")
    url_prefixes = ('http://', 'https://')
    url, url_prefix_index = remove_any_prefix(url, url_prefixes, return_match_index=True)
    output_filename = sanitize_filename(url, for_url=True, max_filename_size=128)
    if url_prefix_index != -1:
        url = url_prefixes[url_prefix_index] + url
    else:
        url = url_prefixes[0] + url
    load_from_file = False

output_path = path.join(
    resolve_path(
        args.output_path, 'output_path', __file__
    ),
    add_suffix(output_filename, '.html')
)
# endregion

if load_from_file:
    page_html = read_all_text(input_path, encoding='utf-8')
else:
    from webaxon.automation.web_driver import WebDriver

    driver = WebDriver(headless=False)
    page_html = driver.get_body_html_from_url(url)

page_html_added_universal_id = page_html
# page_html_added_universal_id = add_unique_index_to_html(page_html, index_name=ATTR_NAME_INCREMENTAL_ID)

cleaned_page_html = clean_html(
    page_html_added_universal_id,
    tags_to_always_remove=DEFAULT_HTML_CLEAN_TAGS_TO_ALWAYS_REMOVE,
    tags_to_keep=DEFAULT_HTML_CLEAN_TAGS_TO_KEEP,
    attributes_to_keep=(
        *DEFAULT_HTML_CLEAN_ATTRIBUTES_TO_KEEP,
        ATTR_NAME_INCREMENTAL_ID
    ),
    keep_elements_with_immediate_text=True,
    keep_only_incremental_change=False,
    html_content_to_compare=None,
    consider_text_for_comparison=False,
    keep_all_text_in_hierarchy_for_incremental_change=True,
    ignore_attrs_for_comparison=(ATTR_NAME_INCREMENTAL_ID,),
    collapse_non_interactive_tags=False,
    collapse_non_interactive_tags_merge_attributes_exclusion=(ATTR_NAME_INCREMENTAL_ID, )
)
write_all_text(cleaned_page_html, output_path, encoding='utf-8')
