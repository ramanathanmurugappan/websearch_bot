"""GitHub repository scraper using the public GitHub REST API."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# File extensions whose content we skip (treat as binary)
_SKIP_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".webm", ".mp3",
    ".zip", ".tar", ".gz", ".bin", ".exe", ".so", ".dylib",
    ".ds_store", ".pdf",
})

# Specific filenames whose content we skip
_SKIP_FILES = frozenset({".gitignore", ".gitattributes"})


def _is_binary(name: str) -> bool:
    lower = name.lower()
    return (
        any(lower.endswith(ext) for ext in _SKIP_EXTENSIONS)
        or lower in _SKIP_FILES
    )


def _fetch_tree(
    api_url: str,
    client: httpx.Client,
    progress_callback=None,
    _state: Optional[dict] = None,
) -> Optional[dict]:
    """Recursively fetch the file tree starting at *api_url*."""
    if _state is None:
        _state = {"processed": 0, "total": 0}

    try:
        resp = client.get(api_url)
        resp.raise_for_status()
        items: list[dict] = resp.json()
    except Exception as exc:
        logger.warning("GitHub API error for %s: %s", api_url, exc)
        return None

    # Set total on the first call so the progress bar is meaningful
    if _state["total"] == 0:
        _state["total"] = len(items)

    structure: dict = {}

    for item in items:
        _state["processed"] += 1
        if progress_callback and _state["total"] > 0:
            try:
                progress_callback(_state["processed"], _state["total"])
            except Exception:
                pass

        name: str = item["name"]

        if item["type"] == "file":
            download_url = item.get("download_url")
            if _is_binary(name) or not download_url:
                structure[name] = {"type": "file"}
            else:
                try:
                    file_resp = client.get(download_url)
                    structure[name] = {
                        "type": "file",
                        "content": file_resp.content.decode("utf-8"),
                    }
                except (UnicodeDecodeError, Exception) as exc:
                    logger.debug("Skipping binary/unreadable file %s: %s", name, exc)
                    structure[name] = {"type": "file"}

        elif item["type"] == "dir" and name.lower() != ".git":
            sub = _fetch_tree(item["url"], client, progress_callback, _state)
            if sub is not None:
                structure[name] = {"type": "dir", "content": sub}

    return structure or None


def scrape_github_repo(repo_url: str, progress_callback=None) -> Optional[dict]:
    """
    Fetch all readable text files from a GitHub repository.

    Accepts URLs in the form https://github.com/owner/repo[/...].
    Uses the GitHub REST API (no authentication required for public repos).
    """
    if repo_url.startswith("https://github.com/"):
        parts = repo_url.rstrip("/").split("/")
        if len(parts) < 5:
            logger.error("Cannot parse GitHub URL: %s", repo_url)
            return None
        owner, repo = parts[3], parts[4]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
    else:
        api_url = (
            repo_url if repo_url.endswith("/contents") else f"{repo_url}/contents"
        )

    with httpx.Client(timeout=20, follow_redirects=True) as client:
        return _fetch_tree(api_url, client, progress_callback)
