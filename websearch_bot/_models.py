"""Non-Groq LLM provider registry — Anthropic, OpenAI, Gemini, Moonshot, HuggingFace.

Each entry in PROVIDER_ENV / PROVIDER_FALLBACK_MODELS maps a litellm provider
prefix to the env var that holds its API key and the models to try (fastest /
cheapest first).  These are appended to the fallback chain in _llm.py after the
Groq models when the corresponding key is present in the environment.

To add a provider: add one entry to each dict below.
"""

from __future__ import annotations

import os

__all__ = ["PROVIDER_ENV", "PROVIDER_FALLBACK_MODELS", "_available_provider_fallbacks"]

#: Maps litellm provider prefix → environment variable for the API key.
PROVIDER_ENV: dict[str, str] = {
    "anthropic":   "ANTHROPIC_API_KEY",   # Claude models
    "openai":      "OPENAI_API_KEY",      # GPT models
    "gemini":      "GEMINI_API_KEY",      # Gemini models
    "moonshot":    "MOONSHOT_API_KEY",    # Kimi native API (also free via Groq)
    "huggingface": "HUGGINGFACE_API_KEY", # HuggingFace Inference API
}

#: Ordered fallback models per provider (fastest / cheapest first).
PROVIDER_FALLBACK_MODELS: dict[str, list[str]] = {
    "anthropic": [
        "anthropic/claude-haiku-4-5-20251001",  # fastest, cheapest
        "anthropic/claude-sonnet-4-6",
        "anthropic/claude-opus-4-6",
    ],
    "openai": [
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
    ],
    "gemini": [
        "gemini/gemini-2.0-flash",
        "gemini/gemini-2.0-flash-lite",
        "gemini/gemini-1.5-flash",
        "gemini/gemini-1.5-pro",
    ],
    "moonshot": [
        "moonshot/moonshot-v1-8k",
        "moonshot/moonshot-v1-32k",
        "moonshot/moonshot-v1-128k",
    ],
    "huggingface": [
        "huggingface/meta-llama/Meta-Llama-3.1-8B-Instruct",
        "huggingface/meta-llama/Meta-Llama-3.1-70B-Instruct",
        "huggingface/mistralai/Mistral-7B-Instruct-v0.3",
        "huggingface/Qwen/Qwen2.5-72B-Instruct",
    ],
}


def _available_provider_fallbacks() -> list[str]:
    """Return fallback model IDs for every non-Groq provider whose key is set.

    Called at LLM-call time (not import time) so newly-set env vars are picked
    up without restarting Python.

    Returns:
        Deduplicated list of litellm model strings in PROVIDER_ENV order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for prefix, env_var in PROVIDER_ENV.items():
        if os.getenv(env_var):
            for model in PROVIDER_FALLBACK_MODELS.get(prefix, []):
                if model not in seen:
                    seen.add(model)
                    result.append(model)
    return result
