from typing import Iterable, Optional, Union
from urllib.parse import urlencode, quote_plus
from datetime import datetime


def create_search_url(
        query: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sites: Optional[Union[str, Iterable[str]]] = None,
        **other_search_args
) -> str:
    """
    Constructs a Google search URL with optional date range, multiple site constraints,
    and additional query parameters.

    Args:
        query (str): The main search terms.
        start_date (Optional[str]): The start date in `YYYY-MM-DD` format. Default is None.
        end_date (Optional[str]): The end date in `YYYY-MM-DD` format. Default is None.
        sites (Optional[Union[str, Iterable[str]]]): List of websites to restrict the search to.
            Can be a string consisting of comma-separated list of websites. Default is None.
        **other_search_args: Additional search parameters for the query string.

    Returns:
        str: A Google search URL with the specified parameters.

    Raises:
        ValueError: If the date format is invalid or if end_date is before start_date.

    Examples:
        >>> create_search_url(
        ...     query="machine learning",
        ...     start_date="2023-01-01",
        ...     end_date="2023-12-31"
        ... )
        'https://www.google.com/search?q=machine+learning&tbs=cdr%3A1%2Ccd_min%3A1%2F1%2F2023%2Ccd_max%3A12%2F31%2F2023'

        >>> create_search_url(
        ...     query="machine learning",
        ...     start_date="2023-01-01"
        ... )
        'https://www.google.com/search?q=machine+learning&tbs=cdr%3A1%2Ccd_min%3A1%2F1%2F2023'

        >>> create_search_url(
        ...     query="data science",
        ...     end_date="2023-12-31"
        ... )
        'https://www.google.com/search?q=data+science&tbs=cdr%3A1%2Ccd_max%3A12%2F31%2F2023'

        >>> create_search_url(
        ...     query="data science",
        ...     sites=["bbc.com", "nytimes.com"],
        ...     safe="active"
        ... )
        'https://www.google.com/search?q=data+science+site%3Abbc.com+OR+site%3Anytimes.com&safe=active'

        >>> create_search_url(
        ...     query="artificial intelligence ethics",
        ...     start_date="2023-06-01",
        ...     end_date="2023-12-31",
        ...     sites=["nature.com", "science.org", "acm.org"],
        ...     hl="en"
        ... )
        'https://www.google.com/search?q=artificial+intelligence+ethics+site%3Anature.com+OR+site%3Ascience.org+OR+site%3Aacm.org&tbs=cdr%3A1%2Ccd_min%3A6%2F1%2F2023%2Ccd_max%3A12%2F31%2F2023&hl=en'
    """
    # Validate input parameters
    if not query.strip():
        raise ValueError("Search query cannot be empty")

    # Validate dates if provided
    start = end = None
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("start_date must be in YYYY-MM-DD format")
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("end_date must be in YYYY-MM-DD format")

    if start and end and end < start:
        raise ValueError("end_date cannot be earlier than start_date")

    # Base Google search URL
    base_url = "https://www.google.com/search"

    # Build the main query string
    search_query = query.strip()

    # Add site restrictions if specified
    if sites:
        if isinstance(sites, str):
            sites = sites.split(',')
        # Filter out empty sites and strip whitespace
        valid_sites = [site.strip() for site in sites if site.strip()]
        if valid_sites:
            # Join multiple sites with the OR operator
            site_query = " OR ".join([f"site:{site}" for site in valid_sites])
            search_query += f" {site_query}"

    # Construct URL parameters
    params = {
        "q": search_query
    }

    # Add date range if specified using the proper tbs format (M/D/YYYY)
    if start or end:
        tbs_parts = ["cdr:1"]
        if start:
            formatted_start = f"{start.month}/{start.day}/{start.year}"
            tbs_parts.append(f"cd_min:{formatted_start}")
        if end:
            formatted_end = f"{end.month}/{end.day}/{end.year}"
            tbs_parts.append(f"cd_max:{formatted_end}")
        params["tbs"] = ",".join(tbs_parts)

    # Include any other custom search arguments provided
    if other_search_args:
        # Filter out None values and strip string values
        cleaned_args = {
            k: v.strip() if isinstance(v, str) else v
            for k, v in other_search_args.items()
            if v is not None
        }
        params.update(cleaned_args)

    # Construct the full URL with properly encoded query parameters
    return f"{base_url}?{urlencode(params, quote_via=quote_plus)}"