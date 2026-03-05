"""Web search — DuckDuckGo query → LLM URL selection → crawl4ai scrape pipeline.

Takes a free-text query, discovers up to 10 URLs via DuckDuckGo, uses an LLM
with structured (Pydantic) output to select the 3 most relevant pages, then
scrapes those with crawl4ai.

Environment:
    GROQ_API_KEY: Optional.  Enables LLM URL selection and compression.
        Without it, falls back to the top-3 DDG results.

Example:
    >>> from websearch_bot._search import _ddg_search
    >>> text = _ddg_search("how to install crawl4ai")
"""

from __future__ import annotations

import warnings

from pydantic import BaseModel, Field

from ._crawl import scrape_many
from ._groq import get_fallbacks as _groq_fallbacks
from ._llm import MAX_CHARS, PRIMARY as _PRIMARY
from ._models import _available_provider_fallbacks

__all__: list[str] = []

# How many results to fetch from DDG before LLM selection.
_DDG_FETCH = 10
# How many URLs to actually crawl after selection.
_CRAWL_TOP = 3

try:
    import tiktoken as _tiktoken
    _ENC = _tiktoken.get_encoding("cl100k_base")
    def _tok(text: str) -> int:
        return len(_ENC.encode(text))
except Exception:
    def _tok(text: str) -> int:  # type: ignore[misc]
        return len(text) // 4


class _URLSelection(BaseModel):
    """Structured response from the LLM URL ranker."""
    urls: list[str] = Field(
        description="The selected URLs ordered by relevance, most relevant first.",
        min_length=1,
        max_length=_CRAWL_TOP,
    )


def _select_urls(query: str, results: list[dict]) -> list[str]:
    """Use an LLM with structured output to pick the most relevant URLs for *query*.

    Builds a numbered candidate list (title + URL + snippet), calls the LLM
    with a Pydantic ``_URLSelection`` response schema, and validates the output.

    Falls back to the top ``_CRAWL_TOP`` DDG URLs if structured output fails.

    Args:
        query: The original search query.
        results: Raw DDGS result dicts with ``href``, ``title``, ``body`` keys.

    Returns:
        List of up to ``_CRAWL_TOP`` URL strings to scrape.
    """
    valid = {r["href"] for r in results}
    fallback = [r["href"] for r in results[:_CRAWL_TOP]]

    lines = []
    for i, r in enumerate(results, 1):
        snippet = (r.get("body") or "")[:150].replace("\n", " ")
        lines.append(f"{i}. {r.get('title', '')}\n   URL: {r['href']}\n   {snippet}")

    system_prompt = (
        "You are a search result ranker. A user has a question and you must pick "
        f"exactly {_CRAWL_TOP} URLs from search results whose page content is most "
        "likely to directly answer that question. "
        "Read each snippet carefully — judge whether the page actually contains the "
        "specific information the question needs. "
        "A highly relevant page scores above a popular but off-topic one. "
        f"Return a JSON object with a 'urls' array of exactly {_CRAWL_TOP} URLs."
    )
    user_prompt = (
        f"Question: {query}\n\n"
        "Rank these candidates by how well their content answers the question "
        f"and return the top {_CRAWL_TOP} URLs:\n\n" + "\n\n".join(lines)
    )
    prompt_chars = len(system_prompt) + len(user_prompt)
    prompt_tokens = _tok(system_prompt + user_prompt)

    msgs = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        import litellm
        litellm.suppress_debug_info = True
        warnings.filterwarnings("ignore", category=RuntimeWarning, module="litellm")

        all_fallbacks = _groq_fallbacks() + _available_provider_fallbacks()
        all_models = [_PRIMARY] + [m for m in all_fallbacks if m != _PRIMARY]

        for model in all_models:
            try:
                resp = litellm.completion(
                    model=model,
                    messages=msgs,
                    response_format=_URLSelection,
                    max_tokens=300,
                    num_retries=0,
                )
                raw = resp.choices[0].message.content or ""
                selection = _URLSelection.model_validate_json(raw)
                selected = [u for u in selection.urls if u in valid][:_CRAWL_TOP]
                if not selected:
                    continue

                resp_chars = len(raw)
                resp_tokens = _tok(raw)
                print(
                    f"[LLM select] 1 call | model: {model.split('/')[-1]} | "
                    f"prompt: {prompt_chars:,} chars / {prompt_tokens:,} tok → "
                    f"response: {resp_chars} chars / {resp_tokens} tok"
                )
                return selected
            except Exception:
                continue

    except Exception:
        pass

    print(f"[LLM select] structured output unavailable — using top-{_CRAWL_TOP} DDG results")
    return fallback


def _ddg_search(
    query: str,
    max_results: int = _DDG_FETCH,
    max_chars: int = MAX_CHARS,
) -> str:
    """Search DuckDuckGo, pick top URLs with an LLM, and scrape them.

    Fetches up to *max_results* candidates from DuckDuckGo, then uses an LLM
    with structured Pydantic output to select the ``_CRAWL_TOP`` most relevant
    pages before scraping.

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
    urls = _select_urls(query, results)

    # 3. Scrape selected URLs in parallel.
    return scrape_many(urls, max_chars=max_chars)
