"""Web search — DuckDuckGo query → crawl4ai scrape pipeline.

Takes a free-text query, discovers relevant URLs via the DuckDuckGo search
API (no API key required), scrapes each URL with crawl4ai, and returns a
single context-engineered Markdown document.

Environment:
    GROQ_API_KEY: Optional.  Enables LLM compression and AI overviews via the
        Groq free tier when the combined content exceeds ``max_chars``.

Example:
    >>> from websearch_bot._search import search_web
    >>> text = search_web("how to install crawl4ai")
"""

from __future__ import annotations

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, SemaphoreDispatcher
from crawl4ai.cache_context import CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy

from ._crawl import _BROWSER, _extract_markdown, _run_sync, finalize
from ._llm import MAX_CHARS

__all__ = ["search_web"]

# CrawlerRunConfig tuned for search result pages:
# - CacheMode.BYPASS  — always fetch fresh content (search results must be current)
# - excluded_tags intentionally minimal — aggressive tag exclusion strips content
#   from SPAs and docs sites that render inside nav/header-like containers
_SEARCH_CONFIG = dict(
    cache_mode=CacheMode.BYPASS,
    word_count_threshold=10,
    excluded_tags=["script", "style"],
    remove_overlay_elements=True,
    exclude_social_media_links=True,
    markdown_generator=DefaultMarkdownGenerator(options={"body_width": 0}),
    scraping_strategy=LXMLWebScrapingStrategy(),
    wait_until="networkidle",
    page_timeout=30_000,
    wait_for_images=False,
    verbose=False,
)


async def _async_search_many(urls: list[str], config: CrawlerRunConfig) -> str:
    """Crawl search-result URLs in parallel (up to 5 concurrent sessions).

    Each URL's content is wrapped in a ``## Source: <url>`` section.
    """
    async with AsyncWebCrawler(config=_BROWSER) as crawler:
        results = await crawler.arun_many(
            urls, config=config,
            dispatcher=SemaphoreDispatcher(max_session_permit=5),
        )
        parts = []
        for r in results:
            text = _extract_markdown(r)
            if r.success and text.strip():
                parts.append(f"## Source: {r.url}\n\n{text}")
        return "\n\n---\n\n".join(parts)


def search_web(
    query: str,
    max_results: int = 5,
    max_chars: int = MAX_CHARS,
) -> str:
    """Search DuckDuckGo for *query* and scrape the top results.

    Discovers up to *max_results* URLs via the DuckDuckGo search API (free,
    no API key), scrapes them in parallel using crawl4ai, and returns a single
    context-engineered Markdown document combining all results.

    Args:
        query: Free-text search query (e.g. ``"crawl4ai installation guide"``).
        max_results: Maximum number of search result URLs to scrape.
        max_chars: Character budget for the combined output.  Content over this
            limit is compressed via map-reduce LLM summarisation when a
            ``GROQ_API_KEY`` is available.

    Returns:
        A context-engineered Markdown document (YAML frontmatter + AI overview
        + content from all scraped pages), or ``""`` if the search returns no
        results or all pages fail to scrape.

    Example:
        >>> text = search_web("python asyncio tutorial", max_results=3)
    """
    try:
        from ddgs import DDGS
    except ImportError:
        raise ImportError(
            "ddgs is required for search_web. "
            "Install it with: pip install 'websearch-bot[search]'"
        ) from None

    # 1. Discover URLs from DuckDuckGo (free, no API key).
    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception:
        return ""

    urls = [r["href"] for r in results if r.get("href")]
    if not urls:
        return ""

    # 2. Scrape all URLs in parallel via crawl4ai (cache bypassed for fresh content).
    try:
        raw = _run_sync(
            _async_search_many(urls, CrawlerRunConfig(**_SEARCH_CONFIG))
        )
    except Exception:
        return ""

    # 3. Build metadata and wrap with context engineering.
    meta: dict = {
        "source": "duckduckgo",
        "type": "web_search",
        "query": query,
        "urls": urls,
    }
    return finalize(raw, meta, max_chars)
