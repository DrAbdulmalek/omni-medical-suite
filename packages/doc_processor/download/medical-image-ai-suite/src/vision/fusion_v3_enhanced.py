# -*- coding: utf-8 -*-
"""Fusion V3 Enhanced — multi-engine OCR result fusion.

This module implements a bounding-box-aware fusion strategy that combines
OCR outputs from several engines (Tesseract, EasyOCR, PaddleOCR, …) into
a single, deduplicated list of tokens.  Overlapping detections are merged
using greedy IOU-based clustering, and per-engine weights are predicted
dynamically from low-level image features so that the best engine for a
given region of the document receives the highest influence.

Typical usage::

    from vision.fusion_v3_enhanced import OCREntry, FusionV3Enhanced

    fusion = FusionV3Enhanced(iou_threshold=0.3)
    results = fusion.fuse(
        engine_results=[
            ("tesseract", tesseract_tokens),
            ("easyocr",   easyocr_tokens),
        ],
        image=some_numpy_array,
    )
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OCREntry:
    """A single OCR detection produced by any recognition engine.

    Attributes:
        text:        The recognised text string.
        confidence:  Engine-reported confidence in the range [0, 1].
        bbox:        Axis-aligned bounding box ``(x1, y1, x2, y2)`` with
                     ``(x1, y1)`` at the top-left corner and ``(x2, y2)``
                     at the bottom-right corner (pixel coordinates).
        engine_name: Human-readable identifier of the originating OCR engine
                     (e.g. ``"tesseract"``, ``"easyocr"``).
        language:    ISO 639-1 language code detected or assumed for this
                     token (e.g. ``"en"``, ``"ar"``).
    """

    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    engine_name: str = ""
    language: str = "en"


@dataclass
class _Cluster:
    """Internal container for a group of spatially-overlapping OCR entries."""

    entries: List[OCREntry] = field(default_factory=list)

    def add(self, entry: OCREntry) -> None:
        """Append an entry to the cluster."""
        self.entries.append(entry)


# ---------------------------------------------------------------------------
# Fusion engine
# ---------------------------------------------------------------------------

class FusionV3Enhanced:
    """Merge results from multiple OCR engines using IOU clustering and
    dynamic, image-feature-driven engine weighting.

    Parameters:
        iou_threshold:       Minimum Intersection-over-Union for two
                             bounding boxes to be considered overlapping.
        use_dynamic_weights: When *True*, per-engine weights are predicted
                             from image features (edge density, contrast,
                             brightness uniformity).  When *False*, every
                             engine receives equal weight.
        min_confidence:      Tokens whose final fused confidence falls below
                             this threshold are discarded.
    """

    def __init__(
        self,
        iou_threshold: float = 0.3,
        use_dynamic_weights: bool = True,
        min_confidence: float = 0.3,
    ) -> None:
        self.iou_threshold: float = iou_threshold
        self.use_dynamic_weights: bool = use_dynamic_weights
        self.min_confidence: float = min_confidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def compute_iou(
        box_a: Tuple[int, int, int, int],
        box_b: Tuple[int, int, int, int],
    ) -> float:
        """Compute the Intersection over Union (IOU) of two axis-aligned
        bounding boxes.

        Args:
            box_a: ``(x1, y1, x2, y2)`` for the first box.
            box_b: ``(x1, y1, x2, y2)`` for the second box.

        Returns:
            A float in ``[0, 1]`` representing the ratio of intersection
            area to union area.
        """
        x_left = max(box_a[0], box_b[0])
        y_top = max(box_a[1], box_b[1])
        x_right = min(box_a[2], box_b[2])
        y_bottom = min(box_a[3], box_b[3])

        if x_right <= x_left or y_bottom <= y_top:
            return 0.0

        intersection_area = float((x_right - x_left) * (y_bottom - y_top))
        area_a = float((box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
        area_b = float((box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))
        union_area = area_a + area_b - intersection_area

        if union_area <= 0.0:
            return 0.0
        return intersection_area / union_area

    def cluster_tokens(
        self, entries: List[OCREntry]
    ) -> List[_Cluster]:
        """Greedy, IOU-based spatial clustering (O(N²) worst-case).

        Each entry is placed into the first cluster whose representative
        bounding box overlaps with it (above *iou_threshold*).  If no such
        cluster exists, a new cluster is created.

        Args:
            entries: Flat list of :class:`OCREntry` objects from any
                     combination of engines.

        Returns:
            A list of :class:`_Cluster` objects, each containing one or
            more overlapping entries.
        """
        clusters: List[_Cluster] = []

        for entry in entries:
            merged = False
            for cluster in clusters:
                representative = cluster.entries[0]
                if self.compute_iou(representative.bbox, entry.bbox) >= self.iou_threshold:
                    cluster.add(entry)
                    merged = True
                    break
            if not merged:
                clusters.append(_Cluster(entries=[entry]))

        return clusters

    def fuse(
        self,
        engine_results: List[Tuple[str, List[OCREntry]]],
        image: Optional[np.ndarray] = None,
    ) -> List[OCREntry]:
        """Fuse OCR results from multiple engines.

        All entries from every engine are pooled together, spatially
        clustered, and then a weighted vote determines the final text
        and confidence for each cluster.

        Args:
            engine_results: A list of ``(engine_name, entries)`` tuples.
            image:          The source image as a NumPy array.  When
                            *use_dynamic_weights* is enabled this is
                            required so that image features can be
                            extracted for weight prediction.

        Returns:
            A deduplicated, fused list of :class:`OCREntry` objects
            sorted by vertical position (top to bottom).
        """
        # 1. Pool every entry and annotate with its engine name.
        pooled: List[OCREntry] = []
        for engine_name, entries in engine_results:
            for entry in entries:
                pooled.append(OCREntry(
                    text=entry.text,
                    confidence=entry.confidence,
                    bbox=entry.bbox,
                    engine_name=engine_name,
                    language=entry.language,
                ))

        if not pooled:
            return []

        # 2. Compute dynamic engine weights (optional).
        weights: Dict[str, float] = {}
        if self.use_dynamic_weights and image is not None:
            weights = self._predict_engine_weights(image, engine_results)
        else:
            for engine_name, _ in engine_results:
                weights[engine_name] = 1.0

        # 3. Cluster overlapping tokens.
        clusters = self.cluster_tokens(pooled)

        # 4. Resolve each cluster to a single OCREntry.
        fused: List[OCREntry] = []
        for cluster in clusters:
            best_entry = self._resolve_cluster(cluster, weights)
            if best_entry.confidence >= self.min_confidence:
                fused.append(best_entry)

        # 5. Sort top-to-bottom.
        fused.sort(key=lambda e: e.bbox[1])
        return fused

    def fuse_with_context(
        self,
        engine_results: List[Tuple[str, List[OCREntry]]],
        image: Optional[np.ndarray] = None,
        document_type: str = "report",
    ) -> List[OCREntry]:
        """Fuse with document-type awareness.

        Certain document types (e.g. prescriptions) contain dense,
        columnar layouts where a higher IOU threshold reduces false
        merges.  This method adjusts internal parameters based on the
        detected or supplied document type.

        Args:
            engine_results: Same as :meth:`fuse`.
            image:          Same as :meth:`fuse`.
            document_type:  One of ``"prescription"``, ``"report"``,
                            ``"lab_result"``, ``"radiology"``.

        Returns:
            Fused list of :class:`OCREntry` objects.
        """
        # Adjust fusion parameters per document type.
        original_iou = self.iou_threshold
        original_min_conf = self.min_confidence

        type_profiles: Dict[str, Tuple[float, float]] = {
            "prescription": (0.20, 0.25),
            "report":       (0.30, 0.30),
            "lab_result":   (0.25, 0.35),
            "radiology":    (0.35, 0.30),
        }
        profile = type_profiles.get(document_type, (0.30, 0.30))
        self.iou_threshold = profile[0]
        self.min_confidence = profile[1]

        try:
            result = self.fuse(engine_results, image)
        finally:
            # Always restore original settings.
            self.iou_threshold = original_iou
            self.min_confidence = original_min_conf

        return result

    # ------------------------------------------------------------------
    # Image-feature extraction
    # ------------------------------------------------------------------

    def _compute_features(self, image: np.ndarray) -> Dict[str, float]:
        """Extract low-level image features used for ML weight prediction.

        Three features are computed:

        * **Edge density** — fraction of Sobel-edge pixels above a
          threshold, capturing text sharpness.
        * **Contrast** — standard deviation of grayscale intensities,
          indicating overall image contrast.
        * **Brightness uniformity** — inverse of the coefficient of
          variation of mean brightness in a 4×4 grid, where a value
          closer to 1.0 means uniform illumination.

        Args:
            image: A BGR or grayscale NumPy image.

        Returns:
            A dictionary mapping feature names to normalised floats.
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # type: ignore[name-defined]
        else:
            gray = image

        # Edge density via Sobel.
        sobel_x = np.abs(np.diff(gray.astype(np.float32), axis=1))
        sobel_y = np.abs(np.diff(gray.astype(np.float32), axis=0))
        edge_mag = np.sqrt(sobel_x[:-1, :] ** 2 + sobel_y[:, :-1] ** 2)
        edge_density = float(np.mean(edge_mag > 50))

        # Contrast.
        contrast = float(np.std(gray))

        # Brightness uniformity (4×4 grid).
        h, w = gray.shape
        cell_h, cell_w = h // 4, w // 4
        grid_means: List[float] = []
        for r in range(4):
            for c in range(4):
                patch = gray[r * cell_h : (r + 1) * cell_h,
                             c * cell_w : (c + 1) * cell_w]
                grid_means.append(float(np.mean(patch)))
        mean_grid = float(np.mean(grid_means))
        std_grid = float(np.std(grid_means))
        brightness_uniformity = 1.0 - (std_grid / (mean_grid + 1e-6))

        return {
            "edge_density": min(edge_density / 0.5, 1.0),
            "contrast": min(contrast / 128.0, 1.0),
            "brightness_uniformity": max(brightness_uniformity, 0.0),
        }

    def _predict_engine_weights(
        self,
        image: np.ndarray,
        engine_results: List[Tuple[str, List[OCREntry]]],
    ) -> Dict[str, float]:
        """Predict per-engine weights based on image features.

        The prediction is a simple heuristic mapping:

        * High edge density favours Tesseract (works well on sharp
          printed text).
        * Low brightness uniformity favours EasyOCR (robust to uneven
          lighting).
        * High contrast favours PaddleOCR (performs well on high-contrast
          forms).

        Engines not explicitly listed receive a default weight of 0.5.

        Args:
            image:          The source image.
            engine_results: List of ``(name, entries)`` tuples.

        Returns:
            A dictionary mapping engine name to a float weight in
            ``[0, 1]``.
        """
        features = self._compute_features(image)
        ed = features["edge_density"]
        bu = features["brightness_uniformity"]
        ct = features["contrast"]

        base: Dict[str, float] = {}
        for name, _ in engine_results:
            base[name] = 0.5

        # Heuristic adjustments.
        if "tesseract" in base:
            base["tesseract"] = 0.5 + 0.3 * ed
        if "easyocr" in base:
            base["easyocr"] = 0.5 + 0.3 * (1.0 - bu)
        if "paddleocr" in base:
            base["paddleocr"] = 0.5 + 0.3 * ct

        # Normalise so that weights sum to 1.0.
        total = sum(base.values())
        if total > 0:
            for k in base:
                base[k] /= total
        return base

    # ------------------------------------------------------------------
    # Cluster resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_cluster(
        cluster: _Cluster,
        weights: Dict[str, float],
    ) -> OCREntry:
        """Pick the best representative entry from a cluster.

        Each entry receives a weighted score equal to
        ``confidence × engine_weight``.  The entry with the highest
        score wins.  The returned bounding box is the union of all
        boxes in the cluster.

        Args:
            cluster: A :class:`_Cluster` with at least one entry.
            weights: Per-engine weight dictionary.

        Returns:
            The winning :class:`OCREntry` with an updated confidence
            and merged bounding box.
        """
        best_entry: Optional[OCREntry] = None
        best_score: float = -1.0

        for entry in cluster.entries:
            w = weights.get(entry.engine_name, 0.5)
            score = entry.confidence * w
            if score > best_score:
                best_score = score
                best_entry = entry

        assert best_entry is not None  # cluster is never empty

        # Merge bounding boxes (union).
        x1 = min(e.bbox[0] for e in cluster.entries)
        y1 = min(e.bbox[1] for e in cluster.entries)
        x2 = max(e.bbox[2] for e in cluster.entries)
        y2 = max(e.bbox[3] for e in cluster.entries)

        return OCREntry(
            text=best_entry.text,
            confidence=best_entry.confidence,
            bbox=(x1, y1, x2, y2),
            engine_name=best_entry.engine_name,
            language=best_entry.language,
        )
