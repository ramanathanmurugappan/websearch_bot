"""Google Gemini integration for answering questions about scraped content."""
from __future__ import annotations

import logging

from google import genai

from config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Return a cached Gemini client, created lazily on first use."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.google_api_key)
    return _client


_PROMPT_TEMPLATE = """\
You are a helpful assistant. Using ONLY the scraped webpage content provided \
below, answer the user's question as accurately and concisely as possible.
If the answer cannot be found in the content, say so explicitly.

Question: {question}

--- Scraped Content ---
{context}
"""


def answer_question(question: str, context: dict | str) -> str:
    """Send *question* with *context* to Gemini and return the model's answer."""
    context_text = str(context) if isinstance(context, dict) else context
    prompt = _PROMPT_TEMPLATE.format(
        question=question,
        context=context_text[: settings.max_context_chars],
    )
    try:
        response = _get_client().models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        return response.text.strip()
    except Exception as exc:
        logger.error("Gemini error: %s", exc)
        return f"Error generating answer: {exc}"
