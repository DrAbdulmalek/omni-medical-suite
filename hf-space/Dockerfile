FROM python:3.11-slim

LABEL maintainer="Dr. Abdulmalek <drabdulmalek@proton.me>"
LABEL description="Omni Medical OCR — Arabic Medical Text Extraction"

WORKDIR /app

# System deps for OCR + OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src/ src/
COPY packages/ packages/
COPY config/ config/

# Create data dirs
RUN mkdir -p uploads crops data

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Pre-download PaddleOCR models
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='ar', show_log=False)" || true

EXPOSE 7860

CMD ["python", "app.py"]