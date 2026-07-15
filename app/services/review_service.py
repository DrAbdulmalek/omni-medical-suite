# app/services/review_service.py
"""Review Service — NER entity extraction, LLM proofreading, and correction logic.

Provides:
  - Dictionary-based NER via ``MEDICAL_TERMS`` and ``_extract_ner()``
  - Jais LLM proofreading via ``jais_proofread_only()`` (requires GPU)
  - Module-level ``proofreader`` and ``ner`` instances (loaded when
    ``ENABLE_LLM=true``)
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
ENABLE_LLM = os.getenv("ENABLE_LLM", "false").lower() == "true"

# ── Conditional LLM Imports ─────────────────────────────────────────────────
HAS_LLM = False
proofreader = None
ner = None

if ENABLE_LLM:
    try:
        from src.llm.proofreader import MedicalProofreader
        from src.ner.jais_ner import JaisNER
        HAS_LLM = True
        logger.info("Jais LLM modules loaded (GPU required)")
    except ImportError as e:
        logger.warning(f"LLM modules not available: {e}")

if HAS_LLM:
    try:
        proofreader = MedicalProofreader()
        ner = JaisNER()
        logger.info("Jais models loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Jais models: {e}")

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
    if not HAS_LLM or proofreader is None:
        return ("⚠️ يتطلب تفعيل ENABLE_LLM=true و GPU\n\n"
                "لا يمكن تشغيل تدقيق Jais بدون وحدة معالجة الرسومات (GPU) "
                "وتفعيل متغير البيئة ENABLE_LLM=true.")

    if not text or not text.strip():
        return "⚠️ لا يوجد نص للتدقيق. الرجاء تشغيل المعالجة الكاملة أولاً."

    try:
        # Lazy import to avoid hard dependency on ocr_service at module load
        from app.services.ocr_service import _auto_correct_ocr, spell_checker

        # Apply OCR corrections first, then spell check, then LLM proofread
        corrected, _corrections = _auto_correct_ocr(text)

        if spell_checker:
            try:
                corrected = spell_checker.correct_text(corrected)
            except Exception as e:
                logger.warning(f"Spell check failed in standalone proofread: {e}")

        proof_result = proofreader.proofread(corrected)
        corrected = proof_result["corrected"]
        logger.info("Standalone Jais proofread applied")
        return corrected
    except Exception as e:
        logger.error(f"Standalone proofread error: {e}")
        return f"❌ خطأ في التدقيق بالذكاء الاصطناعي: {e!s}"