# ─────────────────────────────────────────────────────────────────────────
# Stage 1 – Builder
# Installs system build-dependencies and Python packages into a virtualenv
# that is later copied to the lean runtime image.
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System packages required at build time (tesseract for OCR, mesa for OpenCV)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        tesseract-ocr \
        tesseract-ocr-ara \
        libgl1-mesa-glib \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────
# Stage 2 – Runtime
# Copies only the installed Python packages and the application source,
# keeping the final image as small as possible.
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_HOME="/opt/omni-medical-suite"

WORKDIR ${APP_HOME}

# Install only runtime system dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ara \
        libgl1-mesa-glib \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python site-packages from the builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create a non-root user for security
RUN groupadd -r omniuser && useradd -r -g omniuser -d ${APP_HOME} -s /sbin/nologin omniuser && \
    mkdir -p ${APP_HOME}/uploads ${APP_HOME}/data && \
    chown -R omniuser:omniuser ${APP_HOME}

# Copy application source code
COPY --chown=omniuser:omniuser app/ ./app/

# Expose the API port
EXPOSE 8000

# Health check – matches the /health/live endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Run as non-root user
USER omniuser

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
