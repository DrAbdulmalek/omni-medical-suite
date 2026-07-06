# -*- coding: utf-8 -*-
"""Advanced document deskewing for the OmniMedical Suite.

This module provides three complementary strategies for estimating the
skew angle of a scanned document image:

* **Hough** — detects dominant line orientations using the Probabilistic
  Hough Transform.
* **Projection** — finds the angle that maximises the "peakiness" of
  the horizontal projection profile.
* **Hybrid** — runs both methods and selects the result with the higher
  confidence score.

The public entry point is :meth:`AdvancedDeskew.auto_deskew`.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

import cv2
import numpy as np


class _DeskewMethod(Enum):
    """Supported deskewing strategies."""

    HOUGH = "hough"
    PROJECTION = "projection"
    HYBRID = "hybrid"


class AdvancedDeskew:
    """Estimate and correct the skew angle of document images.

    The class is stateless — all work is performed inside the public
    methods.  This makes it safe to reuse a single instance across
    multiple images.

    Example::

        deskewer = AdvancedDeskew()
        corrected, angle = deskewer.auto_deskew(image, method="hybrid")
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def auto_deskew(
        self,
        img: np.ndarray,
        method: str = "hybrid",
    ) -> Tuple[np.ndarray, float]:
        """Detect and correct the skew of a document image.

        Args:
            img:    Input image (BGR or grayscale) as a NumPy array.
            method: One of ``"hybrid"``, ``"hough"``, or ``"projection"``.

        Returns:
            A 2-tuple ``(corrected_image, detected_angle_degrees)``.
            The angle is positive for counter-clockwise rotation and
            negative for clockwise rotation.
        """
        method_enum = _DeskewMethod(method.lower())
        gray = self._to_gray(img)

        if method_enum == _DeskewMethod.HOUGH:
            angle, _conf = self._hough_method(gray)
        elif method_enum == _DeskewMethod.PROJECTION:
            angle, _conf = self._projection_method(gray)
        else:
            angle, _conf = self._hybrid_method(gray)

        corrected = self._correct_rotation(img, angle)
        return corrected, angle

    # ------------------------------------------------------------------
    # Hough line method
    # ------------------------------------------------------------------

    def _hough_method(
        self,
        gray: np.ndarray,
    ) -> Tuple[float, float]:
        """Estimate skew angle using the Probabilistic Hough Transform.

        The algorithm detects straight line segments, filters by length,
        and computes the median angle of near-horizontal lines.

        Args:
            gray: Grayscale image.

        Returns:
            ``(angle_degrees, confidence)`` where *angle_degrees* is in
            ``[-45, 45]`` and *confidence* is in ``[0, 1]``.
        """
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=100,
            minLineLength=gray.shape[1] // 4,
            maxLineGap=20,
        )

        if lines is None:
            return 0.0, 0.0

        angles: list[float] = []
        for line in lines:
            x1, y1, x2, y2 = line[0]  # type: ignore[index]
            length = np.hypot(float(x2 - x1), float(y2 - y1))
            if length < 10:
                continue
            angle = np.degrees(np.arctan2(float(y2 - y1), float(x2 - x1)))
            # Keep only near-horizontal lines.
            if -45 <= angle <= 45:
                angles.append(angle)

        if not angles:
            return 0.0, 0.0

        median_angle = float(np.median(angles))
        confidence = self._confidence_score(angles)

        return median_angle, confidence

    # ------------------------------------------------------------------
    # Projection profile method
    # ------------------------------------------------------------------

    def _projection_method(
        self,
        gray: np.ndarray,
    ) -> Tuple[float, float]:
        """Estimate skew angle using horizontal projection profiles.

        For each candidate angle the image is rotated and the horizontal
        projection profile (row-wise pixel sum) is computed.  The angle
        that yields the profile with the highest variance (i.e. the
        sharpest text-line separation) is selected.

        Args:
            gray: Grayscale image.

        Returns:
            ``(angle_degrees, confidence)``.
        """
        # Threshold to binary.
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # Subsample the image to keep the search fast.
        max_dim = 600
        h, w = binary.shape
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            binary = cv2.resize(binary, None, fx=scale, fy=scale,
                                interpolation=cv2.INTER_AREA)

        best_angle: float = 0.0
        best_score: float = -1.0
        scores: list[float] = []

        for deg in np.arange(-20.0, 20.5, 0.5):
            rad = np.deg2rad(deg)
            rotated = self._rotate_matrix(binary, rad)
            projection = np.sum(rotated, axis=1).astype(np.float64)
            score = float(np.var(projection))
            scores.append(score)
            if score > best_score:
                best_score = score
                best_angle = deg

        # Confidence: how much does the best score stand out?
        scores_arr = np.array(scores)
        confidence = 0.0
        if len(scores_arr) > 1:
            mean_score = float(np.mean(scores_arr))
            std_score = float(np.std(scores_arr))
            confidence = min((best_score - mean_score) / (std_score + 1e-6), 1.0)
            confidence = max(confidence, 0.0)

        return best_angle, confidence

    # ------------------------------------------------------------------
    # Hybrid method
    # ------------------------------------------------------------------

    def _hybrid_method(
        self,
        gray: np.ndarray,
    ) -> Tuple[float, float]:
        """Combine Hough and Projection methods, returning the result
        with the higher confidence score.

        Args:
            gray: Grayscale image.

        Returns:
            ``(angle_degrees, confidence)`` of the more confident method.
        """
        hough_angle, hough_conf = self._hough_method(gray)
        proj_angle, proj_conf = self._projection_method(gray)

        if hough_conf >= proj_conf:
            return hough_angle, hough_conf
        return proj_angle, proj_conf

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_gray(img: np.ndarray) -> np.ndarray:
        """Convert an image to grayscale if it is not already.

        Args:
            img: BGR or grayscale NumPy array.

        Returns:
            Grayscale image.
        """
        if len(img.shape) == 2:
            return img
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _rotate_matrix(
        img: np.ndarray,
        angle_rad: float,
    ) -> np.ndarray:
        """Rotate an image around its centre by *angle_rad* radians.

        Black padding is used for areas outside the original image
        bounds.

        Args:
            img:       Input image (any number of channels).
            angle_rad: Rotation angle in radians (positive = counter-
                       clockwise).

        Returns:
            Rotated image.
        """
        h, w = img.shape[:2]
        centre = (w / 2.0, h / 2.0)
        rotation_matrix = cv2.getRotationMatrix2D(centre,
                                                   np.degrees(angle_rad), 1.0)
        rotated = cv2.warpAffine(
            img,
            rotation_matrix,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        return rotated

    @staticmethod
    def _correct_rotation(
        img: np.ndarray,
        angle_deg: float,
    ) -> np.ndarray:
        """Apply a counter-clockwise rotation to correct the detected
        skew.

        The image canvas is expanded so that no content is cropped.

        Args:
            img:       Input image.
            angle_deg: Skew angle in degrees (positive = counter-
                       clockwise correction).

        Returns:
            Corrected image.
        """
        if abs(angle_deg) < 0.01:
            return img

        h, w = img.shape[:2]
        centre = (w / 2.0, h / 2.0)
        rotation_matrix = cv2.getRotationMatrix2D(centre, angle_deg, 1.0)

        # Compute new bounding-box dimensions to avoid cropping.
        cos_val = abs(rotation_matrix[0, 0])
        sin_val = abs(rotation_matrix[0, 1])
        new_w = int(h * sin_val + w * cos_val)
        new_h = int(h * cos_val + w * sin_val)

        rotation_matrix[0, 2] += (new_w - w) / 2.0
        rotation_matrix[1, 2] += (new_h - h) / 2.0

        corrected = cv2.warpAffine(
            img,
            rotation_matrix,
            (new_w, new_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255 if len(img.shape) == 2 else (255, 255, 255),
        )
        return corrected

    @staticmethod
    def _confidence_score(angles: list[float]) -> float:
        """Compute a confidence score from a list of detected angles.

        High confidence means the detected angles are tightly clustered
        (low standard deviation).  A value close to 1.0 indicates strong
        agreement among detected lines.

        Args:
            angles: List of near-horizontal angles in degrees.

        Returns:
            Confidence in ``[0, 1]``.
        """
        if len(angles) < 2:
            return 0.5 if angles else 0.0

        std = float(np.std(angles))
        # Map: std=0 → conf=1.0, std≥5 → conf→0.0
        confidence = max(1.0 - std / 5.0, 0.0)
        # Boost confidence when more lines agree.
        agreement_factor = min(len(angles) / 20.0, 1.0)
        return confidence * (0.6 + 0.4 * agreement_factor)
