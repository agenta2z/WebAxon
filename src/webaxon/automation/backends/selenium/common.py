from typing import List, Optional, Tuple, Mapping

from time import sleep
from attr import attrs, attrib
from bs4 import BeautifulSoup
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException
import requests
import fitz
from urllib3.exceptions import ReadTimeoutError


# region page loading & status
def get_ready_state(driver: WebDriver):
    return driver.execute_script("return document.readyState")

def get_single_cookies_dict(driver: WebDriver) -> Mapping:
    selenium_cookies = driver.get_cookies()
    cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
    return cookies


def get_user_agent(driver: WebDriver):
    return driver.execute_script('return navigator.userAgent')


def wait_for_page_loading(driver: WebDriver, timeout: int = 20, additional_wait_time: float = 2.0, ignore_timeout: bool = True):
    """
    Wait for the page to be fully loaded.

    Args:
        timeout: The maximum time to wait for the page to load. Default is 30 seconds.
        additional_wait_time: Additional wait time in seconds after page loading completes.
    """
    try:
        WebDriverWait(driver, timeout).until(
            lambda driver: get_ready_state(driver) == "complete"
        )
    except ReadTimeoutError as timeout_err:
        if ignore_timeout:
            pass
        else:
            raise timeout_err

    if additional_wait_time > 0:
        sleep(additional_wait_time)


def is_element_stale(element: WebElement) -> bool:
    """
    Check if a WebElement reference is stale.

    A stale element is one that is no longer attached to the DOM, typically because:
    - The element was removed and re-added
    - The element was replaced
    - The page refreshed
    - The element's parent was replaced

    Args:
        element: The WebElement to check

    Returns:
        True if the element is stale, False if it's still valid

    Example:
        >>> element = driver.find_element_by_id('my-element')
        >>> driver.refresh()
        >>> is_element_stale(element)
        True
    """
    try:
        # Accessing any property will trigger StaleElementReferenceException if stale
        _ = element.tag_name
        return False
    except StaleElementReferenceException:
        return True


# endregion


# region get html & text
def get_element_html(element: WebElement) -> Optional[str]:
    if element is not None:
        return element.get_attribute("outerHTML")


def get_element_text(element: WebElement) -> Optional[str]:
    """
    Returns the visible text content of the given WebElement.

    Args:
        element (WebElement): The WebElement from which to retrieve the text.

    Returns:
        Optional[str]: The visible text content of the element, or None if the element is None.
    """
    if element is not None:
        return element.text
    return None


def get_pdf_text(
        driver: WebDriver,
        url: str = None,
        wait_after_opening_url: float = 0
):
    """
    Downloads a PDF using an existing Selenium WebDriver session and extracts its text.

    Args:
        driver: Selenium WebDriver instance
        url (str): URL of the PDF

    Returns:
        str: Extracted text from the PDF, or None if an error occurs
    """
    try:
        # Navigate to URL and wait for page load
        if url is not None:
            from .actions import open_url
            open_url(driver, url=url, wait_after_opening_url=wait_after_opening_url)

        # Get cookies from selenium
        cookies = get_single_cookies_dict(driver)

        # Get headers
        headers = {
            'User-Agent': get_user_agent(driver),
            'Accept': 'application/pdf',
            'Referer': driver.current_url
        }

        # Download PDF content
        response = requests.get(url, headers=headers, cookies=cookies)
        response.raise_for_status()

        # Extract text directly from content
        doc = fitz.open(stream=response.content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()

        return text

    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return None


def get_body_html(driver: WebDriver, return_dynamic_contents: bool = True) -> str:
    return (
        driver.execute_script("return document.body.outerHTML")
        if return_dynamic_contents
        else driver.page_source
    )


def get_body_text(driver: WebDriver) -> str:
    """Return the visible text content of the page body via document.body.innerText."""
    return driver.execute_script("return document.body.innerText")



def get_body_html_from_url(
        driver: WebDriver,
        url: str = None,
        initial_wait_after_opening_url: float = 0,
        timeout_for_page_loading: int = 20,
        return_dynamic_contents: bool = True
) -> str:
    from .actions import open_url
    if url:
        open_url(
            driver=driver,
            url=url,
            wait_after_opening_url=initial_wait_after_opening_url
        )
        wait_for_page_loading(driver, timeout_for_page_loading)
    return get_body_html(
        driver=driver,
        return_dynamic_contents=return_dynamic_contents
    )


def get_text(
        driver,
        url: str,
        initial_wait: float = 0,
        timeout_for_page_loading: int = 20,
        id_class_keywords_match_to_remove: List[str] = None,
        id_class_keywords_match_to_keep: List[str] = None,
        return_dynamic_contents: bool = True
):
    html = get_body_html_from_url(
        driver=driver,
        url=url,
        initial_wait_after_opening_url=initial_wait,
        timeout_for_page_loading=timeout_for_page_loading,
        return_dynamic_contents=return_dynamic_contents
    )
    soup = BeautifulSoup(html, 'html.parser')

    def _filter(value):
        return (
                value
                and (
                        id_class_keywords_match_to_keep
                        and any(x in value for x in id_class_keywords_match_to_remove)
                )
                and not
                (
                        id_class_keywords_match_to_keep
                        and any(x in value for x in id_class_keywords_match_to_keep)
                )
        )

    for element in soup.find_all(id=_filter):
        element.decompose()
    for element in soup.find_all(class_=_filter):
        element.decompose()

    return soup.get_text()


# endregion

# region get sizes

@attrs(slots=True)
class ElementDimensionInfo:
    """
    Comprehensive dimension information about a WebElement.

    Attributes:
        width: Total width including borders and scrollbars (same as get_element_size()[0])
        height: Total height including borders and scrollbars (same as get_element_size()[1])
        client_width: Content width (excludes borders/scrollbars)
        client_height: Content height (excludes borders/scrollbars)
        scroll_width: Full scrollable width (includes overflow)
        scroll_height: Full scrollable height (includes overflow)
        is_scrollable_x: True if element can scroll horizontally
        is_scrollable_y: True if element can scroll vertically
        overflow_x: CSS overflowX property value
        overflow_y: CSS overflowY property value
    """
    width: int = attrib()
    height: int = attrib()
    client_width: int = attrib()
    client_height: int = attrib()
    scroll_width: int = attrib()
    scroll_height: int = attrib()
    is_scrollable_x: bool = attrib()
    is_scrollable_y: bool = attrib()
    overflow_x: str = attrib()
    overflow_y: str = attrib()


def get_device_pixel_ratio(driver: WebDriver) -> int:
    return driver.execute_script("return window.devicePixelRatio")


def get_scroll_width(driver: WebDriver) -> int:
    return driver.execute_script("return document.body.parentNode.scrollWidth")


def get_scroll_height(driver: WebDriver) -> int:
    return driver.execute_script("return document.body.parentNode.scrollHeight")


def get_element_dimension_info(driver: WebDriver, element: WebElement) -> ElementDimensionInfo:
    """
    Gets comprehensive dimension information about a WebElement using JavaScript.

    This function retrieves all major dimension properties of an element including
    its total size (width/height), client dimensions (content area), scroll dimensions
    (full scrollable size), and whether it's scrollable.

    Args:
        driver: The Selenium WebDriver instance
        element: The WebElement to measure

    Returns:
        ElementDimensionInfo: Object containing all dimension properties and scrollability info

    Example:
        >>> info = get_element_dimension_info(driver, element)
        >>> if info.is_scrollable_y:
        ...     print(f"Element can scroll {info.scroll_height - info.client_height}px vertically")
    """
    result = driver.execute_script("""
        var element = arguments[0];
        var computedStyle = window.getComputedStyle(element);

        // Get all dimension properties
        var offsetWidth = element.offsetWidth;
        var offsetHeight = element.offsetHeight;
        var clientWidth = element.clientWidth;
        var clientHeight = element.clientHeight;
        var scrollWidth = element.scrollWidth;
        var scrollHeight = element.scrollHeight;
        var overflowX = computedStyle.overflowX;
        var overflowY = computedStyle.overflowY;

        // Determine scrollability (including overflow:hidden for custom scrollers)
        var isScrollableX = (
            (overflowX === 'scroll' || overflowX === 'auto' || overflowX === 'hidden') &&
            scrollWidth > clientWidth
        );
        var isScrollableY = (
            (overflowY === 'scroll' || overflowY === 'auto' || overflowY === 'hidden') &&
            scrollHeight > clientHeight
        );

        return {
            offsetWidth: offsetWidth,
            offsetHeight: offsetHeight,
            clientWidth: clientWidth,
            clientHeight: clientHeight,
            scrollWidth: scrollWidth,
            scrollHeight: scrollHeight,
            isScrollableX: isScrollableX,
            isScrollableY: isScrollableY,
            overflowX: overflowX,
            overflowY: overflowY
        };
    """, element)

    return ElementDimensionInfo(
        width=result['offsetWidth'],
        height=result['offsetHeight'],
        client_width=result['clientWidth'],
        client_height=result['clientHeight'],
        scroll_width=result['scrollWidth'],
        scroll_height=result['scrollHeight'],
        is_scrollable_x=result['isScrollableX'],
        is_scrollable_y=result['isScrollableY'],
        overflow_x=result['overflowX'],
        overflow_y=result['overflowY']
    )


def get_element_scrollability(driver: WebDriver, element: WebElement) -> Tuple[bool, bool]:
    """
    Checks if a WebElement is scrollable in the horizontal and/or vertical directions.

    This is a lightweight function that only checks scrollability without retrieving
    full dimension information. For comprehensive dimension info including scrollability,
    use get_element_dimension_info() instead.

    Args:
        driver: The Selenium WebDriver instance
        element: The WebElement to check

    Returns:
        Tuple[bool, bool]: (is_scrollable_x, is_scrollable_y)
            - is_scrollable_x: True if element can scroll horizontally
            - is_scrollable_y: True if element can scroll vertically

    Example:
        >>> scrollable_x, scrollable_y = get_element_scrollability(driver, element)
        >>> if scrollable_y:
        ...     print("Element can scroll vertically")
    """
    result = driver.execute_script("""
        var element = arguments[0];
        var computedStyle = window.getComputedStyle(element);

        // Check if scrollable in X direction (including overflow:hidden for custom scrollers)
        var isScrollableX = (
            (computedStyle.overflowX === 'scroll' || computedStyle.overflowX === 'auto' || computedStyle.overflowX === 'hidden') &&
            element.scrollWidth > element.clientWidth
        );

        // Check if scrollable in Y direction (including overflow:hidden for custom scrollers)
        var isScrollableY = (
            (computedStyle.overflowY === 'scroll' || computedStyle.overflowY === 'auto' || computedStyle.overflowY === 'hidden') &&
            element.scrollHeight > element.clientHeight
        );

        return {
            isScrollableX: isScrollableX,
            isScrollableY: isScrollableY
        };
    """, element)

    return result['isScrollableX'], result['isScrollableY']


def _solve_scrollable_child_javascript(
        driver: WebDriver,
        element: WebElement,
        strategy: str = 'first_largest_scrollable',
        direction: Optional[str] = None
) -> WebElement:
    """
    Finds the actual scrollable child element using JavaScript implementation.

    Args:
        driver: The Selenium WebDriver instance
        element: The parent element to search within
        strategy: The search strategy to use
        direction: Optional scroll direction to filter by

    Returns:
        WebElement: The scrollable child element if found, otherwise returns the original element
    """
    # Determine which direction to check based on direction parameter
    check_x = True
    check_y = True
    if direction is not None:
        direction_normalized = direction.capitalize()
        if direction_normalized in ['Up', 'Down']:
            check_x = False  # Only check Y
        elif direction_normalized in ['Left', 'Right']:
            check_y = False  # Only check X

    # Common helper functions
    has_scrollable_y_check = "element.scrollHeight > element.clientHeight" if check_y else "false"
    has_scrollable_x_check = "element.scrollWidth > element.clientWidth" if check_x else "false"

    js_common = f"""
        function isScrollable(element) {{
            var hasScrollableY = {has_scrollable_y_check};
            var hasScrollableX = {has_scrollable_x_check};
            return hasScrollableY || hasScrollableX;
        }}

        function getScrollableArea(element) {{
            var verticalScroll = Math.max(0, element.scrollHeight - element.clientHeight);
            var horizontalScroll = Math.max(0, element.scrollWidth - element.clientWidth);
            return verticalScroll + horizontalScroll;
        }}

        function getElementSize(element) {{
            return element.clientHeight * element.clientWidth;
        }}

        var rootElement = arguments[0];
    """

    # Strategy-specific implementations
    if strategy == 'first_scrollable':
        js_strategy = """
            var queue = [rootElement];
            while (queue.length > 0) {
                var current = queue.shift();
                if (isScrollable(current)) {
                    return current;
                }
                for (var i = 0; i < current.children.length; i++) {
                    queue.push(current.children[i]);
                }
            }
            return null;
        """
    elif strategy == 'first_largest_scrollable':
        js_strategy = """
            var queue = [[rootElement]]; // Queue of levels
            while (queue.length > 0) {
                var currentLevel = queue.shift();
                var scrollableAtLevel = [];
                var nextLevel = [];

                // Check all elements at current level
                for (var i = 0; i < currentLevel.length; i++) {
                    var elem = currentLevel[i];
                    if (isScrollable(elem)) {
                        scrollableAtLevel.push(elem);
                    }
                    // Collect children for next level
                    for (var j = 0; j < elem.children.length; j++) {
                        nextLevel.push(elem.children[j]);
                    }
                }

                // If found scrollable elements at this level, return the largest one
                if (scrollableAtLevel.length > 0) {
                    var largest = scrollableAtLevel[0];
                    var largestSize = getElementSize(largest);
                    for (var k = 1; k < scrollableAtLevel.length; k++) {
                        var size = getElementSize(scrollableAtLevel[k]);
                        if (size > largestSize) {
                            largest = scrollableAtLevel[k];
                            largestSize = size;
                        }
                    }
                    return largest;
                }

                // Add next level to queue
                if (nextLevel.length > 0) {
                    queue.push(nextLevel);
                }
            }
            return null;
        """
    elif strategy == 'deepest_scrollable':
        js_strategy = """
            var deepest = null;
            var maxDepth = -1;

            function dfs(element, depth) {
                if (isScrollable(element)) {
                    if (depth > maxDepth) {
                        deepest = element;
                        maxDepth = depth;
                    }
                }
                for (var i = 0; i < element.children.length; i++) {
                    dfs(element.children[i], depth + 1);
                }
            }

            dfs(rootElement, 0);
            return deepest;
        """
    elif strategy == 'largest_scrollable':
        js_strategy = """
            var largest = null;
            var maxScrollableArea = 0;

            function traverse(element) {
                if (isScrollable(element)) {
                    var area = getScrollableArea(element);
                    if (area > maxScrollableArea) {
                        largest = element;
                        maxScrollableArea = area;
                    }
                }
                for (var i = 0; i < element.children.length; i++) {
                    traverse(element.children[i]);
                }
            }

            traverse(rootElement);
            return largest;
        """
    elif strategy == 'largest_scrollable_early_stop':
        js_strategy = """
            var queue = [[rootElement]]; // Queue of levels

            while (queue.length > 0) {
                var currentLevel = queue.shift();
                var scrollableAtLevel = [];
                var nextLevel = [];

                // Check all elements at current level
                for (var i = 0; i < currentLevel.length; i++) {
                    var elem = currentLevel[i];
                    if (isScrollable(elem)) {
                        scrollableAtLevel.push(elem);
                    }
                    // Collect children for next level
                    for (var j = 0; j < elem.children.length; j++) {
                        nextLevel.push(elem.children[j]);
                    }
                }

                // If found scrollable elements at this level
                if (scrollableAtLevel.length > 0) {
                    // Find the largest scrollable at this level
                    var largest = scrollableAtLevel[0];
                    var largestSize = getElementSize(largest);
                    for (var k = 1; k < scrollableAtLevel.length; k++) {
                        var size = getElementSize(scrollableAtLevel[k]);
                        if (size > largestSize) {
                            largest = scrollableAtLevel[k];
                            largestSize = size;
                        }
                    }

                    // Check if we should early stop
                    // Condition 1: Check if all children are non-scrollable
                    var hasScrollableChildren = false;
                    var largestChildSize = 0;
                    for (var m = 0; m < nextLevel.length; m++) {
                        if (isScrollable(nextLevel[m])) {
                            hasScrollableChildren = true;
                            var childSize = getElementSize(nextLevel[m]);
                            if (childSize > largestChildSize) {
                                largestChildSize = childSize;
                            }
                        }
                    }

                    // Early stop if: no scrollable children OR current is larger than all scrollable children
                    if (!hasScrollableChildren || largestSize > largestChildSize) {
                        return largest;
                    }
                }

                // Add next level to queue
                if (nextLevel.length > 0) {
                    queue.push(nextLevel);
                }
            }

            return null;
        """
    else:
        raise ValueError(
            f"Invalid strategy '{strategy}'. Must be one of: "
            f"'first_scrollable', 'first_largest_scrollable', 'deepest_scrollable', "
            f"'largest_scrollable', 'largest_scrollable_early_stop'"
        )

    # Combine common code with strategy-specific code
    js_code = js_common + js_strategy
    result = driver.execute_script(js_code, element)

    # Return the scrollable child if found, otherwise return original element
    return result if result is not None else element


def _solve_scrollable_child_builtin(
        driver: WebDriver,
        element: WebElement,
        strategy: str = 'first_largest_scrollable',
        direction: Optional[str] = None
) -> WebElement:
    """
    Finds the actual scrollable child element using Selenium's builtin methods.

    Args:
        driver: The Selenium WebDriver instance
        element: The parent element to search within
        strategy: The search strategy to use
        direction: Optional scroll direction to filter by

    Returns:
        WebElement: The scrollable child element if found, otherwise returns the original element
    """
    from selenium.webdriver.common.by import By

    def get_children(elem: WebElement) -> List[WebElement]:
        """Get direct children of element"""
        try:
            return elem.find_elements(By.XPATH, './*')
        except:
            return []

    def is_scrollable_in_direction(info: ElementDimensionInfo) -> bool:
        """Check if element is scrollable in the specified direction"""
        if direction is None:
            # No specific direction, check any direction
            return info.is_scrollable_x or info.is_scrollable_y
        else:
            direction_normalized = direction.capitalize()
            if direction_normalized in ['Up', 'Down']:
                return info.is_scrollable_y
            elif direction_normalized in ['Left', 'Right']:
                return info.is_scrollable_x
            else:
                return info.is_scrollable_x or info.is_scrollable_y

    # Strategy: first_scrollable (BFS)
    if strategy == 'first_scrollable':
        queue = [element]
        while queue:
            current = queue.pop(0)
            info = get_element_dimension_info(driver, current)
            if is_scrollable_in_direction(info):
                return current
            queue.extend(get_children(current))
        return element

    # Strategy: first_largest_scrollable (BFS with level-wise selection)
    elif strategy == 'first_largest_scrollable':
        queue = [[element]]  # Queue of levels
        while queue:
            current_level = queue.pop(0)
            scrollable_at_level = []
            next_level = []

            for elem in current_level:
                info = get_element_dimension_info(driver, elem)
                if is_scrollable_in_direction(info):
                    scrollable_at_level.append((elem, info))
                next_level.extend(get_children(elem))

            # If found scrollable elements at this level, return the largest one
            if scrollable_at_level:
                largest = max(scrollable_at_level, key=lambda x: x[1].width * x[1].height)
                return largest[0]

            # Add next level to queue
            if next_level:
                queue.append(next_level)

        return element

    # Strategy: deepest_scrollable (DFS)
    elif strategy == 'deepest_scrollable':
        deepest = None
        max_depth = -1

        def dfs(elem: WebElement, depth: int):
            nonlocal deepest, max_depth
            info = get_element_dimension_info(driver, elem)
            if is_scrollable_in_direction(info):
                if depth > max_depth:
                    deepest = elem
                    max_depth = depth
            for child in get_children(elem):
                dfs(child, depth + 1)

        dfs(element, 0)
        return deepest if deepest is not None else element

    # Strategy: largest_scrollable
    elif strategy == 'largest_scrollable':
        largest = None
        max_scrollable_area = 0

        def traverse(elem: WebElement):
            nonlocal largest, max_scrollable_area
            info = get_element_dimension_info(driver, elem)
            if is_scrollable_in_direction(info):
                area = max(0, info.scroll_height - info.client_height) + max(0, info.scroll_width - info.client_width)
                if area > max_scrollable_area:
                    largest = elem
                    max_scrollable_area = area
            for child in get_children(elem):
                traverse(child)

        traverse(element)
        return largest if largest is not None else element

    # Strategy: largest_scrollable_early_stop
    elif strategy == 'largest_scrollable_early_stop':
        queue = [[element]]  # Queue of levels

        while queue:
            current_level = queue.pop(0)
            scrollable_at_level = []
            next_level = []

            for elem in current_level:
                info = get_element_dimension_info(driver, elem)
                if is_scrollable_in_direction(info):
                    scrollable_at_level.append((elem, info))
                next_level.extend(get_children(elem))

            # If found scrollable elements at this level
            if scrollable_at_level:
                # Find the largest scrollable at this level
                largest_elem, largest_info = max(scrollable_at_level, key=lambda x: x[1].width * x[1].height)
                largest_size = largest_info.width * largest_info.height

                # Check if we should early stop
                scrollable_children = []
                for e in next_level:
                    info = get_element_dimension_info(driver, e)
                    if is_scrollable_in_direction(info):
                        scrollable_children.append((e, info))

                if not scrollable_children:
                    return largest_elem

                largest_child_size = max((info.width * info.height for _, info in scrollable_children), default=0)
                if largest_size > largest_child_size:
                    return largest_elem

            # Add next level to queue
            if next_level:
                queue.append(next_level)

        return element

    else:
        raise ValueError(
            f"Invalid strategy '{strategy}'. Must be one of: "
            f"'first_scrollable', 'first_largest_scrollable', 'deepest_scrollable', "
            f"'largest_scrollable', 'largest_scrollable_early_stop'"
        )


def solve_scrollable_child(
        driver: WebDriver,
        element: WebElement,
        strategy: str = 'first_largest_scrollable',
        implementation: str = 'builtin',
        direction: Optional[str] = None
) -> WebElement:
    """
    Finds the actual scrollable child element within an element hierarchy.

    This is useful for container elements that are not themselves scrollable but contain
    a nested scrollable element (e.g., Slack's virtual lists with c-scrollbar__child).

    Args:
        driver: The Selenium WebDriver instance
        element: The parent element to search within
        strategy: The search strategy to use:
            - 'first_scrollable': BFS, return first scrollable element found
            - 'first_largest_scrollable': BFS, at each level if multiple scrollable children exist,
                                         return the largest one and stop (default)
            - 'deepest_scrollable': Return the scrollable element that's most deeply nested
            - 'largest_scrollable': Return element with largest scrollable content area
            - 'largest_scrollable_early_stop': BFS, return largest scrollable when it's larger than
                                               all scrollable children or when all children are non-scrollable
        implementation: Implementation method:
            - 'builtin': Uses Selenium's builtin methods with get_element_dimension_info() (default)
            - 'javascript': Uses pure JavaScript for faster execution
        direction: Optional scroll direction to check scrollability for:
            - None: Element needs to be scrollable in at least one direction (X or Y) (default)
            - 'Up'/'Down': Element needs to be scrollable in Y direction
            - 'Left'/'Right': Element needs to be scrollable in X direction

    Returns:
        WebElement: The scrollable child element if found, otherwise returns the original element

    Example:
        >>> container = driver.find_element_by_class_name('c-virtual_list')
        >>> scrollable = solve_scrollable_child(driver, container, strategy='deepest_scrollable', direction='Down')
        >>> # scrollable now points to the actual scrollable child
    """
    import warnings

    # Check if element is already scrollable
    scrollable_x, scrollable_y = get_element_scrollability(driver, element)

    # Determine if element is scrollable based on direction
    is_already_scrollable = False
    if direction is None:
        # No specific direction, needs at least one direction scrollable
        is_already_scrollable = scrollable_x or scrollable_y
    else:
        # Specific direction provided
        direction_normalized = direction.capitalize()
        if direction_normalized in ['Up', 'Down']:
            is_already_scrollable = scrollable_y
        elif direction_normalized in ['Left', 'Right']:
            is_already_scrollable = scrollable_x

    if is_already_scrollable:
        return element

    # Element is not scrollable in the specified direction, try to find scrollable child
    if implementation == 'builtin':
        result = _solve_scrollable_child_builtin(driver, element, strategy, direction)
    elif implementation == 'javascript':
        result = _solve_scrollable_child_javascript(driver, element, strategy, direction)
    else:
        raise ValueError(f"Invalid implementation '{implementation}'. Must be 'builtin' or 'javascript'")

    # Check if we found a scrollable child or just returned the original element
    if result == element:
        direction_str = f" in direction '{direction}'" if direction else ""
        warnings.warn(
            f"Could not find scrollable child element{direction_str} using strategy '{strategy}'. "
            f"Returning original non-scrollable element.",
            UserWarning
        )

    return result


def get_element_size(
        element: WebElement,
        driver: Optional[WebDriver] = None,
        implementation: str = 'builtin'
) -> Tuple[int, int]:
    """
    Gets the width and height of the given WebElement.

    Args:
        element: The WebElement to measure
        driver: The Selenium WebDriver instance (required when implementation='javascript')
        implementation: Method to get element size:
            - 'builtin' (default): Uses Selenium's element.size (returns offsetWidth/offsetHeight)
            - 'javascript': Uses JavaScript to get clientWidth/clientHeight (content area only)

    Returns:
        Tuple[int, int]: (width, height) of the element

    Raises:
        ValueError: If implementation='javascript' but driver is not provided

    Examples:
        >>> # Get element size using built-in Selenium (includes borders/scrollbars)
        >>> width, height = get_element_size(element)
        >>>
        >>> # Get element content size using JavaScript (excludes borders/scrollbars)
        >>> width, height = get_element_size(element, driver, implementation='javascript')
    """
    if implementation == 'builtin':
        size = element.size
        return size['width'], size['height']
    elif implementation == 'javascript':
        if driver is None:
            raise ValueError("driver parameter is required when implementation='javascript'")

        result = driver.execute_script("""
            var element = arguments[0];
            return {
                width: element.clientWidth,
                height: element.clientHeight
            };
        """, element)
        return result['width'], result['height']
    else:
        raise ValueError(f"Invalid implementation '{implementation}'. Must be 'builtin' or 'javascript'")


def scroll_element_into_view(
    driver: WebDriver,
    element: WebElement,
    vertical: str = 'center',
    horizontal: str = 'center',
    behavior: str = 'smooth'
) -> None:
    """
    Scrolls the element into view with flexible alignment options.

    This function uses the browser's native scrollIntoView() API to scroll
    the element into the viewport. The scrolling happens on all scrollable
    ancestor containers as needed.

    Args:
        driver (WebDriver): The Selenium WebDriver instance.
        element (WebElement): The element to scroll into view.
        vertical (str): Vertical alignment. Options:
            - 'top': Align element top with viewport top
            - 'center': Center element vertically (default)
            - 'bottom': Align element bottom with viewport bottom
            - 'nearest': Minimal scrolling, only if not visible
        horizontal (str): Horizontal alignment. Options:
            - 'left': Align element left with viewport left
            - 'center': Center element horizontally (default)
            - 'right': Align element right with viewport right
            - 'nearest': Minimal scrolling, only if not visible
        behavior (str): Scroll behavior. Options:
            - 'smooth': Smooth animated scrolling (default)
            - 'auto': Instant scrolling

    Raises:
        ValueError: If any parameter value is invalid.

    Examples:
        >>> # Scroll element to top of viewport
        >>> scroll_element_into_view(driver, element, vertical='top')

        >>> # Scroll with minimal movement (only if not visible)
        >>> scroll_element_into_view(driver, element, vertical='nearest', horizontal='nearest')

        >>> # Scroll to bottom-right with instant behavior
        >>> scroll_element_into_view(driver, element, vertical='bottom', horizontal='right', behavior='auto')
    """
    # Validate parameters
    valid_vertical = ['top', 'center', 'bottom', 'nearest']
    valid_horizontal = ['left', 'center', 'right', 'nearest']
    valid_behavior = ['smooth', 'auto']

    if vertical not in valid_vertical:
        raise ValueError(f"Invalid vertical alignment '{vertical}'. Must be one of: {', '.join(valid_vertical)}")

    if horizontal not in valid_horizontal:
        raise ValueError(f"Invalid horizontal alignment '{horizontal}'. Must be one of: {', '.join(valid_horizontal)}")

    if behavior not in valid_behavior:
        raise ValueError(f"Invalid behavior '{behavior}'. Must be one of: {', '.join(valid_behavior)}")

    # Map user-friendly values to scrollIntoView API values
    vertical_map = {
        'top': 'start',
        'center': 'center',
        'bottom': 'end',
        'nearest': 'nearest'
    }

    horizontal_map = {
        'left': 'start',
        'center': 'center',
        'right': 'end',
        'nearest': 'nearest'
    }

    block_value = vertical_map[vertical]
    inline_value = horizontal_map[horizontal]

    # Execute scrollIntoView with specified options
    driver.execute_script("""
        var element = arguments[0];
        var block = arguments[1];
        var inline = arguments[2];
        var behavior = arguments[3];

        element.scrollIntoView({
            block: block,
            inline: inline,
            behavior: behavior
        });
    """, element, block_value, inline_value, behavior)

# endregion
