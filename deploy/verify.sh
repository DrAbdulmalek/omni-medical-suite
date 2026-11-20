#!/bin/bash
# =============================================================================
# Omni Medical Suite — Quick Verification Script
# =============================================================================
# Run after deployment to verify all components are working
# Usage: ./verify.sh [--domain your-domain.com]
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DOMAIN="${1:-localhost}"
COMPOSE_FILE="docker-compose.prod.yml"
PASS=0
FAIL=0

check() {
    local name="$1"
    local result="$2"
    if [[ "$result" == "OK" ]]; then
        echo -e "  ${GREEN}✓${NC} $name"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}✗${NC} $name — $result"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "=========================================="
echo " Omni Medical Suite — Verification"
echo " Domain: $DOMAIN"
echo "=========================================="
echo ""

# ── Docker Services ──────────────────────────────────────────────────────────
echo -e "${BLUE}[1] Docker Services${NC}"
for svc in api postgres redis qdrant; do
    STATE=$(docker compose -f "$COMPOSE_FILE" ps "$svc" --format json 2>/dev/null | jq -r '.State // "not found"' 2>/dev/null || echo "not found")
    HEALTH=$(docker compose -f "$COMPOSE_FILE" ps "$svc" --format json 2>/dev/null | jq -r '.Health // "unknown"' 2>/dev/null || echo "unknown")
    if [[ "$STATE" == "running" && "$HEALTH" == "healthy" ]]; then
        check "$svc" "OK"
    else
        check "$svc" "State: $STATE, Health: $HEALTH"
    fi
done

# ── API Endpoints ────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[2] API Endpoints${NC}"

# Health check
HTTP_CODE=$(curl -sf -o /dev/null -w '%{http_code}' http://localhost:8000/health 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" ]]; then
    check "/health (HTTP 200)" "OK"
else
    check "/health" "HTTP $HTTP_CODE"
fi

# Root endpoint
HTTP_CODE=$(curl -sf -o /dev/null -w '%{http_code}' http://localhost:8000/ 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" ]]; then
    check "/ (HTTP 200)" "OK"
else
    check "/" "HTTP $HTTP_CODE"
fi

# API docs
HTTP_CODE=$(curl -sf -o /dev/null -w '%{http_code}' http://localhost:8000/api/docs 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" ]]; then
    check "/api/docs (HTTP 200)" "OK"
else
    check "/api/docs" "HTTP $HTTP_CODE"
fi

# ── HTTPS (if domain is not localhost) ───────────────────────────────────────
if [[ "$DOMAIN" != "localhost" ]]; then
    echo ""
    echo -e "${BLUE}[3] HTTPS${NC}"

    HTTPS_CODE=$(curl -sf -o /dev/null -w '%{http_code}' "https://$DOMAIN/health" 2>/dev/null || echo "000")
    if [[ "$HTTPS_CODE" == "200" ]]; then
        check "HTTPS /health" "OK"
    else
        check "HTTPS /health" "HTTP $HTTPS_CODE"
    fi

    # HTTP redirect
    REDIRECT=$(curl -sf -o /dev/null -w '%{http_code}' "http://$DOMAIN/health" 2>/dev/null || echo "000")
    if [[ "$REDIRECT" == "301" || "$REDIRECT" == "302" ]]; then
        check "HTTP→HTTPS redirect" "OK"
    else
        check "HTTP→HTTPS redirect" "HTTP $REDIRECT"
    fi
fi

# ── Security Headers ─────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[4] Security Headers${NC}"

HEADERS=$(curl -sI http://localhost:8000/health 2>/dev/null || echo "")

for header in "X-Content-Type-Options" "X-Frame-Options" "X-XSS-Protection"; do
    if echo "$HEADERS" | grep -qi "$header"; then
        check "$header present" "OK"
    else
        check "$header" "missing"
    fi
done

# ── Database Connectivity ────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[5] Database Connectivity${NC}"

PG_READY=$(docker exec omni-postgres pg_isready -U omni_user -d omni_medical 2>/dev/null && echo "OK" || echo "FAIL")
check "PostgreSQL" "$PG_READY"

REDIS_PING=$(docker exec omni-redis redis-cli ping 2>/dev/null || echo "FAIL")
if [[ "$REDIS_PING" == "PONG" ]]; then
    check "Redis" "OK"
else
    check "Redis" "$REDIS_PING"
fi

QDRANT_HEALTH=$(curl -sf http://localhost:6333/healthz 2>/dev/null && echo "OK" || echo "FAIL")
check "Qdrant" "$QDRANT_HEALTH"

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
TOTAL=$((PASS + FAIL))
if [[ $FAIL -eq 0 ]]; then
    echo -e " ${GREEN}All $TOTAL checks passed! 🎉${NC}"
else
    echo -e " ${YELLOW}$PASS passed, $FAIL failed out of $TOTAL${NC}"
fi
echo "=========================================="
echo ""
