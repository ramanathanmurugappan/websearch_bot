"""LLM integration via LiteLLM (Groq backend).

LiteLLM provides a unified OpenAI-compatible interface across providers.
Switching to a different provider only requires changing the model string
in config.py (e.g. "openai/gpt-4o", "anthropic/claude-3-5-haiku-20241022").
"""
from __future__ import annotations

import logging

import litellm

from config import settings

logger = logging.getLogger(__name__)

# Suppress verbose litellm success logs
litellm.success_callback = []

_PROMPT_TEMPLATE = """\
You are a helpful assistant. Using ONLY the scraped webpage content provided \
below, answer the user's question as accurately and concisely as possible.
If the answer cannot be found in the content, say so explicitly.

Question: {question}

--- Scraped Content ---
{context}
"""


def answer_question(question: str, context: dict | str) -> str:
    """Send *question* with *context* to the configured LLM and return the answer."""
    context_text = str(context) if isinstance(context, dict) else context
    prompt = _PROMPT_TEMPLATE.format(
        question=question,
        context=context_text[: settings.max_context_chars],
    )
    try:
        # GROQ_API_KEY is read automatically by LiteLLM from the environment.
        # Set it as a GitHub Actions secret – never hardcode credentials here.
        response = litellm.completion(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM error: %s", exc)
        return f"Error generating answer: {exc}"
