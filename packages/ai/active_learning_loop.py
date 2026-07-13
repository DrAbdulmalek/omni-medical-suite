# active_learning_loop.py - Active learning feedback loop for OCR improvement

"""Orchestrates the full active-learning cycle: submit OCR results, queue
low-confidence items for human review, collect corrections, and export
training datasets for fine-tuning.

All heavy dependencies (torch, transformers) are imported lazily so the
module can be imported without them.
"""

import json
import csv
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = ["ActiveLearningLoop"]


class ActiveLearningLoop:
    """End-to-end active learning feedback loop.

    Combines :class:`ActiveLearningDB` (persistence) and
    :class:`ActiveLearner` (correction logging & retraining) into a
    single, thread-safe interface that can be used by an OCR pipeline,
    a review UI, or a batch-export script.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        db_path: str = "active_learning.db",
        auto_train_threshold: int = 50,
        min_confidence_for_review: float = 0.7,
    ) -> None:
        self._db_path = db_path
        self._auto_train_threshold = auto_train_threshold
        self._min_confidence_for_review = min_confidence_for_review

        # Lazily initialised on first use
        self._db = None
        self._learner = None

    # ------------------------------------------------------------------
    # Internal helpers (lazy import & singleton accessors)
    # ------------------------------------------------------------------

    def _get_db(self):
        """Return the :class:`ActiveLearningDB` instance (lazy import)."""
        if self._db is None:
            from packages.ai.active_learning import ActiveLearningDB  # noqa: WPS433

            self._db = ActiveLearningDB(self._db_path)
            logger.debug("ActiveLearningDB initialised (path=%s)", self._db_path)
        return self._db

    def _get_learner(self):
        """Return the :class:`ActiveLearner` instance (lazy import)."""
        if self._learner is None:
            from packages.ai.active_learning import ActiveLearner  # noqa: WPS433

            self._learner = ActiveLearner(self._db_path)
            logger.debug("ActiveLearner initialised (path=%s)", self._db_path)
        return self._learner

    # ------------------------------------------------------------------
    # 1. Submit an OCR result
    # ------------------------------------------------------------------

    def submit_ocr_result(
        self,
        original_text: str,
        ocr_text: str,
        confidence: float,
        language: str = "ar",
        image_path: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Record an OCR result and decide whether it needs review.

        If *confidence* is below :attr:`min_confidence_for_review` the
        item is queued for human review; otherwise it is auto-accepted.

        Returns:
            A dict with keys ``id``, ``status`` (``"accepted"`` or
            ``"queued_for_review"``), and ``metadata``.
        """
        db = self._get_db()
        needs_review = confidence < self._min_confidence_for_review

        # When queued for review we leave corrected_text as NULL so that
        # get_review_queue() can distinguish unreviewed items.
        corrected_text = None if needs_review else ocr_text

        training_id = db.save_training_data(
            image_path=image_path or "",
            original_text=ocr_text,
            corrected_text=corrected_text,
            language=language,
            confidence=confidence,
        )

        status = "queued_for_review" if needs_review else "accepted"
        logger.info(
            "OCR result submitted: training_id=%d  status=%s  confidence=%.3f  lang=%s",
            training_id,
            status,
            confidence,
            language,
        )

        return {
            "id": training_id,
            "status": status,
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    # 2. Submit a human correction
    # ------------------------------------------------------------------

    def submit_human_correction(
        self,
        review_id: int,
        corrected_text: str,
        reviewer: str = "human",
    ) -> int:
        """Apply a human correction to a previously queued item.

        Updates the training-data row, logs the correction via
        :class:`ActiveLearner`, and checks whether the
        ``auto_train_threshold`` has been reached.

        Returns:
            The correction ID from :meth:`ActiveLearner.log_correction`.
        """
        db = self._get_db()

        # --- Update the training_data row with the corrected text ------
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT original_text, language, confidence, image_path
                FROM training_data WHERE id = ?
                """,
                (review_id,),
            )
            row = cursor.fetchone()

        if row is None:
            raise ValueError(f"No training_data row found with id={review_id}")

        ocr_text, language, confidence, image_path = row

        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE training_data
                SET corrected_text = ?
                WHERE id = ?
                """,
                (corrected_text, review_id),
            )
            if cursor.rowcount == 0:
                raise RuntimeError(
                    f"Failed to update training_data row id={review_id}"
                )

        logger.info(
            "Training data row %d updated with human correction (reviewer=%s)",
            review_id,
            reviewer,
        )

        # --- Log the correction via ActiveLearner ----------------------
        learner = self._get_learner()
        correction_id = learner.log_correction(
            original_text=ocr_text,
            corrected_text=corrected_text,
            language=language,
            confidence=confidence,
            source=reviewer,
            image_path=image_path,
        )

        logger.info(
            "Correction logged: correction_id=%d  review_id=%d  lang=%s",
            correction_id,
            review_id,
            language,
        )

        # --- Check whether auto-training should be triggered -----------
        self._check_auto_train(language)

        return correction_id

    # ------------------------------------------------------------------
    # 3. Get the review queue
    # ------------------------------------------------------------------

    def get_review_queue(
        self,
        language: str = "ar",
        limit: int = 20,
    ) -> list[dict]:
        """Return items that still need human review.

        Items have low confidence *and* have not yet been corrected
        (``corrected_text IS NULL``).
        """
        db = self._get_db()

        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, original_text, confidence, created_at
                FROM training_data
                WHERE language = ?
                  AND confidence < ?
                  AND corrected_text IS NULL
                ORDER BY confidence ASC, created_at DESC
                LIMIT ?
                """,
                (language, self._min_confidence_for_review, limit),
            )

            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

        # Rename for the expected API surface and attach placeholder metadata
        result = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "original_text": row.get("original_text", ""),
                    "ocr_text": row.get("original_text", ""),
                    "confidence": row["confidence"],
                    "created_at": row["created_at"],
                    "metadata": None,
                }
            )

        logger.debug(
            "Review queue: %d items returned (lang=%s, limit=%d)",
            len(result),
            language,
            limit,
        )
        return result

    # ------------------------------------------------------------------
    # 4. Get statistics
    # ------------------------------------------------------------------

    def get_stats(self, language: str = "ar") -> dict:
        """Return aggregate statistics for a language.

        Delegates to :meth:`ActiveLearner.get_training_stats` and
        enriches with review-queue counts and an accuracy estimate.
        """
        db = self._get_db()
        learner = self._get_learner()

        base_stats = learner.get_training_stats(language)

        # Count items queued for review (corrected_text IS NULL, low conf)
        with db.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COUNT(*) FROM training_data
                WHERE language = ?
                  AND confidence < ?
                  AND corrected_text IS NULL
                """,
                (language, self._min_confidence_for_review),
            )
            queued_for_review = cursor.fetchone()[0]

            # Total submissions for this language
            cursor.execute(
                "SELECT COUNT(*) FROM training_data WHERE language = ?",
                (language,),
            )
            total_submissions = cursor.fetchone()[0]

            # Items that have been corrected (corrected_text IS NOT NULL
            # and differs from original_text)
            cursor.execute(
                """
                SELECT COUNT(*) FROM training_data
                WHERE language = ?
                  AND corrected_text IS NOT NULL
                  AND corrected_text != original_text
                """,
                (language,),
            )
            corrected = cursor.fetchone()[0]

            # Items auto-trained (marked as used in training)
            cursor.execute(
                """
                SELECT COUNT(*) FROM training_data
                WHERE language = ? AND is_used_in_training = TRUE
                """,
                (language,),
            )
            auto_trained = cursor.fetchone()[0]

        # Accuracy estimate: ratio of accepted (high-confidence, no
        # correction needed) to total submissions.  Items where
        # corrected_text == original_text are "accepted"; items where
        # corrected_text IS NULL are still pending and excluded.
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(CASE WHEN corrected_text = original_text THEN 1 END),
                    COUNT(CASE WHEN corrected_text IS NOT NULL THEN 1 END)
                FROM training_data
                WHERE language = ?
                """,
                (language,),
            )
            accepted, resolved = cursor.fetchone()

        accuracy_estimate = (accepted / resolved) if resolved > 0 else None

        stats = {
            "total_submissions": total_submissions,
            "queued_for_review": queued_for_review,
            "corrected": corrected,
            "auto_trained": auto_trained,
            "accuracy_estimate": accuracy_estimate,
            **base_stats,
        }

        logger.debug("Stats for lang=%s: %s", language, stats)
        return stats

    # ------------------------------------------------------------------
    # 5. Get correction suggestions
    # ------------------------------------------------------------------

    def get_correction_suggestions(
        self,
        text: str,
        language: str = "ar",
        limit: int = 5,
    ) -> list[str]:
        """Return known corrections for patterns found in *text*.

        Delegates to :meth:`ActiveLearner.get_suggestions`.
        """
        learner = self._get_learner()
        suggestions = learner.get_suggestions(text=text, language=language, limit=limit)

        logger.debug(
            "Correction suggestions for text (len=%d, lang=%s): %d results",
            len(text),
            language,
            len(suggestions),
        )
        return suggestions

    # ------------------------------------------------------------------
    # 6. Export training dataset
    # ------------------------------------------------------------------

    def export_training_dataset(
        self,
        language: str = "ar",
        format: str = "jsonl",  # noqa: A002 – argument name required by spec
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """Export corrected training data for fine-tuning.

        Args:
            language: Language filter.
            format: ``"jsonl"`` (default) or ``"csv"``.
            output_path: If provided, write to this file path.
                Otherwise return the content as a string.

        Returns:
            ``None`` when *output_path* is given (content written to
            disk), or the serialised string otherwise.
        """
        db = self._get_db()

        # Fetch all resolved training data (has a corrected_text)
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT original_text, corrected_text, confidence
                FROM training_data
                WHERE language = ?
                  AND corrected_text IS NOT NULL
                ORDER BY created_at DESC
                """,
                (language,),
            )
            rows = cursor.fetchall()

        logger.info(
            "Exporting %d training samples (lang=%s, format=%s)",
            len(rows),
            language,
            format,
        )

        if format == "jsonl":
            lines = []
            for original, corrected, conf in rows:
                lines.append(
                    json.dumps(
                        {"original": original, "corrected": corrected, "confidence": conf},
                        ensure_ascii=False,
                    )
                )
            content = "\n".join(lines)
            if content:
                content += "\n"  # trailing newline

        elif format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["original", "corrected", "confidence"])
            for original, corrected, conf in rows:
                writer.writerow([original, corrected, conf])
            content = buf.getvalue()

        else:
            raise ValueError(f"Unsupported export format: {format!r}")

        if output_path is not None:
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            logger.info("Training dataset written to %s", output_path)
            return None

        return content

    # ------------------------------------------------------------------
    # Internal: auto-train threshold check
    # ------------------------------------------------------------------

    def _check_auto_train(self, language: str) -> bool:
        """Return ``True`` if auto-training was triggered."""
        db = self._get_db()

        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM training_data
                WHERE language = ?
                  AND corrected_text IS NOT NULL
                  AND corrected_text != original_text
                """,
                (language,),
            )
            corrected_count = cursor.fetchone()[0]

        if corrected_count >= self._auto_train_threshold:
            logger.info(
                "Auto-train threshold reached (%d >= %d) for lang=%s — "
                "retraining notification issued",
                corrected_count,
                self._auto_train_threshold,
                language,
            )
            return True

        logger.debug(
            "Auto-train: %d/%d corrections for lang=%s",
            corrected_count,
            self._auto_train_threshold,
            language,
        )
        return False