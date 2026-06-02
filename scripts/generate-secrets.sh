#!/usr/bin/env bash
# =============================================================================
# generate-secrets.sh — Generate secure secrets for production deployment
# =============================================================================
# Usage: bash scripts/generate-secrets.sh [--output .env.production]
# =============================================================================

set -euo pipefail

OUTPUT_FILE="${1:-.env.production}"
BASIC_ENV_FILE="env.example.production"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔐 Omni Medical Suite — Secret Generator${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# Check if base env file exists
if [ ! -f "$BASIC_ENV_FILE" ]; then
    echo -e "${RED}Error: ${BASIC_ENV_FILE} not found${NC}"
    echo "Run this script from the project root directory."
    exit 1
fi

# Generate functions
generate_secret() {
    local length=${1:-32}
    openssl rand -hex "$length" 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex($length))"
}

generate_password() {
    local length=${1:-24}
    openssl rand -base64 "$length" 2>/dev/null | tr -d '=/+' | head -c "$length" || \
        python3 -c "import secrets, string; chars=string.ascii_letters+string.digits+'!@#$%'; print(''.join(secrets.choice(chars) for _ in range($length)))"
}

echo -e "${YELLOW}Generating secure secrets...${NC}"

# Copy base env file
cp "$BASIC_ENV_FILE" "$OUTPUT_FILE"

# Replace all CHANGE_ME placeholders with generated secrets
sed -i.bak \
    -e "s|CHANGE_ME_STRONG_PASSWORD|$(generate_password 32)|g" \
    -e "s|CHANGE_ME_REDIS_PASSWORD|$(generate_password 24)|g" \
    -e "s|CHANGE_ME_GENERATE_WITH_SCRIPTS|$(generate_secret 32)|g" \
    -e "s|CHANGE_ME_JWT_SECRET|$(generate_secret 32)|g" \
    -e "s|CHANGE_ME_API_KEY|sk-$(generate_secret 24)|g" \
    -e "s|CHANGE_ME_QDRANT_KEY|$(generate_secret 24)|g" \
    -e "s|CHANGE_ME_GRAFANA_PASS|$(generate_password 20)|g" \
    "$OUTPUT_FILE"

# Clean up backup
rm -f "${OUTPUT_FILE}.bak"

echo ""
echo -e "${GREEN}✅ Secrets generated successfully!${NC}"
echo -e "${GREEN}   Output: ${OUTPUT_FILE}${NC}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT SECURITY NOTES:${NC}"
echo "   1. Review the generated ${OUTPUT_FILE} before deploying"
echo "   2. Add ${OUTPUT_FILE} to .gitignore (it should already be)"
echo "   3. Store secrets securely (e.g., vault, sealed secrets, SOPS)"
echo "   4. Rotate secrets regularly"
echo "   5. Never commit secrets to version control"
echo ""

# Verify no CHANGE_ME placeholders remain
REMAINING=$(grep -c "CHANGE_ME" "$OUTPUT_FILE" 2>/dev/null || echo "0")
if [ "$REMAINING" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Warning: ${REMAINING} CHANGE_ME placeholder(s) remain in ${OUTPUT_FILE}${NC}"
    echo -e "${YELLOW}   These may require manual configuration:${NC}"
    grep "CHANGE_ME" "$OUTPUT_FILE" | while read -r line; do
        echo -e "   ${YELLOW}→ ${line%%=*}${NC}"
    done
    echo ""
fi
