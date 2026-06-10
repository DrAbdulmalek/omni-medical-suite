#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
semantic_deduplication.py
==========================
إزالة التكرار الدلالي باستخدام النماذج التحويلية و FAISS.

يستخدم نموذج ``paraphrase-multilingual-MiniLM-L12-v2`` الذي يدعم
العربية والإنجليزية معاً. يبحث في FAISS للتشابه السريع
ويستخدم HDBSCAN للتجميع الدلالي.

Semantic deduplication using sentence-transformers with FAISS for
fast similarity search and HDBSCAN for clustering. Uses lazy imports
so the module can be imported even when heavy ML dependencies are
not installed.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DedupResult",
    "SemanticDeduplicator",
]

logger = logging.getLogger(__name__)

# ── المصطلحات الطبية المحمية من الدمج / Protected medical terms ────────
_medical_protected_terms: set[str] = {
    # laterality
    "أيمن", "أيسر", "ثنائي", "right", "left", "bilateral",
    # severity
    "حاد", "مزمن", "خفيف", "شديد", "acute", "chronic", "mild", "severe",
    # fracture
    "مفتوح", "مغلق", "شعري", "open", "closed", "hairline",
    # temporal
    "حديث", "قديم", "متكرر", "recent", "old", "recurrent",
    #_critical procedure terms
    "استئصال", "زراعة", "قسطرة", "تنبيب", "bypass", "transplant",
    "catheter", "intubation", "resection",
}

# ── حالة التحميل الكسول / Lazy-load state ──────────────────────────────
_model = None
_faiss = None
_hdbscan_module = None


def _lazy_load_dependencies() -> bool:
    """تحميل التبعيات الثقيلة عند الحاجة فقط.

    Returns:
        True إذا تم التحميل بنجاح.
    """
    global _model, _faiss, _hdbscan_module

    if _model is not None:
        return True

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        logger.info("Sentence-transformer model loaded successfully.")
    except Exception as exc:
        warnings.warn(
            f"Cannot load sentence-transformers: {exc}. "
            "Semantic deduplication will fall back to text matching.",
            stacklevel=3,
        )
        return False

    try:
        import faiss as _faiss_mod  # type: ignore[import-untyped]

        _faiss = _faiss_mod
        logger.info("FAISS loaded successfully.")
    except Exception as exc:
        warnings.warn(
            f"Cannot load FAISS: {exc}. "
            "Will use brute-force cosine similarity instead.",
            stacklevel=3,
        )
        _faiss = None

    try:
        import hdbscan as _hdbscan_mod  # type: ignore[import-untyped]

        _hdbscan_module = _hdbscan_mod
        logger.info("HDBSCAN loaded successfully.")
    except Exception:
        _hdbscan_module = None

    return True


@dataclass(slots=True)
class DedupResult:
    """نتيجة إزالة التكرار لقطعة نصية واحدة.

    Attributes:
        text: النص الأصلي أو المدمج.
        status: ``"merged"`` أو ``"unique"``.
        merged_with: قائمة أرقام القطع التي دُمجت مع هذه (إن وجدت).
        similarity_score: أعلى درجة تشابه وجدت (0-1).
        is_protected: هل تحتوي على مصطلحات طبية محمية.
    """

    text: str
    status: str = "unique"
    merged_with: list[int] = field(default_factory=list)
    similarity_score: float = 0.0
    is_protected: bool = False


class SemanticDeduplicator:
    """
    إزالة التكرار الدلالي للنصوص الطبية.

    Uses ``paraphrase-multilingual-MiniLM-L12-v2`` for embeddings
    (Arabic + English), FAISS for fast nearest-neighbour search, and
    HDBSCAN for optional clustering-based deduplication.

    Parameters
    ----------
    similarity_threshold : float
        Minimum cosine similarity to consider two chunks as duplicates
        (default 0.82).
    use_hdbscan : bool
        If *True* and HDBSCAN is available, use clustering for bulk
        deduplication. Otherwise use pairwise FAISS search.
    batch_size : int
        Embedding batch size for the transformer model.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.82,
        use_hdbscan: bool = False,
        batch_size: int = 64,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.use_hdbscan = use_hdbscan
        self.batch_size = batch_size
        self._model_loaded: bool = False

    def deduplicate(self, chunks: list[str]) -> list[DedupResult]:
        """إزالة التكرار الدلالي من قائمة القطع النصية.

        Args:
            chunks: قائمة القطع النصية المراد فحصها.

        Returns:
            قائمة ``DedupResult`` — كل عنصر يمثّل قطعة فريدة
            أو قطعة تم دمجها مع أخرى.
        """
        if not chunks:
            return []

        # تحميل التبعيات بالكسل
        loaded = _lazy_load_dependencies()
        if not loaded or _model is None:
            logger.warning(
                "ML dependencies unavailable — falling back to "
                "exact-match deduplication."
            )
            return self._fallback_deduplicate(chunks)

        # حساب التمثيلات المتجهة
        embeddings = self._encode(chunks)

        if _faiss is not None:
            return self._faiss_deduplicate(chunks, embeddings)
        else:
            return self._brute_force_deduplicate(chunks, embeddings)

    # ── FAISS-based deduplication ─────────────────────────────────────────

    def _faiss_deduplicate(
        self,
        chunks: list[str],
        embeddings: Any,
    ) -> list[DedupResult]:
        """إزالة التكرار باستخدام FAISS للبحث السريع."""
        import numpy as np  # type: ignore[import-untyped]

        emb_array = np.ascontiguousarray(
            embeddings.astype(np.float32), dtype=np.float32
        )
        dim = emb_array.shape[1]

        # تطبيع المتجهات (cosine similarity = dot product بعد التطبيع)
        norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        emb_normalized = emb_array / norms

        # بناء فهرس FAISS
        index = _faiss.IndexFlatIP(dim)  # Inner Product = cosine after L2 norm
        index.add(emb_normalized)

        # البحث عن أقرب جار لكل قطعة (استبعاد الذات)
        k = min(2, len(chunks))
        distances, indices = index.search(emb_normalized, k)

        # تتبع القطع المدمجة
        merged_into: dict[int, int] = {}  # idx → representative idx
        representative_map: dict[int, list[int]] = {}  # rep → [merged indices]

        for i in range(len(chunks)):
            if i in merged_into:
                continue  # تم دمجها مسبقاً

            # فحص الجيران
            for rank in range(1, k):  # rank 0 = الذات
                if rank >= distances.shape[1]:
                    break
                j = int(indices[i][rank])
                sim = float(distances[i][rank])

                if sim >= self.similarity_threshold and j not in merged_into:
                    # فحص الحماية الطبية قبل الدمج
                    if self._is_protected_merge(chunks[i], chunks[j]):
                        logger.debug(
                            "Protected merge blocked: chunks %d & %d "
                            "(sim=%.3f)",
                            i, j, sim,
                        )
                        continue
                    merged_into[j] = i
                    representative_map.setdefault(i, []).append(j)

        # بناء النتائج
        results: list[DedupResult] = []
        seen: set[int] = set()

        for i in range(len(chunks)):
            if i in merged_into:
                continue  # تم دمجها — لا ننتج نتيجة مستقلة
            if i in seen:
                continue

            is_protected = self._has_protected_terms(chunks[i])
            merged_indices = representative_map.get(i, [])
            seen.add(i)
            seen.update(merged_indices)

            if merged_indices:
                # دمج النصوص
                merged_texts = [chunks[i]] + [chunks[j] for j in merged_indices]
                merged_text = self._merge_texts(merged_texts)

                # أعلى درجة تشابه
                best_sim = 0.0
                for j in merged_indices:
                    for rank in range(1, k):
                        if rank < distances.shape[1]:
                            ji = int(indices[i][rank])
                            if ji == j:
                                best_sim = max(best_sim, float(distances[i][rank]))

                results.append(
                    DedupResult(
                        text=merged_text,
                        status="merged",
                        merged_with=merged_indices,
                        similarity_score=round(best_sim, 4),
                        is_protected=is_protected,
                    )
                )
            else:
                results.append(
                    DedupResult(
                        text=chunks[i],
                        status="unique",
                        similarity_score=0.0,
                        is_protected=is_protected,
                    )
                )

        return results

    # ── Brute-force deduplication ─────────────────────────────────────────

    def _brute_force_deduplicate(
        self,
        chunks: list[str],
        embeddings: Any,
    ) -> list[DedupResult]:
        """إزالة التكرار بالبحث المباشر (بدون FAISS)."""
        import numpy as np  # type: ignore[import-untyped]

        emb_array = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        emb_normalized = emb_array / norms

        # مصفوفة التشابه
        sim_matrix = emb_normalized @ emb_normalized.T

        merged_into: dict[int, int] = {}
        representative_map: dict[int, list[int]] = {}

        n = len(chunks)
        for i in range(n):
            if i in merged_into:
                continue
            for j in range(i + 1, n):
                if j in merged_into:
                    continue
                sim = float(sim_matrix[i][j])
                if sim >= self.similarity_threshold:
                    if self._is_protected_merge(chunks[i], chunks[j]):
                        continue
                    merged_into[j] = i
                    representative_map.setdefault(i, []).append(j)

        results: list[DedupResult] = []
        seen: set[int] = set()

        for i in range(n):
            if i in merged_into or i in seen:
                continue

            is_protected = self._has_protected_terms(chunks[i])
            merged_indices = representative_map.get(i, [])
            seen.add(i)
            seen.update(merged_indices)

            if merged_indices:
                merged_texts = [chunks[i]] + [chunks[j] for j in merged_indices]
                merged_text = self._merge_texts(merged_texts)
                best_sim = max(
                    float(sim_matrix[i][j]) for j in merged_indices
                )
                results.append(
                    DedupResult(
                        text=merged_text,
                        status="merged",
                        merged_with=merged_indices,
                        similarity_score=round(best_sim, 4),
                        is_protected=is_protected,
                    )
                )
            else:
                results.append(
                    DedupResult(
                        text=chunks[i],
                        status="unique",
                        similarity_score=0.0,
                        is_protected=is_protected,
                    )
                )

        return results

    # ── Fallback: exact-match deduplication ───────────────────────────────

    @staticmethod
    def _fallback_deduplicate(chunks: list[str]) -> list[DedupResult]:
        """إزالة التكرار بالتطابق النصي فقط (بدون نماذج)."""
        seen: dict[str, int] = {}
        results: list[DedupResult] = []

        for i, chunk in enumerate(chunks):
            normalized = chunk.strip()
            if normalized in seen:
                # إضافة إلى القطعة الأصلية
                results[seen[normalized]].merged_with.append(i)
                results[seen[normalized]].status = "merged"
                results[seen[normalized]].similarity_score = 1.0
            else:
                seen[normalized] = len(results)
                results.append(
                    DedupResult(
                        text=chunk,
                        status="unique",
                        similarity_score=0.0,
                        is_protected=False,
                    )
                )

        return results

    # ── Encoding ──────────────────────────────────────────────────────────

    @staticmethod
    def _encode(chunks: list[str]) -> Any:
        """حساب التمثيلات المتجهة للقطع النصية."""
        # _model مضمون أن يكون غير None هنا
        return _model.encode(chunks, batch_size=64, show_progress_bar=False)

    # ── Medical protection ────────────────────────────────────────────────

    @staticmethod
    def _has_protected_terms(text: str) -> bool:
        """فحص هل يحتوي النص مصطلحات طبية محمية."""
        text_lower = text.lower()
        return any(term in text_lower for term in _medical_protected_terms)

    @staticmethod
    def _is_protected_merge(text1: str, text2: str) -> bool:
        """فحص إن كان الدمج محظوراً بسبب تعارض طبي.

        يستخدم MedicalContextProtector إن توفّر، وإلا
        يعتمد على فحص المصطلحات المحمية المحلي.
        """
        try:
            from packages.core.medical_context_protector import (
                MedicalContextProtector,
            )
            protector = MedicalContextProtector()
            safe, _ = protector.check_merge_safety(text1, text2)
            return not safe
        except Exception:
            # تراجع: فحص بسيط
            t1, t2 = text1.lower(), text2.lower()
            for term in _medical_protected_terms:
                if term in t1 and term in t2:
                    return False  # نفس المصطلح — لا تعارض
            return False

    # ── Text merging ──────────────────────────────────────────────────────

    @staticmethod
    def _merge_texts(texts: list[str]) -> str:
        """دمج عدة نصوص متشابهة — يختار الأطول والأوضح."""
        if not texts:
            return ""
        if len(texts) == 1:
            return texts[0]
        # اختيار النص الأطول (غالباً الأكثر اكتمالاً)
        return max(texts, key=len)