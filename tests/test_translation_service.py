"""Tests for app/services/translation_service.py — P0-3 extracted module.

These tests verify:
1. The module imports without triggering ``transformers`` or ``torch``
   (lazy loading preserved).
2. ``TRANSLATION_MODELS`` exposes all 4 directions.
3. ``translate_text()`` handles the obvious edge cases (empty input,
   unsupported direction, missing model) without raising.
4. ``_chunk_text()`` respects the 400-char chunk limit.
5. ``correct_translation()`` returns the input unchanged when the
   corrector is unavailable.
6. ``reset_lazy_cache()`` clears the cache.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _fresh_module():
    """Reset translation_service singletons before each test."""
    for mod in list(sys.modules):
        if "translation_service" in mod:
            del sys.modules[mod]
    yield
    try:
        from app.services.translation_service import reset_lazy_cache
        reset_lazy_cache()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Lazy import safety
# ---------------------------------------------------------------------------


def test_import_does_not_load_transformers():
    """Importing translation_service must not import transformers."""
    sys.modules.pop("transformers", None)
    import app.services.translation_service as ts  # noqa: F841

    assert "transformers" not in sys.modules


def test_import_does_not_load_torch():
    """Importing translation_service must not import torch."""
    sys.modules.pop("torch", None)
    import app.services.translation_service as ts  # noqa: F841

    assert "torch" not in sys.modules


# ---------------------------------------------------------------------------
# TRANSLATION_MODELS
# ---------------------------------------------------------------------------


def test_translation_models_has_four_directions():
    """All 4 directions are present."""
    from app.services.translation_service import TRANSLATION_MODELS

    assert "Arabic → English" in TRANSLATION_MODELS
    assert "English → Arabic" in TRANSLATION_MODELS
    assert "Arabic → German" in TRANSLATION_MODELS
    assert "German → Arabic" in TRANSLATION_MODELS
    assert len(TRANSLATION_MODELS) == 4


def test_translation_models_are_helsinki_opus():
    """All models point to Helsinki-NLP opus-mt family."""
    from app.services.translation_service import TRANSLATION_MODELS

    for model_name in TRANSLATION_MODELS.values():
        assert model_name.startswith("Helsinki-NLP/opus-mt-"), model_name


# ---------------------------------------------------------------------------
# translate_text edge cases
# ---------------------------------------------------------------------------


def test_translate_text_empty_input():
    """Empty input returns a friendly Arabic prompt."""
    from app.services.translation_service import translate_text

    assert "الرجاء" in translate_text("", "Arabic → English")


def test_translate_text_whitespace_only():
    """Whitespace-only input is treated as empty."""
    from app.services.translation_service import translate_text

    assert "الرجاء" in translate_text("   \n\n  ", "Arabic → English")


def test_translate_text_unsupported_direction():
    """Unsupported direction returns an Arabic error."""
    from app.services.translation_service import translate_text

    result = translate_text("hello", "Klingon → Elvish")
    assert "غير مدعوم" in result


def test_translate_text_model_load_failure():
    """If the model can't be loaded, translate_text returns a failure message."""
    from app.services.translation_service import translate_text

    # Make load_translator fail by blocking the transformers import
    sys.modules["transformers"] = None  # type: ignore[assignment]
    result = translate_text("hello", "Arabic → English")
    assert "فشل" in result or "❌" in result


# ---------------------------------------------------------------------------
# _chunk_text
# ---------------------------------------------------------------------------


def test_chunk_text_short_text_one_chunk():
    """Short text fits in a single chunk."""
    from app.services.translation_service import _chunk_text, _MAX_CHUNK_CHARS

    text = "hello world"
    chunks = _chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == "hello world"


def test_chunk_text_respects_max_chars():
    """Each chunk is at most _MAX_CHUNK_CHARS characters."""
    from app.services.translation_service import _chunk_text, _MAX_CHUNK_CHARS

    # Build a long text with paragraphs
    para = "x" * (_MAX_CHUNK_CHARS - 50) + "\n\n"
    text = (para * 5).strip()
    chunks = _chunk_text(text)
    assert len(chunks) >= 4
    for chunk in chunks:
        assert len(chunk) <= _MAX_CHUNK_CHARS


def test_chunk_text_preserves_paragraph_boundaries():
    """Paragraph breaks are preserved within chunks."""
    from app.services.translation_service import _chunk_text

    chunks = _chunk_text("first paragraph\n\nsecond paragraph")
    # Should be a single chunk since total < 400 chars
    assert len(chunks) == 1
    assert "\n\n" in chunks[0]


# ---------------------------------------------------------------------------
# correct_translation
# ---------------------------------------------------------------------------


def test_correct_translation_returns_input_when_disabled():
    """When enable=False, the input is returned unchanged."""
    from app.services.translation_service import correct_translation

    assert correct_translation("hello", "مرحبا", enable=False) == "مرحبا"


def test_correct_translation_returns_input_when_corrector_unavailable():
    """When the corrector can't be loaded, the Arabic input is returned unchanged."""
    from app.services.translation_service import correct_translation, reset_lazy_cache

    reset_lazy_cache()
    # Force corrector import to fail
    sys.modules["packages.nlp.translation_corrector"] = None
    result = correct_translation("hello", "مرحبا", enable=True)
    assert result == "مرحبا"


def test_correct_translation_handles_empty_input():
    """Empty arabic_text short-circuits regardless of enable."""
    from app.services.translation_service import correct_translation

    assert correct_translation("hello", "", enable=True) == ""


# ---------------------------------------------------------------------------
# reset_lazy_cache
# ---------------------------------------------------------------------------


def test_reset_lazy_cache_clears_translator_cache():
    """reset_lazy_cache() empties the translator cache."""
    from app.services.translation_service import _translator_cache, reset_lazy_cache

    _translator_cache["dummy"] = ("tok", "mdl")
    reset_lazy_cache()
    assert _translator_cache == {}
