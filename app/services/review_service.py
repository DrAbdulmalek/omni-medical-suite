# app/services/review_service.py
"""Review Service — NER entity extraction, LLM proofreading, and correction logic.

Provides:
  - Dictionary-based NER via ``MEDICAL_TERMS`` and ``_extract_ner()``
  - Jais LLM proofreading via ``jais_proofread_only()`` (requires GPU)
  - Lazy accessors ``get_proofreader()`` / ``get_ner()`` for the Jais
    models, loaded only when ``ENABLE_LLM=true`` *and* first requested.

Since v1.1.0-rc (P0 hardening): Jais models are no longer constructed
at import time. Even with ``ENABLE_LLM=true``, importing this module is
cheap; the proofreader/NER instances are built on first call to
``get_proofreader()`` / ``get_ner()``.
"""

import logging
import os
import re
import threading

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
ENABLE_LLM = os.getenv("ENABLE_LLM", "false").lower() == "true"

# ── Lazy LLM singletons ─────────────────────────────────────────────────────
_lock = threading.Lock()
_proofreader_singleton = None
_ner_singleton = None
_proofreader_failed = False
_ner_failed = False


def get_proofreader():
    """Return the singleton MedicalProofreader, or ``None`` if unavailable.

    Construction requires ``ENABLE_LLM=true``. Failures are cached.
    """
    global _proofreader_singleton, _proofreader_failed
    if _proofreader_singleton is not None:
        return _proofreader_singleton
    if _proofreader_failed or not ENABLE_LLM:
        return None
    with _lock:
        if _proofreader_singleton is not None:
            return _proofreader_singleton
        if _proofreader_failed or not ENABLE_LLM:
            return None
        try:
            from src.llm.proofreader import MedicalProofreader

            _proofreader_singleton = MedicalProofreader()
            logger.info("MedicalProofreader loaded (lazy)")
        except Exception as e:
            _proofreader_failed = True
            logger.error("Failed to load MedicalProofreader (cached): %s", e)
        return _proofreader_singleton


def get_ner():
    """Return the singleton JaisNER, or ``None`` if unavailable."""
    global _ner_singleton, _ner_failed
    if _ner_singleton is not None:
        return _ner_singleton
    if _ner_failed or not ENABLE_LLM:
        return None
    with _lock:
        if _ner_singleton is not None:
            return _ner_singleton
        if _ner_failed or not ENABLE_LLM:
            return None
        try:
            from src.ner.jais_ner import JaisNER

            _ner_singleton = JaisNER()
            logger.info("JaisNER loaded (lazy)")
        except Exception as e:
            _ner_failed = True
            logger.error("Failed to load JaisNER (cached): %s", e)
        return _ner_singleton


def reset_lazy_cache() -> None:
    """Reset LLM singletons. Intended for tests."""
    global _proofreader_singleton, _ner_singleton
    global _proofreader_failed, _ner_failed
    with _lock:
        _proofreader_singleton = None
        _ner_singleton = None
        _proofreader_failed = False
        _ner_failed = False


# ── Backward-compat module-level attributes ─────────────────────────────────
# Pre-P0 callers did `from app.services.review_service import proofreader, ner, HAS_LLM`.
# We preserve these names via PEP 562 module __getattr__ so existing imports
# keep working — but they now trigger lazy construction on first access.

def __getattr__(name):  # PEP 562
    if name == "proofreader":
        return get_proofreader()
    if name == "ner":
        return get_ner()
    if name == "HAS_LLM":
        # True only if both ENABLE_LLM is set AND the modules import successfully.
        # We probe lazily: if get_proofreader() returns None, HAS_LLM is False.
        # This matches the pre-P0 semantics where HAS_LLM was set only on
        # successful import + instantiation.
        return get_proofreader() is not None or get_ner() is not None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── Medical dictionary for NER ──────────────────────────────────────────────
MEDICAL_TERMS = {
    # أدوية
    "باراسيتامول": "medication", "ايبوبروفين": "medication",
    "اموكسيسيلين": "medication", "ازيثرومايسين": "medication",
    "سيفالكسين": "medication", "ميترونيدازول": "medication",
    "اوجمنتين": "medication", "اوميبرازول": "medication",
    "ديكلوفيناك": "medication", "نابروكسين": "medication",
    "ترامادول": "medication", "كوديين": "medication",
    "سالبوتامول": "medication", "لوراتادين": "medication",
    "سيتيريزين": "medication", "رانيتيدين": "medication",
    "فاموتيدين": "medication", "انالجين": "medication",
    "بنادول": "medication", "ادفيل": "medication",
    "كاتافلام": "medication", "فولتارين": "medication",
    "مونتيلوكاست": "medication", "سودوافيدرين": "medication",
    "سيفترياكسون": "medication", "دوكسيسيكلين": "medication",
    "سيبروفلوكساسين": "medication", "لوفلوكساسين": "medication",
    "ميفيناميك": "medication", "انديسيترون": "medication",
    # أمراض
    "سكري": "disease", "ضغط": "disease", "ربو": "disease",
    "التهاب": "disease", "حساسية": "disease", "قرحة": "disease",
    "التهاب رئوي": "disease", "التهاب شعبي": "disease",
    "ارتفاع ضغط": "disease", "سرطان": "disease",
    # أعراض
    "صداع": "symptom", "حمى": "symptom", "سعال": "symptom",
    "الم": "symptom", "غثيان": "symptom", "اقياء": "symptom",
    "اسهال": "symptom", "دوار": "symptom", "تعب": "symptom",
    "ضيق تنفس": "symptom", "الم بطن": "symptom",
}


# ── NER Functions ───────────────────────────────────────────────────────────

def _extract_ner(text: str) -> dict[str, list[str]]:
    """Extract medical entities by dictionary matching."""
    entities = {"medications": [], "diseases": [], "symptoms": [], "dosages": []}
    for term, category in MEDICAL_TERMS.items():
        if term in text:
            entities.setdefault(f"{category}s", []).append(term)
    dosage_re = r'(\d+(?:\.\d+)?)\s*(?:ملغ|mg|مغ|مللي|مل|حبة|كبسولة|قرص|امبول)'
    for m in re.findall(dosage_re, text):
        entities["dosages"].append(m)
    return {k: list(set(v)) for k, v in entities.items() if v}


# ── LLM Proofreading ────────────────────────────────────────────────────────

def jais_proofread_only(text: str) -> str:
    """Standalone Jais LLM proofreading on raw OCR text."""
    proofreader = get_proofreader()
    if proofreader is None:
        return ("⚠️ يتطلب تفعيل ENABLE_LLM=true و GPU\n\n"
                "لا يمكن تشغيل تدقيق Jais بدون وحدة معالجة الرسومات (GPU) "
                "وتفعيل متغير البيئة ENABLE_LLM=true.")

    if not text or not text.strip():
        return "⚠️ لا يوجد نص للتدقيق. الرجاء تشغيل المعالجة الكاملة أولاً."

    try:
        # Lazy import to avoid hard dependency on ocr_service at module load
        from app.services.ocr_service import _auto_correct_ocr, get_spell_checker

        # Apply OCR corrections first, then spell check, then LLM proofread
        corrected, _corrections = _auto_correct_ocr(text)

        checker = get_spell_checker()
        if checker is not None:
            try:
                corrected = checker.correct_text(corrected)
            except Exception as e:
                logger.warning(f"Spell check failed in standalone proofread: {e}")

        proof_result = proofreader.proofread(corrected)
        corrected = proof_result["corrected"]
        logger.info("Standalone Jais proofread applied")
        return corrected
    except Exception as e:
        logger.error(f"Standalone proofread error: {e}")
        return f"❌ خطأ في التدقيق بالذكاء الاصطناعي: {e!s}"
