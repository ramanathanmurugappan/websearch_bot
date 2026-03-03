"""Tests for scraper/github.py – GitHub repository scraper."""
import json
import unittest
from unittest.mock import MagicMock, call, patch

from scraper.github import _fetch_tree, _is_binary, scrape_github_repo


# ── Helper unit tests ──────────────────────────────────────────────────────────

class TestIsBinary(unittest.TestCase):
    def test_image_extensions(self):
        for name in ("logo.png", "photo.JPG", "icon.JPEG", "anim.gif", "graphic.svg"):
            with self.subTest(name=name):
                self.assertTrue(_is_binary(name))

    def test_font_extensions(self):
        for name in ("font.woff", "font.woff2", "font.ttf", "font.eot"):
            with self.subTest(name=name):
                self.assertTrue(_is_binary(name))

    def test_archive_extensions(self):
        for name in ("data.zip", "src.tar", "dist.gz", "app.bin", "win.exe"):
            with self.subTest(name=name):
                self.assertTrue(_is_binary(name))

    def test_skip_files(self):
        self.assertTrue(_is_binary(".gitignore"))
        self.assertTrue(_is_binary(".gitattributes"))

    def test_text_files_not_binary(self):
        for name in ("main.py", "README.md", "config.yaml", "index.js", "style.css"):
            with self.subTest(name=name):
                self.assertFalse(_is_binary(name))

    def test_case_insensitive(self):
        self.assertTrue(_is_binary("IMAGE.PNG"))
        self.assertTrue(_is_binary("Font.WOFF2"))


# ── Mock API responses ─────────────────────────────────────────────────────────

def _make_api_item(name, item_type, url=None, download_url=None):
    return {
        "name": name,
        "type": item_type,
        "url": url or f"https://api.github.com/repos/owner/repo/contents/{name}",
        "download_url": download_url or (
            f"https://raw.githubusercontent.com/owner/repo/main/{name}"
            if item_type == "file"
            else None
        ),
    }


def _mock_client_response(json_data, text_content=None, status=200):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.content = (text_content or "").encode()
    resp.raise_for_status = MagicMock()
    return resp


class TestFetchTree(unittest.TestCase):
    def test_single_text_file(self):
        items = [_make_api_item("README.md", "file")]
        client = MagicMock()
        client.get.side_effect = [
            _mock_client_response(items),                     # directory listing
            _mock_client_response(None, "# Hello World\n"),  # file content
        ]
        result = _fetch_tree("https://api.github.com/repos/x/y/contents", client)
        self.assertIn("README.md", result)
        self.assertEqual(result["README.md"]["type"], "file")
        self.assertEqual(result["README.md"]["content"], "# Hello World\n")

    def test_binary_file_has_no_content(self):
        items = [_make_api_item("logo.png", "file")]
        client = MagicMock()
        client.get.return_value = _mock_client_response(items)
        result = _fetch_tree("https://api.github.com/repos/x/y/contents", client)
        self.assertIn("logo.png", result)
        self.assertNotIn("content", result["logo.png"])

    def test_directory_recurses(self):
        root_items = [_make_api_item("src", "dir", url="https://api.github.com/repos/x/y/contents/src")]
        src_items  = [_make_api_item("main.py", "file", url=None,
                                     download_url="https://raw.githubusercontent.com/x/y/main/src/main.py")]
        client = MagicMock()
        client.get.side_effect = [
            _mock_client_response(root_items),
            _mock_client_response(src_items),
            _mock_client_response(None, "print('hello')\n"),
        ]
        result = _fetch_tree("https://api.github.com/repos/x/y/contents", client)
        self.assertIn("src", result)
        self.assertEqual(result["src"]["type"], "dir")
        self.assertIn("main.py", result["src"]["content"])

    def test_dot_git_directory_skipped(self):
        items = [
            _make_api_item(".git", "dir"),
            _make_api_item("app.py", "file"),
        ]
        client = MagicMock()
        client.get.side_effect = [
            _mock_client_response(items),
            _mock_client_response(None, "# app"),
        ]
        result = _fetch_tree("https://api.github.com/repos/x/y/contents", client)
        self.assertNotIn(".git", result)
        self.assertIn("app.py", result)

    def test_unicode_decode_error_graceful(self):
        items = [_make_api_item("binary.bin", "file")]
        file_resp = MagicMock()
        file_resp.content = b"\xff\xfe\xfd"  # invalid UTF-8
        file_resp.raise_for_status = MagicMock()
        client = MagicMock()
        client.get.side_effect = [
            _mock_client_response(items),
            file_resp,
        ]
        result = _fetch_tree("https://api.github.com/repos/x/y/contents", client)
        self.assertIn("binary.bin", result)
        self.assertNotIn("content", result["binary.bin"])

    def test_api_error_returns_none(self):
        import httpx
        client = MagicMock()
        err_resp = MagicMock()
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock()
        )
        client.get.return_value = err_resp
        result = _fetch_tree("https://api.github.com/repos/x/y/contents", client)
        self.assertIsNone(result)

    def test_progress_callback_called_per_item(self):
        items = [
            _make_api_item("a.py", "file"),
            _make_api_item("b.py", "file"),
            _make_api_item("c.py", "file"),
        ]
        client = MagicMock()
        client.get.side_effect = [
            _mock_client_response(items),
            _mock_client_response(None, "# a"),
            _mock_client_response(None, "# b"),
            _mock_client_response(None, "# c"),
        ]
        calls = []
        _fetch_tree(
            "https://api.github.com/repos/x/y/contents",
            client,
            progress_callback=lambda cur, tot: calls.append((cur, tot)),
        )
        self.assertEqual(len(calls), 3)
        self.assertEqual([c[0] for c in calls], [1, 2, 3])
        self.assertTrue(all(c[1] == 3 for c in calls))

    def test_empty_directory_returns_none(self):
        client = MagicMock()
        client.get.return_value = _mock_client_response([])
        result = _fetch_tree("https://api.github.com/repos/x/y/contents", client)
        self.assertIsNone(result)

    def test_multiple_files_all_fetched(self):
        items = [_make_api_item(f"file{i}.py", "file") for i in range(5)]
        client = MagicMock()
        client.get.side_effect = [
            _mock_client_response(items),
            *[_mock_client_response(None, f"# file{i}") for i in range(5)],
        ]
        result = _fetch_tree("https://api.github.com/repos/x/y/contents", client)
        self.assertEqual(len(result), 5)
        for i in range(5):
            self.assertIn(f"file{i}.py", result)


# ── scrape_github_repo URL parsing ─────────────────────────────────────────────

class TestScrapeGithubRepoUrlParsing(unittest.TestCase):
    @patch("scraper.github.httpx.Client")
    def test_standard_github_url(self, MockClient):
        ctx = MockClient.return_value.__enter__.return_value
        ctx.get.return_value = _mock_client_response([_make_api_item("README.md", "file")])
        ctx.get.side_effect = [
            _mock_client_response([_make_api_item("README.md", "file")]),
            _mock_client_response(None, "# hello"),
        ]
        scrape_github_repo("https://github.com/psf/requests")
        first_call_url = ctx.get.call_args_list[0][0][0]
        self.assertEqual(
            first_call_url,
            "https://api.github.com/repos/psf/requests/contents",
        )

    @patch("scraper.github.httpx.Client")
    def test_invalid_github_url_returns_none(self, MockClient):
        result = scrape_github_repo("https://github.com/only-one-segment")
        self.assertIsNone(result)
        MockClient.assert_not_called()

    @patch("scraper.github.httpx.Client")
    def test_github_url_with_trailing_slash(self, MockClient):
        ctx = MockClient.return_value.__enter__.return_value
        ctx.get.side_effect = [
            _mock_client_response([_make_api_item("setup.py", "file")]),
            _mock_client_response(None, "# setup"),
        ]
        result = scrape_github_repo("https://github.com/psf/requests/")
        first_call_url = ctx.get.call_args_list[0][0][0]
        self.assertEqual(
            first_call_url,
            "https://api.github.com/repos/psf/requests/contents",
        )


# ── Live integration test (runs only when API quota is available) ──────────────

class TestScrapeGithubRepoLive(unittest.TestCase):
    def setUp(self):
        """Skip live tests if GitHub API is rate-limited."""
        import httpx
        r = httpx.get("https://api.github.com/rate_limit", timeout=5)
        remaining = r.json()["resources"]["core"]["remaining"]
        if remaining == 0:
            self.skipTest(f"GitHub API rate-limited (0 requests remaining)")
        print(f"\n  [live] GitHub API quota: {remaining} remaining")

    def test_small_repo_scraped(self):
        """Scrape a small, stable public repo."""
        from scraper import scrape_url
        result = scrape_url("https://github.com/kennethreitz/setup.cfg")
        # setup.cfg is a tiny repo – at minimum the README should appear
        self.assertIsNotNone(result)
        if result:
            sample = next(iter(result.values()))
            self.assertIn("type", sample)
            print(f"  [live] items: {len(result)}, sample key: {next(iter(result))!r}")

    def test_result_structure(self):
        """Every item must have 'type' key; dirs must have 'content'."""
        from scraper.github import scrape_github_repo

        def check_structure(tree):
            for name, item in tree.items():
                self.assertIn("type", item, f"Missing 'type' in {name!r}")
                if item["type"] == "dir":
                    self.assertIn("content", item, f"Dir {name!r} missing 'content'")
                    check_structure(item["content"])

        result = scrape_github_repo("https://github.com/psf/requests")
        if result:
            check_structure(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
