"""Tests for app/scanner_tab.py — interactive crop + advanced edge detection."""

from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pytest

# Ensure app/ is on sys.path
APP_DIR = Path(__file__).resolve().parent.parent / "app"
if str(APP_DIR.parent) not in sys.path:
    sys.path.insert(0, str(APP_DIR.parent))


def _make_test_image(size: int = 100) -> np.ndarray:
    """Make a 3-channel BGR test image with a white square on black."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    img[20:80, 20:80] = 255
    return img


# ---------------------------------------------------------------------------
# apply_manual_crop
# ---------------------------------------------------------------------------
class TestApplyManualCrop:
    def test_dict_format(self):
        from app.scanner_tab import apply_manual_crop

        img = _make_test_image(100)
        result = apply_manual_crop(img, {"x": 10, "y": 10, "width": 50, "height": 50})
        assert result.shape == (50, 50, 3)

    def test_tuple_format(self):
        from app.scanner_tab import apply_manual_crop

        img = _make_test_image(100)
        result = apply_manual_crop(img, (10, 10, 50, 50))
        assert result.shape == (50, 50, 3)

    def test_list_format(self):
        from app.scanner_tab import apply_manual_crop

        img = _make_test_image(100)
        result = apply_manual_crop(img, [10, 10, 50, 50])
        assert result.shape == (50, 50, 3)

    def test_none_returns_original(self):
        from app.scanner_tab import apply_manual_crop

        img = _make_test_image(100)
        result = apply_manual_crop(img, None)
        assert result.shape == img.shape
        # Should be the same data
        np.testing.assert_array_equal(result, img)

    def test_zero_area_returns_original(self):
        from app.scanner_tab import apply_manual_crop

        img = _make_test_image(100)
        # zero width
        result = apply_manual_crop(img, {"x": 10, "y": 10, "width": 0, "height": 50})
        assert result.shape == img.shape
        # zero height
        result = apply_manual_crop(img, {"x": 10, "y": 10, "width": 50, "height": 0})
        assert result.shape == img.shape

    def test_clipping_to_image_bounds(self):
        from app.scanner_tab import apply_manual_crop

        img = _make_test_image(100)
        # Selection extends beyond image bounds — should clip, not error
        result = apply_manual_crop(img, {"x": 80, "y": 80, "width": 100, "height": 100})
        assert result.shape == (20, 20, 3)

    def test_negative_origin_clipped(self):
        from app.scanner_tab import apply_manual_crop

        img = _make_test_image(100)
        # Selection at (-10, -10, w=50, h=50): only the positive part is valid,
        # so effective crop is (0, 0, 40, 40) → shape (40, 40, 3).
        result = apply_manual_crop(img, {"x": -10, "y": -10, "width": 50, "height": 50})
        assert result.shape == (40, 40, 3)

    def test_invalid_format_returns_original(self):
        from app.scanner_tab import apply_manual_crop

        img = _make_test_image(100)
        # String is not a valid format
        result = apply_manual_crop(img, "invalid")
        assert result.shape == img.shape

    def test_empty_image_returns_empty(self):
        from app.scanner_tab import apply_manual_crop

        empty = np.array([])
        result = apply_manual_crop(empty, {"x": 0, "y": 0, "width": 10, "height": 10})
        assert result.size == 0

    def test_short_tuple_returns_original(self):
        from app.scanner_tab import apply_manual_crop

        img = _make_test_image(100)
        result = apply_manual_crop(img, (10, 10))  # too short
        assert result.shape == img.shape


# ---------------------------------------------------------------------------
# apply_canny_edges
# ---------------------------------------------------------------------------
class TestApplyCannyEdges:
    def test_returns_3channel(self):
        from app.scanner_tab import apply_canny_edges

        img = _make_test_image(100)
        result = apply_canny_edges(img, low=50, high=150)
        assert result.shape == (100, 100, 3)

    def test_detects_square_edges(self):
        from app.scanner_tab import apply_canny_edges

        img = _make_test_image(100)
        result = apply_canny_edges(img, low=50, high=150)
        # Edges should be non-zero (square has clear edges)
        # Convert to grayscale to count non-zero
        gray = result[:, :, 0]
        assert (gray > 0).sum() > 0

    def test_works_on_grayscale_input(self):
        from app.scanner_tab import apply_canny_edges

        img = _make_test_image(100)[:, :, 0]  # 2D
        result = apply_canny_edges(img)
        assert len(result.shape) == 3


# ---------------------------------------------------------------------------
# apply_adaptive_threshold
# ---------------------------------------------------------------------------
class TestApplyAdaptiveThreshold:
    def test_returns_3channel(self):
        from app.scanner_tab import apply_adaptive_threshold

        img = _make_test_image(100)
        result = apply_adaptive_threshold(img, block_size=15, c_const=5)
        assert result.shape == (100, 100, 3)

    def test_block_size_made_odd(self):
        """Even block_size should be auto-corrected to odd (OpenCV requirement)."""
        from app.scanner_tab import apply_adaptive_threshold

        img = _make_test_image(100)
        # Should not raise
        result = apply_adaptive_threshold(img, block_size=10)
        assert result.shape == (100, 100, 3)


# ---------------------------------------------------------------------------
# apply_morphology
# ---------------------------------------------------------------------------
class TestApplyMorphology:
    @pytest.mark.parametrize("operation", ["close", "open", "erode", "dilate"])
    def test_all_operations(self, operation):
        from app.scanner_tab import apply_morphology

        img = _make_test_image(100)
        result = apply_morphology(img, operation=operation, kernel_size=5)
        assert result.shape == (100, 100, 3)

    def test_invalid_operation_defaults_to_close(self):
        from app.scanner_tab import apply_morphology

        img = _make_test_image(100)
        result = apply_morphology(img, operation="bogus", kernel_size=5)
        assert result.shape == (100, 100, 3)


# ---------------------------------------------------------------------------
# detect_hough_lines
# ---------------------------------------------------------------------------
class TestDetectHoughLines:
    def test_returns_annotated_and_angles(self):
        from app.scanner_tab import detect_hough_lines

        img = _make_test_image(100)
        annotated, angles = detect_hough_lines(img, threshold=50)
        assert annotated.shape == (100, 100, 3)
        assert isinstance(angles, list)

    def test_no_lines_returns_empty_list(self):
        from app.scanner_tab import detect_hough_lines

        # All-black image should produce few/no lines
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, angles = detect_hough_lines(img, threshold=200)
        assert isinstance(angles, list)


# ---------------------------------------------------------------------------
# apply_advanced_edges (composition)
# ---------------------------------------------------------------------------
class TestApplyAdvancedEdges:
    def test_no_options_returns_copy(self):
        from app.scanner_tab import apply_advanced_edges

        img = _make_test_image(100)
        result, meta = apply_advanced_edges(img)
        assert result.shape == img.shape
        assert meta["operations"] == []

    def test_all_options(self):
        from app.scanner_tab import apply_advanced_edges

        img = _make_test_image(100)
        result, meta = apply_advanced_edges(
            img,
            use_canny=True,
            use_adaptive=True,
            use_morphology=True,
            use_hough=True,
        )
        assert result.shape == img.shape
        assert "canny" in meta["operations"]
        assert "adaptive_threshold" in meta["operations"]
        assert "morphology" in meta["operations"]
        assert "hough" in meta["operations"]

    def test_empty_image_returns_error_meta(self):
        from app.scanner_tab import apply_advanced_edges

        empty = np.array([])
        result, meta = apply_advanced_edges(empty, use_canny=True)
        assert "error" in meta


# ---------------------------------------------------------------------------
# save_processed_image
# ---------------------------------------------------------------------------
class TestSaveProcessedImage:
    def test_saves_png_default(self):
        from app.scanner_tab import save_processed_image

        img = _make_test_image(100)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_processed_image(img, tmpdir, "test.png")
            assert Path(path).exists()
            assert path.endswith("test.png")

    def test_auto_filename_when_none(self):
        from app.scanner_tab import save_processed_image

        img = _make_test_image(100)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_processed_image(img, tmpdir, None)
            assert Path(path).exists()
            assert path.endswith(".png")

    def test_adds_png_extension_if_missing(self):
        from app.scanner_tab import save_processed_image

        img = _make_test_image(100)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_processed_image(img, tmpdir, "no_extension")
            assert path.endswith("no_extension.png")

    def test_creates_output_dir(self):
        from app.scanner_tab import save_processed_image

        img = _make_test_image(100)
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "nested" / "deeper"
            path = save_processed_image(img, str(nested), "test.png")
            assert Path(path).exists()

    def test_raises_on_empty_image(self):
        from app.scanner_tab import save_processed_image

        with pytest.raises(ValueError, match="empty image"):
            save_processed_image(np.array([]), "/tmp", "test.png")

    def test_path_traversal_sanitized(self):
        """Filename with path separators should be sanitized to basename only."""
        from app.scanner_tab import save_processed_image

        img = _make_test_image(100)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_processed_image(img, tmpdir, "../../../etc/passwd")
            # Should end up inside tmpdir, not escape
            assert str(Path(path).resolve()).startswith(str(Path(tmpdir).resolve()))


# ---------------------------------------------------------------------------
# pick_random_from_gallery
# ---------------------------------------------------------------------------
class TestPickRandomFromGallery:
    def test_empty_list_returns_none(self):
        from app.scanner_tab import pick_random_from_gallery

        img, label = pick_random_from_gallery([])
        assert img is None
        assert "لا توجد" in label

    def test_picks_an_image(self):
        from app.scanner_tab import pick_random_from_gallery, save_processed_image

        img = _make_test_image(100)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_processed_image(img, tmpdir, "test.png")
            picked, label = pick_random_from_gallery([path])
            assert picked is not None
            assert picked.shape == (100, 100, 3)
            assert "test.png" in label


# ---------------------------------------------------------------------------
# build_zip_from_dir
# ---------------------------------------------------------------------------
class TestBuildZipFromDir:
    def test_creates_zip(self):
        from app.scanner_tab import build_zip_from_dir, save_processed_image

        img = _make_test_image(100)
        with tempfile.TemporaryDirectory() as tmpdir:
            save_processed_image(img, tmpdir, "a.png")
            save_processed_image(img, tmpdir, "b.png")
            zip_path = build_zip_from_dir(tmpdir)
            assert Path(zip_path).exists()
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
                assert "a.png" in names
                assert "b.png" in names

    def test_default_zip_path(self):
        from app.scanner_tab import build_zip_from_dir, save_processed_image

        img = _make_test_image(100)
        with tempfile.TemporaryDirectory() as tmpdir:
            save_processed_image(img, tmpdir, "a.png")
            zip_path = build_zip_from_dir(tmpdir)
            # Default: <dir>.zip alongside
            assert Path(zip_path).name == f"{Path(tmpdir).name}.zip"

    def test_raises_on_missing_dir(self):
        from app.scanner_tab import build_zip_from_dir

        with pytest.raises(FileNotFoundError):
            build_zip_from_dir("/nonexistent/path/xyz")


# ---------------------------------------------------------------------------
# process_with_options (integration)
# ---------------------------------------------------------------------------
class TestProcessWithOptions:
    def test_none_input_returns_warning(self):
        from app.scanner_tab import process_with_options

        before, after, report = process_with_options(None)
        assert before is None
        assert after is None
        assert "لم يتم" in report

    def test_basic_processing(self):
        from app.scanner_tab import process_with_options

        img = _make_test_image(100)
        # Pass RGB (as Gradio would)
        img_rgb = img[:, :, ::-1].copy()
        before, after, report = process_with_options(
            img_rgb,
            do_crop=False,
            do_deskew=False,
            do_enhance=False,
            do_rotate=False,
        )
        assert before is not None
        # after may be None if scanner_fixer unavailable, but should be PIL if available
        assert "تقرير المعالجة" in report

    def test_with_manual_crop(self):
        from app.scanner_tab import process_with_options

        img = _make_test_image(100)
        img_rgb = img[:, :, ::-1].copy()
        before, after, report = process_with_options(
            img_rgb,
            crop_box={"x": 10, "y": 10, "width": 50, "height": 50},
            do_crop=False,
            do_deskew=False,
            do_enhance=False,
        )
        assert before is not None
        assert "قص يدوي" in report

    def test_with_advanced_edges(self):
        from app.scanner_tab import process_with_options

        img = _make_test_image(100)
        img_rgb = img[:, :, ::-1].copy()
        before, after, report = process_with_options(
            img_rgb,
            do_crop=False,
            do_deskew=False,
            do_enhance=False,
            use_canny=True,
            use_morphology=True,
        )
        assert before is not None
        # Either scanner_fixer ran or fallback applied edges
        assert "كشف الحواف" in report or "خطوات scanner_fixer" in report
