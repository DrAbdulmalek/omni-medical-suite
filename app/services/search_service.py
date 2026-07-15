# app/services/search_service.py
"""Search Service — Unified interface for medical document search.

Wraps QdrantMedicalSearch to provide a simple search(query, top_k) API
that works with or without Qdrant (falls back to local fuzzy search).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy initialization to avoid import errors when Qdrant is not installed
_search_instance = None


def get_search_service():
    """Get or create the search service singleton."""
    global _search_instance
    if _search_instance is None:
        try:
            from src.ocr.deduplication import QdrantMedicalSearch
            from src.ocr.field_extractor import ArabicMedicalFieldExtractor
            
            qdrant_url = None  # Will be configurable via env var
            import os
            qdrant_url = os.getenv("QDRANT_URL")  # None triggers fallback
            
            extractor = ArabicMedicalFieldExtractor()
            _search_instance = QdrantMedicalSearch(
                qdrant_url=qdrant_url,
                collection_name=os.getenv("QDRANT_COLLECTION", "omni_medical_suite_records"),
                extractor=extractor,
            )
            backend = "qdrant" if qdrant_url else "local-fuzzy"
            logger.info(f"SearchService initialized with {backend} backend")
        except Exception as e:
            logger.error(f"SearchService init failed: {e}")
            raise
    return _search_instance


def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search medical documents. Works with or without Qdrant.
    
    Args:
        query: Search query text (Arabic or English)
        top_k: Maximum number of results
        
    Returns:
        List of search hits with id, score, text, metadata, backend
    """
    if not query or not query.strip():
        return []
    service = get_search_service()
    return service.search(query.strip(), top_k=top_k)


def index_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Index records for search.
    
    Args:
        records: List of records with 'raw_text' or 'patient_name' fields
        
    Returns:
        Dict with 'backend' and 'indexed' count
    """
    service = get_search_service()
    return service.upsert_records(records)