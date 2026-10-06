"""Human-review gate for training data.

A staged correction is not training data until a reviewer explicitly approves
it. Rejected samples are retained as audit evidence but are never exportable.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import StrEnum


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class TrainingSample:
    incorrect_ocr_output: str
    correct_text: str
    category: str
    content_hash: str
    provenance: dict
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewer: str | None = None
    review_reason: str | None = None
    dataset_version: str | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        d["review_status"] = self.review_status.value
        return d


def validate_training_sample(row: dict) -> None:
    required = ("incorrect_ocr_output", "correct_text", "category", "content_hash")
    missing = [k for k in required if k not in row]
    if missing:
        raise ValueError(f"missing training fields: {', '.join(missing)}")
    status = row.get("review_status", ReviewStatus.PENDING.value)
    if status not in {s.value for s in ReviewStatus}:
        raise ValueError(f"invalid review_status: {status!r}")
    if status == ReviewStatus.APPROVED and not row.get("reviewer"):
        raise ValueError("approved samples require reviewer provenance")
    if not isinstance(row.get("provenance", {}), dict):
        raise ValueError("provenance must be an object")
