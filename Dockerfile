# =============================================================================
# DEPRECATED — This Dockerfile is kept for backward compatibility only.
# =============================================================================
# Use the canonical Dockerfiles under infrastructure/docker/ instead:
#   - infrastructure/docker/Dockerfile.api   (FastAPI backend)
#   - infrastructure/docker/Dockerfile.web   (Next.js frontend)
#   - infrastructure/docker/Dockerfile.training  (ML training)
#
# For local development, use docker-compose:
#   docker compose -f infrastructure/docker/docker-compose.yml up -d
# =============================================================================

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

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/services/api

# Install API dependencies
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
