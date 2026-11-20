"""
Tests for scanner_fixer.pdf_ocr_processor.PDFOCRProcessor.

Covers:
  1. process_image() on a real verification image
  2. export_results() for both JSON and CSV (verifies on-disk content)
  3. Fallback behaviour when scanner_fixer.fix_scan raises (mock the
     exception -> should fall back to normalize_scanned_image -> then to
     the original image)
  4. _run_ocr() fallback when the requested engine is unavailable
     (after the EngineRegistry unification: request paddleocr on a
     system where only tesseract is installed -> should auto-fall back
     to tesseract and record it in ocr_engine_used)
  5. _ocr_paddle() with a mocked PaddleOCR class — verifies that the
     constructor is called with device='cpu' (the bug fixed in commit
     0a4f470) without needing real PaddleOCR installed.

Run with:
    pytest packages/scanner_fixer/tests/test_pdf_ocr_processor.py -v

Or directly:
    python3 packages/scanner_fixer/tests/test_pdf_ocr_processor.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from PIL import Image

# Make the package importable when run directly (without pytest)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
# Also add monorepo root so packages.core.engine_registry can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scanner_fixer.pdf_ocr_processor import (  # noqa: E402
    PDFOCRProcessor,
    _HAS_PADDLEOCR,
    _HAS_TESSERACT,
)


# Register the 'ocr' marker locally if pytest isn't aware of it (it's defined
# in the top-level pytest.ini but pytest may run from a subdir).
def pytest_configure(config):  # type: ignore[no-untyped-def]
    config.addinivalue_line(
        "markers",
        "ocr: tests requiring OCR engines (tesseract, paddleocr, etc.)",
    )


# ─── Fixtures ─────────────────────────────────────────────────────────────────

# From this test file:
#   parents[0] = tests/
#   parents[1] = scanner_fixer/   <- verification/ lives here
#   parents[2] = packages/
#   parents[3] = omni-medical-suite/   <- monorepo root
VERIFICATION_DIR = Path(__file__).resolve().parents[1] / "verification"


@pytest.fixture
def sample_image_path() -> Path:
    """Return a real verification image path (skips if missing)."""
    p = VERIFICATION_DIR / "arabic_A_fixed.png"
    if not p.exists():
        pytest.skip(f"Verification image not available: {p}")
    return p


@pytest.fixture
def sample_bgr(sample_image_path: Path) -> np.ndarray:
    """Load the verification image as a BGR numpy array."""
    img = cv2.imread(str(sample_image_path))
    assert img is not None, f"cv2.imread failed for {sample_image_path}"
    return img


@pytest.fixture
def processor_tesseract() -> PDFOCRProcessor:
    """A PDFOCRProcessor configured for Tesseract at 200 DPI (fast)."""
    return PDFOCRProcessor(dpi=200, ocr_engine="tesseract", normalize_images=True)


# ─── Test 1: process_image on a real verification image ───────────────────────

@pytest.mark.ocr
def test_process_image_on_real_scan(
    processor_tesseract: PDFOCRProcessor,
    sample_image_path: Path,
) -> None:
    """process_image() must return a dict with all expected keys and non-empty text."""
    if not _HAS_TESSERACT:
        pytest.skip("Tesseract not installed")

    result = processor_tesseract.process_image(str(sample_image_path))

    # Required keys
    expected_keys = {
        "page_num", "text", "ocr_engine", "ocr_engine_used",
        "confidence", "normalized", "skew_angle", "phash",
        "processing_time_ms", "error",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - set(result.keys())}"
    )

    # Page number is 0 for single images
    assert result["page_num"] == 0

    # OCR engine should be tesseract (requested and available)
    assert result["ocr_engine"] == "tesseract"
    assert result["ocr_engine_used"] == "tesseract"

    # Normalization should have run (scanner_fixer is installed)
    assert result["normalized"] is True

    # Text should be non-empty (this is a real scan with content)
    assert len(result["text"]) > 0, "OCR returned empty text for a real scan"

    # Confidence in [0, 1]
    assert 0.0 <= result["confidence"] <= 1.0

    # No errors
    assert result["error"] == ""

    # Processing time should be positive
    assert result["processing_time_ms"] > 0


# ─── Test 2: export_results for JSON and CSV ──────────────────────────────────

def test_export_results_json(
    processor_tesseract: PDFOCRProcessor,
    sample_bgr: np.ndarray,
    tmp_path: Path,
) -> None:
    """export_results(.json) must write a valid JSON file with all results."""
    if not _HAS_TESSERACT:
        pytest.skip("Tesseract not installed")

    result = processor_tesseract.process_image(sample_bgr)
    out_file = tmp_path / "results.json"

    returned_path = PDFOCRProcessor.export_results([result], out_file)

    assert Path(returned_path).exists()
    assert Path(returned_path).resolve() == out_file.resolve()

    with open(out_file, encoding="utf-8") as f:
        loaded = json.load(f)

    assert isinstance(loaded, list)
    assert len(loaded) == 1
    assert loaded[0]["page_num"] == result["page_num"]
    assert loaded[0]["text"] == result["text"]
    assert loaded[0]["ocr_engine_used"] == "tesseract"


def test_export_results_csv(
    processor_tesseract: PDFOCRProcessor,
    sample_bgr: np.ndarray,
    tmp_path: Path,
) -> None:
    """export_results(.csv) must write a CSV file with the expected columns."""
    if not _HAS_TESSERACT:
        pytest.skip("Tesseract not installed")

    result = processor_tesseract.process_image(sample_bgr)
    out_file = tmp_path / "results.csv"

    returned_path = PDFOCRProcessor.export_results([result], out_file)
    assert Path(returned_path).exists()

    csv_text = out_file.read_text(encoding="utf-8")
    # Header must include the new ocr_engine_used column added in the
    # EngineRegistry unification commit.
    assert "ocr_engine_used" in csv_text.split("\n")[0]
    # Body must contain the actually-used engine name
    assert "tesseract" in csv_text


def test_export_results_creates_parent_dirs(tmp_path: Path) -> None:
    """export_results must create parent directories if missing."""
    nested = tmp_path / "a" / "b" / "c" / "out.json"
    PDFOCRProcessor.export_results([], nested)
    assert nested.exists()


# ─── Test 3: scanner_fixer.fix_scan fallback ──────────────────────────────────

def test_normalize_falls_back_to_basic_when_pipeline_fails(
    sample_bgr: np.ndarray,
) -> None:
    """When fix_scan raises, _normalize_image must fall back to
    normalize_scanned_image, and if that also fails, to the original image.
    """
    proc = PDFOCRProcessor(dpi=200, ocr_engine="tesseract", normalize_images=True)

    # Mock fix_scan to raise — verify the fallback to normalize_scanned_image
    with patch("scanner_fixer.pdf_ocr_processor.fix_scan") as mock_fix, \
         patch(
             "scanner_fixer.pdf_ocr_processor.normalize_scanned_image"
         ) as mock_basic:
        mock_fix.side_effect = RuntimeError("simulated pipeline failure")
        mock_basic.return_value = sample_bgr  # successful fallback

        normalized, meta = proc._normalize_image(sample_bgr)

        # fix_scan was called and raised
        assert mock_fix.called
        # normalize_scanned_image was called as fallback
        assert mock_basic.called
        # We got back an image (the fallback's return value)
        assert normalized is sample_bgr


def test_normalize_falls_back_to_original_when_both_fail(
    sample_bgr: np.ndarray,
) -> None:
    """When both fix_scan and normalize_scanned_image raise, _normalize_image
    must return the original BGR image (no exception escapes)."""
    proc = PDFOCRProcessor(dpi=200, ocr_engine="tesseract", normalize_images=True)

    with patch("scanner_fixer.pdf_ocr_processor.fix_scan") as mock_fix, \
         patch(
             "scanner_fixer.pdf_ocr_processor.normalize_scanned_image"
         ) as mock_basic:
        mock_fix.side_effect = RuntimeError("pipeline fail")
        mock_basic.side_effect = RuntimeError("basic normalize fail")

        normalized, _meta = proc._normalize_image(sample_bgr)

        # Original image returned (last-resort fallback)
        assert normalized is sample_bgr


# ─── Test 4: _run_ocr fallback when requested engine is unavailable ──────────

def test_run_ocr_falls_back_when_engine_unavailable(
    sample_bgr: np.ndarray,
) -> None:
    """When the requested engine is unavailable but another is, _run_ocr
    must silently fall back and record the actually-used engine.

    After the EngineRegistry unification, requesting 'paddleocr' on a
    system with only tesseract installed should:
      - return text via tesseract
      - record 'tesseract' as the actually-used engine
    """
    if not _HAS_TESSERACT:
        pytest.skip("Tesseract not installed (needed as fallback target)")

    proc = PDFOCRProcessor(dpi=200, ocr_engine="paddleocr", normalize_images=False)

    # If real PaddleOCR is installed we can't test the fallback — skip.
    if _HAS_PADDLEOCR:
        pytest.skip("PaddleOCR is installed in this env; can't test fallback")

    text, conf, used = proc._run_ocr_with_tracking(sample_bgr)

    # Fallback should have picked tesseract
    assert used == "tesseract"
    # Some text should be returned (we passed a real image)
    assert isinstance(text, str)
    assert 0.0 <= conf <= 1.0


def test_run_ocr_no_engine_available_returns_empty(sample_bgr: np.ndarray) -> None:
    """When NO OCR engine is available, _run_ocr must return ('', 0.0, None)."""
    proc = PDFOCRProcessor(dpi=200, ocr_engine="tesseract", normalize_images=False)

    # Force every engine to look unavailable
    with patch.object(proc, "_is_engine_available", return_value=False), \
         patch.object(proc, "_pick_fallback_engine", return_value=None):
        text, conf, used = proc._run_ocr_with_tracking(sample_bgr)

    assert text == ""
    assert conf == 0.0
    assert used is None


def test_run_ocr_text_extraction_engine_short_circuits(sample_bgr: np.ndarray) -> None:
    """Requesting 'fitz' or 'pdfplumber' must short-circuit with empty text
    (they are text-extraction engines, not image OCR)."""
    proc = PDFOCRProcessor(dpi=200, ocr_engine="fitz", normalize_images=False)
    text, conf, used = proc._run_ocr_with_tracking(sample_bgr)
    assert text == ""
    assert conf == 0.0
    assert used == "fitz"


# ─── Test 5: _ocr_paddle uses device='cpu' (mocked) ───────────────────────────

def test_ocr_paddle_passes_device_cpu_to_constructor(
    sample_bgr: np.ndarray,
) -> None:
    """When _ocr_paddle initializes PaddleOCR, it MUST pass device='cpu'.

    This is the regression test for the bug fixed in commit 0a4f470
    (PaddlePaddle 3.x requires an explicit device argument). We mock the
    PaddleOCR class so this test runs even when real PaddleOCR isn't
    installed.
    """
    # Build a fake paddleocr module with a PaddleOCR class that records
    # how it was instantiated.
    fake_paddle_class = MagicMock()
    fake_paddle_instance = MagicMock()
    fake_paddle_class.return_value = fake_paddle_instance
    # Make .ocr() return an empty result so _ocr_paddle returns ("", 0.0)
    fake_paddle_instance.ocr.return_value = [[]]

    fake_module = MagicMock()
    fake_module.PaddleOCR = fake_paddle_class

    proc = PDFOCRProcessor(dpi=200, ocr_engine="tesseract", normalize_images=False)
    # Force the lazy reader to be None so _ocr_paddle constructs it
    proc._paddle_reader = None

    with patch.dict(sys.modules, {"paddleocr": fake_module}):
        text, conf = proc._ocr_paddle(sample_bgr)

    # PaddleOCR(...) must have been called exactly once
    assert fake_paddle_class.call_count == 1

    # Inspect the kwargs passed to the constructor
    _, kwargs = fake_paddle_class.call_args
    assert "device" in kwargs, (
        "PaddleOCR constructor was called without device=... — "
        "this is the PaddlePaddle 3.x compat bug (commit 0a4f470)"
    )
    assert kwargs["device"] == "cpu", (
        f"Expected device='cpu', got device={kwargs['device']!r}"
    )

    # Sanity-check the other expected kwargs are still there
    assert kwargs.get("use_angle_cls") is True
    assert kwargs.get("lang") == "ar"
    assert kwargs.get("show_log") is False

    # And the instance's .ocr() was called with the image
    assert fake_paddle_instance.ocr.call_count == 1
    # Empty result -> empty text, zero confidence
    assert text == ""
    assert conf == 0.0


# ─── Bonus: glossary extraction + auto_tune helpers ──────────────────────────

def test_extract_glossary_entries_finds_bilingual_pairs() -> None:
    """_extract_glossary_entries must find Arabic=English pairs in 4 patterns."""
    text = (
        "مرض السكري = Diabetes\n"
        "ضغط الدم - Blood Pressure\n"
        "القلب : Heart\n"
        "كبد\tLiver\n"
        "Not a glossary line\n"
        "عربي عربي عربي\n"  # both sides Arabic — must be skipped
    )
    entries = PDFOCRProcessor._extract_glossary_entries(text, source="test")

    assert len(entries) == 4
    pairs = {(e["term_arabic"], e["term_english"]) for e in entries}
    assert ("مرض السكري", "Diabetes") in pairs
    assert ("ضغط الدم", "Blood Pressure") in pairs
    assert ("القلب", "Heart") in pairs
    assert ("كبد", "Liver") in pairs
    # Source label propagated
    for e in entries:
        assert e["source"] == "test"


def test_extract_glossary_entries_dedupes() -> None:
    """Duplicate (ar, en) pairs must be deduplicated."""
    text = "مرض = Disease\nمرض = Disease\n"
    entries = PDFOCRProcessor._extract_glossary_entries(text, source="t")
    assert len(entries) == 1


def test_evaluate_ocr_text_returns_zero_for_empty() -> None:
    """Empty OCR text must score 0.0."""
    assert PDFOCRProcessor._evaluate_ocr_text("") == 0.0
    assert PDFOCRProcessor._evaluate_ocr_text("   \n  ") == 0.0


def test_evaluate_ocr_text_positive_for_arabic() -> None:
    """Real Arabic text must score > 0."""
    score = PDFOCRProcessor._evaluate_ocr_text("مرض السكري ضغط الدم القلب الكبد")
    assert 0.0 < score <= 1.0


# ─── Bonus: export_glossary ───────────────────────────────────────────────────

def test_export_glossary_csv_and_json(tmp_path: Path) -> None:
    """export_glossary must write CSV and JSON with the right content."""
    proc = PDFOCRProcessor(dpi=200, ocr_engine="tesseract", normalize_images=False)
    proc.combined_glossary = [
        {"term_arabic": "مرض", "term_english": "Disease", "source": "t.pdf"},
        {"term_arabic": "قلب", "term_english": "Heart", "source": "t.pdf"},
    ]

    csv_path = proc.export_glossary(tmp_path / "g.csv")
    json_path = proc.export_glossary(tmp_path / "g.json")

    assert Path(csv_path).exists()
    assert Path(json_path).exists()

    csv_content = Path(csv_path).read_text(encoding="utf-8")
    assert "term_arabic" in csv_content
    assert "مرض" in csv_content
    assert "Disease" in csv_content

    json_data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert len(json_data) == 2
    assert json_data[0]["term_arabic"] == "مرض"


if __name__ == "__main__":
    # Allow running directly without pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
