"""BFS website crawler using httpx + trafilatura for clean content extraction."""
from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"
    ),
    "Accept-Language": "en-US,en;q=0.5",
}


def _same_domain(base: str, target: str) -> bool:
    return urlparse(base).netloc == urlparse(target).netloc


def _extract_links(html: str, base_url: str) -> list[str]:
    """Return absolute, fragment-free links found in *html*."""
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        full = urljoin(base_url, tag["href"])
        parsed = urlparse(full)
        if parsed.scheme in {"http", "https"}:
            links.append(full.split("#")[0])
    return links


def scrape_website(
    start_url: str,
    max_pages: int = 10,
    max_depth: int = 3,
    progress_callback=None,
) -> dict:
    """
    BFS-crawl *start_url*, staying on the same domain.

    Returns a dict keyed by URL, each value containing:
        title, text (main readable content), url, links
    """
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(start_url, 0)]
    result: dict = {}

    with httpx.Client(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
        while queue and len(visited) < max_pages:
            url, depth = queue.pop(0)
            if url in visited:
                continue

            try:
                resp = client.get(url)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", url, exc)
                continue

            html = resp.text
            visited.add(url)

            # trafilatura extracts the main readable text; fall back to empty string
            text = (
                trafilatura.extract(html, include_links=False, include_tables=True)
                or ""
            )
            soup = BeautifulSoup(html, "lxml")
            title = (
                soup.title.string.strip()
                if soup.title and soup.title.string
                else url
            )

            outgoing: list[str] = []
            if depth < max_depth:
                for link in _extract_links(html, url):
                    if link not in visited and _same_domain(start_url, link):
                        outgoing.append(link)
                        queue.append((link, depth + 1))

            result[url] = {"title": title, "text": text, "url": url, "links": outgoing}

            if progress_callback:
                progress_callback(len(visited), max_pages)

    return result
