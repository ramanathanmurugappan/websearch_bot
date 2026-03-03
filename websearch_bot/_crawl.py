"""crawl4ai helpers — browser configuration, crawl execution, and output formatting.

Internal functions are prefixed with ``_`` and are not part of the public API.
The two public entry points (:func:`scrape_website` and :func:`scrape_many`)
are called by :mod:`websearch_bot.__init__` after URL routing.

Example:
    >>> from websearch_bot._crawl import scrape_website
    >>> text = scrape_website("https://example.com", max_pages=3)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, SemaphoreDispatcher
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from ._llm import MAX_CHARS, call_llm, compress_text

__all__ = ["scrape_website", "scrape_many", "wrap_context", "finalize"]

# ---------------------------------------------------------------------------
# Browser and crawler configuration
# ---------------------------------------------------------------------------

# Headless Chromium; images and remote fonts disabled for speed.
_BROWSER = BrowserConfig(
    headless=True,
    text_mode=False,
    extra_args=[
        "--blink-settings=imagesEnabled=false",
        "--disable-remote-fonts",
    ],
)

# Shared keyword arguments applied to every CrawlerRunConfig instance.
_BASE: dict = dict(
    word_count_threshold=10,
    excluded_tags=["nav", "footer", "header", "aside", "script", "style"],
    remove_overlay_elements=True,
    exclude_social_media_links=True,
    markdown_generator=DefaultMarkdownGenerator(options={"body_width": 0}),
    scraping_strategy=LXMLWebScrapingStrategy(),
    wait_until="networkidle",  # required for JS-rendered / SPA pages
    page_timeout=30_000,       # 30 s (default is 60 s)
    wait_for_images=False,
    verbose=False,
)

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_markdown(result) -> str:
    """Return the best available Markdown string from a crawl result object."""
    md = result.markdown
    return (md.markdown_with_citations or md.raw_markdown) if md else ""


def _make_strategy(max_depth: int, max_pages: int, keywords: list[str] | None):
    """Build a BestFirst (keyword-scored) or BFS deep-crawl strategy.

    Args:
        max_depth: Maximum link depth from the seed URL.
        max_pages: Maximum total pages to visit.
        keywords: When provided, enables keyword-relevance scoring.

    Returns:
        A crawl4ai deep-crawl strategy instance.
    """
    if keywords:
        return BestFirstCrawlingStrategy(
            max_depth=max_depth,
            max_pages=max_pages,
            include_external=False,
            url_scorer=KeywordRelevanceScorer(keywords=keywords),
        )
    return BFSDeepCrawlStrategy(
        max_depth=max_depth,
        max_pages=max_pages,
        include_external=False,
    )


def _run_sync(coro):
    """Run an async coroutine from synchronous code.

    Applies ``nest_asyncio`` when an event loop is already running (e.g.
    inside Jupyter) so the coroutine can still be awaited via
    ``run_until_complete``.
    """
    try:
        asyncio.get_running_loop()
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.get_event_loop().run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _async_crawl(url: str, config: CrawlerRunConfig) -> str:
    """Crawl a single URL (possibly multiple pages) and return joined Markdown."""
    async with AsyncWebCrawler(config=_BROWSER) as crawler:
        results = await crawler.arun(url, config=config)
        return "\n\n".join(_extract_markdown(r) for r in results if r.success)


async def _async_crawl_many(urls: list[str], config: CrawlerRunConfig) -> str:
    """Crawl multiple URLs in parallel (up to 5 concurrent sessions).

    Each URL's content is wrapped in a ``## Source: <url>`` section so the
    caller can tell which content came from which URL.
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


# ---------------------------------------------------------------------------
# Context engineering wrapper
# ---------------------------------------------------------------------------


def wrap_context(content: str, meta: dict) -> str:
    """Wrap scraped content in a context-engineered Markdown document.

    The output structure follows Anthropic / industry best practices (2025–2026):

    1. **YAML frontmatter** — provenance, timestamps, character/token counts,
       and compression statistics when LLM compression was applied.
    2. **AI overview** — a 2–3 sentence signal-first summary written for
       downstream AI agents so they can understand the content at a glance.
    3. **Content** — the (possibly compressed) Markdown body.

    Args:
        content: The Markdown text to wrap (may be LLM-compressed).
        meta: Provenance dictionary.  Recognised keys:
            ``source``, ``type``, ``original_chars``, ``llm_calls``,
            ``llm_compressed``.  Any additional keys are written verbatim
            into the frontmatter.

    Returns:
        A fully formatted Markdown document string.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    chars = len(content)

    def _tok(n: int) -> str:
        """Format a character count as a human-readable token estimate."""
        t = n // 4  # ~4 chars per token for English / code
        return f"~{t // 1_000}K" if t >= 1_000 else str(t)

    # Keys handled explicitly below — skip them in the generic loop.
    _HANDLED = {"source", "type", "original_chars", "llm_calls", "llm_compressed"}

    lines = ["---"]
    lines.append(f'source: "{meta.get("source", "unknown")}"')
    lines.append(f'type: {meta.get("type", "unknown")}')
    lines.append(f"scraped_at: {now}")

    orig = meta.get("original_chars")
    if orig and orig != chars:
        # Compression occurred — show before → after stats.
        lines += [
            f"original_chars: {orig:,}",
            f"original_tokens: {_tok(orig)}",
            f"compressed_chars: {chars:,}",
            f"compressed_tokens: {_tok(chars)}",
            f"llm_calls: {meta.get('llm_calls', 0)}",
            f"llm_compressed: {str(meta.get('llm_compressed', False)).lower()}",
        ]
    else:
        lines += [f"chars: {chars:,}", f"tokens_est: {_tok(chars)}"]

    for k, v in meta.items():
        if k in _HANDLED:
            continue
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f'  - "{item}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    frontmatter = "\n".join(lines)

    # Generate a signal-first overview for downstream AI agents.
    overview_text, _ = call_llm(
        system=(
            "You are a context engineering assistant. Given scraped content, write a precise "
            "2-3 sentence overview for an AI agent covering: (1) what this content is about, "
            "(2) key information it contains, (3) what tasks or questions it is useful for. "
            "Be specific and factual."
        ),
        user=content[:20_000],  # ~5 K tokens — within every model's TPM budget
        max_tokens=200,
    )
    overview = (
        overview_text
        or "_Overview unavailable — set GROQ_API_KEY or WEBSEARCH_LLM_MODEL to enable._"
    )

    return f"{frontmatter}\n\n## Overview\n\n{overview}\n\n---\n\n## Content\n\n{content}"


# ---------------------------------------------------------------------------
# Shared post-processing helper
# ---------------------------------------------------------------------------


def finalize(raw: str, meta: dict, max_chars: int) -> str:
    """Compress *raw*, attach compression stats to *meta*, and wrap with context.

    This helper eliminates the identical compress → update-meta → wrap pattern
    that would otherwise be duplicated in every public scraper.

    Args:
        raw: Raw scraped text (may be very large).
        meta: Provenance dictionary passed to :func:`wrap_context`.
            ``original_chars``, ``llm_calls``, and ``llm_compressed`` are
            added automatically when LLM compression is applied.
        max_chars: Character budget passed to :func:`~websearch_bot._llm.compress_text`.

    Returns:
        A context-engineered Markdown document, or ``""`` if *raw* is empty.
    """
    original_chars = len(raw)
    content, llm_calls, llm_used = compress_text(raw, max_chars)
    if not content.strip():
        return ""
    if llm_calls > 0:
        meta.update(original_chars=original_chars, llm_calls=llm_calls, llm_compressed=llm_used)
    return wrap_context(content, meta)


# ---------------------------------------------------------------------------
# Public scrapers
# ---------------------------------------------------------------------------


def scrape_website(
    url: str,
    max_pages: int = 5,
    max_depth: int = 1,
    keywords: list[str] | None = None,
    max_chars: int = MAX_CHARS,
) -> str:
    """Scrape a single website and return a context-engineered Markdown document.

    Args:
        url: Target URL to crawl.
        max_pages: Maximum pages to visit during the deep crawl.
        max_depth: Maximum link depth from the seed URL.
        keywords: When provided, BestFirst keyword-relevance scoring is used
            instead of plain BFS traversal.
        max_chars: Character budget; content over this limit is LLM-compressed.

    Returns:
        A context-engineered Markdown document, or ``""`` on failure.
    """
    try:
        config = CrawlerRunConfig(
            **_BASE,
            deep_crawl_strategy=_make_strategy(max_depth, max_pages, keywords),
        )
        raw = _run_sync(_async_crawl(url, config))
        meta: dict = {
            "source": url, "type": "website_crawl",
            "max_pages": max_pages, "max_depth": max_depth,
        }
        if keywords:
            meta["keywords"] = keywords
        return finalize(raw, meta, max_chars)
    except Exception:
        return ""


def scrape_many(urls: list[str], max_chars: int = MAX_CHARS) -> str:
    """Batch-scrape multiple URLs in parallel (up to 5 concurrent).

    Each URL's content is clearly labelled with a ``## Source:`` heading.

    Args:
        urls: List of URLs to scrape.
        max_chars: Character budget; content over this limit is LLM-compressed.

    Returns:
        A context-engineered Markdown document, or ``""`` if every URL fails.
    """
    try:
        raw = _run_sync(_async_crawl_many(urls, CrawlerRunConfig(**_BASE)))
        meta: dict = {"source": "batch", "type": "batch_crawl", "urls": urls}
        return finalize(raw, meta, max_chars)
    except Exception:
        return ""
