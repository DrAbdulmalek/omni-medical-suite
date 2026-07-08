"""
OmniMedical Suite — Feedback Collection System.

Lightweight feedback model and collector. In production (with database),
feedback is persisted. In standalone/Gradio mode, feedback is saved to a
local JSONL file for later analysis.

Usage (standalone):
    from app.core.monitoring.feedback import FeedbackCollector
    collector = FeedbackCollector()
    collector.submit(rating=4, category="ocr", message="Great Arabic recognition!")

Usage (API):
    POST /api/feedback  {"rating": 5, "category": "translation", "message": "Accurate!"}
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class Feedback:
    """User feedback entry."""
    rating: int  # 1-5
    category: str  # ocr, translation, ui, performance, bug, feature_request
    message: str
    metadata: dict | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class FeedbackCollector:
    """
    Collects and persists user feedback.
    Falls back to JSONL file storage when no database is available.
    """

    VALID_CATEGORIES = {"ocr", "translation", "ui", "performance", "bug", "feature_request"}

    def __init__(self, storage_path: str | None = None):
        self._storage_path = Path(storage_path) if storage_path else Path("data/feedback.jsonl")
        self._feedback: list[Feedback] = []
        if self._storage_path.exists():
            self._load()

    def submit(
        self,
        rating: int,
        category: str,
        message: str,
        metadata: dict | None = None,
    ) -> Feedback:
        """Submit a feedback entry. Returns the created Feedback object."""
        if category not in self.VALID_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {self.VALID_CATEGORIES}")
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        fb = Feedback(rating=rating, category=category, message=message, metadata=metadata)
        self._feedback.append(fb)
        self._save(fb)
        return fb

    def get_stats(self) -> dict:
        """Get aggregated feedback statistics."""
        if not self._feedback:
            return {"total": 0, "avg_rating": 0.0, "by_category": {}}

        by_cat: dict[str, list[int]] = {}
        for fb in self._feedback:
            by_cat.setdefault(fb.category, []).append(fb.rating)

        return {
            "total": len(self._feedback),
            "avg_rating": round(sum(fb.rating for fb in self._feedback) / len(self._feedback), 2),
            "by_category": {
                cat: {"count": len(ratings), "avg_rating": round(sum(ratings) / len(ratings), 2)}
                for cat, ratings in by_cat.items()
            },
        }

    def get_recent(self, n: int = 50) -> list[dict]:
        """Get the most recent N feedback entries."""
        return [asdict(fb) for fb in self._feedback[-n:]]

    def _save(self, fb: Feedback):
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(fb), default=str, ensure_ascii=False) + "\n")

    def _load(self):
        if self._storage_path.exists():
            with open(self._storage_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._feedback.append(Feedback(**json.loads(line)))
                        except (json.JSONDecodeError, TypeError):
                            continue
