#!/usr/bin/env bash
# =============================================================================
# pre-deploy-check.sh — Verify environment is ready for production deployment
# =============================================================================
# Designed for Manjaro / Arch Linux.
# Exit 0 on success, 1 on failure with clear error messages.
# =============================================================================

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

error()   { echo -e "  ${RED}✗${NC} $1"; ERRORS=$((ERRORS + 1)); }
warn()    { echo -e "  ${YELLOW}⚠${NC} $1"; WARNINGS=$((WARNINGS + 1)); }
ok()      { echo -e "  ${GREEN}✓${NC} $1"; }

echo "🔍 Pre-Deployment Check — OmniMedical Suite"
echo "============================================"
echo ""

# ── 1. Required files ──────────────────────────────────────────────────────
echo "📁 Checking required files..."
REQUIRED_FILES=(
    docker-compose.prod.yml
    Dockerfile
    .env.production
)
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        ok "$file exists"
    else
        error "$file is missing"
    fi
done

# ── 2. No default secrets ──────────────────────────────────────────────────
echo ""
echo "🔐 Checking for default / placeholder secrets..."
if [ -f .env.production ]; then
    # Check for common placeholder patterns
    PLACEHOLDER_PATTERNS=("changeme" "CHANGE_ME" "placeholder" "TODO" "your-secret-here")
    FOUND_PLACEHOLDERS=0
    for pattern in "${PLACEHOLDER_PATTERNS[@]}"; do
        # Case-insensitive search
        MATCHES=$(grep -ic "$pattern" .env.production 2>/dev/null || true)
        if [ "$MATCHES" -gt 0 ]; then
            while IFS= read -r line; do
                warn "Placeholder '$pattern' found: $line"
            done < <(grep -i "$pattern" .env.production)
            FOUND_PLACEHOLDERS=$((FOUND_PLACEHOLDERS + MATCHES))
        fi
    done
    if [ "$FOUND_PLACEHOLDERS" -eq 0 ]; then
        ok "No default placeholder secrets detected"
    fi
else
    warn ".env.production not found — cannot check secrets"
fi

# ── 3. Docker memory ───────────────────────────────────────────────────────
echo ""
echo "🐳 Checking Docker resources..."
MIN_MEMORY_MB=4096

check_docker_memory() {
    # Try to get total memory available to Docker (works on Linux)
    if ! command -v docker &>/dev/null; then
        error "Docker is not installed"
        return
    fi

    # Method 1: docker info Total Memory
    TOTAL_MEM_KB=$(docker info 2>/dev/null | awk '/Total Memory:/ {print $3}')
    if [ -n "$TOTAL_MEM_KB" ] && [ "$TOTAL_MEM_KB" != "0" ]; then
        # Detect unit — docker info usually reports in GiB or MiB
        TOTAL_MEM_RAW=$(docker info 2>/dev/null | grep -oP 'Total Memory: \K[0-9.]+ ?[A-Za-z]*')
        # If it's GiB, convert
        if echo "$TOTAL_MEM_RAW" | grep -qi "GiB"; then
            TOTAL_MEM_MB=$(echo "$TOTAL_MEM_RAW" | awk '{printf "%.0f", $1 * 1024}')
        elif echo "$TOTAL_MEM_RAW" | grep -qi "MiB"; then
            TOTAL_MEM_MB=$(echo "$TOTAL_MEM_RAW" | awk '{printf "%.0f", $1}')
        else
            # Fallback: read from /proc/meminfo
            TOTAL_MEM_MB=$(awk '/MemTotal/ {printf "%.0f", $2/1024}' /proc/meminfo)
        fi
    else
        # Fallback: read system memory from /proc/meminfo (Linux)
        TOTAL_MEM_MB=$(awk '/MemTotal/ {printf "%.0f", $2/1024}' /proc/meminfo 2>/dev/null || echo "0")
    fi

    if [ "$TOTAL_MEM_MB" -ge "$MIN_MEMORY_MB" ] 2>/dev/null; then
        ok "Docker memory: ${TOTAL_MEM_MB}MB (>= ${MIN_MEMORY_MB}MB)"
    else
        error "Docker memory: ${TOTAL_MEM_MB}MB — need at least ${MIN_MEMORY_MB}MB"
    fi
}

check_docker_memory

# ── 4. Required ports are free ─────────────────────────────────────────────
echo ""
echo "🔌 Checking required ports..."
REQUIRED_PORTS=(8000 6379 5432)

for port in "${REQUIRED_PORTS[@]}"; do
    # Check if port is in use using ss (preferred on Arch/Manjaro)
    if command -v ss &>/dev/null; then
        IN_USE=$(ss -tlnp 2>/dev/null | awk -v p=":${port} " '$0 ~ p {print $0}')
    elif command -v netstat &>/dev/null; then
        IN_USE=$(netstat -tlnp 2>/dev/null | awk -v p=":${port} " '$0 ~ p {print $0}')
    else
        # Last resort: try to bind
        if (echo > /dev/tcp/localhost/"$port") 2>/dev/null; then
            IN_USE="yes"
        else
            IN_USE=""
        fi
    fi

    if [ -z "$IN_USE" ]; then
        ok "Port $port is free"
    else
        error "Port $port is already in use: $IN_USE"
    fi
done

# ── 5. Python version >= 3.10 ──────────────────────────────────────────────
echo ""
echo "🐍 Checking Python version..."
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print("{}.{}".format(sys.version_info.major, sys.version_info.minor))')
    PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
    PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

    if [ "$PY_MAJOR" -gt 3 ] 2>/dev/null || { [ "$PY_MAJOR" -eq 3 ] 2>/dev/null && [ "$PY_MINOR" -ge 10 ] 2>/dev/null; }; then
        ok "Python $PY_VERSION (>= 3.10)"
    else
        error "Python $PY_VERSION — requires >= 3.10"
    fi
else
    error "Python 3 is not installed"
fi

# ── 6. Required pip packages ───────────────────────────────────────────────
echo ""
echo "📦 Checking required pip packages..."
REQUIRED_PACKAGES=(
    fastapi
    uvicorn
    redis
    sqlalchemy
    celery
    prometheus-client
)

for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if python3 -c "import ${pkg//[-_]/_}" 2>/dev/null; then
        ok "$pkg installed"
    else
        error "$pkg is not installed (pip install $pkg)"
    fi
done

# ── 7. Git working tree clean ─────────────────────────────────────────────
echo ""
echo "📝 Checking Git working tree..."
if [ -d .git ]; then
    if command -v git &>/dev/null; then
        # Check for uncommitted changes (staged or unstaged)
        UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l)
        if [ "$UNCOMMITTED" -eq 0 ]; then
            ok "Git working tree is clean"
        else
            error "Git working tree has $UNCOMMITTED uncommitted change(s):"
            git status --short 2>/dev/null | while IFS= read -r line; do
                echo "      $line"
            done
        fi
    else
        warn "Git repository detected but git command not found"
    fi
else
    warn "Not a Git repository — skipping working tree check"
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "============================================"
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}❌ $ERRORS error(s), $WARNINGS warning(s) — fix errors before deploying${NC}"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  0 errors, $WARNINGS warning(s) — review warnings before deploying${NC}"
    exit 0
else
    echo -e "${GREEN}✅ All checks passed — ready for deployment!${NC}"
    exit 0
fi