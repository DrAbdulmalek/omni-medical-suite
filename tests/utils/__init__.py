"""
Shared test utilities for OmniMedical Suite.

Provides helpers for:
- Creating mock image data for OCR tests
- Comparing Arabic text with normalization
- Loading test fixtures from JSON
- Skipping tests based on optional dependencies
"""
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Dependency-aware skip decorators
# ---------------------------------------------------------------------------
def requires_tesseract() -> None:
    """Skip test if tesseract binary is not found."""
    import shutil
    if not shutil.which("tesseract"):
        pytest.skip("tesseract-ocr not installed")


def requires_paddleocr() -> None:
    """Skip test if PaddleOCR is not importable."""
    pytest.importorskip("paddleocr")


def requires_torch() -> None:
    """Skip test if PyTorch is not importable."""
    pytest.importorskip("torch")


def requires_fastapi() -> None:
    """Skip test if FastAPI is not importable."""
    pytest.importorskip("fastapi")


def requires_arabic_reshaper() -> None:
    """Skip test if arabic-reshaper is not importable."""
    pytest.importorskip("arabic_reshaper")


# ---------------------------------------------------------------------------
# Mock image generators
# ---------------------------------------------------------------------------
def create_blank_image(width: int = 800, height: int = 600, channels: int = 3) -> np.ndarray:
    """
    Create a blank white image as a NumPy array.
    Useful as a placeholder for OCR preprocessor / pipeline tests.
    """
    if channels == 1:
        return np.ones((height, width), dtype=np.uint8) * 255
    return np.ones((height, width, channels), dtype=np.uint8) * 255


def create_mock_ocr_response(text: str = "اختبار", confidence: float = 0.95) -> dict[str, Any]:
    """Create a mock OCR response dictionary."""
    return {
        "text": text,
        "confidence": confidence,
        "blocks": [
            {
                "text": text,
                "bbox": [0, 0, 100, 30],
                "confidence": confidence,
            }
        ],
        "language": "ar",
        "page": 1,
    }


# ---------------------------------------------------------------------------
# Arabic text utilities
# ---------------------------------------------------------------------------
def normalize_arabic_text(text: str) -> str:
    """
    Normalize Arabic text for comparison in tests.
    - Remove tatweel (kashida) U+0640
    - Normalize alef variants to bare alef
    - Normalize taa marbuta to haa
    - Strip extra whitespace
    """
    text = text.replace("\u0640", "")  # tatweel
    text = text.replace("\u0622", "\u0627")  # alef madda -> alef
    text = text.replace("\u0623", "\u0627")  # alef hamza above -> alef
    text = text.replace("\u0625", "\u0627")  # alef hamza below -> alef
    text = text.replace("\u0624", "\u0648")  # waw hamza -> waw
    text = text.replace("\u0626", "\u064A")  # yaa hamza -> yaa
    text = text.replace("\u0629", "\u0647")  # taa marbuta -> haa
    text = " ".join(text.split())  # normalize whitespace
    return text.strip()


def assert_text_similar(
    actual: str,
    expected: str,
    threshold: float = 0.85,
    label: str = "",
) -> None:
    """
    Assert two strings are similar above a threshold using character-level comparison.
    Useful for fuzzy-matching OCR output where small errors are acceptable.
    """
    from rapidfuzz import fuzz
    score = fuzz.ratio(actual, expected) / 100.0
    msg = f"Text similarity {score:.2%} < {threshold:.0%}"
    if label:
        msg = f"[{label}] {msg}"
    assert score >= threshold, msg


# ---------------------------------------------------------------------------
# Fixture loaders
# ---------------------------------------------------------------------------
def load_json_fixture(name: str, subdir: str = "fixtures") -> Any:
    """Load a JSON file from tests/{subdir}/{name}.json."""
    base = Path(__file__).resolve().parent
    path = base / subdir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Test fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json_fixture(data: Any, name: str, subdir: str = "fixtures") -> Path:
    """Save data as JSON to tests/{subdir}/{name}.json (for generating test data)."""
    base = Path(__file__).resolve().parent
    dir_path = base / subdir
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path
