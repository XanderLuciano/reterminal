# reTerminal ePaper Dashboard Server
#
# Multi-stage: Python deps first, then Playwright browser, then app.
# The web flasher UI is served as static files — flashing happens
# client-side in the browser via Web Serial API (no USB passthrough needed).

FROM python:3.11-slim AS base

WORKDIR /app

# System deps for Playwright + BLE
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    libxshmfence-dev \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium
RUN playwright install chromium && \
    playwright install-deps chromium 2>/dev/null || true

# ── Runtime stage ──

FROM base AS runtime

WORKDIR /app

COPY . .

# The firmware source isn't needed at runtime, but keep flasher/build_handler.py
# which imports from it. The /api/build endpoint runs PlatformIO builds.
# If you're not using the web flasher, you can skip the PlatformIO install below.

# PlatformIO (needed for web flasher builds)
RUN pip install --no-cache-dir platformio && \
    pio platform install "espressif32" 2>/dev/null || true

EXPOSE 8088

# Default: run the dashboard server. Override CMD if needed.
CMD ["python3", "server/server.py"]
