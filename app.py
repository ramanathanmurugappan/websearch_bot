import streamlit as st
import google.generativeai as genai
import scraper
import os

# === API Initialization ===
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel(os.getenv("GEMINI_MODEL"))

# === Web Scraping Functions ===
def get_webpage_text(url: str, max_pages: int = 10, max_depth: int = 10, progress_bar=None, status_text=None) -> dict:
    """Extract content from webpage as JSON with progress updates."""
    def update_progress(current: int, total: int) -> None:
        if progress_bar and status_text:
            progress = min(current / total, 1.0)
            progress_bar.progress(progress)
            status_text.text(f"Scraped {current} of {total} items")

    try:
        data = scraper.scrape_url_to_json(
            url, 
            max_pages=max_pages, 
            max_depth=max_depth, 
            progress_callback=update_progress
        )
        return data if data else {}
    except Exception as e:
        st.error(f"Error fetching content: {str(e)}")
        return {}

# === AI Model Functions ===
def get_answer_from_gemini(question: str, context: dict) -> str:
    """Get answer from Gemini model"""
    try:
        
        context_text = str(context) if isinstance(context, dict) else context

        prompt = f"""Based on the scraped webpage content,
        answer this question: {question}
        If you can't find a specific answer in the content, please say so.

        Webpage content:
        {context_text[:80000]}"""
        
        response = model.generate_content(prompt)
        
        # Extract text from response
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    content = candidate.content
                    if hasattr(content, 'parts') and content.parts:
                        text = content.parts[0].text
                        return text.strip()
            
            # Fallback to response.text if available
            if hasattr(response, 'text'):
                return response.text.strip()

            return str(response)
            
        except Exception as e:
            return str(response)
            
    except Exception as e:
        return f"Error generating answer: {str(e)}"

# === Streamlit UI Setup ===
st.set_page_config(page_title="Web Content Q&A", layout="wide")

# Custom CSS styling
st.markdown("""
    <style>
    .stApp { margin: 0; padding: 0; }
    .main .block-container { padding: 1rem; max-width: 100%; }
    .content-view {
        background: white;
        border-radius: 5px;
        padding: 10px;
        overflow: auto;
        max-height: 500px;
    }
    </style>
""", unsafe_allow_html=True)

# === Session State Initialization ===
if 'current_url' not in st.session_state:
    st.session_state.current_url = ""
if 'current_content' not in st.session_state:
    st.session_state.current_content = {}

# === Main UI Layout ===
left_col, right_col = st.columns([1, 1])

# === Left Column: Input and Q&A ===
with left_col:
    st.title("Web Content Q&A Tool")
    
    # URL input and scraping controls
    url = st.text_input("Enter URL:", key="url_input")
    max_pages = st.number_input("Maximum pages to scrape", min_value=1, value=10, step=1)
    max_depth = st.number_input("Maximum depth to scrape", min_value=1, value=10, step=1)
    
    # Progress indicators
    progress_container = st.empty()
    status_container = st.empty()
    
    # Handle URL submission and scraping
    if url and url != st.session_state.current_url:
        with st.spinner("Scraping the content..."):
            progress_bar = progress_container.progress(0)
            status_text = status_container.text("Starting...")
            
            text_content = get_webpage_text(
                url, 
                max_pages=max_pages, 
                max_depth=max_depth,
                progress_bar=progress_bar, 
                status_text=status_text
            )
            
            if text_content:
                st.session_state.current_url = url
                st.session_state.current_content = text_content
                st.success("Content scraped successfully!")
            else:
                st.error("No content could be scraped from the URL")
            
            # Clear progress indicators
            progress_container.empty()
            status_container.empty()
    
    # Question input and answer display
    if st.session_state.current_content:
        question = st.text_input("Ask a question about the webpage:")
        if question:
            with st.spinner("Generating answer..."):
                answer = get_answer_from_gemini(question, st.session_state.current_content)
                st.write("Answer:", answer)

# === Right Column: Content Display ===
with right_col:
    st.title("Scraped Content")
    
    if st.session_state.current_content:
        st.write("Current URL:", st.session_state.current_url)
        
        def display_repo_structure(structure: dict, indent: int = 0) -> None:
            """Display repository structure with indentation."""
            for name, data in sorted(structure.items()):  # Sort items alphabetically
                prefix = "│   " * (indent - 1) + "├── " if indent > 0 else ""
                
                if data["type"] == "dir":
                    st.markdown(f"{prefix}📁 **{name}/**")
                    if "content" in data:
                        display_repo_structure(data["content"], indent + 1)
                else:  # file
                    if "content" in data:
                        col1, col2 = st.columns([8, 2])
                        with col1:
                            st.markdown(f"{prefix}📄 **{name}**")
                        with col2:
                            if st.button("View", key=f"view_{indent}_{name}"):
                                st.session_state[f"show_content_{indent}_{name}"] = \
                                    not st.session_state.get(f"show_content_{indent}_{name}", False)
                        
                        if st.session_state.get(f"show_content_{indent}_{name}", False):
                            st.code(data["content"], language=name.split('.')[-1] if '.' in name else None)
                    else:
                        st.markdown(f"{prefix}📄 *{name}* (binary or empty file)")
        
        # Display content based on type (GitHub repo or regular webpage)
        if any(isinstance(v, dict) and "type" in v for v in st.session_state.current_content.values()):
            st.markdown("### Repository Structure")
            st.markdown("---")
            display_repo_structure(st.session_state.current_content)
        else:
            # Display regular webpage content
            for url, data in st.session_state.current_content.items():
                with st.expander(f"Page: {data.get('title', url)}"):
                    st.write("URL:", url)
                    if "text" in data:
                        st.text_area(
                            "Content:",
                            value=data["text"][:1000] + "..." if len(data["text"]) > 1000 else data["text"],
                            height=200,
                            key=f"content_{url}"
                        )
                    if "links" in data:
                        st.write(f"Found {len(data['links'])} links on this page")
    else:
        st.info("Enter a URL on the left to start scraping content")