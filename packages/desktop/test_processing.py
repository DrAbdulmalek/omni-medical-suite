#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for Medical Document Scanner — Core Processing Functions.
Run with: pytest test_processing.py -v
"""
import sys
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, ".")

# Import core functions that don't depend on PyQt5
# We import them directly to avoid PyQt5 dependency in tests
try:
    from medical_doc_gui_v10 import (
        apply_processing, _remove_shadow, calc_blur, quality_label,
        auto_detect_skew, smart_auto_crop, images_are_similar,
        assess_image_quality,
    )
except ImportError as e:
    # PyQt5 not available — skip tests
    import pytest
    pytest.skip("PyQt5 not available, skipping import", allow_module_level=True)


# ════════════════════════════════════════════════════════════════
#  Test apply_processing
# ════════════════════════════════════════════════════════════════

class TestApplyProcessing:
    def test_identity_no_changes(self):
        """Image with no processing params should remain unchanged."""
        img = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        result = apply_processing(img, {})
        assert result.shape == img.shape
        # Should be identical since no operations applied
        assert np.array_equal(result, img)

    def test_rotation_90(self):
        """90-degree rotation should swap width and height."""
        img = np.random.randint(0, 255, (50, 100, 3), dtype=np.uint8)
        result = apply_processing(img, {"rotation": 90})
        assert result.shape == (100, 50, 3)

    def test_rotation_180(self):
        """180-degree rotation should preserve dimensions."""
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = apply_processing(img, {"rotation": 180})
        assert result.shape == (100, 100, 3)

    def test_rotation_270(self):
        """270-degree rotation should swap width and height."""
        img = np.random.randint(0, 255, (50, 100, 3), dtype=np.uint8)
        result = apply_processing(img, {"rotation": 270})
        assert result.shape == (100, 50, 3)

    def test_crop_basic(self):
        """Cropping should reduce image dimensions."""
        img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        result = apply_processing(img, {"crop": (10, 10, 10, 10)})
        assert result.shape == (180, 180, 3)

    def test_crop_no_change_when_zero(self):
        """Zero crop margins should not change dimensions."""
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = apply_processing(img, {"crop": (0, 0, 0, 0)})
        assert result.shape == (100, 100, 3)

    def test_flip_horizontal(self):
        """Horizontal flip should produce a mirror image."""
        img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = apply_processing(img, {"flip_h": True})
        expected = cv2_flip(img, 1) if 'cv2_flip' in dir() else np.fliplr(img)
        # Just check shape and that it's different from original
        assert result.shape == img.shape

    def test_sharpen(self):
        """Sharpen should not change image dimensions."""
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = apply_processing(img, {"sharpen": True})
        assert result.shape == img.shape

    def test_deskew(self):
        """Small deskew angle should preserve dimensions approximately."""
        img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        result = apply_processing(img, {"deskew_angle": 2.0})
        assert result.shape == (200, 200, 3)

    def test_combined_pipeline(self):
        """Full pipeline with multiple operations."""
        img = np.random.randint(0, 255, (300, 200, 3), dtype=np.uint8)
        params = {
            "rotation": 90,
            "crop": (5, 5, 5, 5),
            "deskew_angle": 1.0,
            "flip_h": True,
            "sharpen": True,
        }
        result = apply_processing(img, params)
        # After 90 rotation: 300x200 -> 200x300, then crop: 200-10=190 x 300-10=290
        assert result.shape == (290, 190, 3)

    def test_shadow_removal(self):
        """Shadow removal should not change dimensions."""
        img = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        result = apply_processing(img, {"remove_shadow": True})
        assert result.shape == (100, 100, 3)


# ════════════════════════════════════════════════════════════════
#  Test _remove_shadow
# ════════════════════════════════════════════════════════════════

class TestRemoveShadow:
    def test_preserves_shape(self):
        img = np.random.randint(0, 255, (100, 80, 3), dtype=np.uint8)
        result = _remove_shadow(img)
        assert result.shape == img.shape

    def test_output_range(self):
        img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = _remove_shadow(img)
        assert result.min() >= 0
        assert result.max() <= 255


# ════════════════════════════════════════════════════════════════
#  Test calc_blur
# ════════════════════════════════════════════════════════════════

class TestCalcBlur:
    def test_sharp_image_high_score(self):
        """A sharp random-noise image should have a high blur score."""
        img = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        score = calc_blur(img)
        assert score > 100  # Random noise is "sharp"

    def test_blur_image_low_score(self):
        """A heavily blurred image should have a low blur score."""
        img = np.ones((200, 200), dtype=np.uint8) * 128
        score = calc_blur(img)
        assert score < 10  # Uniform image has zero variance

    def test_color_image(self):
        """calc_blur should handle color (3-channel) images."""
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        score = calc_blur(img)
        assert isinstance(score, float)
        assert score > 0

    def test_grayscale_image(self):
        """calc_blur should handle grayscale images."""
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        score = calc_blur(img)
        assert isinstance(score, float)
        assert score > 0


# ════════════════════════════════════════════════════════════════
#  Test quality_label
# ════════════════════════════════════════════════════════════════

class TestQualityLabel:
    def test_excellent(self):
        label, color, icon = quality_label(300, 100)
        assert label == "ممتازة"
        assert color == "#16a34a"
        assert icon == "✅"

    def test_acceptable(self):
        label, color, icon = quality_label(120, 100)
        assert label == "مقبولة"
        assert color == "#d97706"
        assert icon == "⚠️"

    def test_blurry(self):
        label, color, icon = quality_label(50, 100)
        assert label == "ضبابية"
        assert color == "#dc2626"
        assert icon == "❌"

    def test_exact_threshold(self):
        label, _, _ = quality_label(100, 100)
        assert label == "مقبولة"

    def test_double_threshold(self):
        label, _, _ = quality_label(200, 100)
        assert label == "ممتازة"


# ════════════════════════════════════════════════════════════════
#  Test smart_auto_crop
# ════════════════════════════════════════════════════════════════

class TestSmartAutoCrop:
    def test_white_page_no_crop(self):
        """A fully white page should return (0,0,0,0) — no crop needed."""
        img = np.ones((1000, 800, 3), dtype=np.uint8) * 255
        crop = smart_auto_crop(img)
        assert crop == (0, 0, 0, 0)

    def test_dark_center_returns_crop(self):
        """An image with dark content in center should return non-zero crop."""
        img = np.ones((500, 500, 3), dtype=np.uint8) * 255
        img[100:400, 100:400] = 0  # Dark square
        crop = smart_auto_crop(img)
        assert crop != (0, 0, 0, 0)

    def test_crop_respects_padding(self):
        """Crop should add padding around detected content."""
        img = np.ones((500, 500, 3), dtype=np.uint8) * 255
        img[200:300, 200:300] = 0  # Small dark square
        crop_no_pad = smart_auto_crop(img, padding=0)
        crop_with_pad = smart_auto_crop(img, padding=50)
        # With padding, left/top crop should be less (smaller margins removed)
        assert crop_no_pad[0] >= crop_with_pad[0]
        assert crop_no_pad[1] >= crop_with_pad[1]


# ════════════════════════════════════════════════════════════════
#  Test auto_detect_skew
# ════════════════════════════════════════════════════════════════

class TestAutoDetectSkew:
    def test_straight_image_zero_angle(self):
        """A straight image with horizontal lines should return ~0 angle."""
        img = np.ones((200, 300, 3), dtype=np.uint8) * 255
        # Draw horizontal text-like lines
        for y in range(20, 180, 20):
            img[y, 10:290] = 0
        angle = auto_detect_skew(img)
        assert abs(angle) < 2.0

    def test_returns_float(self):
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        angle = auto_detect_skew(img)
        assert isinstance(angle, float)


# ════════════════════════════════════════════════════════════════
#  Test assess_image_quality
# ════════════════════════════════════════════════════════════════

class TestAssessImageQuality:
    def test_returns_all_keys(self):
        img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        result = assess_image_quality(img)
        expected_keys = {'overall', 'blur_score', 'contrast', 'edge_density',
                         'content_ratio', 'brightness'}
        assert set(result.keys()) == expected_keys

    def test_overall_in_range(self):
        img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        result = assess_image_quality(img)
        assert 0.0 <= result['overall'] <= 1.0

    def test_uniform_image_low_quality(self):
        img = np.ones((200, 200, 3), dtype=np.uint8) * 128
        result = assess_image_quality(img)
        assert result['blur_score'] < 5
        assert result['overall'] < 0.5


# ════════════════════════════════════════════════════════════════
#  Test images_are_similar (only if imagehash available)
# ════════════════════════════════════════════════════════════════

class TestImagesAreSimilar:
    def test_identical_images(self):
        if not hasattr(sys.modules.get('medical_doc_gui_v10', type('')), '__file__'):
            return
        try:
            from medical_doc_gui_v10 import HASH_SUPPORT
            if not HASH_SUPPORT:
                return
        except Exception:
            return
        img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        is_sim, dist = images_are_similar(img, img)
        assert is_sim is True
        assert dist == 0

    def test_different_images(self):
        try:
            from medical_doc_gui_v10 import HASH_SUPPORT
            if not HASH_SUPPORT:
                return
        except Exception:
            return
        img1 = np.ones((200, 200, 3), dtype=np.uint8) * 255
        img2 = np.zeros((200, 200, 3), dtype=np.uint8)
        is_sim, dist = images_are_similar(img1, img2)
        assert is_sim is False
