#!/bin/bash
# Select OmniMedical Suite Tier
# Usage: ./choose-tier.sh [lite|standard|full]

CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/config"
TIER="${1:-standard}"

case "$TIER" in
    lite|standard|full)
        ;;
    *)
        echo "Error: Invalid tier '$TIER'"
        echo "Usage: $0 [lite|standard|full]"
        exit 1
        ;;
esac

CONFIG_FILE="$CONFIG_DIR/${TIER}.yml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

export OMNI_TIER="$TIER"
export OMNI_CONFIG="$CONFIG_FILE"

echo "============================================="
echo "  OmniMedical Suite - $TIER Tier Selected"
echo "============================================="
echo ""
echo "Configuration: $CONFIG_FILE"
echo ""

python -m omni_medical_suite --config "$CONFIG_FILE" "${@:2}"
