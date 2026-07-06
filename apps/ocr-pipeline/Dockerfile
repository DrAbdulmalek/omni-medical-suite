# ─── Stage 1: Base system dependencies ────────────────────────────────────────
FROM python:3.11-slim AS base

# System dependencies for OCR and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata/ \
    HF_HOME=/app/models \
    TRANSFORMERS_CACHE=/app/models \
    PYTHONPATH=/app

WORKDIR /app

# ─── Stage 2: Python dependencies ─────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Stage 3: Application ─────────────────────────────────────────────────────
FROM deps AS app

# Copy project files
COPY . .

# Create model cache directory
RUN mkdir -p /app/models /app/data

# Expose Gradio default port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/')" || exit 1

# Run Gradio application
CMD ["python", "app.py"]