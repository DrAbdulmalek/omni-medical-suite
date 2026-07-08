#!/usr/bin/env python3
"""
Upload TrOCR baseline model to Hugging Face Hub.

Downloads microsoft/trocr-base-handwritten, saves locally with a
medical-OCR Model Card, and pushes to DrAbdulmalek/arabic-medical-ocr-baseline.

Usage:
    huggingface-cli login          # one-time
    python scripts/upload_baseline_model.py
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_MODEL = "microsoft/trocr-base-handwritten"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./baseline-model"))
HF_REPO_ID = os.getenv(
    "HF_REPO_ID", "DrAbdulmalek/arabic-medical-ocr-baseline"
)

MODEL_CARD = f"""\
---
license: mit
language:
  - ar
  - en
tags:
  - ocr
  - medical
  - arabic
  - handwriting
  - trocr
library_name: transformers
pipeline_tag: image-to-text
datasets:
  - DrAbdulmalek/arabic-medical-ocr-corrections
---

# Arabic Medical OCR Baseline

TrOCR model prepared as a baseline for [Omni Medical Suite](https://github.com/DrAbdulmalek/omni-medical-suite).

## Quick Start

```python
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image

processor = TrOCRProcessor.from_pretrained("{HF_REPO_ID}")
model = VisionEncoderDecoderModel.from_pretrained("{HF_REPO_ID}")

image = Image.open("prescription.jpg").convert("RGB")
pixel_values = processor(image, return_tensors="pt").pixel_values
generated_ids = model.generate(pixel_values, max_length=128)
text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
print(text)
```

## Performance

| Metric | Value | Notes |
|--------|-------|-------|
| CER | N/A | Pending fine-tuning on Arabic medical data |
| WER | N/A | Pending fine-tuning on Arabic medical data |

> This is an unmodified baseline. Fine-tuned versions will be published separately.

## Links

- **Suite**: [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)
- **Dataset**: [arabic-medical-ocr-corrections](https://huggingface.co/datasets/DrAbdulmalek/arabic-medical-ocr-corrections)
- **HF Space**: [omni-medical-ocr](https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr)

## Limitations

- Research use only
- Not a substitute for professional medical review
"""


def upload_baseline() -> bool:
    try:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    except ImportError:
        print("ERROR: transformers not installed. Run: pip install transformers torch")
        return False

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("ERROR: huggingface_hub not installed. Run: pip install huggingface_hub")
        return False

    # 1. Download & save locally
    print(f"Downloading {BASE_MODEL} ...")
    processor = TrOCRProcessor.from_pretrained(BASE_MODEL)
    model = VisionEncoderDecoderModel.from_pretrained(BASE_MODEL)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    print(f"Saved to {OUTPUT_DIR}")

    # 2. Write Model Card
    (OUTPUT_DIR / "README.md").write_text(MODEL_CARD, encoding="utf-8")

    # 3. Upload
    print(f"Uploading to {HF_REPO_ID} ...")
    api = HfApi()

    api.create_repo(repo_id=HF_REPO_ID, repo_type="model", exist_ok=True)
    api.upload_folder(
        folder_path=str(OUTPUT_DIR),
        repo_id=HF_REPO_ID,
        repo_type="model",
        commit_message="Initial baseline model upload",
    )

    print(f"Done! https://huggingface.co/{HF_REPO_ID}")
    return True


if __name__ == "__main__":
    import sys

    sys.exit(0 if upload_baseline() else 1)