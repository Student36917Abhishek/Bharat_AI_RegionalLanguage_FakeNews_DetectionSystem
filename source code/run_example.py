"""Example runner that calls the GNews client and prints results.

It prefers `GNEWS_API_KEY` env var. If not set, it will fall back to the key
you provided in the prompt for quick testing. For production, set env var.
"""
import os
from pprint import pprint
from gnews_client import fetch_headlines


DEFAULT_FALLBACK_KEY = "27e168eef0cf8765a7b0c552eacd30e3"


def main():
    token = os.getenv('GNEWS_API_KEY') or DEFAULT_FALLBACK_KEY
    try:
        data = fetch_headlines(query='openai', token=token, max_results=5)
    except Exception as e:
        print('Error fetching headlines:', e)
        return

    pprint(data)


if __name__ == '__main__':
    main()
