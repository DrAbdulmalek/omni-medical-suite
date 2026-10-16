#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════╗
#  Golden Path E2E runner (S2-T2) — PDF -> preprocess -> OCR -> GT correction file
#  Status: READY_FOR_EXECUTION (never run yet — see contract §S2-T2; no claims)
#  Local-first: no network calls anywhere in this script (LOCAL_ONLY §S2-T4).
# ═══════════════════════════════════════════════════════════════════╝
set -euo pipefail
t0=$(date +%s)
INPUT_PDF="${1:?usage: run_e2e.sh <input.pdf> [workdir]}"
WORK="${2:-$(mktemp -d /tmp/golden_path_e2e.XXXXXX)}"
mkdir -p "$WORK/pre" "$WORK/ocr"
echo "[1/4] preprocessing (omni) -> $WORK/pre"
# Real entry point: omni_medical_suite.preprocessing package (see packages/vision).
# ADJUST if the package exposes a different top-level helper:
python3 - <<PY
from omni_medical_suite.preprocessing import preprocess_document  # ADJUST name if needed
preprocess_document("$INPUT_PDF", "$WORK/pre")
PY
echo "[2/4] OCR via ocr-core CLI (v0.7.0 unified command system)"
ocr-core pipeline --input "$WORK/pre" --output "$WORK/ocr" 2>/dev/null \
  || python3 -m ocr_core pipeline --input "$WORK/pre" --output "$WORK/ocr"
echo "[3/4] HUMAN STEP: review $WORK/ocr/*.txt and write corrections as:"
echo "      --- <page>.jpg ---  / corrected line per line   (DatasetBuilder format)"
echo "[4/4] after corrections, build the dataset:"
echo "      python3 -c \"from packages.vision.dataset_builder import DatasetBuilder; ...\""
t1=$(date +%s)
echo "done in $((t1 - t0))s — workdir: $WORK (kept for review)"
