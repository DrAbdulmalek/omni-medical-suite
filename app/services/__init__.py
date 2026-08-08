# app/services/__init__.py
"""Service layer for Omni Medical OCR.

Modules:
    ocr_service        — OCR engine initialization, preprocessing, and recognition
    review_service     — NER extraction, LLM proofreading, and correction logic
    hf_dataset_service — HuggingFace dataset save/upload and training management
    search_service     — Unified search interface (Qdrant + local fuzzy fallback)
    export_service     — Export results to CSV, JSON, and HF Dataset formats
"""