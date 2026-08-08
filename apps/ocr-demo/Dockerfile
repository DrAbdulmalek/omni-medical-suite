FROM python:3.11-slim

LABEL maintainer="Dr. Abdulmalek Tamer Al-husseini <drabdulmalek@proton.me>"
LABEL description="Omni Medical OCR — Arabic Medical Text Extraction"

WORKDIR /app

# System dependencies for OCR + OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for HF Spaces security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Download PaddleOCR models at build time (faster cold start)
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='ar', show_log=False)" || true

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/')" || exit 1

CMD ["python", "app.py"]