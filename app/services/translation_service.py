# app/services/translation_service.py
"""Translation Service — MarianMT + specialty-aware dictionary routing.

Dictionary resources are separated by role:
- Translation rules are delegated to the existing rule engine.
- TMX is exact whole-segment lookup only.
- Bilingual terminology is exact whole-input lookup for short terms; it is
  never a blind substring replacement map.
- Specialty selection is inherited from general -> general_medical -> specialty.
"""

from __future__ import annotations

import logging
import re
import threading
import traceback
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

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

_MAX_CHUNK_CHARS = 400
_lock = threading.Lock()
_translator_cache: dict[str, tuple[Any, Any]] = {}
_translation_corrector = None
_translation_corrector_probed = False
_dictionary_router_cache: dict[str, Any] = {}
_tm_cache: dict[str, Any] = {}


def _resolve_specialty(text: str, specialty: str | None) -> str:
    if specialty:
        return specialty
    try:
        from packages.core.classifier import MedicalClassifier
        result = MedicalClassifier().classify_with_fallback(text, min_confidence=0.15)
        return result.get("category", "general_medical")
    except Exception:
        return "general_medical"


def get_dictionary_router(specialty: str | None = "general_medical"):
    """Return the production dictionary router for a canonical specialty."""
    from packages.medical.dictionary_router import SpecialtyDictionaryRouter
    from packages.medical.dictionary_registry import canonical_specialty
    canonical = canonical_specialty(specialty)
    router = _dictionary_router_cache.get(canonical)
    if router is None:
        router = SpecialtyDictionaryRouter(canonical)
        _dictionary_router_cache[canonical] = router
    return router


def get_exact_translation_memory(specialty: str | None = "general_medical"):
    """Load only TMX resources routed to the selected specialty."""
    from packages.medical.translation_memory import ExactTranslationMemory
    from packages.medical.dictionary_registry import canonical_specialty
    canonical = canonical_specialty(specialty)
    if canonical not in _tm_cache:
        _tm_cache[canonical] = ExactTranslationMemory.from_specialty(canonical)
    return _tm_cache[canonical]


def _lookup_exact_dictionary(text: str, direction: str, specialty: str) -> str | None:
    """Use exact dictionaries only; never rewrite a substring of a sentence.

    The specialty TM artifact is validated FIRST, before the 8-word
    optimization. This ensures that a missing specialty artifact raises
    RuntimeError regardless of input length — a long input must NOT
    silently bypass the fail-closed contract by returning None early.
    """
    if not text:
        return None

    # Validate specialty TM artifact before the word-count optimization.
    # This raises RuntimeError if the specialty artifact is missing,
    # which translate_text() catches and surfaces as a visible error.
    tm = get_exact_translation_memory(specialty)

    # 8-word optimization: exact TM is only useful for short phrases.
    # This is AFTER the specialty validation, so missing artifacts
    # still fail closed even for long inputs.
    if len(text.split()) > 8:
        return None

    tm_target = tm.translate_exact(text)
    if tm_target is not None:
        logger.info("Exact TM hit: specialty=%s direction=%s", specialty, direction)
        return tm_target

    # Only an explicitly bilingual glossary can provide a translation. OCR
    # correction maps and specialty lexicons are intentionally excluded here.
    if direction == "English → Arabic":
        target_lang = "ar"
    elif direction == "Arabic → English":
        target_lang = "en"
    else:
        return None
    router = get_dictionary_router(specialty)
    matches = router.lookup_translation_exact(text, target_lang)
    if matches:
        logger.info("Exact terminology hit: specialty=%s direction=%s", specialty, direction)
        return matches[0]["target"]
    return None


def get_translation_corrector():
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
            base = Path(__file__).resolve().parents[2]
            rules_path = base / "data" / "translation_rules.json"
            if not rules_path.is_file():
                rules_path = None
            from packages.nlp.translation_corrector import ArabicTranslationProcessor
            _translation_corrector = ArabicTranslationProcessor(
                rules_file=str(rules_path) if rules_path else None
            )
            logger.info("Translation corrector loaded (%d rules)", len(_translation_corrector.rules))
        except ImportError as e:
            logger.warning("translation_corrector module not found: %s", e)
            _translation_corrector = None
        except Exception as e:
            logger.warning("Failed to load translation_corrector: %s", e)
            _translation_corrector = None
        return _translation_corrector


def correct_translation(english_text: str, arabic_text: str, enable: bool = True) -> str:
    if not enable or not arabic_text:
        return arabic_text
    corrector = get_translation_corrector()
    if corrector is None:
        return arabic_text
    result = corrector.process_translation(english_text, arabic_text)
    if result["improved"]:
        logger.info(
            "Translation corrected: %d rule changes + %d regex changes",
            len(result["corrections"]), len(result["regex_changes"]),
        )
    return result["corrected"]


def load_translator(model_name: str) -> tuple[Any, Any] | tuple[None, None]:
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
            logger.info("Loading translation model: %s", model_name)
            tok = MarianTokenizer.from_pretrained(model_name)
            mdl = MarianMTModel.from_pretrained(model_name).to(DEVICE)
            _translator_cache[cache_key] = (tok, mdl)
            return tok, mdl
        except Exception as e:
            logger.error("Failed to load translator %s: %s", model_name, e)
            return None, None


def _chunk_text(text: str) -> list[str]:
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
    return None


def translate_text(
    text: str,
    direction: str,
    correct_output: bool = True,
    progress: Callable[[float, str], None] | None = None,
    specialty: str | None = None,
) -> str:
    """Translate using production dictionaries selected by specialty."""
    if not text or not text.strip():
        return "⚠️ الرجاء إدخال نص للترجمة."

    model_name = TRANSLATION_MODELS.get(direction)
    if not model_name:
        return f"❌ اتجاه غير مدعوم: {direction}"

    resolved_specialty = _resolve_specialty(text, specialty)
    try:
        exact = _lookup_exact_dictionary(text.strip(), direction, resolved_specialty)
        if exact is not None:
            return (
                f"{exact}\n\n---\n"
                f"**المصدر**: exact dictionary/TMX  |  **التخصص**: `{resolved_specialty}`"
            )
    except RuntimeError as e:
        # Fail-closed specialty-TM errors must propagate to the caller.
        # Silently swallowing them would violate the "no silent fallback"
        # contract: a missing specialty artifact must be visible, not hidden.
        logger.error("Specialty TM fail-closed: %s", e)
        return f"❌ {e}"
    except Exception as e:
        # Non-artifact lookup failures are recoverable: degrade to MarianMT
        # with a warning. Specialty artifact corruption/read failures are
        # wrapped as RuntimeError by ExactTranslationMemory and therefore
        # never reach this fallback path.
        logger.warning("Dictionary lookup unavailable: %s", e)

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
            progress(0.3 + 0.7 * ((i + 1) / len(chunks)), desc=f"ترجمة الجزء {i+1}/{len(chunks)}…")
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
            f"**التخصص**: `{resolved_specialty}`  |  **الأحرف**: {len(text)} → {len(translated)}"
        )
    except Exception as e:
        logger.error("خطأ ترجمة: %s", traceback.format_exc())
        return f"❌ فشلت الترجمة: {e}"


def reset_lazy_cache() -> None:
    global _translation_corrector, _translation_corrector_probed
    with _lock:
        _translator_cache.clear()
        _dictionary_router_cache.clear()
        _tm_cache.clear()
        _translation_corrector = None
        _translation_corrector_probed = False
