# websearch-bot

**Scrape any website or GitHub repo for free — built for AI agents and tool calling.**

`websearch-bot` is a thin wrapper around [crawl4ai](https://github.com/unclecode/crawl4ai) purpose-built for AI agent orchestration. Drop it as a tool into any LangGraph, LangChain, CrewAI, or raw function-calling workflow — the output is always a single, structured Markdown string that LLMs can read and reason over immediately.

LLM post-processing is powered entirely by [Groq's free-tier models](https://console.groq.com/docs/rate-limits): crawl4ai handles the headless-browser scraping; Groq's free LLMs compress oversized pages and write AI overviews — all at zero cost.

```
 AI Agent / Orchestrator
 (LangGraph · LangChain · CrewAI · raw tool call)
        │  tool call: scrape_website(url) | search_web(query)
        ▼
  websearch-bot
        │
        ├─► DuckDuckGo (free search API)   ← search_web() only
        │         top-N URLs
        │
        ├─► crawl4ai (headless Chromium)   ← free, open-source
        │         raw Markdown
        │
        └─► Groq free-tier LLMs            ← free API, no credit card
                  • map-reduce compression
                  • AI overview (2–3 sentences)
        │
        │  context-engineered Markdown
        │  (YAML frontmatter + overview + content)
        ▼
 AI Agent continues reasoning
```

## Features

- **Full web search** — `search_web(query)` searches DuckDuckGo (no API key) and scrapes the top results
- **Single URL** — deep-crawls any public website via headless Chromium (crawl4ai)
- **GitHub repos** — fetches actual source files via the GitHub REST API (not the rendered page)
- **Batch URLs** — parallel scrape of multiple URLs in one call; each source is clearly labelled
- **Keyword crawl** — BestFirst relevance scoring to prioritise pages matching your keywords
- **LLM compression** — map-reduce compression via Groq free-tier models when content exceeds 100K chars (~25K tokens); falls back gracefully when rate-limited
- **Context engineering** — every output includes YAML frontmatter (provenance, token estimates, compression stats) and an AI overview ready for downstream agents

## Install

```bash
pip install websearch-bot
```

**Development**:
```bash
git clone https://github.com/ramanathanmurugappan/websearch-bot
cd websearch-bot
pip install -e ".[dev]"
playwright install chromium
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Optional | Enables LLM compression and AI overviews (Groq free tier) |
| `WEBSEARCH_LLM_MODEL` | Optional | Override the primary model (litellm model string) |
| `GITHUB_TOKEN` | Optional | Raises GitHub API rate limit from 60 → 5 000 req/hr |

Create a `.env` file in the project root — it is loaded automatically:
```
GROQ_API_KEY=gsk_...
GITHUB_TOKEN=ghp_...
```

## Usage

```python
from websearch_bot import scrape_website, search_web

# Full web search from a text query — searches DuckDuckGo, scrapes top results
text = search_web("how to use crawl4ai for scraping", max_results=5)

# Single website — deep crawl up to 5 pages
text = scrape_website("https://docs.python.org/3/")

# GitHub repository — auto-detected from URL
code = scrape_website("https://github.com/owner/repo")

# Multiple URLs — batch parallel, each source labelled
text = scrape_website([
    "https://example.com",
    "https://github.com/owner/repo",
])

# Keyword-guided crawl
text = scrape_website(
    "https://docs.python.org/3/",
    max_pages=10,
    max_depth=3,
    keywords=["install", "quickstart"],
)
```

### `scrape_website` parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | `str \| list[str]` | — | URL or list of URLs to scrape |
| `max_pages` | `int` | `5` | Max pages to crawl (single-URL deep crawl only) |
| `max_depth` | `int` | `1` | Max link depth from seed URL (single-URL only) |
| `keywords` | `list[str] \| None` | `None` | Keyword filter for BestFirst relevance scoring |
| `max_chars` | `int` | `100_000` | Character budget; larger content is LLM-compressed |

### `search_web` parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | — | Free-text search query |
| `max_results` | `int` | `5` | Number of DuckDuckGo results to scrape |
| `max_chars` | `int` | `100_000` | Character budget; larger content is LLM-compressed |

### Return value

A Markdown string with this structure:

```
---
source: "https://example.com"
type: website_crawl
scraped_at: 2026-03-03T18:00:00Z
chars: 12,345
tokens_est: ~3K
---

## Overview

[2–3 sentence AI summary of the content]

---

## Content

[full scraped Markdown]
```

When LLM compression is applied the frontmatter also includes `original_chars`, `compressed_chars`, `llm_calls`, and `llm_compressed`.

Returns `""` on complete failure (unreachable URL, invalid GitHub repo, etc.).

## Use with LangGraph / agentic frameworks

```python
from langchain_core.tools import tool
from websearch_bot import scrape_website, search_web

@tool
def web_scrape(
    url: str | list[str],
    max_pages: int = 5,
    max_depth: int = 1,
    keywords: list[str] | None = None,
) -> str:
    """Scrape one or more websites or GitHub repos and return their content."""
    return scrape_website(url, max_pages=max_pages, max_depth=max_depth, keywords=keywords)

@tool
def web_search_tool(query: str, max_results: int = 5) -> str:
    """Search the web for a query and return scraped content from the top results."""
    return search_web(query, max_results=max_results)
```

## Project structure

```
websearch_bot/
├── websearch_bot/
│   ├── __init__.py     # public API: scrape_website, search_web, MAX_CHARS
│   ├── _models.py      # Groq model catalog + rate limits
│   ├── _llm.py         # call_llm, compress_text, summarize_file
│   ├── _crawl.py       # crawl4ai helpers, wrap_context, finalize
│   ├── _github.py      # GitHub REST API scraper
│   ├── _search.py      # DuckDuckGo search → scrape pipeline
│   └── py.typed        # PEP 561 type marker
├── tests/
│   └── test_websearch.py
├── .env                # not committed
├── pyproject.toml
└── README.md
```

## Running tests

```bash
python tests/test_websearch.py
```

Test 7 (LangGraph agent) additionally requires:
```bash
pip install langgraph langchain-groq langchain-core
export GROQ_API_KEY=your_key_here
```

## Credits

### [crawl4ai](https://github.com/unclecode/crawl4ai) by [@unclecode](https://github.com/unclecode)

The heavy lifting of headless-browser crawling is done entirely by **crawl4ai** — an outstanding open-source library that makes web scraping with Playwright simple and fast. `websearch-bot` would not exist without it.

- GitHub: [github.com/unclecode/crawl4ai](https://github.com/unclecode/crawl4ai)
- Docs: [docs.crawl4ai.com](https://docs.crawl4ai.com)

### [Groq](https://groq.com)

LLM compression and AI overviews are powered by Groq's free-tier inference API — the fastest publicly available LLM inference at the time of writing, offered at no cost for development use.

- Console & API keys: [console.groq.com](https://console.groq.com)
- Rate limits: [console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits)

## License

MIT
