---
title: Medical OCR Trainer — Ensemble
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# Medical OCR Trainer — Hugging Face Deployment

> **Deployment-only repository** — Source of truth: [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer)

---

## Repository Status

| Field | Value |
|-------|-------|
| **Role** | Deployment Repo (Hugging Face Space) |
| **Status** | Active (Demo) |
| **Layer** | Deployment |
| **Priority** | Low |
| **Source of Truth** | [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer) |

## Active Engines (Free Tier)

| Engine | Status | Description |
|--------|--------|-------------|
| PaddleOCR | Active | Arabic + English, best for mixed medical docs |
| EasyOCR | Active | 80+ languages, Latin text |
| Tesseract | Active | Fast, reliable for printed text |
| TrOCR | Disabled | Needs more RAM (paid space) |
| Surya OCR | Disabled | Needs more RAM (paid space) |

## How to Use

1. Upload a medical note (JPG/PNG)
2. Select which OCR engines to use (sidebar checkboxes)
3. Choose a merging strategy (majority voting, confidence-weighted, etc.)
4. Review and correct results in the interactive editor
5. Export training data (JSONL)

## Merging Strategies

- **Majority Voting** — Text with most engine votes wins
- **Confidence Weighted** — Weighted average by confidence
- **Levenshtein Consensus** — Most similar text across all engines
- **Best Single** — Highest confidence result

## Technical Notes

- Persistent storage via `/data/`
- CPU-only PyTorch (HuggingFace free tier limits)
- Streamlit UI with Arabic RTL support
- SQLite database for corrections

## When to Use This

| Need | Repository |
|------|-----------|
| Quick demo / try online | **This repo** (HF Space) |
| Full local development | [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer) |
| Production OCR | [medical-handwriting-ocr](https://github.com/DrAbdulmalek/medical-handwriting-ocr) |

## Related Repositories

| Repo | Role | Status |
|------|------|--------|
| [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer) | Source of Truth | Active |
| [medical-handwriting-ocr](https://github.com/DrAbdulmalek/medical-handwriting-ocr) | Production OCR | Active |
| [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) | Main Platform | Active |

**License: MIT** — Dr. Abdulmalek Tamer Al-husseini
