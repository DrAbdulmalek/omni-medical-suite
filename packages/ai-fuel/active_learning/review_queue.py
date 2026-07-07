"""
AI Fuel Engine - Human Review Queue

SQLite-backed persistence layer for the active-learning loop.  Chunks whose
classification confidence falls below the configured uncertainty threshold
are automatically queued for human review.  Reviewers can approve, reject,
or skip each sample; corrections are persisted and can be exported for
classifier retraining.

Schema (SQLite ``review_queue`` table)::

    id              INTEGER PRIMARY KEY AUTOINCREMENT
    text            TEXT NOT NULL
    predictions     TEXT NOT NULL  (JSON array of {category, confidence})
    confidence      REAL NOT NULL
    status          TEXT DEFAULT 'pending'
    correct_category TEXT
    notes           TEXT
    source_file     TEXT
    chunk_id        TEXT
    created_at      TEXT NOT NULL  (ISO 8601)
    reviewed_at     TEXT
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from core.schemas import ClassificationResult, ReviewSample, TextChunk

logger = logging.getLogger(__name__)

# Default path when None is passed to the constructor
_DEFAULT_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "db")
_DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "active_learning.db")

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS review_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    text            TEXT NOT NULL,
    predictions     TEXT NOT NULL,
    confidence      REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    correct_category TEXT,
    notes           TEXT DEFAULT '',
    source_file     TEXT DEFAULT '',
    chunk_id        TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    reviewed_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_rq_status   ON review_queue(status);
CREATE INDEX IF NOT EXISTS idx_rq_confidence ON review_queue(confidence);
CREATE INDEX IF NOT EXISTS idx_rq_category  ON review_queue(correct_category);
"""


class HumanReviewQueue:
    """Queue for uncertain classifications requiring human review.

    Uses a local SQLite database for durability.  Each entry corresponds
    to one :class:`ReviewSample`.  Samples are served ordered by lowest
    confidence so that the most uncertain classifications are reviewed
    first.

    Args:
        db_path: Path to the SQLite database file.  Parent directories
            are created automatically.  Defaults to
            ``db/active_learning.db`` relative to this package.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialise the review queue and create the database table."""
        self.db_path = db_path or _DEFAULT_DB_PATH

        # Ensure parent directories exist
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

        logger.info("HumanReviewQueue initialised (db=%s).", self.db_path)

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Create the review_queue table and indices if they don't exist."""
        try:
            self.conn.executescript(_CREATE_TABLE_SQL)
            self.conn.commit()
        except sqlite3.Error as exc:
            logger.error("Failed to create review_queue schema: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_uncertain_sample(
        self,
        chunk: TextChunk,
        classification: ClassificationResult,
    ) -> int:
        """Add a low-confidence sample to the review queue.

        Args:
            chunk: The text chunk whose classification is uncertain.
            classification: The classification result (expected to have
                a low ``confidence`` value).

        Returns:
            The auto-incremented row ID of the inserted sample.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Build predictions list: always include primary + alternatives
        predictions = [
            {"category": classification.category, "confidence": classification.confidence}
        ]
        for alt in classification.alternatives:
            predictions.append(
                {"category": alt.get("category", ""), "confidence": alt.get("confidence", 0.0)}
            )

        try:
            cursor = self.conn.execute(
                """
                INSERT INTO review_queue
                    (text, predictions, confidence, status, source_file, chunk_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.text,
                    json.dumps(predictions, ensure_ascii=False),
                    classification.confidence,
                    "pending",
                    chunk.source_file or "",
                    chunk.id,
                    now,
                ),
            )
            self.conn.commit()
            sample_id = cursor.lastrowid
            logger.info(
                "Queued sample %d (chunk=%s, conf=%.4f, category=%s).",
                sample_id,
                chunk.id,
                classification.confidence,
                classification.category,
            )
            return int(sample_id)
        except sqlite3.Error as exc:
            logger.error("Failed to queue sample: %s", exc)
            raise

    def get_pending_samples(
        self,
        limit: int = 10,
        category: Optional[str] = None,
    ) -> List[ReviewSample]:
        """Get samples pending review, ordered by lowest confidence first.

        Args:
            limit: Maximum number of samples to return.
            category: If provided, filter to samples whose predicted
                category matches.

        Returns:
            A list of :class:`ReviewSample` instances.
        """
        try:
            if category:
                rows = self.conn.execute(
                    """
                    SELECT * FROM review_queue
                    WHERE status = 'pending'
                      AND json_extract(predictions, '$[0].category') = ?
                    ORDER BY confidence ASC
                    LIMIT ?
                    """,
                    (category, limit),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """
                    SELECT * FROM review_queue
                    WHERE status = 'pending'
                    ORDER BY confidence ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            samples: List[ReviewSample] = []
            for row in rows:
                samples.append(self._row_to_sample(row))

            logger.debug("Retrieved %d pending samples.", len(samples))
            return samples

        except sqlite3.Error as exc:
            logger.error("Failed to fetch pending samples: %s", exc)
            return []

    def submit_feedback(
        self,
        sample_id: int,
        correct_category: str,
        notes: Optional[str] = None,
    ) -> None:
        """Submit human correction for a queued sample.

        Args:
            sample_id: The row ID of the sample.
            correct_category: The human-annotated correct category.
            notes: Optional reviewer notes.

        Raises:
            ValueError: If the sample does not exist or is not pending.
        """
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Verify the sample exists and is pending
            row = self.conn.execute(
                "SELECT status FROM review_queue WHERE id = ?",
                (sample_id,),
            ).fetchone()

            if row is None:
                raise ValueError(f"Sample {sample_id} does not exist.")

            if row["status"] != "pending":
                raise ValueError(
                    f"Sample {sample_id} is already '{row['status']}'; "
                    "cannot submit feedback."
                )

            self.conn.execute(
                """
                UPDATE review_queue
                SET status = 'approved',
                    correct_category = ?,
                    notes = COALESCE(?, notes),
                    reviewed_at = ?
                WHERE id = ?
                """,
                (correct_category, notes, now, sample_id),
            )
            self.conn.commit()

            logger.info(
                "Feedback submitted for sample %d → category='%s'.",
                sample_id,
                correct_category,
            )

        except sqlite3.Error as exc:
            logger.error("Failed to submit feedback for sample %d: %s", sample_id, exc)
            raise

    def reject_sample(self, sample_id: int, notes: Optional[str] = None) -> None:
        """Mark a sample as rejected (incorrectly queued).

        Args:
            sample_id: The row ID of the sample.
            notes: Optional reason for rejection.
        """
        now = datetime.now(timezone.utc).isoformat()

        try:
            self.conn.execute(
                """
                UPDATE review_queue
                SET status = 'rejected',
                    notes = COALESCE(?, notes),
                    reviewed_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (notes, now, sample_id),
            )
            self.conn.commit()
            logger.info("Sample %d rejected.", sample_id)

        except sqlite3.Error as exc:
            logger.error("Failed to reject sample %d: %s", sample_id, exc)
            raise

    def skip_sample(self, sample_id: int) -> None:
        """Skip a sample (leave it pending for later review).

        Args:
            sample_id: The row ID of the sample.
        """
        try:
            self.conn.execute(
                """
                UPDATE review_queue
                SET status = 'skipped'
                WHERE id = ? AND status = 'pending'
                """,
                (sample_id,),
            )
            self.conn.commit()
            logger.info("Sample %d skipped.", sample_id)

        except sqlite3.Error as exc:
            logger.error("Failed to skip sample %d: %s", sample_id, exc)
            raise

    def get_feedback_stats(self) -> Dict:
        """Get aggregate feedback statistics.

        Returns:
            A dictionary with counts for each status, category
            distribution of corrections, and average confidence of
            pending samples.
        """
        try:
            status_counts = self.conn.execute(
                "SELECT status, COUNT(*) as cnt FROM review_queue GROUP BY status"
            ).fetchall()

            total_pending = 0
            category_distribution: Dict[str, int] = {}
            status_map: Dict[str, int] = {}

            for row in status_counts:
                status_map[row["status"]] = row["cnt"]
                if row["status"] == "pending":
                    total_pending = row["cnt"]

            # Category distribution of corrections
            correction_rows = self.conn.execute(
                """
                SELECT correct_category, COUNT(*) as cnt
                FROM review_queue
                WHERE status = 'approved' AND correct_category IS NOT NULL
                GROUP BY correct_category
                ORDER BY cnt DESC
                """
            ).fetchall()

            for row in correction_rows:
                category_distribution[row["correct_category"]] = row["cnt"]

            # Average confidence of pending samples
            avg_conf = self.conn.execute(
                "SELECT AVG(confidence) as avg FROM review_queue WHERE status = 'pending'"
            ).fetchone()

            return {
                "total_samples": sum(status_map.values()),
                "status_counts": status_map,
                "pending_count": total_pending,
                "approved_count": status_map.get("approved", 0),
                "rejected_count": status_map.get("rejected", 0),
                "skipped_count": status_map.get("skipped", 0),
                "correction_distribution": category_distribution,
                "avg_pending_confidence": round(avg_conf["avg"], 4) if avg_conf["avg"] else 0.0,
            }

        except sqlite3.Error as exc:
            logger.error("Failed to compute feedback stats: %s", exc)
            return {}

    def export_corrections(self, output_path: str) -> str:
        """Export all approved corrections for classifier retraining.

        Produces a JSONL file where each line contains the text, the
        original predicted category, and the human-corrected category.

        Args:
            output_path: Filesystem path for the output JSONL file.

        Returns:
            The absolute path to the exported file.
        """
        try:
            rows = self.conn.execute(
                """
                SELECT text,
                       json_extract(predictions, '$[0].category') AS predicted,
                       correct_category,
                       confidence,
                       source_file
                FROM review_queue
                WHERE status = 'approved' AND correct_category IS NOT NULL
                ORDER BY confidence ASC
                """
            ).fetchall()

            output_path = os.path.abspath(output_path)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as fh:
                for row in rows:
                    record = {
                        "text": row["text"],
                        "predicted_category": row["predicted"],
                        "correct_category": row["correct_category"],
                        "confidence": row["confidence"],
                        "source_file": row["source_file"],
                    }
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")

            logger.info(
                "Exported %d corrections to %s.", len(rows), output_path
            )
            return output_path

        except (sqlite3.Error, OSError) as exc:
            logger.error("Failed to export corrections: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_sample(row: sqlite3.Row) -> ReviewSample:
        """Convert a database row to a :class:`ReviewSample`."""
        predictions = json.loads(row["predictions"]) if row["predictions"] else []

        return ReviewSample(
            id=row["id"],
            text=row["text"],
            predictions=predictions,
            confidence=row["confidence"],
            status=row["status"],
            correct_category=row["correct_category"],
            created_at=datetime.fromisoformat(row["created_at"]),
            reviewed_at=(
                datetime.fromisoformat(row["reviewed_at"])
                if row["reviewed_at"]
                else None
            ),
        )

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
        logger.info("Review queue database connection closed.")

    def __enter__(self) -> "HumanReviewQueue":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        self.close()

    def __repr__(self) -> str:
        stats = self.get_feedback_stats()
        return (
            f"HumanReviewQueue(db={self.db_path}, "
            f"pending={stats.get('pending_count', '?')}, "
            f"approved={stats.get('approved_count', '?')})"
        )
