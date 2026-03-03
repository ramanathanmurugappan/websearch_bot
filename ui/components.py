"""Reusable Streamlit UI components."""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
.stApp { margin: 0; padding: 0; }
.main .block-container { padding: 1rem; max-width: 100%; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def render_repo_structure(structure: dict, indent: int = 0) -> None:
    """Recursively render a GitHub repository file tree."""
    prefix = "│   " * (indent - 1) + "├── " if indent > 0 else ""

    for name, data in sorted(structure.items()):
        if data["type"] == "dir":
            st.markdown(f"{prefix}📁 **{name}/**")
            if "content" in data:
                render_repo_structure(data["content"], indent + 1)
        else:
            if "content" in data:
                btn_key = f"view_{indent}_{name}"
                show_key = f"show_{btn_key}"
                col1, col2 = st.columns([8, 2])
                with col1:
                    st.markdown(f"{prefix}📄 **{name}**")
                with col2:
                    if st.button("View", key=btn_key):
                        st.session_state[show_key] = not st.session_state.get(
                            show_key, False
                        )
                if st.session_state.get(show_key, False):
                    lang = name.rsplit(".", 1)[-1] if "." in name else None
                    st.code(data["content"], language=lang)
            else:
                st.markdown(f"{prefix}📄 *{name}* (binary or empty)")


def render_web_content(content: dict) -> None:
    """Render scraped webpage entries as collapsible sections."""
    for url, data in content.items():
        title = data.get("title", url)
        with st.expander(f"Page: {title}"):
            st.write("URL:", url)
            text = data.get("text", "")
            if text:
                preview = text[:2000] + "…" if len(text) > 2000 else text
                st.text_area("Content:", value=preview, height=200, key=f"content_{url}")
            links = data.get("links", [])
            if links:
                st.write(f"Found {len(links)} links on this page")


def render_content(content: dict, current_url: str) -> None:
    """Auto-detect content type and delegate to the right renderer."""
    st.write("Current URL:", current_url)
    is_repo = any(
        isinstance(v, dict) and "type" in v for v in content.values()
    )
    if is_repo:
        st.markdown("### Repository Structure")
        st.markdown("---")
        render_repo_structure(content)
    else:
        render_web_content(content)
