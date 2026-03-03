"""LLM helpers — model routing, text compression, and file summarisation.

All LLM calls go through ``litellm``, cycling through the full fallback
chain defined in :mod:`websearch_bot._models`.  ``litellm`` is imported
lazily so the package remains importable when it is not installed.

Set ``GROQ_API_KEY`` (or ``WEBSEARCH_LLM_MODEL``) in the environment to
enable compression and AI overviews; without it the library still scrapes
but returns raw (uncompressed) content.

Example:
    >>> from websearch_bot._llm import call_llm
    >>> text, model = call_llm("You are helpful.", "What is 2+2?")
    >>> print(text)
    4
"""

from __future__ import annotations

import os
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Load .env from the project root automatically (silent when dotenv is absent).
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from ._models import FALLBACKS as _FALLBACKS, MODELS as _MODELS_CATALOG, PRIMARY as _PRIMARY

__all__ = ["MAX_CHARS", "MODEL_TPM", "call_llm", "compress_text", "summarize_file"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Character budget (~25 K tokens).  Content above this threshold is
#: compressed via map-reduce summarisation before being returned.
MAX_CHARS: int = 100_000

#: litellm model ID → free-tier tokens-per-minute.
#: Used by :func:`compress_text` to size chunks within the rate budget.
MODEL_TPM: dict[str, int] = {
    m["litellm_id"]: (m["tpm"] or 6_000)
    for m in _MODELS_CATALOG
    if m.get("litellm_id")
}

_COMPRESS_SYSTEM = (
    "Summarize the following content concisely, preserving all key facts, "
    "technical details, code structures, and important information. "
    "Output dense, information-rich Markdown."
)

# ---------------------------------------------------------------------------
# Core LLM call
# ---------------------------------------------------------------------------


def call_llm(
    system: str,
    user: str,
    max_tokens: int = 1024,
) -> tuple[str | None, str | None]:
    """Send a chat completion request, cycling through every fallback model.

    Args:
        system: System prompt.
        user: User message (the content to process).
        max_tokens: Maximum completion tokens to request.

    Returns:
        ``(response_text, model_id)`` on success, or ``(None, None)`` if
        every model in the fallback chain fails.
    """
    try:
        import litellm
        litellm.suppress_debug_info = True
        warnings.filterwarnings("ignore", category=RuntimeWarning, module="litellm")

        all_models = [_PRIMARY] + [m for m in _FALLBACKS if m != _PRIMARY]
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]

        for model in all_models:
            try:
                resp = litellm.completion(
                    model=model, messages=msgs, max_tokens=max_tokens, num_retries=0
                )
                return resp.choices[0].message.content, model
            except Exception:
                continue
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# File summariser
# ---------------------------------------------------------------------------


def summarize_file(path: str, content: str) -> str:
    """Return an AI summary of a source file, or the full content as a fallback.

    Args:
        path: File path — used to detect language from the extension.
        content: Raw file text.

    Returns:
        A concise Markdown summary, or ``"*(LLM unavailable)*\\n\\n{content}"``
        when every model in the fallback chain is unavailable.
    """
    ext = os.path.splitext(path)[1].lstrip(".")
    summary, _ = call_llm(
        system=(
            "You are a technical code analyst. Given a source file, output a concise "
            "Markdown summary covering: purpose, key functions/classes/exports, and "
            "important logic. Be precise, no code blocks."
        ),
        user=f"File: `{path}`\n\n```{ext}\n{content}\n```",
        max_tokens=512,
    )
    return summary or f"*(LLM unavailable)*\n\n{content}"


# ---------------------------------------------------------------------------
# Map-reduce compression
# ---------------------------------------------------------------------------


def compress_text(
    text: str,
    max_chars: int,
    _depth: int = 0,
    _calls: int = 0,
    _llm_used: bool = False,
) -> tuple[str, int, bool]:
    """Recursively compress *text* to fit within *max_chars* via map-reduce.

    The text is split into chunks sized at 50 % of the primary model's TPM
    budget (to stay within rate limits), then each chunk is summarised in
    parallel at a 4 : 1 compression ratio.  The pass repeats until the
    combined result fits within *max_chars*.

    Two safety conditions stop early without omitting content:

    * **All models rate-limited** — if no LLM call succeeds in a pass,
      the combined text is returned as-is (no infinite loop).
    * **Depth limit** — after 20 passes the text is returned as-is.

    Args:
        text: Input text to compress.
        max_chars: Target character budget.
        _depth: Recursion depth counter (internal — do not pass).
        _calls: Running LLM-call count (internal — do not pass).
        _llm_used: Whether any LLM call ever succeeded (internal — do not pass).

    Returns:
        A 3-tuple ``(compressed_text, total_llm_calls, llm_was_used)``.
    """
    if len(text) <= max_chars:
        return text, _calls, _llm_used

    if _depth >= 20:  # safety valve — all LLMs persistently unavailable
        return text, _calls, _llm_used

    # Chunk size = 50 % of the primary model's per-minute token budget.
    # Example: llama-3.3-70b at 12 K TPM → 12 000 × 4 × 0.5 = 24 000 chars/chunk.
    tpm = MODEL_TPM.get(_PRIMARY, 6_000)
    chunk_chars = max(int(tpm * 4 * 0.5), 8_000)

    chunks = [text[i: i + chunk_chars] for i in range(0, len(text), chunk_chars)]
    llm_succeeded = [False]

    def _summarize(chunk: str) -> str:
        # Target 25 % of input tokens → 4 : 1 compression ratio per chunk.
        target = max(len(chunk) // 16, 256)
        result, model = call_llm(system=_COMPRESS_SYSTEM, user=chunk, max_tokens=target)
        if result and model:
            llm_succeeded[0] = True
            return result
        return chunk  # keep intact on failure — never drop content

    # Two concurrent workers keep token usage ≤ TPM (2 × chunk_tokens ≤ TPM).
    with ThreadPoolExecutor(max_workers=2) as pool:
        summaries = list(pool.map(_summarize, chunks))

    new_calls = _calls + len(chunks)
    used = _llm_used or llm_succeeded[0]
    combined = "\n\n".join(summaries)

    # If nothing was compressed this pass, stop — another pass would be a no-op.
    if not llm_succeeded[0]:
        return combined, new_calls, used

    if len(combined) > max_chars:
        return compress_text(combined, max_chars, _depth + 1, new_calls, used)
    return combined, new_calls, used
