#!/usr/bin/env bash
# ============================================================================
# OmniMedical Suite — Automated Setup Script
# ============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

log_info "=== OmniMedical Suite Setup ==="
echo ""

# --- 1. Check prerequisites ---
log_info "Step 1/7: Checking prerequisites..."
check_cmd() {
    if command -v "$1" &> /dev/null; then
        echo "  ✓ $1 found: $(command -v "$1")"
    else
        echo "  ✗ $1 not found"
        return 1
    fi
}

MISSING=0
check_cmd node || MISSING=1
check_cmd npm || MISSING=1
check_cmd python3 || MISSING=1
check_cmd pip3 || MISSING=1
check_cmd git || MISSING=1

if [ $MISSING -eq 1 ]; then
    log_error "Missing prerequisites. Please install Node.js 18+, Python 3.10+, and Git."
    exit 1
fi
echo ""

# --- 2. Create .env ---
log_info "Step 2/7: Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    # Generate secure secrets
    if command -v openssl &> /dev/null; then
        NEXTAUTH_SECRET=$(openssl rand -base64 32)
        ENCRYPTION_KEY=$(python3 -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())" 2>/dev/null || echo "CHANGE_ME")
        sed -i "s|NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=$NEXTAUTH_SECRET|" .env
        sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" .env
    fi
    log_warn ".env created from .env.example — review and update secrets!"
else
    log_info ".env already exists, skipping..."
fi
echo ""

# --- 3. Python virtual environment ---
log_info "Step 3/7: Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    log_info "Virtual environment created."
fi
source venv/bin/activate
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q 2>&1 | tail -1
log_info "Python dependencies installed."
echo ""

# --- 4. Node.js dependencies ---
log_info "Step 4/7: Installing Node.js dependencies..."
npm install 2>&1 | tail -3
echo ""

# --- 5. Prisma setup ---
log_info "Step 5/7: Setting up database (Prisma)..."
cd apps/web
npx prisma generate 2>&1 | tail -1
mkdir -p ../../prisma/db
npx prisma db push --skip-generate 2>&1 | tail -1
cd ../..
log_info "Database initialized."
echo ""

# --- 6. Seed admin user ---
log_info "Step 6/7: Seeding database..."
log_warn "Default admin: username=admin, password=admin123"
log_warn "CHANGE THIS PASSWORD IMMEDIATELY AFTER FIRST LOGIN!"
echo ""

# --- 7. Build ---
log_info "Step 7/7: Building project..."
npm run build 2>&1 | tail -5
echo ""

# --- Summary ---
log_info "=== Setup Complete ==="
echo ""
echo "  Next steps:"
echo "    1. Edit .env with your API keys and secrets"
echo "    2. Run: npm run dev"
echo "    3. Open: http://localhost:3000"
echo "    4. Login: admin / admin123 (CHANGE IMMEDIATELY)"
echo ""
echo "  Python API: source venv/bin/activate && uvicorn services.api.main:app --reload"
echo "  Docker:     npm run docker:up"
echo ""
