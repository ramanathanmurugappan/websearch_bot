import streamlit as st
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import base64
from PIL import Image
from io import BytesIO
from config import *
import scraper
import os

# Initialize Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

@st.cache_resource
def setup_webdriver():
    """Initialize and return a selenium webdriver with configured options"""
    options = Options()
    for option in CHROME_OPTIONS:
        options.add_argument(option)
    options.binary_location = os.getenv('CHROME_BIN', '/usr/bin/google-chrome')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def get_webpage_text(url: str, max_pages: int = 10, max_depth: int = 10, progress_bar=None, status_text=None):
    """Extract content from webpage as JSON with progress updates"""
    def update_progress(current, total):
        if progress_bar and status_text:
            progress = min(current / total, 1.0)
            progress_bar.progress(progress)
            status_text.text(f"Scraped {current} of {total} items")

    try:
        data = scraper.scrape_url_to_json(url, max_pages=max_pages, max_depth=max_depth, progress_callback=update_progress)
        return data if data else {}
    except Exception as e:
        st.error(f"Error fetching content: {str(e)}")
        return {}

def get_webpage_screenshot(url: str) -> str:
    """Capture webpage screenshot and return as base64 string"""
    try:
        driver = setup_webdriver()
        driver.get(url)
        screenshot = driver.get_screenshot_as_png()
        img = Image.open(BytesIO(screenshot))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        st.error(f"Error capturing screenshot: {str(e)}")
        return ""

def get_answer_from_gemini(question: str, context: dict) -> str:
    """Get answer from Gemini model"""
    try:
        context_text = str(context) if isinstance(context, dict) else context
        prompt = f"""Based on this documentation from the Gemini API website, 
        answer this question: {question}
        If you can't find a specific number in the content, please say so.
        
        Documentation text:
        {context_text[:80000]}"""
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating answer: {str(e)}"

# UI Setup
st.set_page_config(page_title="Web Content Q&A", layout="wide")

# Custom styling
st.markdown("""
    <style>
    .stApp { margin: 0; padding: 0; }
    .main .block-container { padding: 1rem; max-width: 100%; }
    .webpage-view {
        background: white;
        border-radius: 5px;
        overflow: hidden;
    }
    .webpage-view img { width: 100%; height: auto; }
    </style>
""", unsafe_allow_html=True)

# Initialize session state variables
if 'current_url' not in st.session_state:
    st.session_state.current_url = ""
if 'current_content' not in st.session_state:
    st.session_state.current_content = {}
if 'current_screenshot' not in st.session_state:
    st.session_state.current_screenshot = ""

# Main UI Layout
left_col, right_col = st.columns([1, 1])

with left_col:
    st.title("Web Content Q&A Tool")
    url = st.text_input("Enter URL:", key="url_input")
    
    max_pages = st.number_input("Maximum pages to scrape", min_value=1, value=10, step=1)
    max_depth = st.number_input("Maximum depth to scrape", min_value=1, value=10, step=1)
    
    # Progress indicators
    progress_container = st.empty()
    status_container = st.empty()
    
    if url and url != st.session_state.current_url:
        with st.spinner("Initializing scraping..."):
            progress_bar = progress_container.progress(0)
            status_text = status_container.text("Starting...")
            
            text_content = get_webpage_text(url, max_pages=max_pages, max_depth=max_depth, 
                                          progress_bar=progress_bar, status_text=status_text)
            screenshot = get_webpage_screenshot(url)
            
            if text_content:
                st.session_state.current_url = url
                st.session_state.current_content = text_content
                st.session_state.current_screenshot = screenshot
            
            # Clear progress indicators when done
            progress_container.empty()
            status_container.empty()
    
    if st.session_state.current_content:
        question = st.text_input("Ask a question about the webpage:")
        if question:
            with st.spinner("Generating answer..."):
                answer = get_answer_from_gemini(question, st.session_state.current_content)
                st.write("Answer:", answer)

with right_col:
    st.subheader("Webpage Preview")
    if st.session_state.current_screenshot:
        st.markdown(
            f'<div class="webpage-view"><img src="data:image/png;base64,{st.session_state.current_screenshot}"/></div>',
            unsafe_allow_html=True
        )