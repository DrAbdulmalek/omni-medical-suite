"""
Ensemble OCR
=============

Combines results from multiple OCR engines using weighted confidence
fusion, Levenshtein-distance-based text alignment, and a majority-vote
mechanism for word-level consensus.

The ensemble can operate in three modes:

1. **Weighted confidence** — pick the result with the highest
   engine-weighted confidence per region.
2. **Majority vote** — align word-level outputs and select the
   most-voted word at each position.
3. **Text alignment** — use Levenshtein distance to align engine
   outputs and merge at the character / word level.

Typical usage
-------------
>>> engine = EnsembleOCR(
...     engines=[tesseract, easyocr, paddleocr],
...     weights={"tesseract": 0.3, "easyocr": 0.35, "paddleocr": 0.35},
... )
>>> result = engine.ocr("prescription.png")
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from src.engines.base_engine import (
    BBox,
    OCREngine,
    OCRResult,
    ImageInput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Levenshtein distance
# ---------------------------------------------------------------------------

def levenshtein_distance(a: str, b: str) -> int:
    """Compute the Levenshtein (edit) distance between two strings.

    Uses the classic dynamic-programming algorithm with O(min(|a|, |b|))
    space optimisation.

    Parameters
    ----------
    a, b : str
        Input strings.

    Returns
    -------
    int
        The minimum number of single-character edits (insertions,
        deletions, substitutions) required to transform *a* into *b*.
    """
    if len(a) < len(b):
        a, b = b, a

    if not b:
        return len(a)

    previous_row = list(range(len(b) + 1))

    for i, ca in enumerate(a, 1):
        current_row = [i]
        for j, cb in enumerate(b, 1):
            insertions = previous_row[j] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j - 1] + (0 if ca == cb else 1)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def normalized_levenshtein(a: str, b: str) -> float:
    """Normalised Levenshtein distance in ``[0.0, 1.0]``.

    The distance is divided by the length of the longer string so that
    the result is scale-independent.

    Parameters
    ----------
    a, b : str

    Returns
    -------
    float
        Normalised distance where ``0.0`` = identical and ``1.0`` =
        completely different.
    """
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 0.0
    return levenshtein_distance(a, b) / max_len


# ---------------------------------------------------------------------------
# Text alignment helper
# ---------------------------------------------------------------------------

def align_texts(
    texts: List[str],
) -> List[List[Optional[str]]]:
    """Align multiple text outputs using progressive Levenshtein
    alignment.

    Each text is split into words, and the sequences are aligned so
    that matching words appear in the same column.  Gaps are filled
    with *None*.

    Parameters
    ----------
    texts : list[str]
        Text outputs from different engines.

    Returns
    -------
    list[list[str | None]]
        A 2-D grid ``[position][engine]`` of aligned words.
    """
    if not texts:
        return []

    word_lists = [t.split() for t in texts]
    n_engines = len(word_lists)

    # Start with the first engine's words as the base alignment.
    # Each row is a list of (engine_idx, word) or None for gaps.
    aligned: List[List[Optional[str]]] = [
        [word] + [None] * (n_engines - 1) for word in word_lists[0]
    ]

    for eng_idx in range(1, n_engines):
        target_words = word_lists[eng_idx]
        aligned = _align_two_columns(aligned, eng_idx, target_words)

    return aligned


def _align_two_columns(
    current: List[List[Optional[str]]],
    new_eng_idx: int,
    new_words: List[str],
) -> List[List[Optional[str]]]:
    """Align a new engine's word sequence against the current alignment.

    Uses a greedy approach: for each word in the new sequence, find
    the best-matching existing row (by normalised Levenshtein) or
    insert a new row.
    """
    result = [row[:] for row in current]  # deep copy
    used_new_indices: set[int] = set()

    for row_idx, row in enumerate(result):
        best_match_idx = -1
        best_score = 1.0  # lower is better

        for nw_idx, nw in enumerate(new_words):
            if nw_idx in used_new_indices:
                continue
            # Compare with the first non-None word in the row
            row_word = None
            for cell in row:
                if cell is not None:
                    row_word = cell
                    break
            if row_word is None:
                continue

            dist = normalized_levenshtein(row_word, nw)
            if dist < best_score:
                best_score = dist
                best_match_idx = nw_idx

        # Accept match if distance is small enough (< 0.4)
        if best_match_idx >= 0 and best_score < 0.4:
            # Extend row if needed
            while len(result[row_idx]) <= new_eng_idx:
                result[row_idx].append(None)
            result[row_idx][new_eng_idx] = new_words[best_match_idx]
            used_new_indices.add(best_match_idx)

    # Add unmatched new words as new rows
    for nw_idx, nw in enumerate(new_words):
        if nw_idx not in used_new_indices:
            new_row: List[Optional[str]] = [None] * (new_eng_idx + 1)
            new_row[new_eng_idx] = nw
            result.append(new_row)

    return result


# ---------------------------------------------------------------------------
# EnsembleOCR
# ---------------------------------------------------------------------------

class EnsembleOCR(OCREngine):
    """Combines multiple OCR engines into a single, more robust engine.

    The ensemble runs all constituent engines and fuses their outputs
    using configurable strategies.

    Parameters
    ----------
    engines : list[OCREngine]
        The OCR engines to combine.
    weights : dict[str, float] | None
        Per-engine confidence weights.  Keys are ``engine.engine_name``.
        If *None*, all engines receive equal weight.
    strategy : str
        Fusion strategy: ``"weighted_confidence"``, ``"majority_vote"``,
        or ``"text_alignment"``.
    iou_threshold : float
        IoU threshold for clustering overlapping bounding boxes from
        different engines.
    min_confidence : float
        Minimum fused confidence to keep a result.
    align_distance_threshold : float
        Maximum normalised Levenshtein distance for word alignment
        (used by ``"majority_vote"`` and ``"text_alignment"`` strategies).
    """

    def __init__(
        self,
        engines: List[OCREngine],
        weights: Optional[Dict[str, float]] = None,
        strategy: str = "weighted_confidence",
        iou_threshold: float = 0.3,
        min_confidence: float = 0.1,
        align_distance_threshold: float = 0.4,
    ) -> None:
        super().__init__(engine_name="ensemble")
        self._engines = engines
        self._strategy = strategy
        self._iou_threshold = iou_threshold
        self._min_confidence = min_confidence
        self._align_distance_threshold = align_distance_threshold

        # Normalise weights
        if weights is None:
            n = max(len(engines), 1)
            self._weights: Dict[str, float] = {
                e.engine_name: 1.0 / n for e in engines
            }
        else:
            total = sum(weights.values())
            self._weights = {
                k: v / total if total > 0 else 0.0
                for k, v in weights.items()
            }

        self._logger.info(
            "EnsembleOCR initialised with %d engines, strategy='%s', "
            "weights=%s.",
            len(engines), strategy, self._weights,
        )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def _check_availability(self) -> None:
        """Verify at least one engine is available."""
        available = [
            e for e in self._engines if e.is_available()
        ]
        if not available:
            raise RuntimeError(
                "No OCR engines available for the ensemble."
            )
        self._logger.info(
            "%d/%d engines available for ensemble.",
            len(available), len(self._engines),
        )

    # ------------------------------------------------------------------
    # Core OCR
    # ------------------------------------------------------------------

    def ocr(self, image: ImageInput) -> OCRResult:
        """Run all engines and fuse results.

        Parameters
        ----------
        image : ImageInput

        Returns
        -------
        OCRResult
            The fused result.
        """
        t0 = time.perf_counter()

        # Run each engine (skip unavailable ones)
        engine_results: List[OCRResult] = []
        for engine in self._engines:
            if not engine.is_available():
                self._logger.debug(
                    "Skipping unavailable engine '%s'.", engine.engine_name,
                )
                continue
            result = engine.safe_ocr(image)
            engine_results.append(result)

        if not engine_results:
            elapsed = time.perf_counter() - t0
            return OCRResult(
                text="",
                confidence=0.0,
                bbox=None,
                engine_name=self.engine_name,
                processing_time=elapsed,
                metadata={"error": "No engines available"},
            )

        # Fuse based on strategy
        if self._strategy == "weighted_confidence":
            fused = self._fuse_weighted_confidence(engine_results)
        elif self._strategy == "majority_vote":
            fused = self._fuse_majority_vote(engine_results)
        elif self._strategy == "text_alignment":
            fused = self._fuse_text_alignment(engine_results)
        else:
            self._logger.warning(
                "Unknown strategy '%s', falling back to weighted_confidence.",
                self._strategy,
            )
            fused = self._fuse_weighted_confidence(engine_results)

        fused.processing_time = time.perf_counter() - t0
        fused.engine_name = self.engine_name
        fused.metadata["strategy"] = self._strategy
        fused.metadata["engines_used"] = [r.engine_name for r in engine_results]
        fused.metadata["weights"] = dict(self._weights)
        return fused

    def ocr_batch(self, images: Sequence[ImageInput]) -> List[OCRResult]:
        """Run ensemble OCR on a batch of images.

        Parameters
        ----------
        images : sequence of ImageInput

        Returns
        -------
        list[OCRResult]
        """
        results: List[OCRResult] = []
        for idx, img in enumerate(images):
            self._logger.debug(
                "Ensemble batch: image %d/%d.", idx + 1, len(images),
            )
            results.append(self.ocr(img))
        return results

    # ------------------------------------------------------------------
    # select_best_engine
    # ------------------------------------------------------------------

    def select_best_engine(
        self,
        image: ImageInput,
    ) -> OCRResult:
        """Run all engines and return the single best result (highest
        weighted confidence), without fusion.

        Useful for benchmarking or when you want the best single-engine
        output.

        Parameters
        ----------
        image : ImageInput

        Returns
        -------
        OCRResult
            The most confident engine's result.
        """
        t0 = time.perf_counter()

        best_result: Optional[OCRResult] = None
        best_score = -1.0

        for engine in self._engines:
            if not engine.is_available():
                continue
            result = engine.safe_ocr(image)
            weight = self._weights.get(result.engine_name, 0.0)
            score = result.confidence * weight

            if score > best_score:
                best_score = score
                best_result = result

        if best_result is None:
            elapsed = time.perf_counter() - t0
            return OCRResult(
                text="",
                confidence=0.0,
                bbox=None,
                engine_name=self.engine_name,
                processing_time=elapsed,
            )

        best_result.processing_time = time.perf_counter() - t0
        best_result.metadata["best_engine"] = best_result.engine_name
        best_result.metadata["best_score"] = best_score
        return best_result

    # ==================================================================
    # Fusion strategies
    # ==================================================================

    def _fuse_weighted_confidence(
        self,
        results: List[OCRResult],
    ) -> OCRResult:
        """Strategy 1: Weighted confidence fusion.

        Clusters overlapping bounding boxes and selects the text with
        the highest engine-weighted confidence per cluster.  Results
        without bounding boxes are appended as supplemental text.
        """
        # Separate bounded and unbounded results
        bounded: List[OCRResult] = []
        unbounded: List[OCRResult] = []

        for r in results:
            if r.bbox is not None:
                bounded.append(r)
            else:
                unbounded.append(r)

        # Cluster overlapping bboxes
        clusters = self._cluster_bboxes(bounded)

        # For each cluster, select the best text
        merged_lines: List[str] = []
        merged_confs: List[float] = []
        merged_bboxes: List[BBox] = []
        engine_sources: Dict[str, float] = {}

        for cluster in clusters:
            best_result: Optional[OCRResult] = None
            best_score = -1.0

            for r in cluster:
                weight = self._weights.get(r.engine_name, 0.0)
                score = r.confidence * weight
                engine_sources[r.engine_name] = max(
                    engine_sources.get(r.engine_name, 0.0), r.confidence,
                )
                if score > best_score:
                    best_score = score
                    best_result = r

            if best_result is not None and best_result.confidence >= self._min_confidence:
                # Merge bbox by taking the union
                merged_bbox = self._merge_cluster_bboxes(cluster)
                merged_lines.append(best_result.text)
                merged_confs.append(best_score)
                merged_bboxes.append(merged_bbox)

        # Sort by vertical position
        if merged_bboxes:
            order = sorted(
                range(len(merged_bboxes)),
                key=lambda i: merged_bboxes[i].y_min,
            )
            merged_lines = [merged_lines[i] for i in order]
            merged_confs = [merged_confs[i] for i in order]
            merged_bboxes = [merged_bboxes[i] for i in order]

        # Handle unbounded results (e.g. TrOCR)
        supplemental_texts: List[str] = []
        for r in unbounded:
            if r.text.strip():
                supplemental_texts.append(r.text.strip())
                weight = self._weights.get(r.engine_name, 0.0)
                engine_sources[r.engine_name] = max(
                    engine_sources.get(r.engine_name, 0.0), r.confidence,
                )

        # Combine: bounded lines first, then supplemental
        all_text_parts = merged_lines + supplemental_texts
        full_text = "\n".join(all_text_parts)

        avg_conf = sum(merged_confs) / len(merged_confs) if merged_confs else 0.0
        overall_bbox = (
            self._merge_cluster_bboxes(bounded) if bounded else None
        )

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            bbox=overall_bbox,
            engine_name=self.engine_name,
            word_level=None,
            metadata={
                "strategy": "weighted_confidence",
                "engine_sources": engine_sources,
                "line_count": len(merged_lines),
                "cluster_count": len(clusters),
                "supplemental_count": len(supplemental_texts),
            },
        )

    def _fuse_majority_vote(
        self,
        results: List[OCRResult],
    ) -> OCRResult:
        """Strategy 2: Majority vote at the word level.

        All engine outputs are aligned, and for each position the word
        receiving the most votes (weighted by engine confidence) is
        selected.
        """
        texts = [r.text for r in results if r.text.strip()]

        if not texts:
            return OCRResult(
                text="", confidence=0.0, bbox=None,
                engine_name=self.engine_name,
            )

        if len(texts) == 1:
            r = results[0]
            return OCRResult(
                text=r.text, confidence=r.confidence, bbox=r.bbox,
                engine_name=self.engine_name,
                processing_time=r.processing_time,
            )

        # Align all texts
        aligned = align_texts(texts)

        # Majority vote per row
        final_words: List[str] = []
        row_confs: List[float] = []

        for row in aligned:
            # Collect (word, weight) pairs, ignoring Nones
            votes: Dict[str, float] = {}
            for col_idx, word in enumerate(row):
                if word is None:
                    continue
                engine_name = results[col_idx].engine_name if col_idx < len(results) else ""
                weight = self._weights.get(engine_name, 1.0 / len(results))
                votes[word] = votes.get(word, 0.0) + weight

            if not votes:
                continue

            # Select the word with the highest total weight
            best_word = max(votes, key=votes.get)  # type: ignore[arg-type]
            best_weight = votes[best_word]
            final_words.append(best_word)
            # Confidence = fraction of engines agreeing (weighted)
            total_weight = sum(self._weights.values())
            row_confs.append(best_weight / total_weight if total_weight > 0 else 0.0)

        full_text = " ".join(final_words)
        avg_conf = sum(row_confs) / len(row_confs) if row_confs else 0.0

        # Merge all bboxes into one
        bboxes = [r.bbox for r in results if r.bbox is not None]
        overall_bbox = self._merge_cluster_bboxes(results) if bboxes else None

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            bbox=overall_bbox,
            engine_name=self.engine_name,
            metadata={
                "strategy": "majority_vote",
                "word_count": len(final_words),
                "engines_voted": len(texts),
            },
        )

    def _fuse_text_alignment(
        self,
        results: List[OCRResult],
    ) -> OCRResult:
        """Strategy 3: Levenshtein-based text alignment and merge.

        Aligns engine outputs using edit distance, then for each
        position selects the character/word with the highest weighted
        confidence.  Produces a merged text that draws the best parts
        from each engine.
        """
        texts = [r.text for r in results if r.text.strip()]

        if not texts:
            return OCRResult(
                text="", confidence=0.0, bbox=None,
                engine_name=self.engine_name,
            )

        if len(texts) == 1:
            r = results[0]
            return OCRResult(
                text=r.text, confidence=r.confidence, bbox=r.bbox,
                engine_name=self.engine_name,
                processing_time=r.processing_time,
            )

        # Align all texts at word level
        aligned = align_texts(texts)

        # For each aligned position, compute a consensus word
        consensus_words: List[str] = []
        position_confs: List[float] = []

        for row in aligned:
            non_none = [(i, w) for i, w in enumerate(row) if w is not None]
            if not non_none:
                continue

            if len(non_none) == 1:
                # Only one engine has a word here — use it
                idx, word = non_none[0]
                weight = self._weights.get(
                    results[idx].engine_name if idx < len(results) else "", 0.0,
                )
                consensus_words.append(word)
                position_confs.append(results[idx].confidence * weight)
                continue

            # Multiple engines: pick the word that is most "central"
            # by computing average Levenshtein to all others.
            candidates: List[str] = [w for _, w in non_none]
            best_word = candidates[0]
            best_avg_dist = float("inf")

            for cand in candidates:
                dists = [
                    normalized_levenshtein(cand, other)
                    for other in candidates
                ]
                avg_dist = sum(dists) / len(dists)
                if avg_dist < best_avg_dist:
                    best_avg_dist = avg_dist
                    best_word = cand

            # Weight confidence by how many engines agree
            # (lower avg distance = more agreement)
            agreement = 1.0 - best_avg_dist
            # Also factor in the weight of the engine that proposed it
            best_idx = non_none[0][0]  # approximate
            engine_name = (
                results[best_idx].engine_name
                if best_idx < len(results) else ""
            )
            engine_weight = self._weights.get(engine_name, 0.0)
            conf = agreement * engine_weight

            consensus_words.append(best_word)
            position_confs.append(conf)

        full_text = " ".join(consensus_words)
        avg_conf = (
            sum(position_confs) / len(position_confs)
            if position_confs else 0.0
        )

        bboxes = [r.bbox for r in results if r.bbox is not None]
        overall_bbox = self._merge_cluster_bboxes(results) if bboxes else None

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            bbox=overall_bbox,
            engine_name=self.engine_name,
            metadata={
                "strategy": "text_alignment",
                "word_count": len(consensus_words),
                "engines_aligned": len(texts),
                "alignment_threshold": self._align_distance_threshold,
            },
        )

    # ==================================================================
    # Bounding box clustering
    # ==================================================================

    def _cluster_bboxes(
        self,
        results: List[OCRResult],
    ) -> List[List[OCRResult]]:
        """Group results whose bounding boxes overlap (IoU ≥ threshold).

        Uses a greedy clustering approach: for each unvisited result,
        find all other results whose bboxes overlap, and group them
        together.

        Parameters
        ----------
        results : list[OCRResult]
            Results with non-None bboxes.

        Returns
        -------
        list[list[OCRResult]]
            Clusters of overlapping results.
        """
        n = len(results)
        used: set[int] = set()
        clusters: List[List[OCRResult]] = []

        for i in range(n):
            if i in used:
                continue
            cluster = [results[i]]
            used.add(i)

            for j in range(i + 1, n):
                if j in used:
                    continue
                # Check if any member of the cluster overlaps with j
                for member in cluster:
                    if (
                        member.bbox is not None
                        and results[j].bbox is not None
                        and member.bbox.iou(results[j].bbox) >= self._iou_threshold
                    ):
                        cluster.append(results[j])
                        used.add(j)
                        break

            clusters.append(cluster)

        return clusters

    @staticmethod
    def _merge_cluster_bboxes(
        results: List[OCRResult],
    ) -> Optional[BBox]:
        """Compute the union bounding box of all results.

        Parameters
        ----------
        results : list[OCRResult]

        Returns
        -------
        BBox | None
            Union of all bounding boxes, or *None* if none exist.
        """
        bboxes = [r.bbox for r in results if r.bbox is not None]
        if not bboxes:
            return None
        return BBox(
            x_min=min(b.x_min for b in bboxes),
            y_min=min(b.y_min for b in bboxes),
            x_max=max(b.x_max for b in bboxes),
            y_max=max(b.y_max for b in bboxes),
        )

    # ==================================================================
    # Configuration helpers
    # ==================================================================

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Update engine weights at runtime.

        Parameters
        ----------
        weights : dict[str, float]
            New weights keyed by engine name.  Weights are normalised
            to sum to 1.0 internally.
        """
        total = sum(weights.values())
        self._weights = {
            k: v / total if total > 0 else 0.0
            for k, v in weights.items()
        }
        self._logger.info("Ensemble weights updated: %s", self._weights)

    def set_strategy(self, strategy: str) -> None:
        """Change the fusion strategy at runtime.

        Parameters
        ----------
        strategy : str
            One of ``"weighted_confidence"``, ``"majority_vote"``,
            ``"text_alignment"``.
        """
        valid = {"weighted_confidence", "majority_vote", "text_alignment"}
        if strategy not in valid:
            raise ValueError(
                f"Invalid strategy '{strategy}'. Choose from {valid}."
            )
        self._strategy = strategy
        self._logger.info("Ensemble strategy updated to '%s'.", strategy)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close all constituent engines."""
        for engine in self._engines:
            try:
                engine.close()
            except Exception as exc:
                self._logger.warning(
                    "Error closing engine '%s': %s",
                    engine.engine_name, exc,
                )
        super().close()