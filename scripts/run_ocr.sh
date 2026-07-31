#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# run_ocr.sh — سكربت تشغيل PDF OCR Processor
# ══════════════════════════════════════════════════════════════════
#
# Usage: ./run_ocr.sh [GITHUB_TOKEN] [INPUT_PATH]
#
# Examples:
#   ./run_ocr.sh                                    # معالجة data/
#   ./run_ocr.sh ghp_token report.pdf               # ملف واحد مع توكن
#   ./run_ocr.sh ghp_token ./pdfs/                   # مجلد كامل
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── إنشاء مجلد الإخراج ──────────────────────────────────────────
OUTPUT_DIR="${HOME}/glossaries_output"
mkdir -p "$OUTPUT_DIR"

# ── الانتقال لمجلد المشروع ──────────────────────────────────────
cd "$PROJECT_DIR"

# ── معالجة المعاملات ────────────────────────────────────────────
GITHUB_TOKEN=""
INPUT_PATH="data/"
EXTRA_ARGS=""

if [ $# -ge 1 ]; then
    # إذا كان الأول يبدأ بـ ghp_ فهو توكن
    if [[ "$1" == ghp_* ]] || [[ "$1" == github_* ]]; then
        GITHUB_TOKEN="$1"
        export GITHUB_TOKEN
        shift
    fi
fi

if [ $# -ge 1 ]; then
    INPUT_PATH="$1"
    shift
fi

# أي معاملات إضافية
EXTRA_ARGS="$*"

# ── التحقق من التبعيات ──────────────────────────────────────────
echo "═══════════════════════════════════════════════════"
echo "  PDF OCR Processor — فحص التبعيات"
echo "═══════════════════════════════════════════════════"
echo ""

# Tesseract
if command -v tesseract &>/dev/null; then
    echo "✅ Tesseract: $(tesseract --version 2>&1 | head -1)"
else
    echo "❌ Tesseract غير مثبت!"
    echo "   ثبّته: sudo pacman -S tesseract tesseract-data-ara tesseract-data-eng"
    exit 1
fi

# Poppler (for pdf2image)
if command -v pdftoppm &>/dev/null; then
    echo "✅ Poppler: متاح"
else
    echo "⚠️  Poppler غير مثبت — pdf2image لن يعمل"
    echo "   ثبّته: sudo pacman -S poppler"
fi

# Python packages
python3 -c "import pytesseract" 2>/dev/null && echo "✅ pytesseract" || echo "⚠️  pytesseract غير مثبت"
python3 -c "import cv2" 2>/dev/null && echo "✅ OpenCV" || echo "⚠️  OpenCV غير مثبت"
python3 -c "import PIL" 2>/dev/null && echo "✅ Pillow" || echo "⚠️  Pillow غير مثبت"
python3 -c "import fitz" 2>/dev/null && echo "✅ PyMuPDF" || echo "⚠️  PyMuPDF غير مثبت"
python3 -c "import pdf2image" 2>/dev/null && echo "✅ pdf2image" || echo "⚠️  pdf2image غير مثبت"
python3 -c "import scanner_fixer" 2>/dev/null && echo "✅ scanner_fixer" || echo "⚠️  scanner_fixer غير مثبت"

echo ""

# ── تشغيل المعالج ────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════"
echo "  تشغيل المعالج..."
echo "═══════════════════════════════════════════════════"
echo ""
echo "  الإدخال: ${INPUT_PATH}"
echo "  الإخراج: ${OUTPUT_DIR}"
echo ""

python3 "$SCRIPT_DIR/pdf_ocr_processor.py" \
    --input "$INPUT_PATH" \
    --output "$OUTPUT_DIR" \
    $EXTRA_ARGS

# ── عرض النتائج ──────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ اكتملت المعالجة!"
echo "═══════════════════════════════════════════════════"
echo ""
echo "📁 النتائج في: ${OUTPUT_DIR}"
echo ""
ls -lh "$OUTPUT_DIR"/ 2>/dev/null || echo "  (لا ملفات بعد)"
