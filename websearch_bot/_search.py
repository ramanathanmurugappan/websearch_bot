"""Web search — DuckDuckGo query → LLM URL selection → crawl4ai scrape pipeline.

Takes a free-text query, discovers up to 10 URLs via DuckDuckGo, delegates URL
ranking to :func:`~websearch_bot._select.select_urls`, then scrapes the chosen
pages with crawl4ai.

Environment:
    GROQ_API_KEY: Optional.  Enables LLM URL selection and compression.
        Without it, falls back to the top-3 DDG results.

Example:
    >>> from websearch_bot._search import _ddg_search
    >>> text = _ddg_search("how to install crawl4ai")
"""

from __future__ import annotations

from ._crawl import scrape_many
from ._llm import MAX_CHARS
from ._select import select_urls

__all__: list[str] = []

# How many results to fetch from DDG before LLM selection.
_DDG_FETCH = 10


def _ddg_search(
    query: str,
    max_results: int = _DDG_FETCH,
    max_chars: int = MAX_CHARS,
) -> str:
    """Search DuckDuckGo, pick top URLs with an LLM, and scrape them.

    Fetches up to *max_results* candidates from DuckDuckGo, then uses an LLM
    with structured Pydantic output to select the most relevant pages before
    scraping.

    Args:
        query: Free-text search query.
        max_results: How many DDG results to fetch as candidates.
        max_chars: Character budget for the combined output.

    Returns:
        A context-engineered Markdown document, or ``""`` on failure.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        raise ImportError(
            "ddgs is required for search_web. "
            "Install it with: pip install 'websearch-bot[search]'"
        ) from None

    # 1. Fetch candidate results from DuckDuckGo.
    try:
        results = list(DDGS().text(query, max_results=max_results))
    except Exception:
        return ""

    results = [r for r in results if r.get("href")]
    if not results:
        return ""

    # 2. Use LLM structured output to pick the most relevant URLs.
    urls = select_urls(query, results)

    # 3. Scrape selected URLs in parallel.
    return scrape_many(urls, max_chars=max_chars)
