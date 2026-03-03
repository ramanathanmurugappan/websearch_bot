"""Tests for scraper/web.py – BFS website crawler."""
import unittest
from unittest.mock import MagicMock, patch

from scraper.web import _extract_links, _same_domain, scrape_website


# ── Helper unit tests ──────────────────────────────────────────────────────────

class TestSameDomain(unittest.TestCase):
    def test_same_host(self):
        self.assertTrue(_same_domain("https://pypi.org/a", "https://pypi.org/b"))

    def test_different_host(self):
        self.assertFalse(_same_domain("https://pypi.org", "https://github.com"))

    def test_subdomain_differs(self):
        self.assertFalse(_same_domain("https://docs.python.org", "https://python.org"))

    def test_scheme_ignored_in_netloc(self):
        # Only netloc is compared, not scheme
        self.assertTrue(_same_domain("http://pypi.org/a", "https://pypi.org/b"))


class TestExtractLinks(unittest.TestCase):
    def test_relative_link_resolved(self):
        html = '<a href="/project/requests/">Requests</a>'
        links = _extract_links(html, "https://pypi.org")
        self.assertIn("https://pypi.org/project/requests/", links)

    def test_absolute_link_kept(self):
        html = '<a href="https://github.com/psf/requests">GitHub</a>'
        links = _extract_links(html, "https://pypi.org")
        self.assertIn("https://github.com/psf/requests", links)

    def test_fragment_stripped(self):
        html = '<a href="/page#section">Section</a>'
        links = _extract_links(html, "https://example.com")
        self.assertIn("https://example.com/page", links)
        self.assertNotIn("https://example.com/page#section", links)

    def test_mailto_excluded(self):
        html = '<a href="mailto:test@test.com">Email</a>'
        links = _extract_links(html, "https://example.com")
        self.assertEqual(links, [])

    def test_empty_html(self):
        self.assertEqual(_extract_links("", "https://example.com"), [])

    def test_multiple_links(self):
        html = """
        <a href="/a">A</a>
        <a href="/b">B</a>
        <a href="/c">C</a>
        """
        links = _extract_links(html, "https://site.com")
        self.assertEqual(len(links), 3)


# ── Mock-based scrape_website tests ───────────────────────────────────────────

FAKE_HTML = """
<html>
<head><title>Fake Page</title></head>
<body>
  <p>This is the main content of the page.</p>
  <a href="/about">About</a>
  <a href="https://external.com">External</a>
</body>
</html>
"""


def _mock_response(html: str, status: int = 200):
    resp = MagicMock()
    resp.text = html
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    return resp


class TestScrapeWebsite(unittest.TestCase):
    @patch("scraper.web.httpx.Client")
    def test_single_page_scraped(self, MockClient):
        ctx = MockClient.return_value.__enter__.return_value
        ctx.get.return_value = _mock_response(FAKE_HTML)

        result = scrape_website("https://example.com", max_pages=1, max_depth=0)

        self.assertEqual(len(result), 1)
        url, page = next(iter(result.items()))
        self.assertEqual(page["title"], "Fake Page")
        self.assertIn("main content", page["text"])

    @patch("scraper.web.httpx.Client")
    def test_respects_max_pages(self, MockClient):
        ctx = MockClient.return_value.__enter__.return_value
        ctx.get.return_value = _mock_response(FAKE_HTML)

        result = scrape_website("https://example.com", max_pages=1, max_depth=5)
        self.assertLessEqual(len(result), 1)

    @patch("scraper.web.httpx.Client")
    def test_failed_request_skipped(self, MockClient):
        ctx = MockClient.return_value.__enter__.return_value
        ctx.get.side_effect = Exception("Connection refused")

        result = scrape_website("https://example.com", max_pages=5)
        self.assertEqual(result, {})

    @patch("scraper.web.httpx.Client")
    def test_http_error_skipped(self, MockClient):
        import httpx as _httpx
        ctx = MockClient.return_value.__enter__.return_value
        err_resp = _mock_response("", 404)
        err_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "404", request=MagicMock(), response=err_resp
        )
        ctx.get.return_value = err_resp

        result = scrape_website("https://example.com", max_pages=5)
        self.assertEqual(result, {})

    @patch("scraper.web.httpx.Client")
    def test_progress_callback_called(self, MockClient):
        ctx = MockClient.return_value.__enter__.return_value
        ctx.get.return_value = _mock_response(FAKE_HTML)

        calls = []
        scrape_website(
            "https://example.com",
            max_pages=1,
            max_depth=0,
            progress_callback=lambda cur, tot: calls.append((cur, tot)),
        )
        self.assertTrue(len(calls) >= 1)
        self.assertEqual(calls[0][0], 1)

    @patch("scraper.web.httpx.Client")
    def test_same_domain_only(self, MockClient):
        """External links must not be followed."""
        ctx = MockClient.return_value.__enter__.return_value
        ctx.get.return_value = _mock_response(FAKE_HTML)

        result = scrape_website("https://example.com", max_pages=10, max_depth=2)
        for url in result:
            self.assertIn("example.com", url)

    @patch("scraper.web.httpx.Client")
    def test_no_duplicate_pages(self, MockClient):
        ctx = MockClient.return_value.__enter__.return_value
        ctx.get.return_value = _mock_response(FAKE_HTML)

        result = scrape_website("https://example.com", max_pages=10, max_depth=3)
        self.assertEqual(len(result), len(set(result.keys())))

    @patch("scraper.web.httpx.Client")
    def test_page_structure_keys(self, MockClient):
        ctx = MockClient.return_value.__enter__.return_value
        ctx.get.return_value = _mock_response(FAKE_HTML)

        result = scrape_website("https://example.com", max_pages=1, max_depth=0)
        page = next(iter(result.values()))
        for key in ("title", "text", "url", "links"):
            self.assertIn(key, page)


# ── Live integration test (pypi.org is reachable in this env) ─────────────────

class TestScrapeWebsiteLive(unittest.TestCase):
    def test_pypi_requests_page(self):
        """Scrape the PyPI page for the requests library."""
        result = scrape_website(
            "https://pypi.org/project/requests/",
            max_pages=1,
            max_depth=0,
        )
        self.assertGreater(len(result), 0, "Expected at least one page scraped")
        page = next(iter(result.values()))
        self.assertIn("requests", page["title"].lower())
        self.assertTrue(len(page["text"]) > 50, "Expected meaningful text content")
        print(f"\n  [live] title: {page['title']!r}")
        print(f"  [live] text snippet: {page['text'][:120]!r}")
        print(f"  [live] links found: {len(page['links'])}")

    def test_pypi_streamlit_page(self):
        """Scrape a second PyPI page to verify crawl consistency."""
        result = scrape_website(
            "https://pypi.org/project/streamlit/",
            max_pages=1,
            max_depth=0,
        )
        self.assertGreater(len(result), 0)
        page = next(iter(result.values()))
        self.assertIn("streamlit", page["title"].lower())
        print(f"\n  [live] title: {page['title']!r}")

    def test_max_pages_respected_live(self):
        """BFS must stop at max_pages even if more links exist."""
        result = scrape_website(
            "https://pypi.org/project/requests/",
            max_pages=2,
            max_depth=1,
        )
        self.assertLessEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
