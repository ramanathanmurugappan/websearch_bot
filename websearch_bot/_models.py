"""
Groq model catalog — sourced from https://api.groq.com/openai/v1/models
Rate limits   — sourced from https://console.groq.com/docs/rate-limits
Last updated  : 2026-03-03

Usage:
    from websearch_bot.models import PRIMARY, FALLBACKS
    from websearch_bot.models import MODELS  # full catalog

Notes:
    - Groq uses *unified* TPM (no separate input/output token limits).
    - Models whose Groq API ID starts with "groq/" (compound, compound-mini)
      require the full ID sent in the API request body; litellm strips the
      provider prefix, so these cannot be used via the standard groq/ prefix
      in litellm — they are listed in the catalog but excluded from FALLBACKS.
    - FALLBACKS is ordered: TPM desc → TPD desc → RPD desc.
    - Safety/guard, audio, and TTS models are excluded from FALLBACKS.
"""

import os

# ── Primary model ──────────────────────────────────────────────────────────────
# Override via WEBSEARCH_LLM_MODEL env var.
PRIMARY: str = os.getenv("WEBSEARCH_LLM_MODEL", "groq/llama-3.3-70b-versatile")

# ── Fallback chain ─────────────────────────────────────────────────────────────
# All Groq free-tier text-generation models (excluding guard/audio/tts and
# compound models with broken litellm routing).
# Ordered by: TPM desc → TPD desc → RPD desc.
#                                                        RPM   RPD    TPM    TPD
FALLBACKS: list[str] = [
    "groq/meta-llama/llama-4-scout-17b-16e-instruct",    # 30   1K     30K    500K
    "groq/moonshotai/kimi-k2-instruct",                  # 60   1K     10K    300K
    "groq/moonshotai/kimi-k2-instruct-0905",             # 60   1K     10K    300K
    "groq/openai/gpt-oss-120b",                          # 30   1K      8K    200K
    "groq/openai/gpt-oss-20b",                           # 30   1K      8K    200K  (1000 tok/s)
    "groq/llama-3.1-8b-instant",                         # 30   14.4K   6K    500K  (highest RPD)
    "groq/allam-2-7b",                                   # 30   7K      6K    500K
    "groq/meta-llama/llama-4-maverick-17b-128e-instruct", # 30  1K      6K    500K
    "groq/qwen/qwen3-32b",                               # 60   1K      6K    500K
]

# ── Full model catalog ─────────────────────────────────────────────────────────
# api_id       : raw model ID as returned by Groq's /v1/models endpoint
# litellm_id   : model string for litellm (provider/model_name)
#                None = cannot be used via litellm standard routing
# context      : context window in tokens
# max_output   : max completion tokens
# category     : text | guard | audio | tts
# rpm / rpd / tpm / tpd : free-tier rate limits (None = not published / unlimited)
MODELS: list[dict] = [
    # ── Text generation ──────────────────────────────────────────────────────
    {
        "api_id":     "llama-3.3-70b-versatile",
        "litellm_id": "groq/llama-3.3-70b-versatile",
        "owner":      "Meta",
        "context":    131_072,
        "max_output": 32_768,
        "category":   "text",
        "rpm": 30, "rpd": 1_000,  "tpm": 12_000,  "tpd": 100_000,
        "note": "default PRIMARY model",
    },
    {
        "api_id":     "meta-llama/llama-4-scout-17b-16e-instruct",
        "litellm_id": "groq/meta-llama/llama-4-scout-17b-16e-instruct",
        "owner":      "Meta",
        "context":    131_072,
        "max_output": 8_192,
        "category":   "text",
        "rpm": 30, "rpd": 1_000, "tpm": 30_000, "tpd": 500_000,
    },
    {
        "api_id":     "moonshotai/kimi-k2-instruct",
        "litellm_id": "groq/moonshotai/kimi-k2-instruct",
        "owner":      "Moonshot AI",
        "context":    131_072,
        "max_output": 16_384,
        "category":   "text",
        "rpm": 60, "rpd": 1_000, "tpm": 10_000, "tpd": 300_000,
    },
    {
        "api_id":     "moonshotai/kimi-k2-instruct-0905",
        "litellm_id": "groq/moonshotai/kimi-k2-instruct-0905",
        "owner":      "Moonshot AI",
        "context":    262_144,
        "max_output": 16_384,
        "category":   "text",
        "rpm": 60, "rpd": 1_000, "tpm": 10_000, "tpd": 300_000,
    },
    {
        "api_id":     "openai/gpt-oss-120b",
        "litellm_id": "groq/openai/gpt-oss-120b",
        "owner":      "OpenAI",
        "context":    131_072,
        "max_output": 65_536,
        "category":   "text",
        "rpm": 30, "rpd": 1_000, "tpm": 8_000, "tpd": 200_000,
    },
    {
        "api_id":     "openai/gpt-oss-20b",
        "litellm_id": "groq/openai/gpt-oss-20b",
        "owner":      "OpenAI",
        "context":    131_072,
        "max_output": 65_536,
        "category":   "text",
        "rpm": 30, "rpd": 1_000, "tpm": 8_000, "tpd": 200_000,
        "note": "~1000 tok/s output speed",
    },
    {
        "api_id":     "llama-3.1-8b-instant",
        "litellm_id": "groq/llama-3.1-8b-instant",
        "owner":      "Meta",
        "context":    131_072,
        "max_output": 131_072,
        "category":   "text",
        "rpm": 30, "rpd": 14_400, "tpm": 6_000, "tpd": 500_000,
        "note": "highest RPD among 6K-TPM models",
    },
    {
        "api_id":     "allam-2-7b",
        "litellm_id": "groq/allam-2-7b",
        "owner":      "SDAIA",
        "context":    4_096,
        "max_output": 4_096,
        "category":   "text",
        "rpm": 30, "rpd": 7_000, "tpm": 6_000, "tpd": 500_000,
    },
    {
        "api_id":     "meta-llama/llama-4-maverick-17b-128e-instruct",
        "litellm_id": "groq/meta-llama/llama-4-maverick-17b-128e-instruct",
        "owner":      "Meta",
        "context":    131_072,
        "max_output": 8_192,
        "category":   "text",
        "rpm": 30, "rpd": 1_000, "tpm": 6_000, "tpd": 500_000,
    },
    {
        "api_id":     "qwen/qwen3-32b",
        "litellm_id": "groq/qwen/qwen3-32b",
        "owner":      "Alibaba Cloud",
        "context":    131_072,
        "max_output": 40_960,
        "category":   "text",
        "rpm": 60, "rpd": 1_000, "tpm": 6_000, "tpd": 500_000,
    },
    # ── Groq-native models (compound) ────────────────────────────────────────
    # IMPORTANT: Groq API model IDs for these start with "groq/" (e.g. "groq/compound-mini").
    # litellm strips the provider prefix, so it sends "compound-mini" → 404.
    # Use api_id directly with the Groq REST API if needed; skip from FALLBACKS.
    {
        "api_id":     "groq/compound",
        "litellm_id": None,
        "owner":      "Groq",
        "context":    131_072,
        "max_output": 8_192,
        "category":   "text",
        "rpm": 30, "rpd": 250, "tpm": 70_000, "tpd": None,
        "note": "litellm routing broken — use Groq REST API directly",
    },
    {
        "api_id":     "groq/compound-mini",
        "litellm_id": None,
        "owner":      "Groq",
        "context":    131_072,
        "max_output": 8_192,
        "category":   "text",
        "rpm": 30, "rpd": 250, "tpm": 70_000, "tpd": None,
        "note": "litellm routing broken — use Groq REST API directly",
    },
    # ── Guard / safety models ────────────────────────────────────────────────
    {
        "api_id":     "meta-llama/llama-guard-4-12b",
        "litellm_id": "groq/meta-llama/llama-guard-4-12b",
        "owner":      "Meta",
        "context":    131_072,
        "max_output": 1_024,
        "category":   "guard",
        "rpm": 30, "rpd": 14_400, "tpm": 15_000, "tpd": 500_000,
    },
    {
        "api_id":     "meta-llama/llama-prompt-guard-2-22m",
        "litellm_id": "groq/meta-llama/llama-prompt-guard-2-22m",
        "owner":      "Meta",
        "context":    512,
        "max_output": 512,
        "category":   "guard",
        "rpm": 30, "rpd": 14_400, "tpm": 15_000, "tpd": 500_000,
    },
    {
        "api_id":     "meta-llama/llama-prompt-guard-2-86m",
        "litellm_id": "groq/meta-llama/llama-prompt-guard-2-86m",
        "owner":      "Meta",
        "context":    512,
        "max_output": 512,
        "category":   "guard",
        "rpm": 30, "rpd": 14_400, "tpm": 15_000, "tpd": 500_000,
    },
    {
        "api_id":     "openai/gpt-oss-safeguard-20b",
        "litellm_id": "groq/openai/gpt-oss-safeguard-20b",
        "owner":      "OpenAI",
        "context":    131_072,
        "max_output": 65_536,
        "category":   "guard",
        "rpm": 30, "rpd": 1_000, "tpm": 8_000, "tpd": 200_000,
    },
    # ── Audio (speech-to-text) ───────────────────────────────────────────────
    {
        "api_id":     "whisper-large-v3",
        "litellm_id": "groq/whisper-large-v3",
        "owner":      "OpenAI",
        "context":    448,
        "max_output": 448,
        "category":   "audio",
        "rpm": 20, "rpd": 2_000, "tpm": None, "tpd": None,
    },
    {
        "api_id":     "whisper-large-v3-turbo",
        "litellm_id": "groq/whisper-large-v3-turbo",
        "owner":      "OpenAI",
        "context":    448,
        "max_output": 448,
        "category":   "audio",
        "rpm": 20, "rpd": 2_000, "tpm": None, "tpd": None,
    },
    # ── Text-to-speech ───────────────────────────────────────────────────────
    {
        "api_id":     "canopylabs/orpheus-v1-english",
        "litellm_id": None,
        "owner":      "Canopy Labs",
        "context":    4_000,
        "max_output": 50_000,
        "category":   "tts",
        "rpm": None, "rpd": None, "tpm": None, "tpd": None,
    },
    {
        "api_id":     "canopylabs/orpheus-arabic-saudi",
        "litellm_id": None,
        "owner":      "Canopy Labs",
        "context":    4_000,
        "max_output": 50_000,
        "category":   "tts",
        "rpm": None, "rpd": None, "tpm": None, "tpd": None,
    },
]
