# ---- Base stage ----
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set PYTHONPATH so `from app.core.config import ...` resolves correctly
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/services/api

# Copy API requirements first for better caching
COPY services/api/requirements.txt ./services/api/requirements.txt
RUN pip install --no-cache-dir -r services/api/requirements.txt

# ---- Development stage ----
FROM base AS dev

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt || true

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000 7860

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- Production stage ----
FROM base AS production

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
