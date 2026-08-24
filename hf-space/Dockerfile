# =============================================================================
# Omni Medical OCR — HuggingFace Spaces Dockerfile (Optimized)
# =============================================================================
# Multi-stage build optimized for HF Spaces:
#   Stage 1 (builder): Install pip packages + pre-cache PaddleOCR models
#   Stage 2 (runtime): Minimal image with only runtime deps
#
# Key optimizations:
#   - PaddleOCR models pre-downloaded during build (fast cold start)
#   - Non-root user (appuser:1000) for HF Spaces compatibility
#   - Health check on port 7860
#   - Transformers cached separately for lazy translation loading
# =============================================================================

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Debian trixie no longer provides the obsolete libgl1-mesa-glx package.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Pre-download PaddleOCR Arabic models (saves ~30s on cold start)
RUN PYTHONPATH=/install/lib/python3.11/site-packages \
    python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='ar', show_log=False)" || true

# ---- Stage 2: Runtime ----
FROM python:3.11-slim AS runtime

LABEL maintainer="Dr. Abdulmalek <drabdulmalek@proton.me>"
LABEL description="Omni Medical OCR — Arabic Medical Text Extraction"
LABEL org.opencontainers.image.source="https://github.com/DrAbdulmalek/omni-medical-suite"

WORKDIR /app

# Runtime system deps only (no build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

COPY app.py .
COPY src/ src/
COPY packages/ packages/
COPY config/ config/

RUN mkdir -p uploads crops data .cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface

COPY --from=builder /root/.paddleocr /home/appuser/.paddleocr
RUN chown -R appuser:appuser /home/appuser/.paddleocr

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=120s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860')" || exit 1

CMD ["python", "app.py"]