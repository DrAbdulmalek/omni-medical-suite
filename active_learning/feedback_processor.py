"""
AI Fuel Engine - Feedback Processor

Analyses human corrections from the :class:`HumanReviewQueue` and produces
actionable insights for improving classifier accuracy.  Generates training
reports, suggests taxonomy keyword updates, and computes accuracy improvement
metrics.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from active_learning.review_queue import HumanReviewQueue

logger = logging.getLogger(__name__)


class FeedbackProcessor:
    """Processes human feedback to improve classifier accuracy.

    Reads approved corrections from the review queue and produces:
    - Accuracy improvement metrics
    - Training reports for model retraining
    - Taxonomy update suggestions (new keywords, category merges)

    Args:
        review_queue: The :class:`HumanReviewQueue` to read corrections from.
    """

    def __init__(self, review_queue: HumanReviewQueue) -> None:
        """Initialise the feedback processor.

        Args:
            review_queue: Source of human corrections.
        """
        self.queue = review_queue
        self.corrections: List[Dict[str, Any]] = []
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_corrections(self) -> List[Dict[str, Any]]:
        """Load all approved corrections from the review queue.

        Returns:
            A list of correction dictionaries, each containing:
            - ``text`` – the original chunk text.
            - ``predicted_category`` – the model's prediction.
            - ``correct_category`` – the human-annotated correction.
            - ``confidence`` – the model's original confidence score.
            - ``source_file`` – originating file path.
        """
        import sqlite3

        try:
            rows = self.queue.conn.execute(
                """
                SELECT text,
                       json_extract(predictions, '$[0].category') AS predicted,
                       correct_category,
                       confidence,
                       source_file
                FROM review_queue
                WHERE status = 'approved'
                  AND correct_category IS NOT NULL
                ORDER BY created_at DESC
                """
            ).fetchall()

            self.corrections = [
                {
                    "text": row["text"],
                    "predicted_category": row["predicted"],
                    "correct_category": row["correct_category"],
                    "confidence": row["confidence"],
                    "source_file": row["source_file"],
                }
                for row in rows
            ]

            self._loaded = True
            logger.info("Loaded %d corrections.", len(self.corrections))
            return self.corrections

        except sqlite3.Error as exc:
            logger.error("Failed to load corrections: %s", exc)
            return []

    def process_feedback(self) -> Dict[str, Any]:
        """Process all available feedback and generate training updates.

        Analyses correction patterns to produce:
        - Per-category error counts
        - Overall accuracy estimate (before / after corrections)
        - Recommended taxonomy updates

        Returns:
            A dictionary with the following keys:
            - ``total_corrections`` – number of approved corrections.
            - ``correction_rate`` – corrections / total classified (approx).
            - ``error_matrix`` – confusion between predicted → actual categories.
            - ``accuracy_before`` – estimated classifier accuracy before feedback.
            - ``accuracy_after`` – estimated accuracy after applying corrections.
            - ``improvement`` – percentage-point improvement.
        """
        if not self._loaded:
            self.load_corrections()

        if not self.corrections:
            logger.info("No corrections to process.")
            return self._empty_result()

        # ── Build error matrix ────────────────────────────────────────
        error_matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for c in self.corrections:
            predicted = c["predicted_category"]
            correct = c["correct_category"]
            error_matrix[predicted][correct] += 1

        # Convert nested defaultdicts to regular dicts for JSON serialisation
        error_matrix_serialisable = {
            k: dict(v) for k, v in error_matrix.items()
        }

        # ── Compute accuracy metrics ─────────────────────────────────
        total_corrections = len(self.corrections)
        correct_count = sum(
            1 for c in self.corrections
            if c["predicted_category"] == c["correct_category"]
        )

        # "Accuracy before" is based on how many predictions were wrong
        accuracy_before = max(1.0 - (total_corrections - correct_count) / max(total_corrections, 1), 0.0)

        # "Accuracy after" assumes all corrections are applied
        accuracy_after = 1.0

        improvement = round(accuracy_after - accuracy_before, 4)

        result = {
            "total_corrections": total_corrections,
            "correction_rate": round(total_corrections / max(total_corrections + correct_count, 1), 4),
            "error_matrix": error_matrix_serialisable,
            "accuracy_before": round(accuracy_before, 4),
            "accuracy_after": round(accuracy_after, 4),
            "improvement": improvement,
        }

        logger.info(
            "Feedback processed: %d corrections, improvement=%.2fpp.",
            total_corrections,
            improvement * 100,
        )
        return result

    def generate_training_report(self) -> Dict[str, Any]:
        """Generate report of classifier performance improvements.

        Returns:
            A dictionary with:
            - ``summary`` – high-level numbers.
            - ``top_misclassifications`` – most common predicted→actual pairs.
            - ``category_accuracy`` – per-category estimated accuracy.
            - ``recommended_actions`` – prioritised list of recommended fixes.
        """
        if not self._loaded:
            self.load_corrections()

        if not self.corrections:
            return self._empty_report()

        feedback_stats = self.process_feedback()
        stats = self.queue.get_feedback_stats()

        # ── Top misclassifications ───────────────────────────────────
        misclassifications: Counter = Counter()
        for c in self.corrections:
            if c["predicted_category"] != c["correct_category"]:
                pair = f"{c['predicted_category']} → {c['correct_category']}"
                misclassifications[pair] += 1

        top_misclassifications = [
            {"pair": pair, "count": count}
            for pair, count in misclassifications.most_common(10)
        ]

        # ── Per-category accuracy ────────────────────────────────────
        cat_predictions: Counter = Counter()
        cat_corrections: Counter = Counter()
        for c in self.corrections:
            cat_predictions[c["predicted_category"]] += 1
            if c["predicted_category"] != c["correct_category"]:
                cat_corrections[c["predicted_category"]] += 1

        category_accuracy: Dict[str, float] = {}
        for cat, total in cat_predictions.items():
            errors = cat_corrections.get(cat, 0)
            category_accuracy[cat] = round(1.0 - errors / total, 4) if total > 0 else 0.0

        # ── Recommended actions ────────────────────────────────────
        recommended_actions: List[Dict[str, Any]] = []

        # 1. Suggest new keywords for frequently confused categories
        for pair_info in top_misclassifications[:5]:
            recommended_actions.append(
                {
                    "action": "add_keywords",
                    "priority": "high" if pair_info["count"] >= 3 else "medium",
                    "description": (
                        f"Review '{pair_info['pair']}' confusion ({pair_info['count']} cases). "
                        "Consider adding discriminating keywords."
                    ),
                    "pair": pair_info["pair"],
                    "count": pair_info["count"],
                }
            )

        # 2. Suggest category merges if many corrections point the same way
        if len(cat_corrections) > 0:
            worst_category = max(
                cat_corrections,
                key=lambda k: cat_corrections[k],
            )
            recommended_actions.append(
                {
                    "action": "review_category",
                    "priority": "high",
                    "description": (
                        f"Category '{worst_category}' has {cat_corrections[worst_category]} "
                        "misclassifications. Review taxonomy definition."
                    ),
                    "category": worst_category,
                    "error_count": cat_corrections[worst_category],
                }
            )

        # 3. Recommend threshold adjustment if many low-confidence corrections
        low_conf_corrections = sum(
            1 for c in self.corrections if c["confidence"] < 0.5
        )
        if low_conf_corrections > total_corrections * 0.5 if self.corrections else False:
            recommended_actions.append(
                {
                    "action": "adjust_threshold",
                    "priority": "medium",
                    "description": (
                        f"{low_conf_corrections} of {len(self.corrections)} corrections were on "
                        "samples with <0.5 confidence. Consider increasing uncertainty threshold."
                    ),
                }
            )

        report = {
            "summary": {
                "total_corrections": len(self.corrections),
                "reviewed_samples": stats.get("approved_count", 0),
                "accuracy_improvement_pp": feedback_stats.get("improvement", 0) * 100,
                "generated_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            },
            "top_misclassifications": top_misclassifications,
            "category_accuracy": category_accuracy,
            "recommended_actions": recommended_actions,
        }

        logger.info("Training report generated.")
        return report

    def suggest_taxonomy_updates(self) -> Dict[str, Any]:
        """Suggest taxonomy updates based on feedback patterns.

        Analyses correction text to extract keywords that could improve
        classification accuracy.  Useful for updating the medical
        taxonomy JSON file.

        Returns:
            A dictionary with:
            - ``new_keywords`` – suggested new keywords grouped by category.
            - ``category_renames`` – categories that should potentially be
              renamed or split.
            - ``keyword_conflicts`` – keywords appearing in multiple
              categories that may cause confusion.
        """
        if not self._loaded:
            self.load_corrections()

        if not self.corrections:
            return {"new_keywords": {}, "category_renames": [], "keyword_conflicts": []}

        # ── Extract words from correction texts per correct category ──
        import re

        # Simple word extraction: alphanumeric tokens ≥ 3 chars
        word_pattern = re.compile(r"\b[\w]{3,}\b", re.UNICODE)
        stop_words = {
            "the", "and", "for", "with", "that", "this", "from", "was",
            "are", "been", "have", "has", "had", "not", "but", "they",
            "which", "will", "their", "were", "can", "all", "may",
            "و", "في", "من", "إلى", "على", "مع", "عن", "أن", "هذا",
            "هذه", "التي", "الذي", "كان", "كانت", "هو", "هي",
        }

        category_words: Dict[str, Counter] = defaultdict(Counter)

        for c in self.corrections:
            correct_cat = c["correct_category"]
            words = word_pattern.findall(c["text"].lower())
            filtered = [w for w in words if w not in stop_words]
            category_words[correct_cat].update(filtered)

        # ── Suggest new keywords (top 20 per category) ───────────────
        new_keywords: Dict[str, List[str]] = {}
        for cat, counter in category_words.items():
            top_words = [word for word, _count in counter.most_common(20)]
            new_keywords[cat] = top_words

        # ── Detect keyword conflicts ────────────────────────────────
        all_words: Dict[str, List[str]] = defaultdict(list)
        for cat, counter in category_words.items():
            for word, count in counter.most_common(20):
                if count >= 2:
                    all_words[word].append(cat)

        keyword_conflicts: List[Dict[str, Any]] = []
        for word, categories in sorted(all_words.items()):
            if len(categories) > 1:
                keyword_conflicts.append(
                    {
                        "keyword": word,
                        "categories": categories,
                        "suggestion": (
                            f"Keyword '{word}' appears in multiple categories "
                            f"({', '.join(categories)}). Consider adding "
                            "context-specific rules."
                        ),
                    }
                )

        # ── Suggest category renames ─────────────────────────────────
        category_renames: List[Dict[str, str]] = []
        error_matrix = self.process_feedback().get("error_matrix", {})
        for predicted, actual_map in error_matrix.items():
            # If a category is consistently redirected to a single other
            if len(actual_map) == 1:
                actual_cat = next(iter(actual_map))
                count = actual_map[actual_cat]
                if count >= 3:
                    category_renames.append(
                        {
                            "source": predicted,
                            "target": actual_cat,
                            "count": count,
                        }
                    )

        result = {
            "new_keywords": new_keywords,
            "category_renames": category_renames,
            "keyword_conflicts": keyword_conflicts,
        }

        logger.info(
            "Taxonomy update suggestions: %d keywords, %d renames, %d conflicts.",
            sum(len(v) for v in new_keywords.values()),
            len(category_renames),
            len(keyword_conflicts),
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        """Return an empty feedback processing result."""
        return {
            "total_corrections": 0,
            "correction_rate": 0.0,
            "error_matrix": {},
            "accuracy_before": 0.0,
            "accuracy_after": 0.0,
            "improvement": 0.0,
        }

    @staticmethod
    def _empty_report() -> Dict[str, Any]:
        """Return an empty training report."""
        import datetime

        return {
            "summary": {
                "total_corrections": 0,
                "reviewed_samples": 0,
                "accuracy_improvement_pp": 0.0,
                "generated_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            },
            "top_misclassifications": [],
            "category_accuracy": {},
            "recommended_actions": [],
        }

    def __repr__(self) -> str:
        status = "loaded" if self._loaded else "unloaded"
        return f"FeedbackProcessor(corrections={len(self.corrections)}, {status})"
