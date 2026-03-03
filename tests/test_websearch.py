"""
websearch_bot — test suite

Run:
    python test_websearch.py

LangGraph test requires:
    pip install langgraph langchain-groq langchain-core
    export GROQ_API_KEY=your_key_here
"""

import os
import pathlib
import shutil

from websearch_bot import scrape_website

try:
    from langchain_core.tools import tool
    from langchain_groq import ChatGroq
    from langgraph.prebuilt import create_react_agent
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

OUT = pathlib.Path("out")
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()


def save(name, text):
    path = OUT / name
    path.write_text(text, encoding="utf-8")
    print(f"  ✓ saved → {path}  ({len(text):,} chars)")


# ── tests ─────────────────────────────────────────────────────────────────────

def test_scrape_website():
    text = scrape_website("http://httpbin.org/html", max_pages=1, max_depth=0)
    assert text and "Moby" in text
    save("test_1_scrape_website.md", text)


def test_scrape_github():
    # GitHub URL is auto-detected — no separate function needed.
    text = scrape_website("https://github.com/ramanathanmurugappan/portfolio-websites")
    assert text and "## " in text
    save("test_2_scrape_github.md", text)


def test_scrape_keywords():
    text = scrape_website(
        "https://docs.python.org/3/tutorial/",
        max_pages=5, max_depth=2,
        keywords=["install", "pip"],
    )
    assert text
    save("test_3_scrape_keywords.md", text)


def test_scrape_many():
    # Pass a list — scrape_website routes to batch mode automatically.
    text = scrape_website([
        "http://httpbin.org/html",
        "https://example.com",
        "https://quotes.toscrape.com",
    ])
    assert text and "Moby" in text
    save("test_4_scrape_many.md", text)


def test_empty_url():
    assert scrape_website("http://localhost:19999", max_pages=1, max_depth=0) == ""
    print("  ✓ unreachable URL → empty string")


def test_scrape_many_empty():
    assert scrape_website(["http://localhost:19999"]) == ""
    print("  ✓ scrape_website([bad_url]) → empty string")


def test_langgraph():
    if not LANGGRAPH_AVAILABLE:
        print("  SKIPPED — run: pip install langgraph langchain-groq langchain-core")
        return

    @tool
    def web_search(
        url: str | list[str],
        max_pages: int = 5,
        max_depth: int = 1,
        keywords: list[str] | None = None,
    ) -> str:
        """Scrape one or more websites and return their text content.

        Pass a single URL string for a focused deep crawl (respects max_pages,
        max_depth, keywords).  Pass a list of URLs for a parallel batch scrape
        (max_pages/max_depth/keywords are ignored — each URL is fetched once).
        """
        return scrape_website(url, max_pages=max_pages, max_depth=max_depth, keywords=keywords)

    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    agent = create_react_agent(llm, tools=[web_search])
    result = agent.invoke({"messages": [{"role": "user", "content":
        "Use web_search on http://httpbin.org/html and tell me what book is mentioned."}]})
    answer = result["messages"][-1].content
    assert len(answer) > 10
    save("test_7_langgraph_agent.md", answer)


# ── runner ────────────────────────────────────────────────────────────────────

TESTS = [
    ("Test 1: scrape_website() — single page",          test_scrape_website),
    ("Test 2: scrape_github() — GitHub repo",           test_scrape_github),
    ("Test 3: scrape_website() — keyword crawl",        test_scrape_keywords),
    ("Test 4: scrape_website([...]) — batch parallel",  test_scrape_many),
    ("Test 5: unreachable URL → empty string",          test_empty_url),
    ("Test 6: bad batch URL → empty string",            test_scrape_many_empty),
    ("Test 7: LangGraph ReAct agent",                   test_langgraph),
]

if __name__ == "__main__":
    passed = failed = 0
    print("=" * 55)
    print("websearch_bot test suite")
    print("=" * 55)

    for label, fn in TESTS:
        print(label)
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED — {e}")
            failed += 1
        print()

    print("=" * 55)
    print(f"  {passed} passed  |  {failed} failed")
    print("=" * 55)
