# =============================================================================
# Omni Medical Suite — Production Multi-Stage Dockerfile (API)
# =============================================================================
# FastAPI API Worker — lightweight, no heavy ML engines
# For the Gradio HITL interface (with PaddleOCR/EasyOCR), use Dockerfile.gradio
#
# Build:  docker build --target production -t omni-api:latest .
# Run:    docker run -p 8000:8000 --env-file .env omni-api:latest
# =============================================================================

# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time system dependencies (gcc, libpq for psycopg/asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Copy requirements (layered: base → api → ml)
# NOTE: ml.txt has CV/NLP deps but NOT PaddlePaddle (that's in gradio.txt)
COPY requirements/base.txt ./requirements/base.txt
COPY requirements/api.txt ./requirements/api.txt
COPY requirements/ml.txt  ./requirements/ml.txt

# Install Python dependencies in layers (better Docker caching)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements/base.txt && \
    pip install --no-cache-dir -r requirements/api.txt && \
    pip install --no-cache-dir -r requirements/ml.txt && \
    pip install --no-cache-dir asyncpg uvloop httptools

# ─── Stage 2: Production ────────────────────────────────────────────────────
FROM python:3.11-slim AS production

LABEL maintainer="Dr. Abdulmalek Al-husseini"
LABEL description="Omni Medical Suite - Production API Worker (FastAPI)"
LABEL version="2.2.0"
LABEL org.opencontainers.image.source="https://github.com/DrAbdulmalek/omni-medical-suite"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

# Runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Verify Tesseract installation
RUN tesseract --version && tesseract --list-langs

# Create non-root user
RUN groupadd -r omni && useradd -r -g omni -u 1000 -m -d /app omni

# Create application directories
RUN mkdir -p /app/uploads /app/results /app/logs /app/data \
             /app/encrypted /app/model /app/backups && \
    chown -R omni:omni /app

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=omni:omni . .

# The repository provides the production entrypoint as entrypoint.sh.
# Fail the image build if it is missing instead of producing a broken image.
RUN test -f /app/entrypoint.sh \
    && chmod 0755 /app/entrypoint.sh

# Switch to non-root user
USER omni

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
