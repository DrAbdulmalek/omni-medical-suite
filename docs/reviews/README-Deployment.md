# 🐳 OmniMedical Suite v2.0 — Deployment Guide

## Quick Start (5 minutes)

```bash
# 1. Clone and enter directory
cd omni-medical-suite

# 2. Copy environment file
cp .env.example .env
# Edit .env with your secure passwords

# 3. Start all services
docker-compose up -d

# 4. Verify health
curl http://localhost/api/health

# 5. Open interfaces
# Gradio UI:    http://localhost/
# API Docs:     http://localhost/api/docs
# Grafana:      http://localhost/grafana (admin/admin)
# Prometheus:   http://localhost/prometheus
```

## Services Architecture

| Service | Port | Purpose |
|---------|------|---------|
| API + Gradio | 8000 + 7860 | Core processing + Interactive UI |
| Qdrant | 6333 + 6334 | Vector Database (persistent) |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Visualization dashboards |
| PostgreSQL | 5432 | Relational data |
| Redis | 6379 | Cache & message broker |
| Nginx | 80 + 443 | Reverse proxy |

## Monitoring

### Key Metrics
- `omnimedical_fusion_confidence_avg` — OCR fusion quality
- `omnimedical_context_conflicts_total` — Medical safety violations
- `omnimedical_promotion_queue_size` — Auto-promotion backlog
- `omnimedical_dedup_reduction_ratio` — Deduplication efficiency

### Alerts
- **HighErrorRate** — Critical (>10% errors)
- **MedicalContextConflict** — Critical (safety violation)
- **FusionLowConfidence** — Warning (<70% confidence)
- **QdrantDown** — Critical (vector DB unavailable)

## Scaling

```bash
# Scale API workers
docker-compose up -d --scale omnimedical-api=3

# Scale Celery workers
docker-compose up -d --scale celery-worker=5
```

## Backup

```bash
# Backup Qdrant vectors
docker exec omnimedical-qdrant ./qdrant.sh snapshot create

# Backup PostgreSQL
docker exec omnimedical-postgres pg_dump -U postgres omnimedical > backup.sql

# Backup Correction Memory
docker cp omnimedical-api:/data/corrections_v2.db ./backups/
```
