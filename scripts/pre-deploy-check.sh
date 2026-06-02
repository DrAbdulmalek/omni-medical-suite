#!/usr/bin/env bash
# =============================================================================
# pre-deploy-check.sh — Verify environment is ready for production deployment
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

echo "🔍 Pre-Deployment Check"
echo "======================="
echo ""

# Check required files
echo "📁 Checking required files..."
for file in .env.production docker-compose.yml Dockerfile; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (missing)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check for CHANGE_ME placeholders
echo ""
echo "🔐 Checking for unset secrets..."
if [ -f .env.production ]; then
    FOUND=$(grep -c "CHANGE_ME" .env.production 2>/dev/null || echo "0")
    if [ "$FOUND" -gt 0 ]; then
        echo -e "  ${YELLOW}⚠${NC} $FOUND CHANGE_ME placeholder(s) found in .env.production"
        WARNINGS=$((WARNINGS + FOUND))
    else
        echo -e "  ${GREEN}✓${NC} All secrets configured"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} .env.production not found"
    WARNINGS=$((WARNINGS + 1))
fi

# Check Docker
echo ""
echo "🐳 Checking Docker..."
if command -v docker &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} Docker installed ($(docker --version 2>&1 | head -1))"
else
    echo -e "  ${RED}✗${NC} Docker not installed"
    ERRORS=$((ERRORS + 1))
fi

if command -v docker-compose &> /dev/null || docker compose version &> /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Docker Compose available"
else
    echo -e "  ${RED}✗${NC} Docker Compose not installed"
    ERRORS=$((ERRORS + 1))
fi

# Check Python
echo ""
echo "🐍 Checking Python..."
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓${NC} Python ($PY_VERSION)"
else
    echo -e "  ${RED}✗${NC} Python not installed"
    ERRORS=$((ERRORS + 1))
fi

# Check .gitignore
echo ""
echo "🔒 Checking .gitignore..."
if [ -f .gitignore ]; then
    for pattern in ".env" "*.db" "*.sqlite" "__pycache__" ".venv"; do
        if grep -q "$pattern" .gitignore; then
            echo -e "  ${GREEN}✓${NC} $pattern"
        else
            echo -e "  ${YELLOW}⚠${NC} $pattern (not in .gitignore)"
            WARNINGS=$((WARNINGS + 1))
        fi
    done
else
    echo -e "  ${RED}✗${NC} .gitignore not found"
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo ""
echo "======================="
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}❌ $ERRORS error(s), $WARNINGS warning(s) — fix errors before deploying${NC}"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  0 errors, $WARNINGS warning(s) — review warnings${NC}"
    exit 0
else
    echo -e "${GREEN}✅ All checks passed — ready for deployment!${NC}"
    exit 0
fi
