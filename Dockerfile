FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers (only if using CRYPTO_TOOLBOX_NEW=1)
# Note: This adds ~300MB to image size
RUN pip install playwright && playwright install chromium --with-deps

COPY . .

# Environment variables
ENV CRYPTO_TOOLBOX_NEW=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Use single worker for Playwright compatibility
CMD ["uvicorn","api.main:app","--host","0.0.0.0","--port","8000","--workers","1"]
