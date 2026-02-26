from typing import Iterable, Optional, Union
from urllib.parse import urlencode, quote_plus
from datetime import datetime, date


def create_search_url(
        query: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sites: Optional[Union[str, Iterable[str]]] = None,
        **other_search_args
) -> str:
    """
    Constructs a Bing search URL with optional date range, multiple site constraints,
    and additional query parameters.

    Args:
        query (str): The main search terms.
        start_date (Optional[str]): The start date in `YYYY-MM-DD` format. Default is None.
        end_date (Optional[str]): The end date in `YYYY-MM-DD` format. Default is None.
        sites (Optional[Union[str, Iterable[str]]]): List of websites to restrict the search to.
            Can be a string consisting of comma-separated list of websites. Default is None.
        **other_search_args: Additional search parameters for the query string.

    Returns:
        str: A Bing search URL with the specified parameters.

    Raises:
        ValueError: If the date format is invalid or if end_date is before start_date.

    Examples:
        >>> create_search_url(
        ...     query="machine learning",
        ...     start_date="2023-01-01",
        ...     end_date="2023-12-31"
        ... )
        'https://www.bing.com/search?q=machine+learning&filters=ex1%3A%22ez5_19358_19722%22'

        >>> create_search_url(
        ...     query="machine learning",
        ...     start_date="2023-01-01"
        ... )
        'https://www.bing.com/search?q=machine+learning&filters=ex1%3A%22ez5_19358_%22'

        >>> create_search_url(
        ...     query="data science",
        ...     end_date="2023-12-31"
        ... )
        'https://www.bing.com/search?q=data+science&filters=ex1%3A%22ez5__19722%22'

        >>> create_search_url(
        ...     query="data science",
        ...     sites=["bbc.com", "nytimes.com"],
        ...     setlang="en"
        ... )
        'https://www.bing.com/search?q=data+science+site%3Abbc.com+OR+site%3Anytimes.com&setlang=en'

        >>> create_search_url(
        ...     query="artificial intelligence ethics",
        ...     start_date="2023-06-01",
        ...     end_date="2023-12-31",
        ...     sites=["nature.com", "science.org"],
        ...     form="QBLH"
        ... )
        'https://www.bing.com/search?q=artificial+intelligence+ethics+site%3Anature.com+OR+site%3Ascience.org&filters=ex1%3A%22ez5_19509_19722%22&form=QBLH'
    """
    if not query.strip():
        raise ValueError("Search query cannot be empty")

    # Initialize date variables
    start_epoch = end_epoch = None

    # Validate start_date if provided
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            # Calculate epoch days since 1970-01-01
            BING_BASE_DATE = datetime(1970, 1, 1)
            start_epoch = (start_dt - BING_BASE_DATE).days
        except ValueError:
            raise ValueError("start_date must be in YYYY-MM-DD format")

    # Validate end_date if provided
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            BING_BASE_DATE = datetime(1970, 1, 1)
            end_epoch = (end_dt - BING_BASE_DATE).days
        except ValueError:
            raise ValueError("end_date must be in YYYY-MM-DD format")

    # Check if both dates are provided and end_date is before start_date
    if start_epoch is not None and end_epoch is not None and end_epoch < start_epoch:
        raise ValueError("end_date cannot be earlier than start_date")

    # Base Bing search URL
    base_url = "https://www.bing.com/search"

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

    # Add date range if specified
    if start_epoch is not None or end_epoch is not None:
        # Build the filters parameter
        filter_parts = []
        if start_epoch is not None and end_epoch is not None:
            filter_parts.append(f'ex1:"ez5_{start_epoch}_{end_epoch}"')
        elif start_epoch is not None:
            filter_parts.append(f'ex1:"ez5_{start_epoch}_"')
        elif end_epoch is not None:
            filter_parts.append(f'ex1:"ez5__{end_epoch}"')
        params["filters"] = ' '.join(filter_parts)

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