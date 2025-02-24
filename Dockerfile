# Stage 1: Build Python dependencies
FROM --platform=linux/arm64 python:3.9-slim as builder

WORKDIR /install

# Install Python dependencies
COPY requirements.txt .
RUN pip install --prefix=/install --no-warn-script-location -r requirements.txt

# Stage 2: Final image
FROM --platform=linux/arm64 mcr.microsoft.com/playwright/python:v1.41.1-jammy

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

# Install additional Python packages
RUN pip install streamlit

# Expose Streamlit port
EXPOSE 8501

# Start Xvfb and run the application
CMD Xvfb :99 -screen 0 1024x768x16 & streamlit run app.py
