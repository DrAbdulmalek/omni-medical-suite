FROM python:3.11-slim

LABEL maintainer="DrAbdulmalek"
LABEL description="Medical Document Processor - Python Core API Server"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ara \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
COPY packages/core/ /app/core/
RUN pip install --no-cache-dir -e ".[api,ocr]"

# Create upload directories
RUN mkdir -p /tmp/medical_docs/uploads /tmp/medical_docs/processed

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["python", "-m", "uvicorn", "core.api_server:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
