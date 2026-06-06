# reTerminal ePaper Dashboard — Dockerfile
# Multi-stage: Python (Flask) + Node (Nuxt 4) in one container.
# Flask serves dashboard rendering & builds on :8088.
# Nuxt Nitro serves web UI + devices/screens API on :3000.

# ── Stage 1: Python base ──
FROM python:3.11-slim AS python-base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg \
    libxshmfence-dev libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium && playwright install-deps chromium 2>/dev/null || true
RUN pip install --no-cache-dir platformio==6.1.19 esptool==5.2.0 \
    && pio platform install "espressif32" 2>/dev/null || true

# ── Stage 2: Nuxt build ──
FROM node:22-slim AS nuxt-build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN NODE_ENV=production npm run build

# ── Stage 3: Runtime ──
FROM python-base AS runtime
WORKDIR /app

# Install Node.js 22 for Nuxt Nitro server (must match build stage)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy Python app
COPY server/ ./server/
COPY flasher/ ./flasher/

# Copy Nuxt built output (already built in stage 2)
COPY --from=nuxt-build /app/web/.output/ ./web/.output/
COPY --from=nuxt-build /app/web/package.json ./web/

# Create data directory for SQLite
RUN mkdir -p web/.data

EXPOSE 8088 3000

# Startup script: Flask on :8088, Nuxt on :3000
COPY <<EOF /app/start.sh
#!/bin/sh
set -e
mkdir -p /app/web/.data
echo "[start] Flask → :8088"
python3 server/server.py &
sleep 2
echo "[start] Nuxt  → :3000"
cd /app/web && exec node .output/server/index.mjs
EOF

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
