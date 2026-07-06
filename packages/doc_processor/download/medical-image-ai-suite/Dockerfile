# -*- coding: utf-8 -*-
# Dockerfile for the OmniMedical Suite — multi-stage build.
#
# Stage 1 (builder): Install system build dependencies and Python packages.
# Stage 2 (runtime): Copy installed packages, application code, and set up
#                     a non-root user for production security.
#
# Build:
#   docker build -t omni-medical-suite .
#
# Run:
#   docker run --rm -p 8000:8000 omni-medical-suite

# ==================================================================
# Stage 1 — Builder
# ==================================================================
FROM python:3.10-slim AS builder

# Install system-level build dependencies required by some Python packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements and install Python packages into a dedicated directory.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==================================================================
# Stage 2 — Runtime
# ==================================================================
FROM python:3.10-slim AS runtime

LABEL maintainer="OmniMedical Suite <infra@omnimedical.dev>"
LABEL description="Medical Image AI Suite — OCR, Fusion, Dictionary, Infrastructure"
LABEL org.opencontainers.image.source="https://github.com/omnimedical/suite"

# Install runtime system dependencies including Tesseract OCR with Arabic support.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-data-ara \
        tesseract-data-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage.
COPY --from=builder /install /usr/local

# Create non-root user and group for security.
RUN groupadd --gid 1000 omniuser \
    && useradd --uid 1000 --gid omniuser --create-home --shell /bin/bash omniuser

WORKDIR /app

# Copy application source code.
COPY . .

# Ensure non-root user owns the application directory.
RUN chown -R omniuser:omniuser /app

USER omniuser

# Expose the default API port.
EXPOSE 8000

# Default health-check endpoint for container orchestrators.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the main processing pipeline.
CMD ["python", "-u", "main_pipeline.py"]
