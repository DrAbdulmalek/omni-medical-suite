"""Compare raw OCR text against preprocessed / printed OCR text.

The validation log showed that a single global similarity score is unsafe for
medical forms.  This module therefore reports both full-text similarity and a
field-aware patient-safe similarity score.

P1-2 (v1.1.0-rc): added CSV/JSON export and aggregate metrics for batch runs.
"""

from __future__ import annotations

import csv
import io
import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

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

    # ------------------------------------------------------------------
    # P1-2: CSV / JSON export + aggregate metrics
    # ------------------------------------------------------------------
    @staticmethod
    def to_csv(
        results: list[dict[str, Any]],
        path: str | Path | None = None,
        *,
        flatten_field_aware: bool = True,
    ) -> str:
        """Serialize comparison results to CSV.

        Args:
            results: list of result dicts (from compare_batch or result.to_dict()).
            path: output file path. If None, returns the CSV as a string.
            flatten_field_aware: if True, flatten the field_aware_similarity
                dict into top-level columns (field_aware_similarity.<key>);
                otherwise serialize it as a JSON string in one column.

        Returns:
            The CSV content as a string (also written to `path` if given).
        """
        if not results:
            csv_str = ""
        else:
            # Build a flattened row list
            flat_rows: list[dict[str, Any]] = []
            for r in results:
                row = {}
                for k, v in r.items():
                    if k == "field_aware_similarity" and isinstance(v, dict):
                        if flatten_field_aware:
                            for sub_k, sub_v in v.items():
                                row[f"field_aware_similarity.{sub_k}"] = sub_v
                        else:
                            row["field_aware_similarity"] = json.dumps(v, ensure_ascii=False)
                    else:
                        row[k] = v
                flat_rows.append(row)
            # Collect all column names (preserve insertion order, but make unique)
            seen: set[str] = set()
            fieldnames: list[str] = []
            for row in flat_rows:
                for k in row.keys():
                    if k not in seen:
                        seen.add(k)
                        fieldnames.append(k)
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in flat_rows:
                writer.writerow(row)
            csv_str = buf.getvalue()
        if path is not None:
            Path(path).expanduser().write_text(csv_str, encoding="utf-8")
        return csv_str

    @staticmethod
    def to_json(
        results: list[dict[str, Any]],
        path: str | Path | None = None,
        *,
        indent: int = 2,
    ) -> str:
        """Serialize comparison results to JSON.

        Args:
            results: list of result dicts.
            path: output file path. If None, returns the JSON as a string.
            indent: JSON indentation (default 2).

        Returns:
            The JSON content as a string (also written to `path` if given).
        """
        json_str = json.dumps(results, ensure_ascii=False, indent=indent, default=str)
        if path is not None:
            Path(path).expanduser().write_text(json_str, encoding="utf-8")
        return json_str

    @staticmethod
    def aggregate_metrics(
        results: list[dict[str, Any]],
        *,
        percentiles: Iterable[float] = (0.5, 0.9, 0.95),
    ) -> dict[str, Any]:
        """Compute summary statistics across a batch of comparison results.

        Returns a dict with:
        - count: number of results
        - for each numeric metric (raw_vs_processed_similarity,
          raw_vs_reference_similarity, processed_vs_reference_similarity,
          improvement_vs_reference): min, max, mean, median, stdev,
          and requested percentiles.
        - field_aware sub-keys are aggregated separately (same stats).
        - improvement_mean: mean of improvement_vs_reference (convenience).
        - processed_better_count: how many results had
          processed_vs_reference > raw_vs_reference.

        Args:
            results: list of result dicts.
            percentiles: percentiles to compute (default p50, p90, p95).
        """
        if not results:
            return {"count": 0}

        pctiles = sorted(set(percentiles))
        # Top-level numeric metrics
        top_level_metrics = [
            "raw_vs_processed_similarity",
            "raw_vs_reference_similarity",
            "processed_vs_reference_similarity",
            "improvement_vs_reference",
        ]
        agg: dict[str, Any] = {"count": len(results)}

        for metric in top_level_metrics:
            values = [
                r[metric]
                for r in results
                if r.get(metric) is not None and isinstance(r[metric], (int, float))
            ]
            agg[metric] = _stats(values, pctiles)

        # Field-aware sub-metrics
        fa_keys: set[str] = set()
        for r in results:
            fa = r.get("field_aware_similarity")
            if isinstance(fa, dict):
                fa_keys.update(fa.keys())
        agg["field_aware_similarity"] = {}
        for key in sorted(fa_keys):
            values: list[float] = []
            for r in results:
                fa = r.get("field_aware_similarity")
                if isinstance(fa, dict):
                    v = fa.get(key)
                    if isinstance(v, (int, float)):
                        values.append(float(v))
            agg["field_aware_similarity"][key] = _stats(values, pctiles)

        # Convenience rollups
        improvements = [
            r["improvement_vs_reference"]
            for r in results
            if r.get("improvement_vs_reference") is not None
        ]
        agg["improvement_mean"] = (
            round(statistics.mean(improvements), 4) if improvements else None
        )
        better_count = sum(
            1
            for r in results
            if r.get("processed_vs_reference_similarity") is not None
            and r.get("raw_vs_reference_similarity") is not None
            and r["processed_vs_reference_similarity"] > r["raw_vs_reference_similarity"]
        )
        agg["processed_better_count"] = better_count
        agg["processed_better_ratio"] = (
            round(better_count / len(results), 4) if results else 0.0
        )
        return agg


def _stats(values: list[float], percentiles: list[float]) -> dict[str, Any]:
    """Compute min/max/mean/median/stdev/percentiles for a numeric list."""
    if not values:
        return {"count": 0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    result: dict[str, Any] = {
        "count": n,
        "min": round(sorted_vals[0], 4),
        "max": round(sorted_vals[-1], 4),
        "mean": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
    }
    if n >= 2:
        result["stdev"] = round(statistics.stdev(values), 4)
    else:
        result["stdev"] = 0.0
    # Percentiles via linear interpolation (statistics.quantiles in 3.8+)
    for p in percentiles:
        key = f"p{int(p * 100)}"
        if n == 1:
            result[key] = round(sorted_vals[0], 4)
        else:
            try:
                q = statistics.quantiles(values, n=100, method="inclusive")[
                    int(p * 100) - 1
                ]
                result[key] = round(q, 4)
            except Exception:
                result[key] = None
    return result


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
