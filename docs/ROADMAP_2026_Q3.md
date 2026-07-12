# Omni Medical Suite — Q3 2026 Upgrade Plan

## Scope completed in this refactor

1. **Core OCR modules merged into `src/ocr/` and `omni_medical_suite/preprocessing/`**
   - `src/ocr/rtl_utils.py`
   - `src/ocr/field_extractor.py`
   - `src/ocr/deduplication.py`
   - `omni_medical_suite/preprocessing/compare_raw_vs_printed.py`

2. **Routing expanded with explicit fallback chains**
   - Handwriting → `Arabic-handwritten-OCR (Qwen)` → `QARI` → `TrOCR`
   - Vocalized Arabic → `QARI`
   - Structured extraction / forms → `Nougat`
   - Printed Arabic fallback → `EasyOCR` / `PaddleOCR` / `Tesseract`

3. **Patient-safe deduplication**
   - Weighted fields: patient name, patient ID, date, diagnosis, medications, template signature
   - Same-template / different-patient cases are now intentionally penalized

4. **Semantic search path**
   - `QdrantMedicalSearch` uses Qdrant when configured
   - Falls back to local fuzzy retrieval when vector dependencies are unavailable

5. **UI refresh**
   - `app/advanced_review_app.py` becomes the review-oriented Gradio entrypoint
   - Tabs: Compare / Search / Review
   - `app/gradio_full_hitl.py` remains as a compatibility shim

6. **Packaging and repository hygiene**
   - `pyproject.toml` keeps `setuptools.build_meta` and now includes Qdrant support
   - root `requirements-dev.txt` reduced to a compatibility wrapper
   - `.gitattributes` now tracks `data/**`, `*.jsonl`, and `*.parquet` with Git LFS

7. **Regression coverage**
   - RTL fixes
   - Field extraction
   - Advanced engine routing
   - Same-template / different-patient dedup edge case

## Next development milestones

### Milestone A — Runtime integration
- Wire `WeightedMedicalDeduplicator` into API / job processors
- Persist search index metadata alongside OCR jobs
- Add upload-and-index flow in the review app

### Milestone B — Benchmarks
- Add CER/WER batch benchmark fixtures for raw vs preprocessed text
- Store experiment outputs under a dedicated benchmark artifact path instead of the repo root
- Validate Qwen/QARI/Nougat routing on representative medical samples

### Milestone C — Human review loop
- Save physician corrections in a single durable schema
- Link corrected text back into search and dedup pipelines
- Surface confidence + routing decisions in the UI for auditability

### Milestone D — Repository cleanup
- Remove obsolete duplicate scripts once imports are verified safe
- Continue collapsing legacy requirement files into `pyproject.toml` extras
- Move large benchmark fixtures fully behind Git LFS
