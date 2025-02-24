# Stage 1: Build dependencies
FROM --platform=linux/arm64 python:3.9-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install

# Install Python dependencies
COPY requirements.txt .
RUN pip install --prefix=/install --no-warn-script-location -r requirements.txt

# Stage 2: Final image
FROM --platform=linux/arm64 python:3.9-slim

# Install Chrome and dependencies
RUN apt-get update && \
    apt-get install -y wget gnupg2 && \
    echo "deb http://deb.debian.org/debian/ bookworm main contrib non-free" > /etc/apt/sources.list.d/debian.list && \
    echo "deb http://deb.debian.org/debian-security/ bookworm-security main contrib non-free" >> /etc/apt/sources.list.d/debian.list && \
    echo "deb http://deb.debian.org/debian/ bookworm-updates main contrib non-free" >> /etc/apt/sources.list.d/debian.list && \
    apt-get update && \
    apt-get install -y \
    chromium \
    chromium-driver \
    xvfb \
    libnss3 \
    libglib2.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application files
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    CHROME_BIN=/usr/bin/chromium \
    DISPLAY=:99

# Expose Streamlit port
EXPOSE 8501

# Start Xvfb and run the application
CMD Xvfb :99 -screen 0 1024x768x16 & streamlit run app.py
