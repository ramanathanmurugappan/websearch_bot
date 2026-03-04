"""websearch_bot — one function to search, scrape, or fetch anything.

Auto-detects what to do from the input:

* **Plain text query** → DuckDuckGo search, scrapes top results.
* **Single URL** → GitHub REST API (for repo URLs) or headless browser.
* **List of URLs** → parallel batch scrape, results combined.

Quickstart::

    from websearch_bot import search_web

    # Plain text → DDG search + scrape
    text = search_web("how to install crawl4ai", max_results=5)

    # Single URL → auto-routed scraper
    text = search_web("https://docs.python.org/3/")

    # GitHub repo → REST API scraper
    text = search_web("https://github.com/owner/repo")

    # List of URLs → parallel batch scrape
    text = search_web(["https://example.com", "https://github.com/owner/repo"])

Environment variables::

    GROQ_API_KEY          — enables LLM compression and AI overviews (Groq free tier)
    WEBSEARCH_LLM_MODEL   — override the primary LLM (litellm model string)
    GITHUB_TOKEN          — raises GitHub API rate limit from 60 → 5 000 req/hr
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from ._llm import MAX_CHARS
from ._crawl import scrape_website as _scrape_one, scrape_many as _scrape_many
from ._github import scrape_github as _scrape_github
from ._search import _ddg_search

__version__ = "0.1.0"
__all__ = ["search_web", "MAX_CHARS", "__version__"]

_GITHUB_RE = re.compile(r"https?://github\.com/[^/]+/[^/?#]+(?:\.git)?/?$")


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _is_github(url: str) -> bool:
    return bool(_GITHUB_RE.match(url))


def _scrape_list(urls: list[str], max_chars: int) -> str:
    github_urls = [u for u in urls if _is_github(u)]
    web_urls    = [u for u in urls if not _is_github(u)]

    parts: list[str] = []

    if github_urls:
        with ThreadPoolExecutor(max_workers=len(github_urls)) as pool:
            futures = [pool.submit(_scrape_github, u, max_chars=max_chars) for u in github_urls]
            parts += [r for f in futures if (r := f.result())]

    if web_urls:
        result = _scrape_many(web_urls, max_chars=max_chars)
        if result:
            parts.append(result)

    return "\n\n".join(parts)


def search_web(
    query: str | list[str],
    max_results: int = 5,
    max_pages: int = 5,
    max_depth: int = 1,
    keywords: list[str] | None = None,
    max_chars: int = MAX_CHARS,
) -> str:
    """Search, scrape, or fetch — one function for everything.

    Auto-detects what to do based on *query*:

    * **Plain text** (e.g. ``"python asyncio tutorial"``) → DuckDuckGo search,
      scrapes the top *max_results* pages and returns combined Markdown.
    * **Single URL** (starts with ``http://`` or ``https://``) → scrapes that
      URL; GitHub repo URLs use the REST API, all others use the headless browser.
    * **List of URLs** → scrapes all URLs in parallel, results combined.

    Args:
        query: Search query string, single URL, or list of URLs.
        max_results: How many DDG candidates to fetch; LLM picks the best 3 to scrape.
        max_pages: Max pages to crawl per site (single-URL deep crawl only).
        max_depth: Max link depth from seed URL (single-URL deep crawl only).
        keywords: Relevance filter for BestFirst crawl (single-URL only).
        max_chars: Character budget; content over limit is LLM-compressed.

    Returns:
        Context-engineered Markdown document, or ``""`` on complete failure.

    Example:
        >>> text = search_web("python asyncio tutorial")
        >>> text = search_web("https://example.com")
        >>> text = search_web(["https://a.com", "https://github.com/x/y"])
    """
    if isinstance(query, list):
        return _scrape_list(query, max_chars)

    if _is_url(query):
        if _is_github(query):
            return _scrape_github(query, max_chars=max_chars)
        return _scrape_one(
            query,
            max_pages=max_pages,
            max_depth=max_depth,
            keywords=keywords,
            max_chars=max_chars,
        )

    return _ddg_search(query, max_results=max_results, max_chars=max_chars)
