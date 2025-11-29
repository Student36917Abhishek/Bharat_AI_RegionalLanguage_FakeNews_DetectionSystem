"""Small GNews API client helper.

Usage:
    from gnews_client import fetch_headlines
    data = fetch_headlines(query='python', token='MY_TOKEN')

The function prefers a passed `token` argument, otherwise reads `GNEWS_API_KEY` from
the environment.
"""
from typing import Optional, Any, Dict
import os
import requests


def fetch_headlines(query: str = 'news', token: Optional[str] = None, *,
                    lang: str = 'en', max_results: int = 10, timeout: int = 10) -> Dict[str, Any]:
    """Fetch search results from gnews.io API.

    Args:
        query: search query string.
        token: API key. If None, will use `GNEWS_API_KEY` env var.
        lang: language code (default 'en').
        max_results: number of results to request (API may cap it).
        timeout: request timeout in seconds.

    Returns:
        Parsed JSON response as a Python dict.

    Raises:
        ValueError: when API key is not provided.
        requests.RequestException: on network/HTTP errors.
    """
    if token is None:
        token = os.getenv('GNEWS_API_KEY')
    if not token:
        raise ValueError('GNEWS API key not provided via token or GNEWS_API_KEY env var')

    params = {
        'q': query,
        'token': token,
        'lang': lang,
        'max': max_results,
    }

    resp = requests.get('https://gnews.io/api/v4/search', params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
