# DEPLOY.md — Deployment Guide

## Quick Deploy to Hugging Face Spaces

### Prerequisites
- HuggingFace account with `hf` CLI installed and authenticated
- Docker SDK on Spaces

### Steps

```bash
# 1. Create a new Space on HF (Docker SDK)
# Go to: https://huggingface.co/spaces → New Space → Docker

# 2. Clone and push
cd omni-medical-suite
git remote add space https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
git push space main

# 3. Add HF_TOKEN as Secret in Space Settings (for dataset upload)
```

### Build will take ~5-15 min first time.

## Docker (Local)

```bash
docker build -t omni-medical-ocr .
docker run -p 7860:7860 -e ENABLE_LLM=false omni-medical-ocr
# Open http://localhost:7860
```

## With LLM Features (requires GPU)

```bash
docker run --gpus all -p 7860:7860 \
  -e ENABLE_LLM=true \
  -e HF_TOKEN=hf_xxx \
  omni-medical-ocr
```

## Test Scanner-Fixer Standalone

```bash
cd scanner-fixer
pip install -r requirements.txt

# Single image
python -c "
from src.scanner_fixer import DocumentPreprocessor
p = DocumentPreprocessor(debug=True)
p.process('test.jpg', 'output.jpg')
"

# Batch processing
python scripts/batch_fixer.py --input ./data/raw --output ./data/cleaned --debug
```