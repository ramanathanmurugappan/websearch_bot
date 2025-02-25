# Web Scraper Bot with Gemini AI

A powerful web scraping application that combines web content extraction with Google's Gemini AI to provide intelligent answers to your questions about any webpage or GitHub repository.

## Features

- 🌐 Web Scraping: Extract content from any webpage or GitHub repository
- 🤖 AI-Powered Q&A: Ask questions about the scraped content using Google's Gemini AI
- 📊 Interactive UI: Built with Streamlit for a seamless user experience
- 🐳 Docker Support: Easy deployment using Docker

## Prerequisites

- Python 3.9 or higher
- Docker (optional)
- Google API Key for Gemini AI

## Installation

### Local Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Web_Scraper_bot.git
cd Web_Scraper_bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export GOOGLE_API_KEY=your_api_key_here
export GEMINI_MODEL=gemini-2.0-flash
```

4. Run the application:
```bash
streamlit run app.py
```

### Docker Setup

1. Build the Docker image:
```bash
docker build -t web-scraper-bot .
```

2. Run the container:
```bash
docker run -p 8501:8501 \
  -e GOOGLE_API_KEY=your_api_key_here \
  -e GEMINI_MODEL=gemini-2.0-flash \
  web-scraper-bot
```

## Usage

1. Access the application at `http://localhost:8501`
2. Enter a URL to scrape (webpage or GitHub repository)
3. Wait for the content to be extracted
4. Ask questions about the scraped content
5. Get AI-powered answers based on the content

## Project Structure

```
Web_Scraper_bot/
├── app.py              # Main Streamlit application
├── scraper.py         # Web scraping functionality
├── test_scraper.py    # Unit tests
├── requirements.txt   # Python dependencies
├── Dockerfile        # Docker configuration
└── .dockerignore    # Docker ignore rules
```

## Dependencies

- streamlit==1.32.0
- google-generativeai==0.3.2
- beautifulsoup4==4.12.3
- requests==2.31.0
- urllib3==2.2.0

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Google Gemini AI for providing the question-answering capabilities
- Streamlit for the amazing web framework
- BeautifulSoup4 for web scraping functionality
