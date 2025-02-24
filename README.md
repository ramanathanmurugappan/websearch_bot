# Web Search Bot

A Streamlit-based web application that allows users to search and ask questions about web content using Google's Gemini AI model.

## Features
- Web page content extraction
- Screenshot capture
- AI-powered question answering using Gemini
- Dockerized deployment

## Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd websearch_bot
```

2. Set up environment variables:
```bash
cp .env.example .env
```
Edit `.env` and add your Google API key.

3. Run with Docker:
```bash
docker-compose up --build
```

The application will be available at `http://localhost:8501`

## Environment Variables
- `GOOGLE_API_KEY`: Your Google API key for Gemini
- `GEMINI_MODEL`: Gemini model to use (defaults to gemini-2.0-flash)

## License
MIT
