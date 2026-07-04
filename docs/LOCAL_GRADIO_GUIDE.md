# Local Gradio Testing Guide

## Purpose
Test the HF Space locally before deploying to avoid consuming HF trial time.

## Quick Start

```bash
# 1. Activate the virtual environment
source ~/GitHub/gradio-venv/bin/activate

# 2. Go to the HF Space clone
cd ~/GitHub/hf-space-medical-ocr-demo

# 3. Run
ENABLE_LLM=false python3 app.py
```

Or use the launcher script:
```bash
bash ~/GitHub/omni-medical-suite/scripts/run-gradio-local.sh
```

## Access
- **Local**: http://localhost:7860
- **Network**: http://0.0.0.0:7860

## Critical Version Pins

These versions MUST be maintained to avoid crashes:

| Package | Version | Reason |
|---------|---------|--------|
| gradio | 4.43.0 | Stable version with Arabic support |
| pydantic | <2.11 | 2.11+ crashes gradio_client (gradio#11722) |
| huggingface_hub | <1.0.0 | 1.0+ removed HfFolder, breaks gradio 4.x |

## Virtual Environment

The venv is at `~/GitHub/gradio-venv/` with pre-installed:
- gradio 4.43.0
- pydantic 2.10.6
- huggingface_hub 0.36.2
- opencv-python-headless 4.10.0.84
- Pillow 10.4.0
- numpy 1.26.4

### Installing Optional OCR Engines

```bash
source ~/GitHub/gradio-venv/bin/activate

# PaddleOCR (Arabic printed text, primary engine)
pip install paddleocr==2.7.3 paddlepaddle==2.6.2

# EasyOCR (handwriting support)
pip install easyocr==1.7.1

# Full install (all engines)
pip install -r ~/GitHub/hf-space-medical-ocr-demo/requirements.txt
```

## Repos in ~/GitHub

| Repo | Description |
|------|-------------|
| omni-medical-suite | Main project (126 commits) |
| hf-space-medical-ocr-demo | HF Space clone (runs locally) |
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