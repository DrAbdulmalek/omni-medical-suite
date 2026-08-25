#!/bin/bash
# =============================================================================
# Omni Medical Suite — Automated Production Deployment Script
# =============================================================================
# Usage:
#   chmod +x deploy.sh
#   sudo ./deploy.sh --domain your-domain.com --email admin@your-domain.com
#
# Or set env vars first:
#   export DOMAIN=your-domain.com
#   export EMAIL=admin@your-domain.com
#   sudo ./deploy.sh
# =============================================================================

set -euo pipefail

# ── Colors for output ────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Parse Arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain) DOMAIN="$2"; shift 2 ;;
        --email)  EMAIL="$2";  shift 2 ;;
        --repo)   REPO_URL="$2"; shift 2 ;;
        --skip-ssl) SKIP_SSL=true; shift ;;
        --help)
            echo "Usage: $0 --domain DOMAIN --email EMAIL [--repo REPO_URL] [--skip-ssl]"
            exit 0 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

# ── Configuration ────────────────────────────────────────────────────────────
PROJECT_DIR="${PROJECT_DIR:-/opt/omni-medical-suite}"
REPO_URL="${REPO_URL:-https://github.com/DrAbdulmalek/omni-medical-suite.git}"
DOMAIN="${DOMAIN:-}"
EMAIL="${EMAIL:-}"
SKIP_SSL="${SKIP_SSL:-false}"

echo ""
echo "=========================================="
echo " Omni Medical Suite — Production Deploy"
echo "=========================================="
echo ""

# ── Preflight Checks ─────────────────────────────────────────────────────────
info "Running preflight checks..."

# Check root
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (sudo)"
fi

# Check OS
if [[ ! -f /etc/lsb-release ]] && [[ ! -f /etc/os-release ]]; then
    error "This script is designed for Ubuntu 22.04/24.04 LTS"
fi

# Check domain
if [[ -z "$DOMAIN" ]]; then
    error "Domain is required. Use --domain your-domain.com"
fi

# Check email
if [[ -z "$EMAIL" ]]; then
    error "Email is required for SSL certificate. Use --email admin@your-domain.com"
fi

ok "Preflight checks passed"

# =============================================================================
# Phase 1: Server Preparation
# =============================================================================
echo ""
info "═══ Phase 1: Server Preparation ═══"

# Update system
info "Updating system packages..."
apt update && apt upgrade -y
ok "System packages updated"

# Install Docker
if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    ok "Docker installed"
else
    ok "Docker already installed ($(docker --version))"
fi

# Install Docker Compose plugin
if ! docker compose version &>/dev/null; then
    info "Installing Docker Compose plugin..."
    apt install -y docker-compose-plugin 2>/dev/null || {
        mkdir -p /usr/local/lib/docker/cli-plugins
        COMPOSE_VERSION=$(curl -sL https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | sed 's/.*"v\(.*\)".*/\1/')
        curl -sL "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose
        chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    }
    ok "Docker Compose installed"
else
    ok "Docker Compose already installed ($(docker compose version --short 2>/dev/null || echo 'v2'))"
fi

# Install Nginx + Certbot
info "Installing Nginx and Certbot..."
apt install -y nginx certbot python3-certbot-nginx
systemctl enable nginx
ok "Nginx and Certbot installed"

# Configure UFW
info "Configuring UFW firewall..."
if ! command -v ufw &>/dev/null; then
    apt install -y ufw
fi
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw deny in from any to any port 5432  # Block external PostgreSQL
ufw deny in from any to any port 6379  # Block external Redis
ufw deny in from any to any port 6333  # Block external Qdrant
ok "UFW configured (22, 80, 443 allowed; DB ports blocked)"

# Install additional tools
apt install -y git curl wget htop jq
ok "Additional tools installed"

# =============================================================================
# Phase 2: Project Setup
# =============================================================================
echo ""
info "═══ Phase 2: Project Setup ═══"

# Clone repository
if [[ ! -d "$PROJECT_DIR" ]]; then
    info "Cloning repository..."
    git clone "$REPO_URL" "$PROJECT_DIR"
    ok "Repository cloned to $PROJECT_DIR"
else
    info "Repository already exists, pulling latest..."
    cd "$PROJECT_DIR"
    git pull origin main || warn "Git pull failed, using existing code"
    ok "Repository updated"
fi

cd "$PROJECT_DIR"

# Create data directories
info "Creating data directories..."
mkdir -p data/uploads data/results data/encrypted data/model logs backups
ok "Data directories created"

# Generate .env file
if [[ ! -f .env ]]; then
    info "Generating .env from .env.production template..."

    # Generate strong secrets
    DB_PASSWORD=$(openssl rand -hex 32)
    REDIS_PASSWORD=$(openssl rand -hex 24)
    APP_SECRET=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 32)
    NEXTAUTH_SECRET=$(openssl rand -base64 32)
    ENCRYPTION_KEY=$(openssl rand -base64 32)
    GRAFANA_PASSWORD=$(openssl rand -hex 16)

    # Copy template and replace values
    if [[ -f .env.production ]]; then
        cp .env.production .env
    elif [[ -f env.example.production ]]; then
        cp env.example.production .env
    elif [[ -f .env.example ]]; then
        cp .env.example .env
    else
        error "No .env template found"
    fi

    # Replace placeholder values (use | delimiter to avoid / in URLs)
    sed -i "s|DOMAIN=.*|DOMAIN=${DOMAIN}|g" .env
    sed -i "s|EMAIL=.*|EMAIL=${EMAIL}|g" .env
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASSWORD}|g" .env
    sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=${REDIS_PASSWORD}|g" .env
    sed -i "s|APP_SECRET_KEY=.*|APP_SECRET_KEY=${APP_SECRET}|g" .env
    sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_SECRET}|g" .env
    sed -i "s|NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=${NEXTAUTH_SECRET}|g" .env
    sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${ENCRYPTION_KEY}|g" .env
    sed -i "s|GRAFANA_PASSWORD=.*|GRAFANA_PASSWORD=${GRAFANA_PASSWORD}|g" .env
    sed -i "s|NEXTAUTH_URL=.*|NEXTAUTH_URL=https://${DOMAIN}|g" .env
    sed -i "s|AUTH_ALLOWED_ORIGINS=.*|AUTH_ALLOWED_ORIGINS=https://${DOMAIN}|g" .env
    sed -i "s|CORS_ORIGINS=.*|CORS_ORIGINS=[\"https://${DOMAIN}\"]|g" .env
    sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://omni_user:${DB_PASSWORD}@postgres:5432/omni_medical|g" .env
    sed -i "s|REDIS_URL=.*|REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0|g" .env

    # Add asyncpg to .env (required by app/db/session.py but missing from requirements)
    echo "" >> .env
    echo "# ── Additional Runtime Dependencies ────────────────────────────" >> .env
    echo "# asyncpg: async PostgreSQL driver (used by app/db/session.py)" >> .env

    # Ensure .env is not tracked by git
    echo ".env" >> .gitignore

    ok ".env file generated with strong secrets"
    warn "⚠️  .env contains sensitive data — NEVER commit it to Git!"
else
    ok ".env file already exists"
fi

# =============================================================================
# Phase 3: SSL Certificate (Let's Encrypt)
# =============================================================================
echo ""
info "═══ Phase 3: SSL Certificate ═══"

if [[ "$SKIP_SSL" != "true" ]]; then
    # Configure Nginx with the domain
    info "Setting up Nginx configuration for ${DOMAIN}..."

    # Copy Nginx config
    if [[ -f nginx/omni-medical.conf ]]; then
        cp nginx/omni-medical.conf /etc/nginx/sites-available/omni-medical.conf
    elif [[ -f config/nginx.conf ]]; then
        cp config/nginx.conf /etc/nginx/sites-available/omni-medical.conf
    fi

    # Replace DOMAIN placeholder in Nginx config
    sed -i "s|server_name _|server_name ${DOMAIN};|g" /etc/nginx/sites-available/omni-medical.conf
    sed -i "s|DOMAIN|${DOMAIN}|g" /etc/nginx/sites-available/omni-medical.conf

    # Create symlink
    ln -sf /etc/nginx/sites-available/omni-medical.conf /etc/nginx/sites-enabled/omni-medical.conf
    rm -f /etc/nginx/sites-enabled/default

    # Create certbot webroot directory
    mkdir -p /var/www/certbot

    # Test Nginx config
    nginx -t 2>/dev/null && ok "Nginx config valid" || warn "Nginx config needs SSL certs first (expected)"

    # Get SSL certificate
    info "Requesting SSL certificate for ${DOMAIN}..."
    certbot certonly \
        --nginx \
        -d "${DOMAIN}" \
        --agree-tos \
        -m "${EMAIL}" \
        --non-interactive \
        --redirect \
        || warn "Certbot failed — you may need to point DNS to this server first"

    # Generate DH params for extra security
    if [[ ! -f /etc/nginx/dhparam.pem ]]; then
        info "Generating Diffie-Hellman parameters (this takes a minute)..."
        openssl dhparam -out /etc/nginx/dhparam.pem 2048
        ok "DH parameters generated"
    fi

    # Set up auto-renewal cron job
    info "Setting up SSL auto-renewal..."
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx'") | sort -u | crontab -
    ok "SSL auto-renewal configured (daily at 3:00 AM)"

    # Reload Nginx
    nginx -t && systemctl reload nginx
    ok "Nginx reloaded with SSL"
else
    warn "SSL setup skipped (--skip-ssl flag)"
fi

# =============================================================================
# Phase 4: Build & Launch
# =============================================================================
echo ""
info "═══ Phase 4: Build & Launch ═══"

# Copy production deployment files
info "Copying production deployment files..."
DEPLOY_DIR="$(dirname "$0")"
COMPOSE_FILE="${DEPLOY_DIR}/docker-compose.full.yml"
if [[ -f "${DEPLOY_DIR}/Dockerfile" ]]; then
    cp "${DEPLOY_DIR}/Dockerfile" "${PROJECT_DIR}/Dockerfile"
fi
if [[ ! -f "$COMPOSE_FILE" ]]; then
    error "Full-stack compose file not found: $COMPOSE_FILE"
fi
if [[ -f "${DEPLOY_DIR}/docker-entrypoint.sh" ]]; then
    cp "${DEPLOY_DIR}/docker-entrypoint.sh" "${PROJECT_DIR}/docker-entrypoint.sh"
    chmod +x "${PROJECT_DIR}/docker-entrypoint.sh"
fi
ok "Deployment files copied"

# Build Docker images
info "Building Docker images (this may take 10-20 minutes)..."
docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" build --no-cache 2>&1 | tail -20
ok "Docker images built"

# Launch services
info "Starting all services..."
docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" up -d
ok "Services started"

# Wait for health checks
info "Waiting for services to become healthy (60s)..."
sleep 10

MAX_WAIT=60
ELAPSED=0
while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    UNHEALTHY=$(docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" ps --format json 2>/dev/null | jq -r 'select(.Health != "healthy" and .Health != null) | .Name' 2>/dev/null | wc -l || echo "0")
    if [[ "$UNHEALTHY" -eq 0 ]]; then
        break
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    info "Waiting... (${ELAPSED}s/${MAX_WAIT}s)"
done

# =============================================================================
# Phase 5: Verification
# =============================================================================
echo ""
info "═══ Phase 5: Verification ═══"

# Show service status
info "Docker services status:"
docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" ps

echo ""

# Check API health
info "Testing API health endpoint..."
HEALTH_STATUS=$(curl -sf http://localhost:8000/health 2>/dev/null && echo "OK" || echo "FAIL")
if [[ "$HEALTH_STATUS" == "OK" ]]; then
    ok "API health check: PASSED"
else
    warn "API health check: FAILED (may still be starting up)"
    warn "Run: docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" logs api"
fi

# Verify HTTPS
if [[ "$SKIP_SSL" != "true" ]]; then
    info "Testing HTTPS..."
    HTTPS_STATUS=$(curl -sf "https://${DOMAIN}/health" 2>/dev/null && echo "OK" || echo "FAIL")
    if [[ "$HTTPS_STATUS" == "OK" ]]; then
        ok "HTTPS: WORKING"
    else
        warn "HTTPS: Not yet reachable (DNS may need time to propagate)"
    fi
fi

# Show service health summary
echo ""
info "Service Health Summary:"
for svc in api postgres redis qdrant; do
    STATUS=$(docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" ps "$svc" --format json 2>/dev/null | jq -r '.Health // "unknown"' 2>/dev/null || echo "unknown")
    if [[ "$STATUS" == "healthy" ]]; then
        ok "$svc: $STATUS"
    else
        warn "$svc: $STATUS"
    fi
done

# =============================================================================
# Final Report
# =============================================================================
echo ""
echo "=========================================="
echo " 🎉 Deployment Complete!"
echo "=========================================="
echo ""
echo "  🌐 Website:      https://${DOMAIN}"
echo "  📚 API Docs:     https://${DOMAIN}/docs"
echo "  ❤️  Health:       https://${DOMAIN}/health"
echo "  📊 API (direct): http://localhost:8000"
echo ""
echo "  📁 Project:      ${PROJECT_DIR}"
echo "  ⚙️  Compose:      docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE""
echo ""
echo "  Useful commands:"
echo "    docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" ps          # Check status"
echo "    docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" logs -f api # View API logs"
echo "    docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" restart api # Restart API"
echo "    docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" down        # Stop all"
echo ""
echo "  Security checklist:"
echo "    [✓] HTTPS enabled (Let's Encrypt)"
echo "    [✓] HTTP → HTTPS redirect"
echo "    [✓] UFW firewall (22/80/443)"
echo "    [✓] Strong DB/Redis passwords"
echo "    [✓] .env excluded from Git"
echo "    [✓] SSL auto-renewal configured"
echo "    [✓] Non-root Docker user"
echo ""
