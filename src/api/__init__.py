# src/api — REST API layer wrapping core engines
"""
FastAPI-based REST API that exposes the Omni Medical Suite core engines:
  - MedicalClassifier → POST /api/classify
  - FileHandler      → POST /api/organize
  - SemanticSearch    → GET  /api/search
  - Stats & Health    → GET  /api/stats, GET /api/health

All engine imports are lazy — the server starts instantly and gracefully
degrades when optional dependencies (Ollama, Qdrant, PaddleOCR, etc.)
are unavailable.
"""
