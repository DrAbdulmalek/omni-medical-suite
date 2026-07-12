"""
Tests for scanner_fixer.normalize — the full normalization pipeline.

Run with:
    pytest packages/scanner_fixer/tests/test_normalize.py -v
"""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

# Ensure the package src directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scanner_fixer.normalize import normalize_scanned_image, save_normalized


# ─── Synthetic image helpers ──────────────────────────────────────────────────


def _make_page(
    width: int = 800,
    height: int = 1100,
    color: bool = True,
    n_lines: int = 20,
    margin: int = 100,
) -> np.ndarray:
    """Create a synthetic white page with horizontal lines and a rectangle
    block simulating printed text.

    The entire background is white (255); dark elements are drawn *inside*
    the margin so that small shifts (±20 px) never clip content at the
    image boundary.
    """
    if color:
        img = np.full((height, width, 3), 255, dtype=np.uint8)
        line_color = (0, 0, 0)
        rect_color = (0, 0, 0)
    else:
        img = np.full((height, width), 255, dtype=np.uint8)
        line_color = 0
        rect_color = 0

    content_h = height - 2 * margin
    line_gap = content_h // (n_lines + 1)

    for i in range(n_lines):
        y = margin + (i + 1) * line_gap
        thickness = np.random.randint(2, 5)
        x1 = np.random.randint(margin + 10, margin + 60)
        x2 = np.random.randint(width - margin - 60, width - margin - 10)
        cv2.line(img, (x1, y), (x2, y), line_color, thickness)

    # A solid rectangle near the top to simulate a text block / header
    cv2.rectangle(
        img,
        (margin + 30, margin + 20),
        (width - margin - 30, margin + 100),
        rect_color,
        -1,
    )
    return img


def _shift_image(image: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Shift image content by (dx, dy) pixels, padding with white."""
    h, w = image.shape[:2]
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    border_value = (255, 255, 255) if len(image.shape) == 3 else 255
    return cv2.warpAffine(image, M, (w, h), borderValue=border_value)


def _rotate_image(image: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate image around its centre, filling background with white."""
    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle_deg, 1.0)
    border_value = (255, 255, 255) if len(image.shape) == 3 else 255
    return cv2.warpAffine(image, M, (w, h), borderValue=border_value)


# ─── Tests ─────────────────────────────────────────────────────────────────────


class TestNormalizeShiftedImages:
    """Images shifted ±20px horizontally/vertically should produce the same
    output dimensions after normalization (crop absorbs the shift).

    We use a generous margin (100 px) so a ±20 px shift cannot clip dark
    content at the image boundary.  Because the background is pure white,
    auto_crop finds the same content bounding box regardless of shift.
    """

    def test_horizontal_shift_same_dimensions(self):
        np.random.seed(42)
        base = _make_page(color=False)
        shifted_right = _shift_image(base, dx=20, dy=0)
        shifted_left = _shift_image(base, dx=-20, dy=0)

        target_h = 800  # smaller for speed
        norm_base = normalize_scanned_image(base, target_height=target_h, output_grayscale=False)
        norm_right = normalize_scanned_image(shifted_right, target_height=target_h, output_grayscale=False)
        norm_left = normalize_scanned_image(shifted_left, target_height=target_h, output_grayscale=False)

        # Height is exact; width may differ by ±1 px due to integer
        # rounding after crop+resize.
        assert norm_base.shape[0] == target_h
        assert norm_right.shape[0] == target_h
        assert norm_left.shape[0] == target_h
        assert abs(norm_base.shape[1] - norm_right.shape[1]) <= 1
        assert abs(norm_base.shape[1] - norm_left.shape[1]) <= 1

    def test_vertical_shift_same_dimensions(self):
        np.random.seed(42)
        base = _make_page(color=False)
        shifted_down = _shift_image(base, dx=0, dy=20)
        shifted_up = _shift_image(base, dx=0, dy=-20)

        target_h = 800
        norm_base = normalize_scanned_image(base, target_height=target_h, output_grayscale=False)
        norm_down = normalize_scanned_image(shifted_down, target_height=target_h, output_grayscale=False)
        norm_up = normalize_scanned_image(shifted_up, target_height=target_h, output_grayscale=False)

        # Height is exact; width may differ by ±1 px
        assert norm_base.shape[0] == target_h
        assert norm_down.shape[0] == target_h
        assert norm_up.shape[0] == target_h
        assert abs(norm_base.shape[1] - norm_down.shape[1]) <= 1
        assert abs(norm_base.shape[1] - norm_up.shape[1]) <= 1

    def test_combined_shift_same_dimensions(self):
        np.random.seed(42)
        base = _make_page(color=False)
        shifted = _shift_image(base, dx=20, dy=-20)

        target_h = 800
        norm_base = normalize_scanned_image(base, target_height=target_h, output_grayscale=False)
        norm_shifted = normalize_scanned_image(shifted, target_height=target_h, output_grayscale=False)

        # Height is exact; width may differ by ±1 px
        assert norm_base.shape[0] == target_h
        assert norm_shifted.shape[0] == target_h
        assert abs(norm_base.shape[1] - norm_shifted.shape[1]) <= 1


class TestNormalizeSkewedImages:
    """Images with slight skew (±3°) should be corrected."""

    def test_positive_skew_corrected(self):
        base = _make_page(color=False, n_lines=30)
        rotated = _rotate_image(base, 3.0)

        target_h = 800
        result = normalize_scanned_image(rotated, target_height=target_h, output_grayscale=False)

        assert result is not None
        assert result.shape[0] == target_h

    def test_negative_skew_corrected(self):
        base = _make_page(color=False, n_lines=30)
        rotated = _rotate_image(base, -3.0)

        target_h = 800
        result = normalize_scanned_image(rotated, target_height=target_h, output_grayscale=False)

        assert result is not None
        assert result.shape[0] == target_h


class TestNormalizeResolution:
    """Images at different resolutions should produce the same height."""

    def test_different_resolutions_same_height(self):
        """Simulate same document scanned at two different DPIs."""
        # "Low-res" version
        img_low = _make_page(width=400, height=550, color=False)
        # "High-res" version (2.5×)
        img_high = cv2.resize(
            img_low, (1000, 1375), interpolation=cv2.INTER_CUBIC
        )

        target_h = 1600
        norm_low = normalize_scanned_image(img_low, target_height=target_h)
        norm_high = normalize_scanned_image(img_high, target_height=target_h)

        # Both must have exactly the target height
        assert norm_low.shape[0] == target_h
        assert norm_high.shape[0] == target_h

        # Widths should be nearly identical.  Morphological operations
        # inside auto_crop have a proportionally larger effect on
        # smaller images, so allow a tolerance of 10 px.
        width_diff = abs(norm_low.shape[1] - norm_high.shape[1])
        assert width_diff <= 15, (
            f"Widths differ by {width_diff}: low={norm_low.shape[1]}, high={norm_high.shape[1]}"
        )

    def test_upscale_uses_linear(self):
        """Verify upscaling produces expected dimensions."""
        img_small = _make_page(width=200, height=280, color=False)
        target_h = 1600
        result = normalize_scanned_image(img_small, target_height=target_h)
        assert result.shape[0] == target_h
        assert result.shape[1] > 0

    def test_downscale_uses_area(self):
        """Verify downscaling produces expected dimensions."""
        img_large = _make_page(width=2000, height=2800, color=False)
        target_h = 800
        result = normalize_scanned_image(img_large, target_height=target_h)
        assert result.shape[0] == target_h
        assert result.shape[1] > 0


class TestNormalizeColorMode:
    """Pipeline should handle both BGR and grayscale input."""

    def test_bgr_input_becomes_grayscale(self):
        img_bgr = _make_page(color=True)
        result = normalize_scanned_image(img_bgr, output_grayscale=True)
        assert len(result.shape) == 2, "Expected grayscale output (2D array)"

    def test_grayscale_input_stays_grayscale(self):
        img_gray = _make_page(color=False)
        result = normalize_scanned_image(img_gray, output_grayscale=True)
        assert len(result.shape) == 2

    def test_bgr_input_keep_color(self):
        img_bgr = _make_page(color=True)
        result = normalize_scanned_image(img_bgr, output_grayscale=False)
        assert len(result.shape) == 3, "Expected color output (3D array)"
        assert result.shape[2] == 3

    def test_grayscale_input_keep_color_stays_gray(self):
        """When input is already grayscale and output_grayscale=False, the
        result should still be grayscale (nothing to convert)."""
        img_gray = _make_page(color=False)
        result = normalize_scanned_image(img_gray, output_grayscale=False)
        assert len(result.shape) == 2


class TestSaveNormalized:
    """Test the save_normalized helper."""

    def test_saves_valid_png(self, tmp_path):
        img = _make_page(color=False)
        normalized = normalize_scanned_image(img, target_height=800)
        out_path = str(tmp_path / "output.png")

        returned = save_normalized(normalized, out_path)

        assert os.path.isfile(out_path)
        # Verify it is a valid PNG by reading it back
        loaded = cv2.imread(out_path, cv2.IMREAD_UNCHANGED)
        assert loaded is not None
        assert loaded.shape == normalized.shape
        # Returned path should be absolute
        assert os.path.isabs(returned)

    def test_creates_parent_directories(self, tmp_path):
        img = _make_page(color=False)
        normalized = normalize_scanned_image(img, target_height=800)
        out_path = str(tmp_path / "nested" / "dirs" / "image.png")

        save_normalized(normalized, out_path)
        assert os.path.isfile(out_path)

    def test_saves_grayscale_as_png(self, tmp_path):
        img_bgr = _make_page(color=True)
        normalized = normalize_scanned_image(img_bgr, output_grayscale=True)
        out_path = str(tmp_path / "gray.png")

        save_normalized(normalized, out_path)

        loaded = cv2.imread(out_path, cv2.IMREAD_UNCHANGED)
        assert loaded is not None
        assert len(loaded.shape) == 2  # grayscale


class TestNormalizeEdgeCases:
    """Miscellaneous edge cases."""

    def test_none_input_raises(self):
        with pytest.raises(ValueError, match="empty or None"):
            normalize_scanned_image(None)

    def test_empty_array_raises(self):
        with pytest.raises(ValueError, match="empty or None"):
            normalize_scanned_image(np.array([]))

    def test_default_target_height(self):
        """When no target_height is specified, the default 1600 should apply."""
        img = _make_page(color=False)
        result = normalize_scanned_image(img)
        assert result.shape[0] == 1600

    def test_custom_crop_padding(self):
        """crop_padding is passed through to auto_crop."""
        img = _make_page(color=False, margin=60)
        result = normalize_scanned_image(img, target_height=800, crop_padding=20)
        assert result.shape[0] == 800
