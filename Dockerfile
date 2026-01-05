# Stage 1: Build CSS with Node.js
FROM node:20-slim AS css-builder

WORKDIR /app

# Copy package files and Tailwind config
COPY package.json package-lock.json* ./
COPY tailwind.config.js postcss.config.js ./
COPY src/ ./src/
COPY app/templates/ ./app/templates/
COPY app/modules/ ./app/modules/

# Install dependencies and build CSS
RUN npm ci && \
    mkdir -p app/static/css && \
    npm run css:build


# Stage 2: Build Python dependencies
FROM python:3.11-slim AS builder

ENV POETRY_VERSION=1.7.1 \
    POETRY_NO_INTERACTION=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Create venv and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && \
    pip install "poetry==$POETRY_VERSION" "poetry-plugin-export==1.6.0" && \
    poetry export --only main -f requirements.txt --output requirements.txt --without-hashes && \
    pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Copy compiled CSS from css-builder stage
COPY --from=css-builder --chown=appuser:appuser /app/app/static/css/styles.css ./app/static/css/styles.css
USER appuser

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["gunicorn", "app.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--graceful-timeout", "30", "--timeout", "60"]
