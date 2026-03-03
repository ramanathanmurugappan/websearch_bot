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
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    # Maximum characters of scraped content passed to the LLM
    max_context_chars: int = 80_000
    # HTTP request timeout in seconds
    request_timeout: int = 15
    # Scraper defaults
    default_max_pages: int = 10
    default_max_depth: int = 3


settings = Settings()
