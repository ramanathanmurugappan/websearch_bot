"""Centralised application settings loaded from environment variables."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)


@dataclass
class Settings:
    # LiteLLM model string – prefix determines the provider.
    # GROQ_API_KEY is read directly from the environment by LiteLLM.
    # Set it in .env for local dev, or as a GitHub Actions secret in CI.
    groq_model: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile")
    )
    # Maximum characters of scraped content passed to the LLM
    max_context_chars: int = 80_000
    # HTTP request timeout in seconds
    request_timeout: int = 15
    # Scraper defaults
    default_max_pages: int = 10
    default_max_depth: int = 3


settings = Settings()
