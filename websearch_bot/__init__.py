"""websearch_bot — web scraper and search tool for websites and GitHub repositories.

Scrapes content via ``crawl4ai`` (headless Chromium) for regular websites
and via the GitHub REST API for repository URLs.  All results are returned
as context-engineered Markdown with YAML frontmatter, an AI-generated
overview, and optional LLM compression when content exceeds the character
budget.

Quickstart::

    from websearch_bot import scrape_website, search_web

    # Single website — deep crawl up to 5 pages
    text = scrape_website("https://docs.python.org/3/")

    # GitHub repository — auto-detected from URL
    code = scrape_website("https://github.com/owner/repo")

    # Multiple URLs in one call — each routed automatically, batched in parallel
    text = scrape_website(["https://example.com", "https://github.com/owner/repo"])

    # Full web search from a text query — discovers and scrapes top results
    text = search_web("how to install crawl4ai", max_results=5)

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
from ._search import search_web

__version__ = "0.1.0"
__all__ = ["scrape_website", "search_web", "MAX_CHARS", "__version__"]

# ---------------------------------------------------------------------------
# URL routing helpers
# ---------------------------------------------------------------------------

_GITHUB_RE = re.compile(r"https?://github\.com/[^/]+/[^/?#]+(?:\.git)?/?$")


def _is_github(url: str) -> bool:
    """Return ``True`` when *url* points to a GitHub repository root."""
    return bool(_GITHUB_RE.match(url))


def _scrape_list(urls: list[str], max_chars: int) -> str:
    """Route each URL in a list to the right scraper and combine results.

    GitHub URLs are scraped with :func:`~websearch_bot._github.scrape_github`
    (one thread per repo).  All remaining URLs are batch-crawled together via
    :func:`~websearch_bot._crawl.scrape_many`.
    """
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scrape_website(
    url: str | list[str],
    max_pages: int = 5,
    max_depth: int = 1,
    keywords: list[str] | None = None,
    max_chars: int = MAX_CHARS,
) -> str:
    """Scrape one or more URLs and return a context-engineered Markdown document.

    URL routing is automatic:

    * ``github.com/<owner>/<repo>`` → GitHub REST API scraper
      (returns actual source files, not the rendered web page).
    * Any other URL → crawl4ai headless-browser crawler.
    * List of URLs → each URL routed as above, results combined.

    Args:
        url: A single URL string **or** a list of URL strings.
        max_pages: Maximum pages to crawl per site.  Applies to single-URL
            deep crawls only; ignored for batch and GitHub.
        max_depth: Maximum link depth from the seed URL.  Single-URL only.
        keywords: Optional relevance filter.  When provided, BestFirst
            keyword-scoring is used instead of plain BFS.  Single-URL only.
        max_chars: Character budget (~25 K tokens).  Content over this limit
            is compressed via map-reduce LLM summarisation.

    Returns:
        A context-engineered Markdown document, or ``""`` on complete failure.

    Example:
        >>> text = scrape_website("https://example.com")
        >>> text = scrape_website(["https://a.com", "https://github.com/x/y"])
    """
    if isinstance(url, list):
        return _scrape_list(url, max_chars)

    if _is_github(url):
        return _scrape_github(url, max_chars=max_chars)

    return _scrape_one(
        url,
        max_pages=max_pages,
        max_depth=max_depth,
        keywords=keywords,
        max_chars=max_chars,
    )
