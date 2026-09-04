# tests/test_image_processor.py
"""Unit tests for src.processors.image_processor.MedicalImageProcessor."""
import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from src.processors.image_processor import MedicalImageProcessor  # noqa: E402


def test_to_grayscale_converts_bgr_to_2d():
    image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    gray = MedicalImageProcessor.to_grayscale(image)
    assert gray.shape == (100, 100)
    assert gray.dtype == np.uint8


def test_to_grayscale_passthrough_for_already_grayscale():
    image = np.random.randint(0, 255, (50, 50), dtype=np.uint8)
    gray = MedicalImageProcessor.to_grayscale(image)
    assert gray.shape == (50, 50)


def test_to_grayscale_raises_on_none():
    with pytest.raises(ValueError):
        MedicalImageProcessor.to_grayscale(None)


def test_denoise_returns_same_shape_2d():
    image = np.random.randint(0, 255, (120, 120), dtype=np.uint8)
    denoised = MedicalImageProcessor.denoise(image)
    assert denoised.shape == image.shape


def test_denoise_returns_same_shape_3d():
    image = np.random.randint(0, 255, (120, 120, 3), dtype=np.uint8)
    denoised = MedicalImageProcessor.denoise(image)
    assert denoised.shape == image.shape


def test_enhance_contrast_returns_grayscale_shape():
    image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    enhanced = MedicalImageProcessor.enhance_contrast(image)
    assert enhanced.shape == (100, 100)
    assert enhanced.dtype == np.uint8


def test_binarize_returns_binary_image():
    image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    binary = MedicalImageProcessor.binarize(image)
    assert binary.shape == (100, 100)
    unique = np.unique(binary)
    assert set(unique.tolist()).issubset({0, 255})


def test_full_pipeline_rejects_missing_file(tmp_path):
    missing = tmp_path / "missing.png"
    with pytest.raises(ValueError):
        MedicalImageProcessor.full_pipeline(missing)


def test_full_pipeline_returns_processed_array(tmp_path):
    # Write a synthetic image to disk so imread can read it back.
    image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    path = tmp_path / "synthetic.png"
    cv2.imwrite(str(path), image)
    processed = MedicalImageProcessor.full_pipeline(path)
    assert processed.ndim == 2
    assert processed.dtype == np.uint8
