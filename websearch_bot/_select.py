"""LLM-powered URL selection — structured output agent for search result ranking.

Given a free-text query and a list of DuckDuckGo result dicts, uses litellm
structured output (Pydantic ``_URLSelection``) to pick the most relevant pages
to scrape.  Falls back to the top-N DDG results when the LLM is unavailable.
"""

from __future__ import annotations

import warnings

from pydantic import BaseModel, Field

from ._groq import get_fallbacks as _groq_fallbacks
from ._llm import PRIMARY as _PRIMARY
from ._models import _available_provider_fallbacks

__all__: list[str] = []

# How many URLs to return after selection.
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


def select_urls(query: str, results: list[dict]) -> list[str]:
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
