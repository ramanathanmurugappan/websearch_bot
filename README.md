# Web Search Bot with Gemini AI

An intelligent web search application powered by Google's Gemini AI (using the Gemini 2.0 Flash model) that helps you search and analyze web content efficiently. Ask questions about any webpage or GitHub repository and get accurate, context-aware answers.

## Features

- 🌐 Smart Web Search: Search and analyze content from any webpage or GitHub repository
- 🤖 AI-Powered Q&A: Get intelligent answers using Gemini 2.0 Flash model
- 📊 User-Friendly Interface: Built with Streamlit for easy interaction
- 🐳 Docker Support: Simple deployment with Docker

## Requirements

- Google API Key (with access to Gemini 2.0 Flash model)
- Python 3.9 or higher (for local installation)
- Docker (optional, for container deployment)

## Quick Start Guide

### Option 1: Direct Download and Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/ramanathanmurugappan/websearch_bot.git
   cd websearch_bot
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Google API Key**
   - Get your Google API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Set it as an environment variable:
     ```bash
     export GOOGLE_API_KEY=your_api_key_here
     export GEMINI_MODEL=gemini-2.0-flash    # The model we're using
     ```

4. **Run the Application**
   ```bash
   streamlit run app.py
   ```
   The app will open in your default web browser at `http://localhost:8501`

### Option 2: Docker Setup

1. **Pull the Docker Image**
   ```bash
   docker pull ramanathanmurugappan/websearch_bot
   ```

2. **Run with Docker**
   ```bash
   docker run -p 8501:8501 \
     -e GOOGLE_API_KEY=your_api_key_here \
     -e GEMINI_MODEL=gemini-2.0-flash \
     ramanathanmurugappan/websearch_bot
   ```

## How to Use

1. **Start the Application**
   - The web interface will open in your browser
   - If not, go to `http://localhost:8501`

2. **Enter a URL**
   - Paste any webpage URL or GitHub repository URL
   - Click "Search" to analyze the content

3. **Ask Questions**
   - Type your question about the webpage content
   - The AI will provide relevant answers based on the content using Gemini 2.0 Flash

4. **View Results**
   - See the AI-generated response
   - View relevant snippets from the source content

## Troubleshooting

- **API Key Issues**: Make sure your Google API key is correctly set and has access to Gemini 2.0 Flash model
- **Connection Errors**: Check your internet connection and the validity of the URL
- **Docker Issues**: Ensure Docker is running and ports are not in use
- **Model Issues**: Verify that GEMINI_MODEL is set to 'gemini-2.0-flash'

## Support

For issues or questions:
1. Open an issue on [GitHub](https://github.com/ramanathanmurugappan/websearch_bot/issues)
2. Check existing issues for solutions

## License

MIT License - Feel free to use and modify as needed
