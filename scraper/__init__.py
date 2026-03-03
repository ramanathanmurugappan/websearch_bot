"""Scraper package – public entry point."""
from __future__ import annotations

from .github import scrape_github_repo
from .web import scrape_website

__all__ = ["scrape_url"]


def scrape_url(
    url: str,
    max_pages: int = 10,
    max_depth: int = 3,
    progress_callback=None,
) -> dict:
    """Route *url* to the appropriate scraper and return a content dict."""
    if "github.com" in url.lower():
        return scrape_github_repo(url, progress_callback=progress_callback) or {}
    return scrape_website(
        url,
        max_pages=max_pages,
        max_depth=max_depth,
        progress_callback=progress_callback,
    )
