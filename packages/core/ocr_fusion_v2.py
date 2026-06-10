#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ocr_fusion_v2.py
================
محرك دمج OCR مرجّح مكانياً (Spatial-Weighted OCR Fusion V2).

الخوارزمية:
  1. جمع جميع الرموز من جميع المحركات
  2. فلترة حسب الحد الأدنى للثقة (0.55)
  3. تجميع مكاني باستخدام DBSCAN على مراكز BBox (eps=15)
  4. تصويت مرجّح داخل كل مجموعة (ثقة × وزن المحرك)
  5. مكافأة ×1.4 للمصطلحات الطبية الكاملة
  6. إعادة بناء الأسطر بالمحاذاة الأفقية

Spatial-weighted OCR fusion engine that merges tokens from multiple
OCR engines (Tesseract, EasyOCR, PaddleOCR, TrOCR, Surya) using
DBSCAN spatial clustering and weighted voting.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "EngineResult",
    "FusedResult",
    "FusedToken",
    "OCRFusionV2",
]

logger = logging.getLogger(__name__)

# ── أوزان المحركات الافتراضية / Default engine weights ───────────────────
_DEFAULT_ENGINE_WEIGHTS: dict[str, float] = {
    "tesseract": 0.85,
    "easyocr": 0.90,
    "paddleocr": 0.88,
    "trocr": 0.92,
    "surya": 0.87,
}

# ── قائمة المصطلحات الطبية الشائعة / Common medical terms for bonus ────
_MEDICAL_TERMS: set[str] = {
    # مصطلحات طبية عربية شائعة
    "تشخيص", "علاج", "جراحة", "أشعة", "مخبر", "مضاد",
    "حبوب", "حقنة", "مريض", "طبيب", "مستشفى", "عيادة",
    "ضغط", "سكري", "قلب", "رئة", "كبد", "كلى",
    "كسر", "التواء", "تمزق", "التهاب", "ورم", "نزيف",
    "تحليل", "صورة", "موجات", "منظار", "خزعة", " transfusion",
    # English medical terms
    "diagnosis", "treatment", "surgery", "radiology", "laboratory",
    "antibiotic", "prescription", "patient", "hospital", "clinic",
    "hypertension", "diabetes", "cardiac", "pulmonary", "hepatic",
    "renal", "fracture", "sprain", "tear", "inflammation",
    "tumor", "hemorrhage", "biopsy", "transfusion",
    "blood", "pressure", "dosage", "mg", "ml", "iv", "po",
}


@dataclass(slots=True)
class BBox:
    """مربع إحاطة بسيط / Simple bounding box."""

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    @property
    def center(self) -> tuple[int, int]:
        """مركز المربع."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass(slots=True)
class EngineResult:
    """نتيجة محرك OCR واحد / Result from a single OCR engine.

    Attributes:
        text: النص المتعرف عليه.
        confidence: درجة الثقة (0-1).
        bbox: مربع الإحاطة.
        engine_name: اسم المحرك (tesseract, easyocr, ...).
    """

    text: str
    confidence: float
    bbox: BBox
    engine_name: str


@dataclass(slots=True)
class FusedToken:
    """رمز مدمج من عدة محركات / A token fused from multiple engines."""

    text: str
    confidence: float
    contributing_engines: list[str] = field(default_factory=list)
    cluster_id: int = -1
    center: tuple[int, int] = (0, 0)
    is_medical_term: bool = False
    medical_bonus_applied: bool = False


@dataclass(slots=True)
class FusedResult:
    """نتيجة الدمج النهائية / Final fusion result.

    Attributes:
        text: النص المدمج الكامل.
        confidence: الثقة الإجمالية.
        strategy_used: اسم الاستراتيجية المستخدمة.
        engine_contributions: مساهمة كل محرك.
        tokens: الرموز المدمجة الفردية.
    """

    text: str
    confidence: float
    strategy_used: str
    engine_contributions: dict[str, float] = field(default_factory=dict)
    tokens: list[FusedToken] = field(default_factory=list)


class OCRFusionV2:
    """
    محرك دمج OCR الإصدار الثاني — تجميع مكاني + تصويت مرجّح.

    Algorithm overview:
      1. Collect all tokens from all engines.
      2. Filter by ``min_confidence``.
      3. Spatial clustering via DBSCAN on BBox centres (``eps=15``).
      4. Weighted voting within each cluster (confidence × engine_weight).
      5. ×1.4 bonus for complete medical terms.
      6. Reconstruct lines by horizontal alignment (Y-proximity).

    Parameters
    ----------
    min_confidence : float
        Minimum confidence for a token to be considered (default 0.55).
    dbscan_eps : int
        DBSCAN epsilon in pixels for spatial clustering (default 15).
    medical_bonus : float
        Confidence multiplier for recognised medical terms (default 1.4).
    engine_weights : dict[str, float] | None
        Per-engine reliability weights. Falls back to ``_DEFAULT_ENGINE_WEIGHTS``.
    line_tolerance_y : int
        Pixel tolerance for grouping tokens into the same text line (default 20).
    """

    def __init__(
        self,
        min_confidence: float = 0.55,
        dbscan_eps: int = 15,
        medical_bonus: float = 1.4,
        engine_weights: dict[str, float] | None = None,
        line_tolerance_y: int = 20,
    ) -> None:
        self.min_confidence = min_confidence
        self.dbscan_eps = dbscan_eps
        self.medical_bonus = medical_bonus
        self.engine_weights = engine_weights or dict(_DEFAULT_ENGINE_WEIGHTS)
        self.line_tolerance_y = line_tolerance_y

    def fuse(self, engine_results: list[EngineResult]) -> FusedResult:
        """دمج نتائج عدة محركات OCR.

        Args:
            engine_results: قائمة نتائج المحركات.

        Returns:
            ``FusedResult`` مع النص المدمج والثقة والتفاصيل.
        """
        if not engine_results:
            return FusedResult(
                text="",
                confidence=0.0,
                strategy_used="none",
            )

        # ── 1. الفلترة / Filter by confidence ─────────────────────────
        filtered = [
            r for r in engine_results if r.confidence >= self.min_confidence
        ]
        if not filtered:
            # تراجع: استخدم أعلى نتيجة حتى لو تحت العتبة
            best = max(engine_results, key=lambda r: r.confidence)
            return FusedResult(
                text=best.text,
                confidence=best.confidence,
                strategy_used="fallback_best",
                engine_contributions={best.engine_name: best.confidence},
            )

        # ── 2. التجميع المكاني / Spatial clustering (DBSCAN) ──────────
        clusters = self._dbscan_clusters(filtered)

        # ── 3. التصويت المرجّح لكل مجموعة / Weighted voting ─────────
        fused_tokens: list[FusedToken] = []
        for cluster_id, token_group in clusters.items():
            token = self._weighted_vote(token_group, cluster_id)
            fused_tokens.append(token)

        # ── 4. إعادة بناء الأسطر / Line reconstruction ──────────────
        lines = self._reconstruct_lines(fused_tokens)

        # ── 5. تجميع النتائج / Aggregate result ─────────────────────
        full_text = "\n".join(lines)
        avg_conf = (
            sum(t.confidence for t in fused_tokens) / len(fused_tokens)
            if fused_tokens
            else 0.0
        )

        contributions = self._compute_contributions(fused_tokens)

        return FusedResult(
            text=full_text,
            confidence=round(min(avg_conf, 1.0), 4),
            strategy_used="spatial_weighted_dbscan",
            engine_contributions=contributions,
            tokens=fused_tokens,
        )

    # ── تجميع DBSCAN / DBSCAN clustering ─────────────────────────────────

    def _dbscan_clusters(
        self, tokens: list[EngineResult]
    ) -> dict[int, list[EngineResult]]:
        """
        تجميع بسيط على نمط DBSCAN باستخدام مراكز BBox.

        Simple DBSCAN-style clustering on BBox centres. Does **not**
        require scikit-learn — the spatial domain is 2-D pixel
        coordinates and the dataset is small (hundreds of tokens at
        most), so a brute-force implementation is fast enough.
        """
        n = len(tokens)
        if n == 0:
            return {}

        # -1 = غير مصنّف, 0+ = معرّف المجموعة
        labels: list[int] = [-1] * n
        cluster_id = 0

        centres = [t.bbox.center for t in tokens]
        eps_sq = self.dbscan_eps ** 2

        def _neighbours(idx: int) -> list[int]:
            cx, cy = centres[idx]
            return [
                j
                for j in range(n)
                if (centres[j][0] - cx) ** 2 + (centres[j][1] - cy) ** 2
                <= eps_sq
            ]

        for i in range(n):
            if labels[i] != -1:
                continue
            neighbours = _neighbours(i)
            if len(neighbours) < 1:
                labels[i] = -1  # ضوضاء / noise
                continue
            cluster_id += 1
            labels[i] = cluster_id
            seed_set = list(neighbours)
            seed_set.remove(i)
            while seed_set:
                q = seed_set.pop(0)
                if labels[q] == -1:
                    labels[q] = cluster_id
                elif labels[q] != 0:
                    continue
                labels[q] = cluster_id
                q_neighbours = _neighbours(q)
                if len(q_neighbours) >= 1:
                    seed_set.extend(q_neighbours)

        clusters: dict[int, list[EngineResult]] = {}
        for idx, cid in enumerate(labels):
            if cid > 0:
                clusters.setdefault(cid, []).append(tokens[idx])
            else:
                # ضوضاء — مجموعتها الخاصة
                noise_id = cluster_id + idx
                clusters.setdefault(noise_id, []).append(tokens[idx])

        return clusters

    # ── التصويت المرجّح / Weighted voting ─────────────────────────────────

    def _weighted_vote(
        self, group: list[EngineResult], cluster_id: int
    ) -> FusedToken:
        """تصويت مرجّح داخل مجموعة واحدة.

        يحسب وزن كل نص = ثقة × وزن_المركب، ثم يختار الأعلى.
        يطبّق مكافأة ×1.4 إن كان النص مصطلحاً طبياً كاملاً.
        """
        if not group:
            return FusedToken(text="", confidence=0.0, cluster_id=cluster_id)

        best_score = -1.0
        best_text = ""
        best_conf = 0.0
        contributing: list[str] = []

        # تجميع النصوص المتطابقة
        text_votes: dict[str, list[tuple[float, str]]] = {}
        for token in group:
            normalized = token.text.strip()
            text_votes.setdefault(normalized, []).append(
                (token.confidence, token.engine_name)
            )

        for text, votes in text_votes.items():
            # مجموع الأوزان المرجّحة
            total_weight = 0.0
            total_conf = 0.0
            engines: list[str] = []
            for conf, engine in votes:
                w = self.engine_weights.get(engine, 0.5)
                total_weight += conf * w
                total_conf += conf
                engines.append(engine)

            # متوسط الثقة
            avg_conf = total_conf / len(votes)

            # مكافأة المصطلحات الطبية
            is_medical = self._is_medical_term(text)
            if is_medical:
                total_weight *= self.medical_bonus
                avg_conf = min(avg_conf * self.medical_bonus, 1.0)

            if total_weight > best_score:
                best_score = total_weight
                best_text = text
                best_conf = avg_conf
                contributing = list(set(engines))

        # مركز المجموعة (متوسط مراكز BBox)
        cx = sum(t.bbox.center[0] for t in group) // len(group)
        cy = sum(t.bbox.center[1] for t in group) // len(group)

        return FusedToken(
            text=best_text,
            confidence=round(best_conf, 4),
            contributing_engines=contributing,
            cluster_id=cluster_id,
            center=(cx, cy),
            is_medical_term=self._is_medical_term(best_text),
            medical_bonus_applied=(
                self._is_medical_term(best_text) and self.medical_bonus > 1.0
            ),
        )

    # ── إعادة بناء الأسطر / Line reconstruction ─────────────────────────

    def _reconstruct_lines(self, tokens: list[FusedToken]) -> list[str]:
        """ترتيب الرموز في أسطر حسب المحاذاة الأفقية.

        Tokens with similar Y-coordinates (within ``line_tolerance_y``)
        are placed on the same line and ordered left-to-right by X.
        """
        if not tokens:
            return []

        # ترتيب حسب Y ثم X
        sorted_tokens = sorted(tokens, key=lambda t: (t.center[1], t.center[0]))

        lines: list[list[str]] = []
        current_line: list[str] = []
        current_y = sorted_tokens[0].center[1]

        for token in sorted_tokens:
            if abs(token.center[1] - current_y) <= self.line_tolerance_y:
                current_line.append(token.text)
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [token.text]
                current_y = token.center[1]

        if current_line:
            lines.append(current_line)

        # دمج النص في كل سطر مع مسافة
        return [" ".join(line_tokens) for line_tokens in lines]

    # ── مساعدات / Helpers ────────────────────────────────────────────────

    @staticmethod
    def _is_medical_term(text: str) -> bool:
        """فحص إن كان النص يحتوي مصطلحاً طبياً."""
        text_lower = text.strip().lower()
        for term in _MEDICAL_TERMS:
            if term in text_lower:
                return True
        return False

    @staticmethod
    def _compute_contributions(
        tokens: list[FusedToken],
    ) -> dict[str, float]:
        """حساب مساهمة كل محرك في النتيجة النهائية."""
        contributions: dict[str, float] = {}
        for token in tokens:
            for engine in token.contributing_engines:
                contributions[engine] = (
                    contributions.get(engine, 0.0) + token.confidence
                )
        # تطبيع
        total = sum(contributions.values())
        if total > 0:
            contributions = {
                k: round(v / total, 4) for k, v in contributions.items()
            }
        return contributions