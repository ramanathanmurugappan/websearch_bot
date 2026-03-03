# Use Python 3.12 slim as base
FROM python:3.12-slim

WORKDIR /app

# System libs required by lxml / trafilatura
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
 && rm -rf /var/lib/apt/lists/*

# Leverage Docker layer cache: install Python deps before copying source
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

ENV PYTHONUNBUFFERED=1

CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
