"""
Output quality tests – compare scraped content against known ground truth.

Each test:
  1. Fetches the page HTML via httpx (ground truth)
  2. Runs it through our scraper pipeline
  3. Asserts that specific known facts appear in the extracted content
  4. Prints a side-by-side comparison for human inspection
"""
import textwrap
import unittest

import httpx
from bs4 import BeautifulSoup

from scraper.web import scrape_website

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"}

# ── Ground-truth knowledge about each test page ───────────────────────────────

GROUND_TRUTH = {
    "https://pypi.org/project/requests/": {
        "title_contains":   ["requests", "PyPI"],
        "content_must_have": [
            "HTTP",             # core purpose
            "Python",           # language
            "psf",              # now PSF-maintained (Kenneth Reitz handed it over)
            "install",          # installation instructions
        ],
        # Structural page chrome that must be stripped by trafilatura.
        # NOTE: we do NOT forbid '<html' here because httpx/requests docs
        # legitimately embed HTML code examples (e.g. r.text = '<!doctype html>…').
        # Instead we check for JS/CSS artefacts that only appear in raw page chrome.
        "content_must_not_have": [
            "document.ready",   # jQuery / JS artefact
            "display:none",     # inline CSS artefact
            "googletag",        # ad-tech JS
        ],
    },
    "https://pypi.org/project/httpx/": {
        "title_contains":   ["httpx", "PyPI"],
        "content_must_have": [
            "HTTP",
            "async",            # httpx is async-capable
            "Python",
        ],
        # '<html' deliberately excluded – the httpx README shows an HTTP response
        # whose body is HTML (r.text = '<!doctype html>\n<html>…'), which
        # trafilatura correctly preserves as code-example content.
        "content_must_not_have": [
            "document.ready",
            "display:none",
            "googletag",
        ],
    },
    "https://pypi.org/project/trafilatura/": {
        "title_contains":   ["trafilatura", "PyPI"],
        "content_must_have": [
            "text",             # text extraction
            "web",              # web content
        ],
        "content_must_not_have": [
            "document.ready",
            "display:none",
            "googletag",
        ],
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_html(url: str) -> str:
    resp = httpx.get(url, timeout=15, follow_redirects=True, headers=HEADERS)
    resp.raise_for_status()
    return resp.text


def _raw_text_via_bs4(html: str) -> str:
    """Naive extraction: all visible text joined (pre-trafilatura baseline)."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "head", "nav", "footer"]):
        tag.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


def _print_comparison(url: str, html: str, scraped_page: dict) -> None:
    raw_text = _raw_text_via_bs4(html)
    extracted = scraped_page.get("text", "")

    print(f"\n{'='*70}")
    print(f"URL : {url}")
    print(f"{'='*70}")
    print(f"  Raw HTML size        : {len(html):>7,} chars")
    print(f"  BS4 naïve text size  : {len(raw_text):>7,} chars")
    print(f"  trafilatura text size: {len(extracted):>7,} chars  "
          f"({len(extracted)/len(raw_text)*100:.0f}% of naïve)")
    print(f"  Title                : {scraped_page.get('title', 'N/A')!r}")
    print(f"\n--- Extracted text (first 600 chars) ---")
    print(textwrap.fill(extracted[:600], width=70))
    print(f"...\n--- Extracted text (last 200 chars) ---")
    print(textwrap.fill(extracted[-200:], width=70))


# ── Test class ────────────────────────────────────────────────────────────────

class TestScraperOutputQuality(unittest.TestCase):

    def _run_quality_check(self, url: str, truth: dict) -> None:
        # 1. Fetch raw HTML
        html = _fetch_html(url)
        self.assertTrue(len(html) > 1000, "Page HTML seems empty")

        # 2. Scrape via our pipeline (single page, no crawl)
        result = scrape_website(url, max_pages=1, max_depth=0)
        self.assertGreater(len(result), 0, f"Scraper returned nothing for {url}")
        page = next(iter(result.values()))

        # 3. Print human-readable comparison
        _print_comparison(url, html, page)

        # 4. Title check
        title = page.get("title", "").lower()
        for phrase in truth["title_contains"]:
            self.assertIn(
                phrase.lower(), title,
                f"Expected {phrase!r} in title, got {title!r}",
            )

        # 5. Content must-have checks (case-insensitive)
        text = page.get("text", "").lower()
        self.assertTrue(len(text) > 100, "Extracted text is too short to be meaningful")

        for phrase in truth["content_must_have"]:
            self.assertIn(
                phrase.lower(), text,
                f"Expected phrase {phrase!r} missing from extracted content",
            )

        # 6. Content must-NOT-have checks (no raw HTML leaking through)
        for artifact in truth["content_must_not_have"]:
            self.assertNotIn(
                artifact.lower(), text,
                f"Raw HTML artifact {artifact!r} found in extracted text — trafilatura should strip this",
            )

        # 7. Noise ratio: extracted text should be significantly shorter than raw HTML
        self.assertLess(
            len(text),
            len(html) * 0.6,
            "Extracted text is almost as long as the raw HTML – likely not cleaned",
        )

        # 8. No excessive whitespace
        consecutive_spaces = max(
            (len(s) - len(s.lstrip(" "))) for s in text.split("\n") if s.strip()
        ) if text else 0
        self.assertLess(consecutive_spaces, 20, "Excessive whitespace in extracted text")

    # --- Individual page tests ---

    def test_pypi_requests_quality(self):
        """PyPI page for the 'requests' library."""
        self._run_quality_check(
            "https://pypi.org/project/requests/",
            GROUND_TRUTH["https://pypi.org/project/requests/"],
        )

    def test_pypi_httpx_quality(self):
        """PyPI page for the 'httpx' library."""
        self._run_quality_check(
            "https://pypi.org/project/httpx/",
            GROUND_TRUTH["https://pypi.org/project/httpx/"],
        )

    def test_pypi_trafilatura_quality(self):
        """PyPI page for the 'trafilatura' library."""
        self._run_quality_check(
            "https://pypi.org/project/trafilatura/",
            GROUND_TRUTH["https://pypi.org/project/trafilatura/"],
        )

    def test_content_cleaner_than_naive_bs4(self):
        """
        trafilatura must produce cleaner output than naive BS4 extraction.
        Measured by: extracted text should be substantially shorter (less noise).
        """
        url = "https://pypi.org/project/requests/"
        html = _fetch_html(url)
        result = scrape_website(url, max_pages=1, max_depth=0)
        page = next(iter(result.values()))

        trafilatura_len = len(page.get("text", ""))
        naive_len = len(_raw_text_via_bs4(html))

        ratio = trafilatura_len / naive_len
        print(f"\n  Noise ratio: trafilatura={trafilatura_len:,} / naive={naive_len:,} = {ratio:.2%}")
        self.assertLess(ratio, 0.85, "trafilatura should remove significant noise vs naive BS4")

    def test_no_structural_html_in_output(self):
        """
        Structural page-chrome tags must not appear in extracted text.

        We check for layout/script/style tags that only exist in raw page
        structure – NOT content tags like <html> which may appear legitimately
        inside code examples (e.g. httpx README shows r.text = '<!doctype html>…').
        """
        import re
        # Tags that belong to page structure, never to readable content
        structural = re.compile(
            r"<(script|style|nav|header|footer|aside|noscript)\b",
            re.IGNORECASE,
        )
        for url in GROUND_TRUTH:
            with self.subTest(url=url):
                result = scrape_website(url, max_pages=1, max_depth=0)
                text = next(iter(result.values())).get("text", "")
                found = structural.findall(text)
                self.assertEqual(
                    found, [],
                    f"Structural HTML tags leaked into output for {url}: {found[:5]}",
                )

    def test_extracted_text_is_utf8_clean(self):
        """Extracted text must be valid, encodeable UTF-8."""
        url = "https://pypi.org/project/requests/"
        result = scrape_website(url, max_pages=1, max_depth=0)
        text = next(iter(result.values())).get("text", "")
        try:
            encoded = text.encode("utf-8")
            self.assertGreater(len(encoded), 0)
        except UnicodeEncodeError as e:
            self.fail(f"Extracted text is not clean UTF-8: {e}")

    def test_links_are_absolute_urls(self):
        """All links returned by the scraper must be fully-qualified URLs."""
        from urllib.parse import urlparse
        url = "https://pypi.org/project/requests/"
        result = scrape_website(url, max_pages=1, max_depth=1)
        page = next(iter(result.values()))
        for link in page.get("links", []):
            parsed = urlparse(link)
            self.assertIn(
                parsed.scheme, {"http", "https"},
                f"Non-absolute link found: {link!r}",
            )
            self.assertTrue(parsed.netloc, f"Link has no host: {link!r}")

    def test_title_not_empty_or_url(self):
        """Title must be a human-readable string, not a raw URL fallback."""
        import re
        # A URL fallback looks like https://... or http://... – use a proper regex
        # to avoid false positives from package names starting with 'http' (e.g. 'httpx').
        url_pattern = re.compile(r"^https?://")
        for url in GROUND_TRUTH:
            with self.subTest(url=url):
                result = scrape_website(url, max_pages=1, max_depth=0)
                page = next(iter(result.values()))
                title = page.get("title", "")
                self.assertTrue(len(title) > 3, f"Title too short: {title!r}")
                self.assertFalse(
                    url_pattern.match(title),
                    f"Title is a raw URL fallback: {title!r}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
