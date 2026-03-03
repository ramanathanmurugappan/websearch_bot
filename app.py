"""Web Content Q&A – Streamlit entry point."""
from __future__ import annotations

import streamlit as st

from config import settings
from llm import answer_question
from scraper import scrape_url
from ui.components import inject_css, render_content

# ── Page configuration ─────────────────────────────────────────────────────────
st.set_page_config(page_title="Web Content Q&A", layout="wide")
inject_css()

# ── Session state defaults ─────────────────────────────────────────────────────
st.session_state.setdefault("current_url", "")
st.session_state.setdefault("current_content", {})

# ── Layout ─────────────────────────────────────────────────────────────────────
left_col, right_col = st.columns([1, 1])

# ── Left column: controls and Q&A ─────────────────────────────────────────────
with left_col:
    st.title("Web Content Q&A")

    url = st.text_input("Enter URL:", key="url_input")
    max_pages = st.number_input(
        "Max pages to scrape",
        min_value=1,
        value=settings.default_max_pages,
        step=1,
    )
    max_depth = st.number_input(
        "Max crawl depth",
        min_value=1,
        value=settings.default_max_depth,
        step=1,
    )

    progress_slot = st.empty()
    status_slot = st.empty()

    if url and url != st.session_state.current_url:
        with st.spinner("Scraping content…"):
            progress_bar = progress_slot.progress(0)
            status_text = status_slot.text("Starting…")

            def _on_progress(current: int, total: int) -> None:
                progress_bar.progress(min(current / total, 1.0))
                status_text.text(f"Scraped {current} of {total} items")

            content = scrape_url(
                url,
                max_pages=int(max_pages),
                max_depth=int(max_depth),
                progress_callback=_on_progress,
            )

            progress_slot.empty()
            status_slot.empty()

            if content:
                st.session_state.current_url = url
                st.session_state.current_content = content
                st.success("Content scraped successfully!")
            else:
                st.error("No content could be scraped from the URL.")

    if st.session_state.current_content:
        question = st.text_input("Ask a question about the webpage:")
        if question:
            with st.spinner("Thinking…"):
                answer = answer_question(question, st.session_state.current_content)
            st.write("**Answer:**", answer)

# ── Right column: content display ──────────────────────────────────────────────
with right_col:
    st.title("Scraped Content")
    if st.session_state.current_content:
        render_content(st.session_state.current_content, st.session_state.current_url)
    else:
        st.info("Enter a URL on the left to start scraping.")
