# Production Dockerfile for Nuxt 4 app
FROM node:22-slim AS base

WORKDIR /app

# Install Python for Flask server
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv curl \
    && rm -rf /var/lib/apt/lists/*

# Nuxt output
COPY .output/ .output/

# Create data directory for SQLite
RUN mkdir -p .data

EXPOSE 3000

CMD ["sh", "-c", "node .output/server/index.mjs"]
