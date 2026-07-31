# app/services/translation_service.py
"""Translation Service — MarianMT translation + post-MT correction.

Extracted from ``app/gradio_full_hitl.py`` in v1.1.0-rc (P0 hardening)
so the Gradio UI layer stays thin and focused on orchestration.

Public API
----------
- ``TRANSLATION_MODELS`` — dict of direction → HF model name
- ``get_translation_corrector()`` — lazy singleton for the rule-based
  ArabicTranslationProcessor (returns None if unavailable)
- ``correct_translation(english_text, arabic_text, enable=True)`` —
  post-MT rule correction
- ``load_translator(model_name)`` — lazy MarianMT loader with cache
- ``translate_text(text, direction, correct_output=True, progress=None)``
  — full translation pipeline (chunking + MT + optional post-correction)

Design notes
------------
- The translation model cache and the corrector singleton live here,
  not in the UI file. Multiple Gradio tabs can share the same cache.
- ``transformers`` and ``torch`` are imported lazily inside
  ``load_translator()`` so importing this module is cheap.
- The module is independent of Gradio: ``translate_text()`` accepts an
  optional ``progress`` callable (Gradio's ``gr.Progress()`` duck-types
  to this), but falls back to a no-op when None.
"""

from __future__ import annotations

import logging
import re
import threading
import traceback
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────

DEVICE = "cpu"
try:
    import torch

    if torch.cuda.is_available():
        DEVICE = "cuda"
except ImportError:
    pass

TRANSLATION_MODELS = {
    "Arabic → English": "Helsinki-NLP/opus-mt-ar-en",
    "English → Arabic": "Helsinki-NLP/opus-mt-en-ar",
    "Arabic → German": "Helsinki-NLP/opus-mt-ar-de",
    "German → Arabic": "Helsinki-NLP/opus-mt-de-ar",
}

# Maximum chunk size in characters. MarianMT models have a 512-token
# context; ~400 chars is a safe upper bound for Arabic+English mixed.
_MAX_CHUNK_CHARS = 400

# ── Lazy singletons ─────────────────────────────────────────────────────────

_lock = threading.Lock()
_translator_cache: dict[str, tuple[Any, Any]] = {}
_translation_corrector = None
_translation_corrector_probed = False


def get_translation_corrector():
    """Return the singleton ArabicTranslationProcessor, or ``None`` if unavailable.

    Construction happens on first call and the result is cached. A failed
    import is also cached (``_translation_corrector_probed``) so we don't
    retry on every call.
    """
    global _translation_corrector, _translation_corrector_probed
    if _translation_corrector is not None:
        return _translation_corrector
    if _translation_corrector_probed:
        return None
    with _lock:
        if _translation_corrector is not None:
            return _translation_corrector
        if _translation_corrector_probed:
            return None
        _translation_corrector_probed = True
        try:
            # app/services/ → repo root (was previously calculated relative
            # to app/gradio_full_hitl.py; the +1 in parents accounts for
            # the extra directory level).
            base = Path(__file__).resolve().parents[2]
            rules_path = base / "data" / "translation_rules.json"
            if not rules_path.is_file():
                rules_path = None  # type: ignore[assignment]
            from packages.nlp.translation_corrector import ArabicTranslationProcessor

            _translation_corrector = ArabicTranslationProcessor(
                rules_file=str(rules_path) if rules_path else None
            )
            logger.info(
                "Translation corrector loaded (%d rules)",
                len(_translation_corrector.rules),
            )
        except ImportError as e:
            logger.warning("translation_corrector module not found — using inline fallback: %s", e)
            _translation_corrector = None  # type: ignore[assignment]
        except Exception as e:
            logger.warning("Failed to load translation_corrector: %s", e)
            _translation_corrector = None  # type: ignore[assignment]
        return _translation_corrector


def correct_translation(english_text: str, arabic_text: str, enable: bool = True) -> str:
    """Apply post-MT correction to Arabic translation.

    Returns the corrected Arabic text. If ``enable`` is False, no
    correction is applied. If the corrector is unavailable, the input
    Arabic text is returned unchanged.
    """
    if not enable or not arabic_text:
        return arabic_text
    corrector = get_translation_corrector()
    if corrector is None:
        return arabic_text
    result = corrector.process_translation(english_text, arabic_text)
    if result["improved"]:
        logger.info(
            "Translation corrected: %d rule changes + %d regex changes",
            len(result["corrections"]),
            len(result["regex_changes"]),
        )
    return result["corrected"]


def load_translator(model_name: str) -> tuple[Any, Any] | tuple[None, None]:
    """Lazy-load MarianMT translator on first use.

    Returns ``(tokenizer, model)`` or ``(None, None)`` on failure.
    Cached per ``model_name``.
    """
    cache_key = f"translator_{model_name}"
    cached = _translator_cache.get(cache_key)
    if cached:
        return cached
    with _lock:
        cached = _translator_cache.get(cache_key)
        if cached:
            return cached
        try:
            from transformers import MarianMTModel, MarianTokenizer

            logger.info("Loading translation model: %s (this may take a moment...)", model_name)
            tok = MarianTokenizer.from_pretrained(model_name)
            mdl = MarianMTModel.from_pretrained(model_name).to(DEVICE)
            _translator_cache[cache_key] = (tok, mdl)
            return tok, mdl
        except Exception as e:
            logger.error("Failed to load translator %s: %s", model_name, e)
            return None, None


def _chunk_text(text: str) -> list[str]:
    """Split text into chunks of at most ``_MAX_CHUNK_CHARS`` chars,
    preserving paragraph boundaries.
    """
    chunks: list[str] = []
    cur = ""
    for para in re.split(r"\n\s*\n", text.strip()):
        if len(cur) + len(para) + 2 <= _MAX_CHUNK_CHARS:
            cur += ("\n\n" if cur else "") + para
        else:
            if cur:
                chunks.append(cur)
            cur = para
    if cur:
        chunks.append(cur)
    return chunks


def _noop_progress(_frac: float, desc: str = "") -> None:
    """Default progress callback when no Gradio progress object is supplied."""
    return None


def translate_text(
    text: str,
    direction: str,
    correct_output: bool = True,
    progress: Callable[[float, str], None] | None = None,
) -> str:
    """Translate text between Arabic, English, and German (lazy-loaded).

    Parameters
    ----------
    text : str
        Source text to translate.
    direction : str
        One of the keys in ``TRANSLATION_MODELS`` (e.g. ``"Arabic → English"``).
    correct_output : bool
        If True and the target language is Arabic, apply post-MT rule
        correction via ``correct_translation()``.
    progress : callable, optional
        Duck-typed Gradio ``gr.Progress()`` (or any callable accepting
        ``(fraction, desc)``). If None, a no-op is used.
    """
    if not text or not text.strip():
        return "⚠️ الرجاء إدخال نص للترجمة."

    model_name = TRANSLATION_MODELS.get(direction)
    if not model_name:
        return f"❌ اتجاه غير مدعوم: {direction}"

    progress = progress or _noop_progress
    progress(0.2, desc=f"تحميل النموذج ({direction})…")
    tok, mdl = load_translator(model_name)
    if tok is None or mdl is None:
        return "❌ فشل تحميل النموذج. راجع السجل."

    try:
        import torch

        chunks = _chunk_text(text)
        parts: list[str] = []
        for i, chunk in enumerate(chunks):
            progress(
                0.3 + 0.7 * ((i + 1) / len(chunks)),
                desc=f"ترجمة الجزء {i+1}/{len(chunks)}…",
            )
            inputs = tok(chunk, return_tensors="pt", truncation=True, max_length=512, padding=True)
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
            with torch.no_grad():
                gen = mdl.generate(**inputs, max_length=512)
            parts.append(tok.decode(gen[0], skip_special_tokens=True))

        translated = "\n\n".join(parts)

        correction_note = ""
        if correct_output and "Arabic" in direction:
            corrected = correct_translation(text, translated)
            if corrected != translated:
                correction_note = "✅ تم تطبيق تصحيح ما بعد الترجمة\n\n"
                translated = corrected

        return (
            f"{translated}\n\n"
            f"{correction_note}"
            f"---\n"
            f"**النموذج**: `{model_name}`  |  **الجهاز**: `{DEVICE}`  |  "
            f"**الأحرف**: {len(text)} → {len(translated)}"
        )
    except Exception as e:
        logger.error("خطأ ترجمة: %s", traceback.format_exc())
        return f"❌ فشلت الترجمة: {e}"


def reset_lazy_cache() -> None:
    """Reset translation singletons. Intended for tests."""
    global _translation_corrector, _translation_corrector_probed
    with _lock:
        _translator_cache.clear()
        _translation_corrector = None
        _translation_corrector_probed = False
