#!/usr/bin/env bash
# ============================================
# OmniMedical Suite — Secret Generator
# ============================================
# Generates secure random values for all secrets needed in production.
# Usage: bash scripts/generate-secrets.sh > .env.production
#
# Requirements: openssl, python3

set -euo pipefail

echo "# ============================================"
echo "# OmniMedical Suite — Production Environment"
echo "# Auto-generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "# ============================================"
echo ""
echo "# ---- Application ----"
echo "APP_ENV=production"
echo "APP_URL=https://your-domain.com"
echo "APP_PORT=8000"
echo "APP_LOG_LEVEL=warning"
echo ""

# Database password
DB_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
echo "# ---- Database (PostgreSQL) ----"
echo "DATABASE_URL=postgresql://omnimed_user:${DB_PASS}@db_host:5432/omnimed_prod"
echo "DATABASE_POOL_MIN=5"
echo "DATABASE_POOL_MAX=20"
echo ""

# Redis password
REDIS_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)
echo "# ---- Redis ----"
echo "REDIS_URL=redis://:${REDIS_PASS}@redis_host:6379/0"
echo ""

# Celery
echo "# ---- Celery ----"
echo "CELERY_BROKER_URL=redis://:${REDIS_PASS}@redis_host:6379/1"
echo "CELERY_RESULT_BACKEND=redis://:${REDIS_PASS}@redis_host:6379/2"
echo ""

# Qdrant
QDRANT_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
echo "# ---- Qdrant Vector Database ----"
echo "QDRANT_URL=http://qdrant_host:6333"
echo "QDRANT_API_KEY=${QDRANT_KEY}"
echo "QDRANT_COLLECTION=medical_documents"
echo ""

# NextAuth
NEXTAUTH_SECRET=$(openssl rand -base64 32)
echo "# ---- Authentication (NextAuth) ----"
echo "NEXTAUTH_SECRET=${NEXTAUTH_SECRET}"
echo "NEXTAUTH_URL=https://your-domain.com"
echo ""

# AES key
AES_KEY=$(openssl rand -hex 16)
echo "# ---- Encryption ----"
echo "AES_ENCRYPTION_KEY=${AES_KEY}"
echo ""

# Grafana
GRAFANA_PASS=$(openssl rand -base64 16 | tr -d '/+=' | head -c 20)
echo "# ---- Monitoring ----"
echo "PROMETHEUS_PORT=9090"
echo "GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASS}"
echo ""

# MinIO
MINIO_ACCESS=$(openssl rand -hex 8)
MINIO_SECRET=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
echo "# ---- MinIO / S3 Storage ----"
echo "MINIO_ENDPOINT=minio_host:9000"
echo "MINIO_ACCESS_KEY=${MINIO_ACCESS}"
echo "MINIO_SECRET_KEY=${MINIO_SECRET}"
echo "MINIO_BUCKET=medical-documents"
echo "MINIO_USE_SSL=true"
echo ""

echo "# ---- Rate Limiting ----"
echo "RATE_LIMIT_PER_MINUTE=60"
echo "RATE_LIMIT_BURST=10"
echo ""

echo "# ============================================"
echo "# IMPORTANT: Replace 'your-domain.com' with your actual domain"
echo "# IMPORTANT: Replace 'db_host', 'redis_host', 'qdrant_host', 'minio_host' with actual hosts"
echo "# IMPORTANT: Add your API keys (Mistral, OpenAI) manually"
echo "# ============================================"
