#!/usr/bin/env bash
# =============================================================================
# deploy_monitoring.sh — Deploy Prometheus + Grafana monitoring stack
# =============================================================================
# Creates the monitoring directory structure, docker-compose file, starts
# the stack, and imports Grafana dashboards via the HTTP API.
# =============================================================================

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

error()   { echo -e "${RED}ERROR:${NC} $1" >&2; exit 1; }
info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MONITORING_DIR="${PROJECT_ROOT}/monitoring"

# ── 1. Check dependencies ───────────────────────────────────────────────────
echo "🔍 Checking dependencies..."
for cmd in docker docker-compose jq curl git; do
    if command -v "$cmd" &>/dev/null; then
        info "$cmd: $(command -v "$cmd")"
    else
        # docker-compose may be a plugin: try 'docker compose'
        if [ "$cmd" = "docker-compose" ] && docker compose version &>/dev/null 2>&1; then
            info "docker compose plugin: available"
        else
            error "$cmd is not installed. Please install it first."
        fi
    fi
done

# Normalise compose command
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# ── 2. Create directory structure ───────────────────────────────────────────
echo ""
info "Creating monitoring directory structure..."
mkdir -p "${MONITORING_DIR}/prometheus"
mkdir -p "${MONITORING_DIR}/grafana"
mkdir -p "${MONITORING_DIR}/dashboards"
mkdir -p "${MONITORING_DIR}/alerts"
info "Directories created under ${MONITORING_DIR}/"

# ── 3. Create docker-compose.monitoring.yml ────────────────────────────────
COMPOSE_FILE="${MONITORING_DIR}/docker-compose.monitoring.yml"

info "Writing ${COMPOSE_FILE}..."
cat > "$COMPOSE_FILE" <<'COMPOSE_EOF'
# =============================================================================
# OmniMedical Suite — Monitoring Stack (Prometheus + Grafana)
# =============================================================================
# Usage: docker compose -f monitoring/docker-compose.monitoring.yml up -d
# =============================================================================

services:
  prometheus:
    image: prom/prometheus:v2.53.0
    container_name: omni-prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./alerts:/etc/prometheus/alerts:ro
      - prometheus-data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=30d"
      - "--web.enable-lifecycle"
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:11.2.0
    container_name: omni-grafana
    restart: unless-stopped
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_DEFAULT_LANGUAGE: ar
      GF_AUTH_DISABLE_SIGNUP_MENU: "true"
      GF_PANELS_DISABLE_SANITIZE_CSS: "true"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/grafana.ini:/etc/grafana/grafana.ini:ro
      - ./grafana/custom-rtl.css:/etc/grafana/custom-rtl.css:ro
      - ./dashboards:/var/lib/grafana/dashboards:ro
    depends_on:
      - prometheus
    networks:
      - monitoring

networks:
  monitoring:
    driver: bridge

volumes:
  prometheus-data:
  grafana-data:
COMPOSE_EOF

info "docker-compose.monitoring.yml created"

# ── 4. Create Grafana datasource provisioning ──────────────────────────────
mkdir -p "${MONITORING_DIR}/grafana/provisioning/datasources"
cat > "${MONITORING_DIR}/grafana/provisioning/datasources/prometheus.yml" <<'DS_EOF'
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    uid: prometheus
    isDefault: true
    editable: true
DS_EOF
info "Grafana datasource provisioning created"

# ── 5. Start the monitoring stack ──────────────────────────────────────────
echo ""
info "Starting monitoring stack..."
$COMPOSE_CMD -f "$COMPOSE_FILE" up -d

# ── 6. Wait for services to become healthy ─────────────────────────────────
echo ""
info "Waiting for services to start..."

wait_for_url() {
    local url="$1"
    local name="$2"
    local max_wait="${3:-30}"
    local waited=0

    while ! curl -sf "$url" >/dev/null 2>&1; do
        sleep 1
        waited=$((waited + 1))
        if [ "$waited" -ge "$max_wait" ]; then
            warn "$name did not become ready within ${max_wait}s"
            return 1
        fi
    done
    info "$name is ready"
    return 0
}

wait_for_url "http://localhost:9090/-/healthy" "Prometheus" 60
wait_for_url "http://localhost:3001/api/health" "Grafana" 60

# ── 7. Import Grafana dashboards ───────────────────────────────────────────
echo ""
info "Importing Grafana dashboards..."

GRAFANA_URL="http://localhost:3001"
GRAFANA_USER="admin"
GRAFANA_PASS="admin"

# Authenticate and get API token
LOGIN_RESPONSE=$(curl -sf -X POST "${GRAFANA_URL}/api/login" \
    -H "Content-Type: application/json" \
    -d "{\"user\":\"${GRAFANA_USER}\",\"password\":\"${GRAFANA_PASS}\"}" 2>/dev/null) || true

API_TOKEN=""
if [ -n "$LOGIN_RESPONSE" ] && echo "$LOGIN_RESPONSE" | jq -e .token >/dev/null 2>&1; then
    API_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r .token)
    AUTH_HEADER="Authorization: Bearer ${API_TOKEN}"
    info "Authenticated with Grafana API"
else
    # Fallback: basic auth
    AUTH_HEADER="Authorization: Basic $(echo -n "${GRAFANA_USER}:${GRAFANA_PASS}" | base64)"
    warn "Using basic auth for Grafana API"
fi

# Import each dashboard JSON found in monitoring/dashboards/
for dashboard_file in "${MONITORING_DIR}/dashboards/"*.json; do
    [ -f "$dashboard_file" ] || continue

    DASHBOARD_NAME=$(basename "$dashboard_file")

    # Set the dashboard to use the Prometheus datasource uid
    DASHBOARD_PAYLOAD=$(jq --arg ds "prometheus" '
        if .__inputs then del(.__inputs) else . end |
        if .__requires then del(.__requires) else . end |
        walk(if type == "object" then
            if .datasource and .datasource.type == "prometheus" then
                .datasource.uid = $ds
            else . end
        else . end)
    ' "$dashboard_file")

    # Wrap in the import payload
    IMPORT_PAYLOAD=$(jq -n --argjson dashboard "$DASHBOARD_PAYLOAD" '{
        dashboard: $dashboard,
        folderId: 0,
        overwrite: true,
        message: "Auto-imported by deploy_monitoring.sh"
    }')

    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
        -X POST "${GRAFANA_URL}/api/dashboards/db" \
        -H "Content-Type: application/json" \
        -H "$AUTH_HEADER" \
        -d "$IMPORT_PAYLOAD" 2>/dev/null) || HTTP_CODE="000"

    if [ "$HTTP_CODE" = "200" ]; then
        info "Imported dashboard: $DASHBOARD_NAME"
    else
        warn "Failed to import $DASHBOARD_NAME (HTTP $HTTP_CODE)"
    fi
done

# ── 8. Print status ─────────────────────────────────────────────────────────
echo ""
echo "==========================================="
info "Monitoring Stack Status"
echo "==========================================="
echo ""

# Prometheus
if curl -sf http://localhost:9090/-/healthy >/dev/null 2>&1; then
    echo -e "  Prometheus:  ${GREEN}RUNNING${NC}  → http://localhost:9090"
else
    echo -e "  Prometheus:  ${RED}NOT RUNNING${NC}"
fi

# Grafana
if curl -sf http://localhost:3001/api/health >/dev/null 2>&1; then
    echo -e "  Grafana:     ${GREEN}RUNNING${NC}  → http://localhost:3001"
    echo -e "                 User: ${GRAFANA_USER} / ${GRAFANA_PASS}"
else
    echo -e "  Grafana:     ${RED}NOT RUNNING${NC}"
fi

echo ""
echo "==========================================="
info "Monitoring stack deployed successfully!"
echo "========================================="