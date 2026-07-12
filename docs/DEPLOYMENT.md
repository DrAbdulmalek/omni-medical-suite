# 🚀 Deployment Guide — Omni Medical Suite

> Consolidated from DEPLOYMENT_GUIDE.md, DEPLOY.md, and README-Deployment.md

---

## Quick Start (v2.0 — 5 minutes)

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
# Grafana:      http://localhost/grafana (password: set GRAFANA_PASSWORD in .env)
# Prometheus:   http://localhost/prometheus
```

### Services Architecture

| Service | Port | Purpose |
|---------|------|---------|
| API + Gradio | 8000 + 7860 | Core processing + Interactive UI |
| Qdrant | 6333 + 6334 | Vector Database (persistent) |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Visualization dashboards |
| PostgreSQL | 5432 | Relational data |
| Redis | 6379 | Cache & message broker |
| Nginx | 80 + 443 | Reverse proxy |

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

### Scaling

```bash
# Scale API workers
docker-compose up -d --scale omnimedical-api=3

# Scale Celery workers
docker-compose up -d --scale celery-worker=5
```

### Quick Backup

```bash
# Backup Qdrant vectors
docker exec omnimedical-qdrant ./qdrant.sh snapshot create

# Backup PostgreSQL
docker exec omnimedical-postgres pg_dump -U postgres omnimedical > backup.sql

# Backup Correction Memory
docker cp omnimedical-api:/data/corrections_v2.db ./backups/
```

---

## 📋 Table of Contents

1. [Quick Deploy to Hugging Face Spaces](#quick-deploy-to-hugging-face-spaces)
2. [Local Development](#2-local-development)
3. [Docker Deployment](#3-docker-deployment)
4. [Hugging Face Spaces (Full Guide)](#4-hugging-face-spaces)
5. [Production Server](#5-production-server)
6. [Backup & Restore](#6-backup--restore)
7. [Troubleshooting](#7-troubleshooting)
8. [Deployment Summary](#8-deployment-summary)

---

## Quick Deploy to Hugging Face Spaces

> Prerequisites: HuggingFace account with `hf` CLI installed and authenticated, Docker SDK on Spaces

```bash
# 1. Create a new Space on HF (Docker SDK)
# Go to: https://huggingface.co/spaces → New Space → Docker

# 2. Clone and push
cd omni-medical-suite
git remote add space https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
git push space main

# 3. Add HF_TOKEN as Secret in Space Settings (for dataset upload)
```

Build will take ~5-15 min first time.

### With LLM Features (requires GPU)

```bash
docker run --gpus all -p 7860:7860 \
  -e ENABLE_LLM=true \
  -e HF_TOKEN=hf_xxx \
  omni-medical-ocr
```

### Test Scanner-Fixer Standalone

```bash
cd scanner-fixer
pip install -r requirements.txt

# Single image
python -c "
from src.scanner_fixer import DocumentPreprocessor
p = DocumentPreprocessor(debug=True)
p.process('test.jpg', 'output.jpg')
"

# Batch processing
python scripts/batch_fixer.py --input ./data/raw --output ./data/cleaned --debug
```

---

## 2. Local Development

### 2.1 Prerequisites

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv git

# Manjaro/Arch
sudo pacman -S python python-pip git
```

### 2.2 Clone the Repository

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
```

### 2.3 Set Up Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
```

### 2.4 Install Dependencies

```bash
# Basic install
pip install -e .

# With extra options
pip install -e .[api,ml,dev,ops]  # All
```

### 2.5 Set Up Environment Variables

```bash
cp .env.example .env
nano .env
```

Enter at minimum:

```env
APP_ENV=development
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here
DB_USER=postgres
DB_PASSWORD=your_db_password
REDIS_PASSWORD=your_redis_password
```

### 2.6 Initialize Database

```bash
# Run PostgreSQL locally (optional)
docker run -d --name postgres-dev \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=omni \
  -p 5432:5432 postgres:16

# Run migrations
alembic upgrade head
```

### 2.7 Run Applications

#### Gradio (HITL)
```bash
python app/gradio_full_hitl.py
# → http://localhost:7860
```

#### FastAPI (Backend)
```bash
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs
```

#### Next.js (Frontend)
```bash
cd apps/web && npm install && npm run dev
# → http://localhost:3000
```

### 2.8 Run Tests

```bash
pytest -v                                    # All
pytest packages/scanner_fixer/ -v           # Specific package
pytest --cov=packages/ --cov-report=html    # With coverage
```

---

## 3. Docker Deployment

### 3.1 Prerequisites

```bash
# Ubuntu/Debian
sudo apt install docker.io docker-compose

# Verify
docker --version
docker-compose --version
```

### 3.2 Build Images

```bash
# Build Gradio image
docker build -f Dockerfile.gradio -t omni-ocr .

# Build full image
docker build -t omni-suite .
```

### 3.3 Gradio Only (Lightweight)

```bash
docker-compose up gradio
# → http://localhost:7860
```

### 3.4 All Services

```bash
# Apps + Infrastructure
docker-compose --profile infra up -d
```

### 3.5 Monitoring Stack

```bash
docker-compose -f docker-compose.yml -f infra/monitoring/docker-compose.monitoring.yml up -d
```

### 3.6 Available Services

| Service | Port | Description |
|---------|------|-------------|
| **Gradio** | 7860 | HITL correction interface |
| **FastAPI** | 8000 | REST API |
| **PostgreSQL** | 5432 | Database (internal) |
| **Redis** | 6379 | Cache (internal) |
| **Qdrant** | 6333 | Vectors (internal) |
| **Prometheus** | 9090 | Metrics (monitoring) |
| **Grafana** | 3000 | Dashboards (monitoring) |

### 3.7 Useful Docker Commands

```bash
docker-compose ps                              # Service status
docker-compose logs -f gradio                  # Gradio logs
docker-compose restart api                     # Restart service
docker-compose down                            # Stop all
docker-compose down -v                         # Stop + remove volumes
```

---

## 4. Hugging Face Spaces

### 4.1 Prerequisites

- Hugging Face account with Access Token (write permissions)

### 4.2 Auto-Deploy Setup

1. In GitHub: `Settings` > `Secrets and variables` > `Actions`
2. Add secret: `HF_TOKEN` = your Hugging Face token
3. Push any change to `hf-space/` — the workflow runs automatically

### 4.3 HF Space Files

| File | Description |
|-------|-------|
| `hf-space/app.py` | Gradio app (460 lines) |
| `hf-space/Dockerfile` | Multi-stage with PaddleOCR pre-cache |
| `hf-space/requirements.txt` | Optimized dependencies |
| `hf-space/README.md` | YAML header |

### 4.4 Manual Deploy

```bash
git clone https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
cp -r hf-space/* omni-medical-ocr/
cd omni-medical-ocr
git add . && git commit -m "deploy" && git push
```

### 4.5 Link

```
https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
```

---

## 5. Production Server

### 5.1 Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
```

### 5.2 Clone and Configure

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite

# Set up production environment
cat > .env.production << EOF
APP_ENV=production
DEBUG=False
LOG_LEVEL=INFO
ALLOWED_HOSTS=your-domain.com
SECRET_KEY=$(openssl rand -base64 32)
JWT_SECRET_KEY=$(openssl rand -base64 32)
DB_HOST=postgres
DB_PASSWORD=$(openssl rand -base64 24)
REDIS_PASSWORD=$(openssl rand -base64 24)
GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 24)
EOF
```

### 5.3 Run Production

```bash
docker-compose --env-file .env.production --profile infra up -d
```

### 5.4 Nginx Reverse Proxy

```bash
sudo apt install nginx

sudo tee /etc/nginx/sites-available/omni-medical << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:7860;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /metrics {
        allow 127.0.0.1;
        deny all;
        proxy_pass http://localhost:9090;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/omni-medical /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

### 5.5 SSL (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 6. Backup & Restore

### 6.1 Automatic Backup

```bash
# Manual trigger
python scripts/backup.py

# Backups saved to /app/backups/:
#   database/  — pg_dump (SQL)
#   redis/     — RDB snapshot
#   files/     — app/, packages/, src/, config/
```

### 6.2 Restore

```bash
# Database
docker exec -i postgres psql -U omni_user -d omni < backups/database/omni_medical_YYYYMMDD.sql

# Redis
docker exec -i redis redis-cli --rdb backups/redis/redis_YYYYMMDD.rdb
```

### 6.3 Daily Schedule (cron)

```bash
0 2 * * * cd /opt/omni-medical-suite && python scripts/backup.py
```

---

## 7. Troubleshooting

### 7.1 Gradio Not Working

```bash
docker-compose logs gradio        # Check logs
docker-compose restart gradio     # Restart
sudo netstat -tulpn | grep 7860  # Check port
```

### 7.2 Database Not Connected

```bash
docker-compose ps postgres        # Check status
docker-compose restart postgres   # Restart
docker-compose exec api python -c "import asyncpg; print('ok')"  # Test connection
```

### 7.3 OCR Not Working

```bash
# Install Arabic Tesseract language
docker-compose exec api apt-get install -y tesseract-ocr-ara

# Verify PaddleOCR
docker-compose exec api python -c "import paddleocr; print('OK')"

# Restart
docker-compose restart gradio
```

### 7.4 HF Space Build Failure

1. Check build log on the Space page
2. Verify `Dockerfile` and `requirements.txt`
3. Reduce image size using `python:3.11-slim`
4. Ensure `.dockerignore` excludes large files

### 7.5 Health Check

```bash
curl http://localhost:8000/health           # Full check
curl http://localhost:8000/health/liveness   # Liveness
curl http://localhost:8000/health/readiness  # Readiness
```

---

## 8. Deployment Summary

| Method | Level | Time |
|---------|---------|-------|
| Local | Development | 5 minutes |
| Docker | Dev/Production | 10 minutes |
| HF Spaces | Demo/Production | 15 minutes |
| Production Server (VPS) | Production | 30 minutes |

**Start with HF Spaces or Docker for the fastest experience!**

---

## Support

- **GitHub Issues**: https://github.com/DrAbdulmalek/omni-medical-suite/issues
- **Hugging Face Space**: https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
