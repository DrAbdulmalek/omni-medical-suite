"""Confidence provenance contracts.

Scores from different OCR engines are not comparable by magnitude unless a
calibration contract explicitly says they are. This module therefore refuses
to combine raw cross-engine confidence values.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class ConfidenceEvidence:
    engine: str
    raw_confidence: float | None
    confidence_scale: str
    confidence_source: str
    calibration_version: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def combine_calibrated(evidence: Iterable[ConfidenceEvidence]) -> float | None:
    """Return the mean only when all usable scores share a calibration contract.

    Raw/missing scores are not silently coerced. A single uncalibrated or
    mismatched calibration version makes the aggregate unavailable.
    """
    items = list(evidence)
    if not items or any(e.raw_confidence is None for e in items):
        return None
    scales = {e.confidence_scale for e in items}
    versions = {e.calibration_version for e in items}
    if len(scales) != 1 or len(versions) != 1 or None in versions:
        return None
    if any(not 0.0 <= float(e.raw_confidence) <= 1.0 for e in items):
        raise ValueError("confidence must be within [0,1] after declared scaling")
    return sum(float(e.raw_confidence) for e in items) / len(items)
