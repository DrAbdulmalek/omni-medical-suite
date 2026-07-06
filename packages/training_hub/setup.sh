#!/bin/bash
# ── Setup Script: medical-ocr-training-hub ──
# Run this ONCE after cloning the repo to GitHub.
# Creates the repo on GitHub and links everything together.
#
# Prerequisites:
#   - gh CLI installed and authenticated: gh auth login
#   - Or: manually create repo on GitHub and push

set -e

REPO_NAME="medical-ocr-training-hub"
GITHUB_USER="DrAbdulmalek"
FULL_REPO="${GITHUB_USER}/${REPO_NAME}"
HF_SPACE_DIR="../hf-space-push"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Medical OCR Training Hub — Initial Setup              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Create GitHub repo
echo "━━━ Step 1: Create GitHub Repository ━━━"
if command -v gh &> /dev/null; then
    if gh repo view "$FULL_REPO" &> /dev/null; then
        echo "✅ Repo already exists: https://github.com/$FULL_REPO"
    else
        gh repo create "$FULL_REPO" \
            --public \
            --description "Bridge: HuggingFace Space corrections <-> GitHub training data for continuous Medical OCR model improvement" \
            --source=. \
            --push
        echo "✅ Repo created and pushed: https://github.com/$FULL_REPO"
    fi
else
    echo "⚠️  'gh' CLI not found. Create the repo manually:"
    echo "   1. Go to https://github.com/new"
    echo "   2. Name: $REPO_NAME"
    echo "   3. Description: Bridge between HF corrections and GitHub training data"
    echo "   4. Create as Public"
    echo "   5. Then run: git push -u origin main"
    echo ""
    read -p "Press Enter after creating the repo on GitHub..."
    git push -u origin main
    echo "✅ Pushed to GitHub"
fi

echo ""

# Step 2: Verify HF Space link
echo "━━━ Step 2: Verify HF Space ━━━"
HF_SPACE_URL="https://huggingface.co/spaces/DrAbdulmalek/medical-handwriting-ocr"
echo "HF Space URL: $HF_SPACE_URL"
echo "The HF Space has been updated with Training Hub tab."
echo ""

# Step 3: Data flow summary
echo "━━━ Step 3: Data Flow Architecture ━━━"
echo ""
echo "  ┌─────────────────┐     corrections.jsonl     ┌──────────────────────────┐"
echo "  │   HF Space      │ ─────────────────────────> │  GitHub Training Hub     │"
echo "  │ (Gradio App)    │     (export + sync)        │  training_data/word_crops│"
echo "  │                 │                            │  training_data/ground_tr │"
echo "  └─────────────────┘ <───────────────────────── └──────────────────────────┘"
echo "                       config.yaml + ground_truth"
echo ""
echo "  ┌──────────────────────────┐   reads training_data/   ┌──────────────┐"
echo "  │  Models (config.yaml)    │ ──────────────────────>  │ PaddleOCR    │"
echo "  │  - trocr_finetune.yaml   │                          │ TrOCR        │"
echo "  │  - paddleocr_custom.yaml │                          │ Postprocessor│"
echo "  └──────────────────────────┘                          └──────────────┘"
echo ""

# Step 4: Next steps
echo "━━━ Step 4: Next Steps ━━━"
echo ""
echo "1. Use the HF Space to correct OCR results (saves to SQLite)"
echo "2. Click 'Export to Training Hub' in the Training Hub tab"
echo "3. Run: python scripts/sync_hf_github.py --direction hf_to_github"
echo "4. Run: python scripts/build_training_datasets.py --all"
echo "5. Fine-tune models using the generated datasets"
echo ""
echo "Model configs point to these training data paths:"
echo "  - PaddleOCR → training_data/word_crops/ (custom dict)"
echo "  - TrOCR     → training_data/exports/trocr_hf/ (image+text)"
echo "  - Postproc  → training_data/exports/correction_pairs/ (raw→corrected)"
echo ""
echo "✅ Setup complete!"