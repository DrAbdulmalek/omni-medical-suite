#!/bin/bash
# ============================================================================
# Local Gradio Launcher — HF Space Clone
# Runs medical-ocr-demo locally for testing without consuming HF trial time.
# ============================================================================

set -e

VENV_DIR="$HOME/GitHub/gradio-venv"
APP_DIR="$HOME/GitHub/hf-space-medical-ocr-demo"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Medical OCR Demo — Local Gradio${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check venv
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}[ERROR] Virtual environment not found at $VENV_DIR${NC}"
    echo "Run setup first:"
    echo "  python3 -m venv $VENV_DIR"
    echo "  source $VENV_DIR/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Check app dir
if [ ! -f "$APP_DIR/app.py" ]; then
    echo -e "${RED}[ERROR] app.py not found at $APP_DIR${NC}"
    exit 1
fi

# Activate venv
echo -e "${BLUE}[1/3] Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}[OK] Python: $(python3 --version)${NC}"

# Verify versions
echo -e "${BLUE}[2/3] Verifying dependencies...${NC}"
python3 -c "
import gradio; print(f'  gradio: {gradio.__version__}')
import pydantic; print(f'  pydantic: {pydantic.__version__}')
import huggingface_hub; print(f'  huggingface_hub: {huggingface_hub.__version__}')
import cv2; print(f'  opencv: {cv2.__version__}')

# Critical checks
if pydantic.__version__.startswith('2.1') and int(pydantic.__version__.split('.')[1]) >= 11:
    print('  \033[0;31m[WARN] pydantic >= 2.11 will crash gradio_client!\033[0m')
    exit(1)
if huggingface_hub.__version__.startswith('1.') or float(huggingface_hub.__version__) >= 1.0:
    print('  \033[0;31m[WARN] huggingface_hub >= 1.0 breaks gradio 4.x!\033[0m')
    exit(1)
print('  \033[0;32m[OK] All version constraints satisfied\033[0m')
" || { echo -e "${RED}[FAIL] Version check failed${NC}"; exit 1; }

# Launch
echo -e "${BLUE}[3/3] Launching Gradio...${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Local URL:     http://localhost:7860${NC}"
echo -e "${GREEN}  Network URL:   http://0.0.0.0:7860${NC}"
echo -e "${GREEN}  Press Ctrl+C to stop${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

cd "$APP_DIR"
export ENABLE_LLM=false
python3 app.py