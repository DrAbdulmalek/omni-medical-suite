#!/bin/bash
# ============================================================================
# إعداد بيئة Gradio المحلية لتجريب HF Space بدون استهلاك فترة التجريب
# ============================================================================
# يعمل على: Linux (Arch/Manjaro), macOS, Windows (WSL/Git Bash)
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║     Medical OCR Demo — إعداد بيئة التشغيل المحلية                   ║"
echo "║     Local Gradio Testing Environment Setup                          ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# STEP 1: Clone HF Space (if not already cloned)
# ============================================================================
echo -e "${BLUE}[1/5] التحقق من المستودع...${NC}"

REPO_DIR="$HOME/GitHub/hf-space-medical-ocr-demo"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo -e "${YELLOW}  المستودع غير موجود. جاري التحميل...${NC}"
    mkdir -p "$HOME/GitHub"
    git clone https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-demo "$REPO_DIR"
    echo -e "${GREEN}  ✓ تم التحميل${NC}"
else
    echo -e "${GREEN}  ✓ المستودع موجود${NC}"
    echo -e "${YELLOW}  جاري تحديث أحدث التعديلات...${NC}"
    cd "$REPO_DIR"
    git pull origin main 2>/dev/null || echo -e "${YELLOW}  (فشل السحب — مستخدم محلي فقط)${NC}"
fi

# ============================================================================
# STEP 2: Create virtual environment
# ============================================================================
echo -e "${BLUE}[2/5] إنشاء بيئة افتراضية...${NC}"

VENV_DIR="$HOME/GitHub/gradio-venv"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}  ✓ تم إنشاء: $VENV_DIR${NC}"
else
    echo -e "${GREEN}  ✓ البيئة موجودة: $VENV_DIR${NC}"
fi

source "$VENV_DIR/bin/activate"
echo -e "${GREEN}  ✓ Python: $(python3 --version)${NC}"

# ============================================================================
# STEP 3: Install core dependencies (with critical version pins)
# ============================================================================
echo -e "${BLUE}[3/5] تثبيت المكتبات الأساسية...${NC}"

pip install --upgrade pip -q

# Critical version pins — DO NOT change these!
# See: gradio-app/gradio#11722, huggingface_hub HfFolder removal
pip install -q \
    "gradio==4.43.0" \
    "huggingface_hub<1.0.0" \
    "pydantic<2.11" \
    "opencv-python-headless>=4.8.0,<5.0.0" \
    "Pillow>=10.0.0,<11.0.0" \
    "numpy<2.0.0" \
    "pytesseract>=0.3.10"

echo -e "${GREEN}  ✓ المكتبات الأساسية مثبتة${NC}"

# ============================================================================
# STEP 4: Optional — Install OCR engines
# ============================================================================
echo -e "${BLUE}[4/5] محركات OCR (اختياري)...${NC}"

echo ""
echo -e "${CYAN}  محركات OCR المتاحة:${NC}"
echo -e "  ${GREEN}1.${NC} PaddleOCR + PaddlePaddle 3.x  (الأفضل للعربية المطبوعة — ~2GB)"
echo -e "  ${GREEN}2.${NC} EasyOCR  (الكتابة اليدوية — ~1.5GB)"
echo -e "  ${GREEN}3.${NC} كلاهما"
echo -e "  ${YELLOW}4.${NC} تخطي (التطبيق يعمل بدونها — Tesseract فقط)"
echo ""
read -p "  اختر [1-4]: " OCR_CHOICE

case $OCR_CHOICE in
    1)
        echo -e "${YELLOW}  جاري تثبيت PaddlePaddle + PaddleOCR...${NC}"
        pip install -q "paddlepaddle>=3.0.0" "paddleocr>=2.7.3"
        echo -e "${GREEN}  ✓ PaddleOCR مثبت${NC}"
        ;;
    2)
        echo -e "${YELLOW}  جاري تثبيت EasyOCR...${NC}"
        pip install -q "easyocr>=1.7.0"
        echo -e "${GREEN}  ✓ EasyOCR مثبت${NC}"
        ;;
    3)
        echo -e "${YELLOW}  جاري تثبيت الكل...${NC}"
        pip install -q "paddlepaddle>=3.0.0" "paddleocr>=2.7.3" "easyocr>=1.7.0"
        echo -e "${GREEN}  ✓ الكل مثبت${NC}"
        ;;
    *)
        echo -e "${YELLOW}  ⚠ تم تخطي محركات OCR الإضافية. Tesseract فقط سيعمل.${NC}"
        ;;
esac

# ============================================================================
# STEP 5: Verify and test
# ============================================================================
echo -e "${BLUE}[5/5] التحقق...${NC}"

echo ""
python3 << 'PYEOF'
import sys

errors = []
warnings = []

# Check versions
try:
    import gradio; print(f"  gradio:          {gradio.__version__}")
    if not gradio.__version__.startswith("4.43"):
        warnings.append(f"gradio {gradio.__version__} (مختبر على 4.43.0)")
except Exception as e:
    errors.append(f"gradio: {e}")

try:
    import pydantic; print(f"  pydantic:        {pydantic.__version__}")
    v = [int(x) for x in pydantic.__version__.split('.')[:2]]
    if v >= [2, 11]:
        errors.append("pydantic >= 2.11 سيُعطل gradio_client!")
except Exception as e:
    errors.append(f"pydantic: {e}")

try:
    import huggingface_hub; print(f"  huggingface_hub: {huggingface_hub.__version__}")
    if float(huggingface_hub.__version__) >= 1.0:
        errors.append("huggingface_hub >= 1.0 سيُعطل gradio 4.x!")
except Exception as e:
    errors.append(f"huggingface_hub: {e}")

try:
    import cv2; print(f"  opencv:          {cv2.__version__}")
except Exception as e:
    errors.append(f"opencv: {e}")

try:
    import numpy; print(f"  numpy:           {numpy.__version__}")
    if float(numpy.__version__) >= 2.0:
        warnings.append("numpy >= 2.0 قد يسبب مشاكل مع OpenCV")
except Exception as e:
    errors.append(f"numpy: {e}")

# Optional engines
for name, mod in [("paddleocr", "paddleocr"), ("easyocr", "easyocr")]:
    try:
        __import__(mod); print(f"  {name}:          متوفر ✓")
    except ImportError:
        print(f"  {name}:          غير مثبت (اختياري)")

print("")
if errors:
    print(f"\033[0;31m  ✗ أخطاء ({len(errors)}):")
    for e in errors:
        print(f"    - {e}")
    print("\033[0m")
    sys.exit(1)
elif warnings:
    print(f"\033[1;33m  ⚠ تحذيرات ({len(warnings)}):")
    for w in warnings:
        print(f"    - {w}")
    print("\033[0m")
    print("\033[0;32m  ✓ التثبيت مكتمل (مع تحذيرات)\033[0m")
else:
    print("\033[0;32m  ✓ كل الإصدارات صحيحة — جاهز للتشغيل!\033[0m")
PYEOF

VERIFY_EXIT=$?

# ============================================================================
# DONE
# ============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✅ الإعداد مكتمل!                                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}للتشغيل:${NC}"
echo ""
echo -e "  ${GREEN}source $VENV_DIR/bin/activate${NC}"
echo -e "  ${GREEN}cd $REPO_DIR${NC}"
echo -e "  ${GREEN}ENABLE_LLM=false python3 app.py${NC}"
echo ""
echo -e "${CYAN}ثم افتح في المتصفح:${NC}"
echo -e "  ${BLUE}http://localhost:7860${NC}"
echo ""
echo -e "${YELLOW}ملاحظة: التطبيق يعمل بدون محركات OCR إضافية (Tesseract فقط).${NC}"
echo -e "${YELLOW}إذا أردت تثبيتها لاحقاً:${NC}"
echo -e "  source $VENV_DIR/bin/activate"
echo -e "  pip install paddlepaddle>=3.0.0 paddleocr>=2.7.3"
echo -e "  pip install easyocr>=1.7.0"
echo ""

exit $VERIFY_EXIT