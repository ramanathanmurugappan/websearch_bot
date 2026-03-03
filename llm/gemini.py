"""Google Gemini integration for answering questions about scraped content."""
from __future__ import annotations

import logging

import google.generativeai as genai

from config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.google_api_key)
_model = genai.GenerativeModel(settings.gemini_model)

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
        response = _model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        logger.error("Gemini error: %s", exc)
        return f"Error generating answer: {exc}"
