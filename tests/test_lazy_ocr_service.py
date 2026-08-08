"""Tests for lazy OCR engine factories in app/services/ocr_service.py.

These tests verify:
1. Importing the module does NOT trigger any heavy engine construction
   (PaddleOCR, ImagePreprocessor, Tesseract, HybridSpellChecker).
2. The lazy getters (get_paddle_ocr, get_image_preprocessor, etc.)
   return None gracefully when the underlying dep is missing.
3. Failures are cached — a second call does not retry the import.
4. The backward-compat module __getattr__ (PEP 562) preserves the
   pre-P0 attribute names (``paddle_ocr``, ``HAS_TESSERACT``, etc.).
5. reset_lazy_cache() clears the cache for re-testing.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _fresh_module():
    """Force a fresh import of ocr_service before each test, and reset cache after."""
    # Drop any cached module so lazy singletons start clean
    for mod in list(sys.modules):
        if "ocr_service" in mod:
            del sys.modules[mod]
    yield
    # Reset cache after the test
    try:
        from app.services.ocr_service import reset_lazy_cache
        reset_lazy_cache()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Import-time safety
# ---------------------------------------------------------------------------


def test_import_does_not_touch_paddleocr():
    """Importing ocr_service must not import paddleocr."""
    # Drop paddleocr if it happens to be importable in the test env
    sys.modules.pop("paddleocr", None)
    import app.services.ocr_service as svc

    assert "paddleocr" not in sys.modules, (
        "paddleocr was imported at module load — P0-2 lazy loading regressed"
    )


def test_import_does_not_touch_pytesseract():
    """Importing ocr_service must not import pytesseract."""
    sys.modules.pop("pytesseract", None)
    import app.services.ocr_service as svc  # noqa: F841

    assert "pytesseract" not in sys.modules, (
        "pytesseract was imported at module load — P0-2 lazy loading regressed"
    )


def test_import_does_not_touch_image_preprocessor():
    """Importing ocr_service must not construct ImagePreprocessor."""
    sys.modules.pop("packages.vision.image_preprocessor", None)
    import app.services.ocr_service as svc  # noqa: F841

    assert "packages.vision.image_preprocessor" not in sys.modules


# ---------------------------------------------------------------------------
# Lazy getter behavior
# ---------------------------------------------------------------------------


def test_get_paddle_ocr_returns_none_when_unavailable():
    """get_paddle_ocr() returns None when paddleocr is not installed."""
    from app.services.ocr_service import get_paddle_ocr, reset_lazy_cache

    reset_lazy_cache()
    # Ensure paddleocr import fails
    sys.modules["paddleocr"] = None  # makes `import paddleocr` raise ImportError
    result = get_paddle_ocr()
    assert result is None


def test_get_paddle_ocr_caches_failure():
    """A failed init is cached — second call doesn't retry."""
    from app.services import ocr_service as svc

    svc.reset_lazy_cache()
    sys.modules["paddleocr"] = None
    assert svc.get_paddle_ocr() is None
    # Read the flag off the live module (not via `from … import`, which
    # would have captured the pre-call False value).
    assert svc._paddle_ocr_failed is True
    # Second call should also return None without re-attempting
    assert svc.get_paddle_ocr() is None


def test_get_image_preprocessor_returns_none_when_unavailable():
    """get_image_preprocessor() returns None when packages.vision.image_preprocessor is missing."""
    from app.services.ocr_service import get_image_preprocessor, reset_lazy_cache

    reset_lazy_cache()
    sys.modules["packages.vision.image_preprocessor"] = None
    assert get_image_preprocessor() is None


def test_has_tesseract_returns_false_when_unavailable():
    """has_tesseract() returns False when pytesseract is missing."""
    from app.services.ocr_service import has_tesseract, reset_lazy_cache

    reset_lazy_cache()
    sys.modules["pytesseract"] = None
    assert has_tesseract() is False


def test_get_spell_checker_returns_none_when_unavailable():
    """get_spell_checker() returns None when packages.core.spell_checker is missing."""
    from app.services.ocr_service import get_spell_checker, reset_lazy_cache

    reset_lazy_cache()
    sys.modules["packages.core.spell_checker"] = None
    assert get_spell_checker() is None


# ---------------------------------------------------------------------------
# Backward-compat __getattr__
# ---------------------------------------------------------------------------


def test_legacy_attribute_paddle_ocr_resolves_lazily():
    """``ocr_service.paddle_ocr`` resolves via PEP 562 __getattr__."""
    from app.services.ocr_service import reset_lazy_cache

    reset_lazy_cache()
    sys.modules["paddleocr"] = None
    import app.services.ocr_service as svc

    # Accessing the legacy attribute triggers the getter
    assert svc.paddle_ocr is None


def test_legacy_attribute_HAS_TESSERACT():
    """``ocr_service.HAS_TESSERACT`` resolves via PEP 562 __getattr__."""
    from app.services.ocr_service import reset_lazy_cache

    reset_lazy_cache()
    sys.modules["pytesseract"] = None
    import app.services.ocr_service as svc

    assert svc.HAS_TESSERACT is False


def test_unknown_attribute_raises_attribute_error():
    """PEP 562 __getattr__ raises AttributeError for unknown names."""
    import app.services.ocr_service as svc

    with pytest.raises(AttributeError):
        _ = svc.this_does_not_exist


# ---------------------------------------------------------------------------
# reset_lazy_cache
# ---------------------------------------------------------------------------


def test_reset_lazy_cache_clears_state():
    """reset_lazy_cache() clears all singleton + failure-flag state."""
    from app.services import ocr_service as svc

    sys.modules["paddleocr"] = None
    _ = svc.get_paddle_ocr()
    assert svc._paddle_ocr_failed is True
    svc.reset_lazy_cache()
    # After reset, the flags should be back to their default
    assert svc._paddle_ocr_failed is False
    assert svc._paddle_ocr_singleton is None


# ---------------------------------------------------------------------------
# _auto_correct_ocr still works without spell_checker
# ---------------------------------------------------------------------------


def test_auto_correct_ocr_works_without_spell_checker():
    """_auto_correct_ocr must not crash when spell_checker is unavailable."""
    from app.services.ocr_service import _auto_correct_ocr, reset_lazy_cache

    reset_lazy_cache()
    sys.modules["packages.core.spell_checker"] = None
    corrected, changes = _auto_correct_ocr("باراسيتبمول 5mg")
    # The OCR_CORRECTIONS dict should still apply
    assert "باراسيتامول" in corrected
    assert isinstance(changes, list)


# ---------------------------------------------------------------------------
# review_service lazy loading (P0-2 covers review_service too)
# ---------------------------------------------------------------------------


def test_review_service_import_does_not_load_llm():
    """Importing review_service must not eagerly import Jais modules."""
    for mod in list(sys.modules):
        if "jais_ner" in mod or "proofreader" in mod:
            del sys.modules[mod]
    sys.modules.pop("src.llm.proofreader", None)
    sys.modules.pop("src.ner.jais_ner", None)
    import app.services.review_service as rsvc  # noqa: F841

    assert "src.llm.proofreader" not in sys.modules
    assert "src.ner.jais_ner" not in sys.modules


def test_review_service_get_proofreader_none_without_enable_llm(monkeypatch):
    """get_proofreader() returns None when ENABLE_LLM is not set."""
    monkeypatch.delenv("ENABLE_LLM", raising=False)
    # Force re-import so the module reads the env var fresh
    for mod in list(sys.modules):
        if "review_service" in mod:
            del sys.modules[mod]
    import app.services.review_service as rsvc

    # reload to pick up env var
    importlib.reload(rsvc)
    assert rsvc.ENABLE_LLM is False
    assert rsvc.get_proofreader() is None
    assert rsvc.get_ner() is None
