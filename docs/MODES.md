# 🚀 Deployment Modes

OmniMedical Suite supports three deployment modes designed for different use cases and resource requirements.

## Quick Start

```bash
# Lite mode (local development)
cp .env.lite .env
docker compose -f docker-compose.lite.yml up

# Standard mode (team staging)  
cp .env.standard .env
docker compose -f docker-compose.standard.yml up

# Production mode
cp .env.production .env
# Edit .env — change ALL passwords and secrets!
docker compose -f docker-compose.prod.yml up -d
```

## Mode Comparison

| Feature | Lite | Standard | Production |
|---------|:----:|:--------:|:----------:|
| **Purpose** | Local dev & testing | Staging & small teams | Multi-user production |
| **Web UI** | ✅ | ✅ | ✅ |
| **API Server** | ✅ (1 worker) | ✅ (2 workers) | ✅ (4+ workers) |
| **Database** | SQLite | PostgreSQL | PostgreSQL (managed) |
| **Redis** | ❌ | ✅ | ✅ (auth + persistence) |
| **Celery Workers** | ❌ | ✅ (2) | ✅ (4+, beat scheduler) |
| **Vector Search (Qdrant)** | ❌ | ✅ | ✅ |
| **Nginx Reverse Proxy** | ❌ | ❌ | ✅ (TLS termination) |
| **Monitoring (Prometheus+Grafana)** | ❌ | ✅ | ✅ |
| **Distributed Tracing (Tempo)** | ❌ | ❌ | ✅ |
| **Load Balancer** | ❌ | ❌ | ✅ |
| **WebSocket Server** | ❌ | ❌ | ✅ |
| **OCR Engine** | paddleocr | ensemble | ensemble (GPU) |
| **PHI Protection** | medium | high | high + audit |
| **Min RAM** | 2 GB | 8 GB | 16 GB+ |
| **Min CPUs** | 1 | 2-4 | 8+ |

## Mode Details

### 🔹 Lite Mode
Designed for developers working locally. Only runs the web frontend and API server with SQLite.

**When to use:**
- Local development and feature testing
- Quick prototyping
- Single-user environments
- CI/CD testing pipelines
- Resource-constrained machines

**Limitations:**
- No async task processing (Celery)
- No vector search capabilities
- No monitoring dashboards
- SQLite has limited concurrency

### 🔹 Standard Mode
Full-featured deployment for small teams and staging environments.

**When to use:**
- Team development environments
- Staging/pre-production testing
- Self-hosted single-server deployments
- Small clinic or lab setups
- Demo environments

**Features over Lite:**
- PostgreSQL for concurrent access
- Redis for caching and Celery message broker
- Async task processing for heavy OCR jobs
- Vector search via Qdrant
- Monitoring dashboards (Prometheus + Grafana)

### 🔹 Production Mode
Enterprise-grade deployment with high availability, security, and monitoring.

**When to use:**
- Multi-tenant deployments
- HIPAA-compliant environments
- Public-facing services
- High-traffic applications
- Healthcare institution deployments

**Features over Standard:**
- TLS termination via Nginx
- Distributed tracing (Tempo)
- Load balancing for API servers
- WebSocket for real-time notifications
- GPU-accelerated OCR
- PHI audit trail with 7-year retention
- Resource limits and health checks
- Sentry error tracking

## Switching Modes

```bash
# Save current config
cp .env .env.backup

# Switch to standard mode
cp .env.standard .env
docker compose -f docker-compose.lite.yml down
docker compose -f docker-compose.standard.yml up -d

# Verify services
curl http://localhost:8000/health
curl http://localhost:3000
```

## Makefile Commands

```bash
make lite        # Start lite mode
make standard    # Start standard mode
make prod        # Start production mode
make status      # Check running services
```

## Environment Variables Reference

See individual env files for complete variable lists:
- `.env.lite` — 20 variables (essential only)
- `.env.standard` — 45 variables (staging-ready)
- `.env.production` — 130+ variables (enterprise)
