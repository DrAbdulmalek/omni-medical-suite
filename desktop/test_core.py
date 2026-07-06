#!/usr/bin/env python3
"""
Desktop Test Suite - Imports from packages/core for consistency.
All tests here delegate to the shared core modules.
"""

import sys
import os
import pytest

# Add packages/core to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "core"))

import numpy as np
import cv2
from image_processor import (
    find_page_bounds, auto_detect_skew, smart_auto_crop,
    detect_blur_laplacian, assess_image_quality, apply_processing,
    image_segmentation,
)


def create_test_image(has_text=True):
    """Create a synthetic test image resembling a scanned medical document."""
    img = np.full((1000, 800, 3), 200, dtype=np.uint8)
    cv2.rectangle(img, (150, 100), (650, 900), (255, 255, 255), -1)
    if has_text:
        cv2.putText(img, "Test Page", (200, 500), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    return img


class TestFindPageBounds:
    """Tests for page boundary detection (imported from packages/core)."""

    def test_returns_four_values(self):
        img = create_test_image()
        l, t, r, b = find_page_bounds(img)
        assert len([l, t, r, b]) == 4
        assert l >= 0 and t >= 0 and r > 0 and b > 0

    def test_crops_gray_borders(self):
        img = np.full((500, 500, 3), 150, dtype=np.uint8)
        cv2.rectangle(img, (100, 100), (400, 400), (255, 255, 255), -1)
        l, t, r, b = find_page_bounds(img, threshold=180)
        assert l >= 95 and t >= 95 and r >= 95 and b >= 95


class TestAutoDetectSkew:
    """Tests for skew angle detection (imported from packages/core)."""

    def test_straight_image_returns_zero(self):
        img = create_test_image()
        angle = auto_detect_skew(img)
        assert abs(angle) < 0.5, f"Expected ~0 degrees, got {angle}"

    def test_rotated_image_detects_angle(self):
        img = create_test_image()
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), 2.5, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h))
        angle = auto_detect_skew(rotated)
        assert abs(angle - 2.5) < 1.0, f"Expected ~2.5 degrees, got {angle}"


class TestSmartAutoCrop:
    """Tests for auto cropping (imported from packages/core)."""

    def test_crops_to_content(self):
        img = create_test_image()
        cropped = smart_auto_crop(img)
        assert cropped.shape[0] <= 1000
        assert cropped.shape[1] <= 800
        assert cropped.shape[0] > 100

    def test_no_crash_empty(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cropped = smart_auto_crop(img)
        assert cropped is not None


class TestQuality:
    """Tests for image quality assessment (imported from packages/core)."""

    def test_blur_score(self):
        img = create_test_image()
        blur = detect_blur_laplacian(img)
        assert blur > 0

    def test_quality_assessment(self):
        img = create_test_image()
        quality = assess_image_quality(img)
        assert "blur_score" in quality
        assert "label" in quality


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
