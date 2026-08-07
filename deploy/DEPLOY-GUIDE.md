# Omni Medical Suite — Production Deployment Guide

## Package Contents

```
omni-deploy/
├── deploy.sh                    # Main automated deployment script
├── verify.sh                    # Post-deployment verification
├── backup.sh                    # Backup & restore utilities
├── setup-ssl.sh                 # SSL certificate setup helper
├── Dockerfile                   # Multi-stage production build
├── docker-compose.prod.yml      # Full production orchestration
├── docker-entrypoint.sh         # Container startup script
├── .env.production              # Environment template
├── .dockerignore                # Build context exclusions
├── supervisord.conf             # Process manager config
├── nginx/
│   ├── omni-medical.conf        # Nginx reverse proxy + SSL
│   └── ssl-params.conf         # SSL/TLS parameters
└── DEPLOY-GUIDE.md             # This file
```

## Prerequisites

| Requirement | Specification |
|-------------|---------------|
| OS | Ubuntu 22.04 or 24.04 LTS |
| CPU | 2+ cores |
| RAM | 4+ GB (8 GB recommended for EasyOCR) |
| Storage | 20+ GB SSD |
| Domain | DNS A record pointing to server IP |
| Ports | 22 (SSH), 80 (HTTP), 443 (HTTPS) open |

## Quick Deploy (One Command)

```bash
# 1. Upload the omni-deploy/ directory to your server
scp -r omni-deploy/ root@YOUR_SERVER_IP:/tmp/omni-deploy

# 2. SSH into your server
ssh root@YOUR_SERVER_IP

# 3. Run the deployment script
cd /tmp/omni-deploy
chmod +x deploy.sh
sudo ./deploy.sh --domain your-domain.com --email admin@your-domain.com
```

## Step-by-Step Deployment

### Phase 1: Server Preparation

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# Install Nginx + Certbot
apt install -y nginx certbot python3-certbot-nginx

# Configure UFW firewall
ufw enable
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
```

### Phase 2: Project Setup

```bash
# Clone repository
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git /opt/omni-medical-suite
cd /opt/omni-medical-suite

# Copy deployment files from omni-deploy/
cp /tmp/omni-deploy/Dockerfile .
cp /tmp/omni-deploy/docker-compose.prod.yml .
cp /tmp/omni-deploy/docker-entrypoint.sh .
cp /tmp/omni-deploy/.dockerignore .
cp /tmp/omni-deploy/.env.production .env

# Create data directories
mkdir -p data/uploads data/results data/encrypted data/model logs backups

# Generate secrets and edit .env
# IMPORTANT: Replace ALL CHANGE_ME values!
openssl rand -hex 32    # For DB_PASSWORD, JWT_SECRET, APP_SECRET
openssl rand -base64 32 # For NEXTAUTH_SECRET, ENCRYPTION_KEY

# Edit .env with your values
nano .env
```

### Phase 3: SSL Certificate

```bash
# Get Let's Encrypt certificate
certbot certonly --nginx -d your-domain.com --agree-tos -m admin@your-domain.com

# Generate DH parameters
openssl dhparam -out /etc/nginx/dhparam.pem 2048

# Setup auto-renewal
echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx'" | crontab -
```

### Phase 4: Nginx Configuration

```bash
# Copy and enable Nginx config
cp /tmp/omni-deploy/nginx/omni-medical.conf /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/omni-medical.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Replace DOMAIN placeholder
sed -i 's/DOMAIN/your-domain.com/g' /etc/nginx/sites-available/omni-medical.conf

# Test and reload
nginx -t && systemctl reload nginx
```

### Phase 5: Build & Launch

```bash
cd /opt/omni-medical-suite

# Build Docker images
docker compose -f docker-compose.prod.yml build --no-cache

# Launch all services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps
```

### Phase 6: Verification

```bash
# Run the verification script
cd /tmp/omni-deploy
chmod +x verify.sh
./verify.sh --domain your-domain.com

# Manual checks
curl -f http://localhost:8000/health
curl -f https://your-domain.com/health
```

## Post-Deployment URLs

| Service | URL |
|---------|-----|
| Website | `https://your-domain.com` |
| API Docs (Swagger) | `https://your-domain.com/docs` |
| API Docs (ReDoc) | `https://your-domain.com/redoc` |
| Health Check | `https://your-domain.com/health` |
| OCR Process | `POST https://your-domain.com/api/v1/ocr/process` |

## Useful Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f celery-worker

# Restart a service
docker compose -f docker-compose.prod.yml restart api

# Scale API workers
docker compose -f docker-compose.prod.yml up -d --scale api=2

# Stop all services
docker compose -f docker-compose.prod.yml down

# Full restart (rebuild + restart)
docker compose -f docker-compose.prod.yml up -d --build

# Database shell
docker exec -it omni-postgres psql -U omni_user -d omni_medical

# Redis shell
docker exec -it omni-redis redis-cli

# Backup
./backup.sh backup

# Restore
./backup.sh restore 20260808_120000
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 502 Bad Gateway | `docker compose -f docker-compose.prod.yml logs api` |
| DB connection error | Verify DATABASE_URL uses `postgres:5432` not `localhost` |
| Tesseract not found | Rebuild: `docker compose -f docker-compose.prod.yml build --no-cache` |
| SSL errors | `certbot certificates` and `nginx -t` |
| Container won't start | `docker compose -f docker-compose.prod.yml logs <service>` |
| Permission denied on uploads | `docker exec omni-api chown -R omni:omni /app/uploads` |
| Out of memory | Increase `--workers` in Dockerfile or add swap |
| Slow OCR | Set `OCR_DEVICE=cuda` if GPU available, or reduce `OCR_BATCH_SIZE` |

## Security Checklist

- [x] HTTPS only (HTTP → HTTPS redirect)
- [x] Strong DB_PASSWORD (32-char random hex)
- [x] Strong JWT_SECRET_KEY (32-char random hex)
- [x] UFW enabled (only 22/80/443 open)
- [x] .env excluded from Git
- [x] SSL auto-renewal configured (Let's Encrypt)
- [x] Non-root Docker user (omni:1000)
- [x] Security headers (HSTS, CSP, X-Frame-Options)
- [x] Rate limiting configured
- [x] DB/Redis/Qdrant ports not exposed externally

## Architecture

```
Internet → Nginx (443/SSL) → Docker Network
                                    ├── api (FastAPI :8000)
                                    ├── celery-worker
                                    ├── celery-beat
                                    ├── postgres (:5432 internal)
                                    ├── redis (:6379 internal)
                                    └── qdrant (:6333 internal)
```
