"""GitHub repository scraper using the GitHub REST API.

Fetches the full recursive file tree via ``/git/trees`` and downloads each
source file from ``raw.githubusercontent.com`` in parallel.  The combined
content is then LLM-compressed to fit within the character budget.

Per-file AI summaries are intentionally avoided: they consume one LLM call
per file, exhausting free-tier rate limits before compression even starts.
Map-reduce compression on the combined text achieves the same result in far
fewer calls.

Environment:
    GITHUB_TOKEN: Optional personal access token.  When set, the API rate
        limit rises from 60 → 5 000 requests per hour.

Example:
    >>> from websearch_bot._github import scrape_github
    >>> text = scrape_github("https://github.com/owner/repo")
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from ._llm import MAX_CHARS
from ._crawl import finalize

__all__ = ["scrape_github"]

# ---------------------------------------------------------------------------
# File-type and path filters
# ---------------------------------------------------------------------------

#: Extensions of files considered useful for code understanding.
_CODE_EXTS: frozenset[str] = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".java", ".rb", ".cpp", ".c", ".h", ".cs",
    ".md", ".toml", ".yaml", ".yml", ".json", ".txt", ".sh",
    ".env.example",
})

#: Directory names to skip entirely (generated artefacts, VCS data, etc.).
_SKIP_DIRS: frozenset[str] = frozenset({
    "node_modules", "dist", "build", "out", ".git", ".github",
    "vendor", "__pycache__", ".next", ".nuxt", "coverage",
})

#: Specific file names to skip (lock files, OS metadata, etc.).
#: These are machine-generated, often very large, and not useful for
#: understanding the codebase.
_SKIP_FILES: frozenset[str] = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "composer.lock", "Gemfile.lock", "Pipfile.lock",
    "poetry.lock", "cargo.lock", "mix.lock",
    ".DS_Store", "Thumbs.db",
})

#: Files larger than this are almost always generated (minified JS, compiled
#: CSS, bundled output, etc.) and are skipped to avoid bloating the context.
_MAX_FILE_CHARS: int = 20_000

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _should_skip(path: str) -> bool:
    """Return ``True`` if the file path should be excluded.

    Args:
        path: Forward-slash-delimited repo-relative file path.

    Returns:
        ``True`` when any path segment matches :data:`_SKIP_DIRS` or the
        file name matches :data:`_SKIP_FILES`.
    """
    parts = path.split("/")
    return any(part in _SKIP_DIRS for part in parts) or parts[-1] in _SKIP_FILES


def _auth_headers() -> dict[str, str]:
    """Build GitHub API request headers, adding a Bearer token when available.

    Returns:
        A headers dictionary suitable for ``requests.get``.
    """
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_raw(
    owner: str, repo: str, path: str, headers: dict[str, str]
) -> tuple[str, str] | None:
    """Download a single file from ``raw.githubusercontent.com``.

    Args:
        owner: Repository owner (user or organisation).
        repo: Repository name.
        path: Repo-relative file path.
        headers: Pre-built request headers (see :func:`_auth_headers`).

    Returns:
        ``(path, text)`` on success, or ``None`` on any network/HTTP error.
    """
    try:
        r = requests.get(
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}",
            headers=headers,
            timeout=10,
        )
        r.raise_for_status()
        return path, r.text
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public scraper
# ---------------------------------------------------------------------------


def scrape_github(
    repo_url: str,
    extensions: list[str] | None = None,
    max_files: int = 200,
    max_chars: int = MAX_CHARS,
) -> str:
    """Fetch source files from a public GitHub repository.

    Uses the GitHub REST API to retrieve the full recursive file tree, then
    downloads each matching file in parallel.  All files are concatenated
    verbatim and passed through :func:`~websearch_bot._llm.compress_text`
    in a single map-reduce pass to fit within *max_chars*.

    Args:
        repo_url: Full GitHub repository URL, e.g.
            ``"https://github.com/owner/repo"``.
        extensions: File extensions to include.  Defaults to
            :data:`_CODE_EXTS` when ``None``.
        max_files: Maximum number of files to fetch (default: 200).
        max_chars: Character budget for the final document (default:
            :data:`~websearch_bot._llm.MAX_CHARS`).

    Returns:
        A context-engineered Markdown document, or ``""`` on failure or
        if *repo_url* does not match the expected ``github.com`` pattern.
    """
    m = re.match(
        r"https?://github\.com/([^/]+)/([^/?#]+?)(?:\.git)?/?$",
        repo_url,
    )
    if not m:
        return ""
    owner, repo = m.group(1), m.group(2)

    exts = set(extensions) if extensions else _CODE_EXTS
    headers = _auth_headers()

    # Fetch the recursive file tree from the GitHub API.
    try:
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1",
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        tree = r.json().get("tree", [])
    except Exception:
        return ""

    candidates = [
        item for item in tree
        if item["type"] == "blob"
        and not _should_skip(item["path"])
        and any(item["path"].endswith(ext) for ext in exts)
    ][:max_files]

    # Download all candidate files in parallel (10 workers).
    fetched: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(_fetch_raw, owner, repo, item["path"], headers): item["path"]
            for item in candidates
        }
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                fetched[result[0]] = result[1]

    # Build the combined document in tree order.
    # Files larger than _MAX_FILE_CHARS are skipped — they are almost always
    # generated artefacts (minified bundles, compiled output, etc.).
    parts = [
        f"### {item['path']}\n\n```\n{fetched[item['path']]}\n```"
        for item in candidates
        if item["path"] in fetched and len(fetched[item["path"]]) <= _MAX_FILE_CHARS
    ]
    raw = "\n\n".join(parts)
    meta: dict = {
        "source": repo_url,
        "type": "github_repo",
        "repo": f"{owner}/{repo}",
        "files_total": len(fetched),
    }
    return finalize(raw, meta, max_chars)
