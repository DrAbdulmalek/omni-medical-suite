# Local Gradio Testing Guide

## Purpose
Test the HF Space locally before deploying to avoid consuming HF trial time.

## One-Command Setup (Recommended)

Run this on **your local machine** — not on any server:

```bash
# Clone omni-medical-suite first (if not already)
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git ~/GitHub/omni-medical-suite

# Run the setup script
bash ~/GitHub/omni-medical-suite/scripts/setup-local-gradio.sh
```

The script will:
1. Clone HF Space to `~/GitHub/hf-space-medical-ocr-demo/`
2. Create venv at `~/GitHub/gradio-venv/`
3. Install core dependencies with correct version pins
4. Ask which OCR engines to install (PaddleOCR, EasyOCR, or skip)
5. Verify all versions are correct

## Manual Setup

```bash
# 1. Clone HF Space
mkdir -p ~/GitHub
git clone https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-demo ~/GitHub/hf-space-medical-ocr-demo

# 2. Create venv
python3 -m venv ~/GitHub/gradio-venv
source ~/GitHub/gradio-venv/bin/activate

# 3. Install core (with critical version pins)
pip install --upgrade pip
pip install \
    "gradio==4.43.0" \
    "huggingface_hub<1.0.0" \
    "pydantic<2.11" \
    "opencv-python-headless>=4.8.0,<5.0.0" \
    "Pillow>=10.0.0,<11.0.0" \
    "numpy<2.0.0" \
    "pytesseract>=0.3.10"

# 4. (Optional) Install OCR engines
pip install "paddlepaddle>=3.0.0" "paddleocr>=2.7.3"   # Arabic printed text (~2GB)
pip install "easyocr>=1.7.1"                            # Handwriting (~1.5GB)
```

## Run

```bash
source ~/GitHub/gradio-venv/bin/activate
cd ~/GitHub/hf-space-medical-ocr-demo
ENABLE_LLM=false python3 app.py
```

**Access**: http://localhost:7860

## Critical Version Pins

These versions MUST be maintained to avoid crashes:

| Package | Constraint | Reason |
|---------|-----------|--------|
| gradio | 4.43.0 | Stable with Arabic, tested |
| pydantic | <2.11 | 2.11+ crashes gradio_client (gradio#11722) |
| huggingface_hub | <1.0.0 | 1.0+ removed HfFolder, breaks gradio 4.x |
| numpy | <2.0.0 | OpenCV compatibility |
| paddlepaddle | >=3.0.0 | 2.x retired, only 3.x available now |

## Troubleshooting

### `paddlepaddle==2.6.2 not found`
PaddlePaddle 2.x was retired. Use `paddlepaddle>=3.0.0` instead.

### `source: no such file or directory`
The venv doesn't exist on your machine yet. Run the setup script first.

### `No module named 'paddleocr'`
Optional — the app works with Tesseract only. PaddleOCR gives better Arabic results.

### `TypeError: bool is not iterable`
pydantic >= 2.11 got installed. Fix:
```bash
source ~/GitHub/gradio-venv/bin/activate
pip install "pydantic<2.11"
```

## All Repos in ~/GitHub

| Repo | Description |
|------|-------------|
| omni-medical-suite | Main project |
| hf-space-medical-ocr-demo | HF Space (runs locally) |
| scanner-fixer | Pre-OCR image enhancement |
| medical-handwriting-ocr | Production OCR platform |
| medical-ocr-trainer | Evaluation & training |
| medical-ocr-training-hub | Training data pipeline |
| medical-ocr-postprocessor | Post-processing (archived) |
| medical-ocr-benchmarks | OCR benchmarking |
| ai-fuel-engine | Data processing engine |
| bilingual-extractor | Medical term extraction |
| IntelliFile-app | File management |
| git-sync-system | Repo synchronization |
| reset-net | Network reset tool |
| manjaro-care | System maintenance |