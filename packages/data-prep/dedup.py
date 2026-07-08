"""
Medical-Safe Deduplication Engine
===================================
Adapted from ai-fuel-engine dedup module.
Prevents clinically important content (dosages, vitals, lab values) from being removed.

Author: Dr. Abdulmalek
Version: 1.0.0
"""

import hashlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DedupResult:
    """Result of deduplication check for a single chunk."""
    chunk_id: str
    is_duplicate: bool = False
    dedup_method: str = ""  # "exact", "semantic", "context_protected"
    similarity_score: float = 0.0
    matched_with: str | None = None
    protected: bool = False


@dataclass
class DedupReport:
    """Aggregate deduplication report."""
    total_chunks: int = 0
    duplicates_found: int = 0
    protected_chunks: int = 0
    method_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    details: list[DedupResult] = field(default_factory=list)


class MedicalDeduplicationEngine:
    """
    Three-phase deduplication pipeline for medical document preparation.

    Phase 1: Exact dedup (SHA-256 hash)
    Phase 2: Semantic dedup (optional, requires sentence-transformers)
    Phase 3: Medical context protection (restore protected content)

    This is a DATA PREPARATION tool. Use it when building training datasets
    or deduplicating corpus data. Do NOT use it in the live OCR pipeline.
    """

    # Medical content patterns that must NOT be deduplicated
    PROTECTED_PATTERNS = [
        # Drug dosages
        (r'\d+\s*(?:mg|ml|mcg|g|mmol|IU|unit)\b', 7, "drug_dosage"),
        (r'\d+\.\d+\s*(?:mg|ml|mcg)\b', 7, "drug_dosage_decimal"),
        # Arabic dosage patterns
        (r'\d+\s*(?:ملغ|ملي|جرام)\b', 7, "drug_dosage_ar"),
        # Vital signs
        (r'BP\s*[:/]?\s*\d+/\d+', 6, "blood_pressure"),
        (r'HR\s*[:/]?\s*\d+\s*bpm', 6, "heart_rate"),
        (r'SpO2\s*[:/]?\s*\d+%', 6, "oxygen_saturation"),
        (r'Temp(?:erature)?\s*[:/]?\s*\d+\.?\d*\s*[°C]?F?', 5, "temperature"),
        (r'RR\s*[:/]?\s*\d+', 5, "respiratory_rate"),
        # Lab values with units
        (r'(?:Hb|Hgb|Hemoglobin)\s*[:=]?\s*\d+\.?\d*', 6, "lab_hemoglobin"),
        (r'WBC\s*[:=]?\s*\d+', 5, "lab_wbc"),
        (r'(?:Creatinine|BUN|Glucose)\s*[:=]?\s*\d+\.?\d*', 5, "lab_chemistry"),
        (r'(?:TSH|T3|T4)\s*[:=]?\s*\d+\.?\d*', 6, "lab_thyroid"),
        # Reference ranges
        (r'\d+\.?\d*\s*[-–]\s*\d+\.?\d*\s*(?:mg|ml|g|mmol|%)\b', 4, "reference_range"),
        # ICD codes
        (r'[A-Z]\d{2}(?:\.\d{1,4})?', 3, "icd_code"),
        # Diagnostic scores
        (r'(?:APACHE|SOFA|GCS|CHARLSON)\s*[:=]?\s*\d+', 6, "diagnostic_score"),
    ]

    def __init__(self, semantic_threshold: float = 0.95):
        self.semantic_threshold = semantic_threshold
        self._exact_index: dict[str, str] = {}  # hash -> chunk_id
        self._semantic_model = None
        self._semantic_index: list[tuple[str, list[float]]] = []
        self._protected_chunks: set[str] = set()

    def _normalize(self, text: str) -> str:
        """Normalize text for deduplication."""
        text = text.strip().lower()
        text = re.sub(r'\s+', ' ', text)
        return text

    def _exact_hash(self, text: str) -> str:
        """Compute SHA-256 hash for exact dedup."""
        return hashlib.sha256(self._normalize(text).encode()).hexdigest()

    def _has_protected_content(self, text: str) -> tuple[bool, int]:
        """Check if text contains medically protected content."""
        max_priority = 0
        for pattern, priority, _name in self.PROTECTED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                max_priority = max(max_priority, priority)
        return max_priority > 0, max_priority

    def check_duplicate(self, chunk_id: str, text: str) -> DedupResult:
        """Check if a chunk is a duplicate."""
        # Phase 0: Check if protected
        is_protected, _priority = self._has_protected_content(text)
        if is_protected:
            self._protected_chunks.add(chunk_id)
            return DedupResult(
                chunk_id=chunk_id,
                is_duplicate=False,
                dedup_method="context_protected",
                protected=True,
            )

        # Phase 1: Exact dedup
        hash_val = self._exact_hash(text)
        if hash_val in self._exact_index:
            return DedupResult(
                chunk_id=chunk_id,
                is_duplicate=True,
                dedup_method="exact",
                similarity_score=1.0,
                matched_with=self._exact_index[hash_val],
            )

        self._exact_index[hash_val] = chunk_id

        # Phase 2: Semantic dedup (if model available)
        if self._semantic_model is not None:
            return self._semantic_check(chunk_id, text)

        return DedupResult(chunk_id=chunk_id, is_duplicate=False)

    def _semantic_check(self, chunk_id: str, text: str) -> DedupResult:
        """Check semantic similarity (requires sentence-transformers)."""
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer

            if self._semantic_model is None:
                self._semantic_model = SentenceTransformer(
                    'paraphrase-multilingual-mpnet-base-v2'
                )

            embedding = self._semantic_model.encode(text)

            for existing_id, existing_emb in self._semantic_index:
                similarity = float(np.dot(embedding, existing_emb) /
                                   (np.linalg.norm(embedding) * np.linalg.norm(existing_emb) + 1e-8))
                if similarity >= self.semantic_threshold:
                    return DedupResult(
                        chunk_id=chunk_id,
                        is_duplicate=True,
                        dedup_method="semantic",
                        similarity_score=similarity,
                        matched_with=existing_id,
                    )

            self._semantic_index.append((chunk_id, embedding))

        except ImportError:
            logger.debug("sentence-transformers not available, skipping semantic dedup")
        except Exception as e:
            logger.warning(f"Semantic dedup failed: {e}")

        return DedupResult(chunk_id=chunk_id, is_duplicate=False)

    def deduplicate(self, chunks: list[dict]) -> tuple[list[dict], DedupReport]:
        """
        Deduplicate a list of chunks.

        Args:
            chunks: List of dicts with at least 'id' and 'text' keys

        Returns:
            (unique_chunks, report) tuple
        """
        report = DedupReport(total_chunks=len(chunks))
        unique = []

        for chunk in chunks:
            chunk_id = str(chunk.get('id', chunk.get('chunk_id', '')))
            text = chunk.get('text', '')

            result = self.check_duplicate(chunk_id, text)
            report.details.append(result)

            if result.is_duplicate:
                report.duplicates_found += 1
                report.method_counts[result.dedup_method] += 1
                logger.debug(
                    f"Duplicate found: {chunk_id} ({result.dedup_method}) "
                    f"matches {result.matched_with}"
                )
            else:
                unique.append(chunk)
                if result.protected:
                    report.protected_chunks += 1

        logger.info(
            f"Deduplication complete: {report.total_chunks} → {len(unique)} unique "
            f"({report.duplicates_found} removed, {report.protected_chunks} protected)"
        )

        return unique, report

    def get_stats(self) -> dict:
        """Get deduplication statistics."""
        return {
            "exact_index_size": len(self._exact_index),
            "semantic_index_size": len(self._semantic_index),
            "protected_chunks": len(self._protected_chunks),
        }
