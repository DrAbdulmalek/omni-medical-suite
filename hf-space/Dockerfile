# =============================================================================
# Omni Medical OCR — HuggingFace Spaces Dockerfile (Optimized)
# =============================================================================
# Multi-stage build optimized for HF Spaces.
#
# The runtime image is deliberately non-root. PaddleOCR models are downloaded
# lazily at runtime because PaddleOCR's cache location is version-dependent;
# copying a hard-coded /root/.paddleocr directory makes the build brittle.
# =============================================================================

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Do not pre-download PaddleOCR models here. PaddleOCR changes its cache
# location between releases, and model downloads are safely performed lazily
# by the non-root runtime user.

# ---- Stage 2: Runtime ----
FROM python:3.11-slim AS runtime

LABEL maintainer="Dr. Abdulmalek <drabdulmalek@proton.me>"
LABEL description="Omni Medical OCR — Arabic Medical Text Extraction"
LABEL org.opencontainers.image.source="https://github.com/DrAbdulmalek/omni-medical-suite"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/uploads /app/crops /app/data /app/.cache/huggingface /home/appuser/.paddlex \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

COPY app.py .
COPY src/ src/
COPY packages/ packages/
COPY config/ config/

ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=120s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860')" || exit 1

CMD ["python", "app.py"]
