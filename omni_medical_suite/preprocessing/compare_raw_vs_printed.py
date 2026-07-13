"""Compare raw OCR text against preprocessed / printed OCR text.

The validation log showed that a single global similarity score is unsafe for
medical forms.  This module therefore reports both full-text similarity and a
field-aware patient-safe similarity score.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from rapidfuzz import fuzz

from src.ocr.deduplication import WeightedMedicalDeduplicator, field_aware_similarity
from src.ocr.field_extractor import ArabicMedicalFieldExtractor
from src.ocr.normalization import arabic_strong_normalize
from src.ocr.rtl_utils import ArabicRTLFixer


@dataclass(slots=True)
class OCRComparisonResult:
    raw_text: str
    processed_text: str
    raw_vs_processed_similarity: float
    field_aware_similarity: dict[str, Any]
    raw_vs_reference_similarity: float | None = None
    processed_vs_reference_similarity: float | None = None
    improvement_vs_reference: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OCRComparisonPipeline:
    """Batch-friendly comparison pipeline for OCR experiments."""

    def __init__(self, extractor: ArabicMedicalFieldExtractor | None = None) -> None:
        self.extractor = extractor or ArabicMedicalFieldExtractor()
        self.rtl_fixer = ArabicRTLFixer()
        self.deduplicator = WeightedMedicalDeduplicator(extractor=self.extractor)

    @staticmethod
    def _text_similarity(left: str, right: str) -> float:
        if not left and not right:
            return 1.0
        if not left or not right:
            return 0.0
        return round(
            fuzz.ratio(arabic_strong_normalize(left), arabic_strong_normalize(right)) / 100.0,
            4,
        )

    def compare_texts(
        self,
        raw_text: str,
        processed_text: str,
        reference_text: str | None = None,
        *,
        force_rtl_fix: bool = False,
    ) -> OCRComparisonResult:
        raw_fixed = self.rtl_fixer.fix_text(raw_text, force=force_rtl_fix)
        processed_fixed = self.rtl_fixer.fix_text(processed_text, force=force_rtl_fix)
        field_similarity = field_aware_similarity(
            raw_fixed,
            processed_fixed,
            extractor=self.extractor,
        )

        raw_ref = None
        processed_ref = None
        delta = None
        if reference_text is not None:
            reference_fixed = self.rtl_fixer.fix_text(reference_text, force=force_rtl_fix)
            raw_ref = self._text_similarity(raw_fixed, reference_fixed)
            processed_ref = self._text_similarity(processed_fixed, reference_fixed)
            delta = round(processed_ref - raw_ref, 4)

        return OCRComparisonResult(
            raw_text=raw_fixed,
            processed_text=processed_fixed,
            raw_vs_processed_similarity=self._text_similarity(raw_fixed, processed_fixed),
            field_aware_similarity=field_similarity,
            raw_vs_reference_similarity=raw_ref,
            processed_vs_reference_similarity=processed_ref,
            improvement_vs_reference=delta,
        )

    def compare_batch(self, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for row in rows:
            result = self.compare_texts(
                row.get("raw_text", ""),
                row.get("processed_text", ""),
                row.get("reference_text"),
                force_rtl_fix=bool(row.get("force_rtl_fix", False)),
            )
            payload = result.to_dict()
            payload["document_id"] = row.get("document_id", "")
            results.append(payload)
        return results


def compare_raw_vs_printed_text(
    raw_text: str,
    processed_text: str,
    reference_text: str | None = None,
    *,
    force_rtl_fix: bool = False,
) -> dict[str, Any]:
    pipeline = OCRComparisonPipeline()
    return pipeline.compare_texts(
        raw_text,
        processed_text,
        reference_text,
        force_rtl_fix=force_rtl_fix,
    ).to_dict()
