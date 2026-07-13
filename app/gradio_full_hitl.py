# app/gradio_full_hitl.py
"""
Full Omni Medical OCR — Gradio HITL Interface.

Pipeline: Upload Image → Preprocess → OCR Ensemble → LLM Proofread → NER → Save

Features:
  - Complete OCR processing pipeline
  - LLM proofreading (Jais) — enabled via ENABLE_LLM=true env var (requires GPU)
  - NER entity extraction
  - Save corrections to HuggingFace Dataset
  - Update Medical Dictionary from accumulated corrections
  - Retrain Jais NER (requires GPU)

Environment Variables:
  ENABLE_LLM=true       Enable Jais proofreader + NER (requires GPU)
  HF_TOKEN=hf_xxx       HuggingFace token for dataset upload
"""
import hashlib
import json
import logging
import os
import re
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path

import cv2
import gradio as gr
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
ENABLE_LLM = os.getenv("ENABLE_LLM", "false").lower() == "true"
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_DATASET = "DrAbdulmalek/arabic-medical-ocr-corrections"

# ── Conditional Imports ─────────────────────────────────────────────────────
HAS_LLM = False
HAS_HF = False

# LLM
if ENABLE_LLM:
    try:
        from src.llm.proofreader import MedicalProofreader
        from src.ner.jais_ner import JaisNER
        HAS_LLM = True
        logger.info("Jais LLM modules loaded (GPU required)")
    except ImportError as e:
        logger.warning(f"LLM modules not available: {e}")

# HuggingFace
try:
    import pandas as pd
    from datasets import Dataset, load_dataset
    HAS_HF = True
except ImportError:
    logger.warning("HuggingFace libs not available — save disabled")

# ── Initialize OCR Engines ──────────────────────────────────────────────────
logger.info("Initializing OCR engines...")

# ImagePreprocessor (حقيقي — 582 سطر في packages/vision/)
image_preprocessor = None
HAS_PREPROCESSOR = False
try:
    from packages.vision.image_preprocessor import ImagePreprocessor
    image_preprocessor = ImagePreprocessor(
        apply_clahe=True, apply_denoise=True,
        apply_deskew=True, deskew_angle_threshold=5.0,
        apply_binarize=True,
    )
    HAS_PREPROCESSOR = True
    logger.info("ImagePreprocessor loaded (CLAHE+denoise+deskew+binarize)")
except Exception as e:
    logger.warning(f"ImagePreprocessor not available, will use fallback: {e}")

# PaddleOCR (primary — best Arabic support)
paddle_ocr = None
try:
    from paddleocr import PaddleOCR
    paddle_ocr = PaddleOCR(
        use_angle_cls=True, lang="ar", show_log=False,
        use_gpu=False, det_db_thresh=0.3, det_db_box_thresh=0.5,
        det_db_unclip_ratio=1.6, max_text_length=800, use_mp=True,
    )
    logger.info("PaddleOCR initialized successfully")
except Exception as e:
    logger.error(f"PaddleOCR init failed: {e}")

# Tesseract (secondary — يعمل دائماً كضمان أساسي)
HAS_TESSERACT = False
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    HAS_TESSERACT = True
    logger.info("Tesseract initialized successfully")
except Exception as e:
    logger.warning(f"Tesseract not available: {e}")

# Spell Checker (وحدة مُختبرة موجودة مسبقاً — v7.1)
spell_checker = None
try:
    from packages.core.spell_checker import HybridSpellChecker
    spell_checker = HybridSpellChecker()
    logger.info("HybridSpellChecker v7.1 loaded")
except Exception as e:
    logger.warning(f"Spell checker not available: {e}")

# Medical dictionary for NER
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

# OCR common misrecognition corrections
OCR_CORRECTIONS = {
    "باراسيتبمول": "باراسيتامول", "ايبوروفين": "ايبوبروفين",
    "اموكسيستلين": "اموكسيسيلين", "اموكسيسلين": "اموكسيسيلين",
    "ازيثروميسين": "ازيثرومايسين", "ميتروندازول": "ميترونيدازول",
    "ديكلوفيناك ": "ديكلوفيناك", "اوجمينتين": "اوجمنتين",
    "اوميبرازول ": "اوميبرازول", "سيليبريكس ": "سيليبريكس",
    "ترامادول ": "ترامادول", "كاتافلام ": "كاتافلام",
    "نوفافين ": "نوفافين", "فلاميكس ": "فلاميكس",
    "بنادول ": "بنادول", "ادفيل ": "ادفيل",
}

# ── Initialize Heavy Models (lazy) ──────────────────────────────────────────
proofreader = None
ner = None

if HAS_LLM:
    try:
        proofreader = MedicalProofreader()
        ner = JaisNER()
        logger.info("Jais models loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Jais models: {e}")


# ── Processing Functions ────────────────────────────────────────────────────

def _preprocess_image(image: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """
    Preprocess image using ImagePreprocessor (حقيقي — 582 سطر) if available,
    otherwise fallback to basic CLAHE+Otsu. Returns (processed, steps_log).
    """
    steps = []
    cleaned = None

    # المُعالج الحقيقي (CLAHE + denoise + deskew 5°+ + binarize)
    if HAS_PREPROCESSOR and image_preprocessor is not None:
        try:
            cleaned = image_preprocessor.preprocess(image, return_numpy=True)
            if cleaned.ndim == 2:  # رمادي → RGB للعرض في Gradio
                cleaned = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2RGB)
            steps.append("ImagePreprocessor (CLAHE+denoise+deskew+binarize)")
        except Exception as e:
            logger.warning(f"ImagePreprocessor failed, falling back: {e}")
            cleaned = None

    # Fallback: CLAHE + Otsu بسيطة
    if cleaned is None:
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            cleaned = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
            steps.append("Fallback CLAHE+Otsu")
        except Exception as e:
            logger.debug(f"Basic preprocessing fallback failed: {e}")
            cleaned = image
            steps.append("No preprocessing")

    return cleaned, steps


def _run_paddle_ocr(image: np.ndarray) -> tuple[str, list[dict]]:
    """Run PaddleOCR. Returns (full_text, line_details)."""
    if paddle_ocr is None:
        return "", []
    try:
        img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        result = paddle_ocr.ocr(img_bgr, cls=True)
        lines, details = [], []
        if result and result[0]:
            for idx, line in enumerate(result[0]):
                text = line[1][0].strip()
                conf = line[1][1]
                if text:
                    lines.append(text)
                    details.append({"line": idx+1, "text": text,
                                   "confidence": round(float(conf), 4)})
        return "\n".join(lines), details
    except Exception as e:
        logger.error(f"PaddleOCR error: {e}")
        return "", []


def _run_tesseract(image: np.ndarray) -> tuple[str, float]:
    """Run Tesseract. Returns (text, avg_confidence)."""
    if not HAS_TESSERACT:
        return "", 0.0
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        text = pytesseract.image_to_string(gray, lang="ara+eng", config="--psm 6")
        try:
            data = pytesseract.image_to_data(gray, lang="ara+eng", output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data["conf"] if int(c) > 0]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
        except Exception:
            avg_conf = 0.0
        return text.strip(), round(avg_conf, 2)
    except Exception as e:
        logger.error(f"Tesseract error: {e}")
        return "", 0.0


def _auto_correct_ocr(text: str) -> tuple[str, list[dict]]:
    """Apply OCR corrections + spell checker. Returns (corrected, changes)."""
    changes = []
    corrected = text
    for wrong, right in OCR_CORRECTIONS.items():
        if wrong in corrected:
            count = corrected.count(wrong)
            corrected = corrected.replace(wrong, right)
            changes.append({"type": "ocr_fix", "from": wrong, "to": right, "count": count})
    # Normalize whitespace
    corrected = re.sub(r'[ \t]+', ' ', corrected)
    corrected = re.sub(r'\n{3,}', '\n\n', corrected).strip()
    return corrected, changes


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


# ====================================================================
# منقول من OmniFile_Processor/hf_app.py (اندماج مؤكَّد الجودة — 6 يوليو 2026)
# ملاحظة: correct_text()/pyspellchecker الخاصة بـhf_app.py لم تُنقَل عمداً —
# اختبار فعلي أظهر أنها تُفسد أرقام الجرعات ("5OO"→"TOO")، بينما
# HybridSpellChecker أعلاه يحمي منها عبر _try_digit_fix(). لا داعي لمصحّح
# ثانٍ أضعف بجانب الأقوى.
# ====================================================================

_translation_corrector = None
_model_cache: dict[str, object] = {}

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


def _get_translation_corrector():
    """Lazy-load the translation corrector with rules."""
    global _translation_corrector
    if _translation_corrector is not None:
        return _translation_corrector
    try:
        # app/ -> جذر المستودع (كان المسار الأصلي في hf_app.py يشير خطأً
        # لـ app/data/ بدل data/ بعد نقل الملف من جذر OmniFile_Processor)
        base = Path(__file__).parent.parent
        rules_path = base / "data" / "translation_rules.json"
        if not rules_path.is_file():
            rules_path = None
        from packages.nlp.translation_corrector import ArabicTranslationProcessor
        _translation_corrector = ArabicTranslationProcessor(rules_file=str(rules_path) if rules_path else None)
        logger.info("Translation corrector loaded (%d rules)", len(_translation_corrector.rules))
    except ImportError:
        logger.warning("translation_corrector module not found — using inline fallback")
        _translation_corrector = None
    return _translation_corrector


def _correct_translation(english_text: str, arabic_text: str, enable: bool = True) -> str:
    """Apply post-MT correction to Arabic translation."""
    if not enable or not arabic_text:
        return arabic_text
    corrector = _get_translation_corrector()
    if corrector is None:
        return arabic_text
    result = corrector.process_translation(english_text, arabic_text)
    if result["improved"]:
        logger.info("Translation corrected: %d rule changes + %d regex changes",
                     len(result["corrections"]), len(result["regex_changes"]))
    return result["corrected"]


def _get_model(key: str):
    return _model_cache.get(key)


def _set_model(key: str, obj) -> None:
    _model_cache[key] = obj


def _load_translator(model_name: str):
    cache_key = f"translator_{model_name}"
    cached = _get_model(cache_key)
    if cached:
        return cached
    try:
        from transformers import MarianMTModel, MarianTokenizer
        tok = MarianTokenizer.from_pretrained(model_name)
        mdl = MarianMTModel.from_pretrained(model_name).to(DEVICE)
        _set_model(cache_key, (tok, mdl))
        return tok, mdl
    except Exception as e:
        logger.error("Failed to load translator %s: %s", model_name, e)
        return None, None


def translate_text(text: str, direction: str, correct_output: bool = True, progress=gr.Progress()) -> str:
    """ترجمة النصوص بين العربية والإنجليزية والألمانية مع تصحيح اختياري."""
    if not text or not text.strip():
        return "⚠️ الرجاء إدخال نص للترجمة."

    model_name = TRANSLATION_MODELS.get(direction)
    if not model_name:
        return f"❌ اتجاه غير مدعوم: {direction}"

    progress(0.2, desc=f"تحميل النموذج ({direction})…")
    tok, mdl = _load_translator(model_name)
    if tok is None or mdl is None:
        return "❌ فشل تحميل النموذج. راجع السجل."

    try:
        import torch
        chunks: list[str] = []
        cur = ""
        for para in re.split(r"\n\s*\n", text.strip()):
            if len(cur) + len(para) + 2 <= 400:
                cur += ("\n\n" if cur else "") + para
            else:
                if cur:
                    chunks.append(cur)
                cur = para
        if cur:
            chunks.append(cur)

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
            corrected = _correct_translation(text, translated)
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


def _normalize_text_metrics(text: str) -> str:
    """تطبيع بسيط للمقارنة (تشكيل + همزات فقط، بلا تحيّز ة/ه)."""
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)  # إزالة التشكيل
    text = re.sub(r'[إأآا]', 'ا', text)
    return text.strip()


def _levenshtein(s1, s2) -> int:
    m, n = len(s1), len(s2)
    if m == 0:
        return n
    if n == 0:
        return m
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def calculate_metrics(reference: str, hypothesis: str) -> str:
    """حساب CER/WER بين نص مرجعي ونص فعلي — مُختبَرة (مطابقة لـjiwer)."""
    if not reference or not hypothesis:
        return "⚠️ الرجاء إدخال النصين المرجعي والفعلي."

    ref = _normalize_text_metrics(reference)
    hyp = _normalize_text_metrics(hypothesis)
    ref_w = ref.split()
    hyp_w = hyp.split()

    cer_val = _levenshtein(ref, hyp) / max(len(ref), 1)
    wer_val = _levenshtein(ref_w, hyp_w) / max(len(ref_w), 1)

    if cer_val < 0.05:
        grade = "A (ممتاز) ✅"
    elif cer_val < 0.15:
        grade = "B (جيد) 🟢"
    elif cer_val < 0.30:
        grade = "C (متوسط) 🟡"
    else:
        grade = "D (ضعيف) ❌"

    out = "## 📊 نتائج تقييم OCR\n\n"
    out += "| المقياس | القيمة |\n|---|---|\n"
    out += f"| **CER** (معدل خطأ الأحرف) | **{cer_val:.2%}** |\n"
    out += f"| **WER** (معدل خطأ الكلمات) | **{wer_val:.2%}** |\n"
    out += f"| **دقة الأحرف** | **{(1 - cer_val) * 100:.1f}%** |\n"
    out += f"| **التقييم** | **{grade}** |\n\n"
    out += "| تفصيل | القيمة |\n|---|---|\n"
    out += f"| أحرف مرجعية | {len(ref)} |\n"
    out += f"| كلمات مرجعية | {len(ref_w)} |\n"
    out += f"| مسافة تحرير الأحرف | {_levenshtein(ref, hyp)} |\n"
    out += f"| مسافة تحرير الكلمات | {_levenshtein(ref_w, hyp_w)} |\n"

    try:
        import jiwer
        out += "\n### تحقق مستقل عبر jiwer\n"
        out += "| المقياس | القيمة |\n|---|---|\n"
        out += f"| CER | {jiwer.cer(reference, hypothesis):.2%} |\n"
        out += f"| WER | {jiwer.wer(reference, hypothesis):.2%} |\n"
    except ImportError:
        out += "\n> ℹ️ ثبّت `jiwer` للتحقق المستقل."
    except Exception:
        pass

    return out


def full_process(image):
    """
    Complete processing pipeline:
    Image → Preprocess → OCR Ensemble → Spell Check → LLM Proofread → NER
    """
    if image is None:
        return None, "لم يتم رفع صورة", "", {}, "يرجى رفع صورة طبية"

    t0 = time.time()
    try:
        # 1. Preprocessing
        cleaned, prep_steps = _preprocess_image(image)

        # 2. OCR — run all available engines
        paddle_text, paddle_details = _run_paddle_ocr(cleaned)
        tesseract_text, tess_conf = _run_tesseract(cleaned)

        # 3. Ensemble: PaddleOCR primary, Tesseract supplement
        raw_text = paddle_text if (paddle_text and len(paddle_text.strip()) > 5) else tesseract_text
        if not raw_text.strip():
            raw_text = paddle_text or tesseract_text or "[لم يتم اكتشاف نص]"

        engine_info = {}
        if paddle_text:
            engine_info["PaddleOCR"] = f"{len(paddle_details)} سطر"
        if tesseract_text:
            engine_info["Tesseract"] = f"ثقة {tess_conf:.0f}%"

        # 4. Auto-correct OCR artifacts
        corrected, corrections = _auto_correct_ocr(raw_text)

        # 4.5 Spell check (HybridSpellChecker — existing v7.0)
        spell_info = ""
        if spell_checker:
            try:
                before_spell = corrected
                corrected = spell_checker.correct_text(corrected)
                if before_spell != corrected:
                    spell_info = f"SpellChecker: {sum(1 for a,b in zip(before_spell, corrected, strict=False) if a!=b)} تعديل"
            except Exception as e:
                logger.warning(f"Spell check failed: {e}")

        # 5. LLM Proofreading (optional, GPU required)
        if proofreader:
            try:
                proof_result = proofreader.proofread(corrected)
                corrected = proof_result["corrected"]
                logger.info("Proofread applied")
            except Exception as e:
                logger.warning(f"Proofreading failed: {e}")

        # 6. NER
        entities = {}
        if ner:
            try:
                entities = ner.extract_entities(corrected)
            except Exception as e:
                logger.warning(f"LLM NER failed: {e}")
        # Fallback: dictionary-based NER
        if not entities:
            entities = _extract_ner(corrected)

        # Build status
        elapsed = time.time() - t0
        parts = [f"✅ معالجة مسبقة: {' + '.join(prep_steps)}"]

        if not HAS_TESSERACT and paddle_ocr is None:
            parts.append("❌ لا يوجد محرك OCR مثبت — ثبّت pytesseract أو paddleocr")
        elif not raw_text.strip():
            parts.append("⚠️ لم يُستخرَج أي نص (تحقق من جودة الصورة)")

        parts.extend(f"✅ {k}: {v}" for k, v in engine_info.items())
        parts.append(f"✅ تصحيح OCR: {len(corrections)} تعديل")
        if spell_info:
            parts.append(f"✅ {spell_info}")
        parts.append(f"✅ كيانات: {sum(len(v) for v in entities.values())}")
        parts.append(f"⏱️ {elapsed:.1f} ثانية")

        if not HAS_LLM:
            parts.append("(وضع أساسي — LLM غير مفعّل)")

        return cleaned, corrected, raw_text, entities, "\n".join(parts)

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        return None, f"خطأ: {e!s}", "", {}, f"حدث خطأ: {e!s}"


def jais_proofread_only(text: str) -> str:
    """Standalone Jais LLM proofreading on raw OCR text."""
    if not HAS_LLM or proofreader is None:
        return ("⚠️ يتطلب تفعيل ENABLE_LLM=true و GPU\n\n"
                "لا يمكن تشغيل تدقيق Jais بدون وحدة معالجة الرسومات (GPU) "
                "وتفعيل متغير البيئة ENABLE_LLM=true.")

    if not text or not text.strip():
        return "⚠️ لا يوجد نص للتدقيق. الرجاء تشغيل المعالجة الكاملة أولاً."

    try:
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


def copy_to_clipboard(text: str) -> str:
    """Return text for Gradio clipboard copy via browser."""
    return text


def save_to_hf(corrected_text: str, original_text: str, entities, category: str) -> str:
    """Save correction pair to HuggingFace Dataset."""
    if not HAS_HF:
        return "❌ مكتبات HuggingFace غير متاحة"

    if not corrected_text or not corrected_text.strip():
        return "⚠️ لا يوجد نص مصحح للحفظ. الرجاء معالجة صورة أولاً."

    try:
        previous_count = 0
        try:
            existing = load_dataset(HF_DATASET, split="train")
            previous_count = len(existing)
        except Exception:
            pass

        # Image hash for deduplication hint
        content_hash = hashlib.md5(
            (str(original_text or "") + str(corrected_text)).encode()
        ).hexdigest()[:12]

        row = {
            "incorrect_ocr_output": str(original_text or ""),
            "correct_text": str(corrected_text),
            "category": str(category),
            "entities": json.dumps(entities, ensure_ascii=False) if isinstance(entities, dict) else str(entities),
            "timestamp": datetime.now().isoformat(),
            "content_hash": content_hash,
        }

        new_row = pd.DataFrame([row])

        # Load existing and append
        try:
            existing = load_dataset(HF_DATASET, split="train").to_pandas()
            df = pd.concat([existing, new_row], ignore_index=True)
        except Exception:
            df = new_row

        # Upload
        new_ds = Dataset.from_pandas(df)
        push_kwargs = {"repo_id": HF_DATASET, "private": False}
        if HF_TOKEN:
            push_kwargs["token"] = HF_TOKEN
        new_ds.push_to_hub(**push_kwargs)

        total = len(df)
        logger.info("Saved to HF: total %d samples (hash=%s)", total, content_hash)
        return (
            f"✅ تم الحفظ بنجاح!\n\n"
            f"📊 التفاصيل:\n"
            f"  • العينات السابقة: {previous_count}\n"
            f"  • الإجمالي بعد الحفظ: {total}\n"
            f"  • بصمة المحتوى: {content_hash}\n"
            f"  • النوع: {category}\n"
            f"  • الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    except Exception as e:
        logger.error(f"Save error: {e}")
        return f"❌ خطأ في الحفظ: {e!s}"


def update_medical_dictionary():
    """Generator: auto-expand medical dictionary from accumulated corrections."""
    try:
        yield "جاري تحليل التصحيحات من HF Dataset..."
        from src.ocr.build_medical_dict import build_and_expand_dict
        medical_dict = build_and_expand_dict(min_freq=2)
        yield f"تم تحديث القاموس الطبي!\nعدد المصطلحات: {len(medical_dict)}"
        examples = list(medical_dict.keys())[:10]
        yield f"تم التحديث بنجاح!\nالمصطلحات ({len(medical_dict)}):\n" + "\n".join(f"  - {e}" for e in examples)
    except Exception as e:
        logger.error(f"Dict update error: {e}")
        yield f"خطأ في تحديث القاموس: {e!s}"


def retrain_now():
    """Generator: regenerate Jais NER dataset and start fine-tuning."""
    try:
        yield "المرحلة 1/2: جاري إنشاء dataset للتدريب..."

        # 1. Generate prompt dataset
        try:
            from scripts.create_jais_prompt_dataset import generate_jais_dataset
            ds = generate_jais_dataset(output_dir="jais_ner_data")
            yield f"تم إنشاء {len(ds)} عينة\n\nالمرحلة 2/2: جاري التدريب..."
        except Exception as e:
            yield f"خطأ في إنشاء Dataset: {e}"
            return

        # 2. Fine-tuning (subprocess — non-blocking would need Celery in production)
        try:
            result = subprocess.run(
                ["python", "src/ner/fine_tune_jais_ner.py", "--epochs", "2"],
                capture_output=True, text=True, timeout=1800,
            )
            if result.returncode == 0:
                last_lines = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
                yield f"اكتمل التدريب بنجاح!\n\n{last_lines}"
            else:
                yield f"فشل التدريب (code {result.returncode}):\n{result.stderr[-500:]}"
        except subprocess.TimeoutExpired:
            yield "انتهت مهلة التدريب (30 دقيقة)"
        except Exception as e:
            yield f"خطأ في التدريب: {e}"

    except Exception as e:
        logger.error(f"Retrain error: {e}")
        yield f"خطأ: {e!s}"


# ── Gradio UI ───────────────────────────────────────────────────────────────

# RTL CSS for Arabic + UI
custom_css = """
.gradio-container { direction: rtl; }
footer { display: none !important; }
.jais-banner { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 16px; border-radius: 12px; margin: 8px 0; }
.jais-banner h3 { color: #e2e8f0; margin: 0 0 8px 0; }
.jais-banner p { color: #94a3b8; margin: 0; font-size: 14px; }
.before-after-row { display: flex; gap: 16px; }
.before-after-row > div { flex: 1; }
.comparison-label { font-weight: bold; padding: 4px 8px; border-radius: 4px; display: inline-block; margin-bottom: 4px; }
.label-before { background: #fee2e2; color: #991b1b; }
.label-after { background: #dcfce7; color: #166534; }
"""

with gr.Blocks(
    title="Omni Medical OCR",
    theme=gr.themes.Soft(),
    css=custom_css,
) as demo:

    gr.Markdown(
        "# Omni Medical OCR\n"
        "**نظام متكامل لاستخراج وتصحيح النصوص الطبية العربية**\n\n"
        "Upload → Preprocess → OCR → LLM Proofread → NER → Save"
    )

    # ── Main Processing ─────────────────────────────────────────────────
    with gr.Row():
        input_image = gr.Image(type="numpy", label="رفع صورة طبية")
        process_btn = gr.Button("معالجة كاملة", variant="primary", size="lg")

    with gr.Row():
        with gr.Column(scale=1):
            cleaned_img = gr.Image(label="الصورة بعد التنظيف")
        with gr.Column(scale=2):
            raw_ocr = gr.Textbox(label="النص الخام من OCR", lines=4)
            corrected = gr.Textbox(label="النص بعد التدقيق (LLM)", lines=4)

    with gr.Row():
        copy_btn = gr.Button("📋 نسخ النص المصحح")
        copy_status = gr.Textbox(label="", interactive=False, max_lines=1)

    entities_output = gr.JSON(label="الكيانات المستخرجة (NER)")

    # ── Jais Proofread Section (prominent) ─────────────────────────────
    with gr.Group(visible=True):
        gr.Markdown(
            "### 🧠 Proofread with Jais LLM\n"
            "استخدم نموذج Jais اللغوي لتصحيح أخطاء OCR تلقائياً. "
            "يتطلب **GPU** و **ENABLE_LLM=true**."
        )
        with gr.Row():
            jais_input = gr.Textbox(
                label="أدخل النص للتدقيق (أو استخدم النص الخام من OCR أعلاه)",
                lines=4,
                placeholder="الصق النص هنا أو شغّل المعالجة الكاملة أولاً...",
            )
            jais_output = gr.Textbox(
                label="النص بعد تدقيق Jais ✨",
                lines=4,
                interactive=False,
            )
        with gr.Row():
            jais_btn = gr.Button(
                "🧠 Proofread with Jais — تدقيق بالذكاء الاصطناعي",
                variant="primary",
                size="lg",
            )
            jais_copy_btn = gr.Button("📋 نسخ النتيجة")
        jais_status = gr.Markdown()

    # ── Before / After Comparison ────────────────────────────────────────
    with gr.Accordion("🔍 Before / After Comparison — مقارنة قبل وبعد", open=False):
        gr.Markdown("قارن النص الخام مع النص المصحح لتقييم جودة التصحيح")
        with gr.Row():
            with gr.Column():
                gr.Markdown('<span class="comparison-label label-before">BEFORE — قبل التصحيح</span>')
                before_text = gr.Textbox(
                    label="النص الخام",
                    lines=6,
                    interactive=False,
                )
            with gr.Column():
                gr.Markdown('<span class="comparison-label label-after">AFTER — بعد التصحيح</span>')
                after_text = gr.Textbox(
                    label="النص المصحح",
                    lines=6,
                    interactive=False,
                )
        compare_btn = gr.Button("🔄 مقارنة (ملء من نتائج المعالجة)", variant="secondary")
        compare_output = gr.Markdown()

    # ── Save ────────────────────────────────────────────────────────────
    with gr.Row():
        category = gr.Dropdown(
            choices=["prescription", "report", "handwriting", "lab_result", "other"],
            value="prescription",
            label="نوع الوثيقة",
        )
        save_btn = gr.Button("💾 حفظ التصحيح في HF Dataset", variant="secondary")

    status = gr.Textbox(label="الحالة", interactive=False)

    # ── Advanced Actions ────────────────────────────────────────────────
    with gr.Accordion("أدوات متقدمة", open=False), gr.Row():
        with gr.Column():
            retrain_btn = gr.Button("إعادة تدريب Jais NER", variant="stop")
            retrain_status = gr.Textbox(label="حالة التدريب", lines=8, interactive=False)

        with gr.Column():
            dict_btn = gr.Button("تحديث القاموس الطبي", variant="primary")
            dict_status = gr.Textbox(label="حالة القاموس", lines=8, interactive=False)

    # ── الترجمة ────────────────────────────────────────────────────────
    with gr.Accordion("🌐 ترجمة النصوص", open=False), gr.Row():
        with gr.Column():
            translate_input = gr.Textbox(label="النص المصدر", lines=6)
            translate_direction = gr.Dropdown(
                choices=list(TRANSLATION_MODELS.keys()),
                value="Arabic → English",
                label="اتجاه الترجمة",
            )
            translate_correct = gr.Checkbox(value=True, label="تصحيح ما بعد الترجمة (للعربية)")
            translate_btn = gr.Button("ترجم", variant="primary")
        with gr.Column():
            translate_output = gr.Textbox(label="النص المترجَم", lines=8, interactive=False)

    # ── حاسبة CER/WER ─────────────────────────────────────────────────
    with gr.Accordion("📊 حاسبة دقة OCR (CER/WER)", open=False), gr.Row():
        with gr.Column():
            metrics_ref = gr.Textbox(label="النص المرجعي (الصحيح)", lines=4)
            metrics_hyp = gr.Textbox(label="نص OCR الفعلي", lines=4)
            metrics_btn = gr.Button("احسب المقاييس", variant="primary")
        with gr.Column():
            metrics_output = gr.Markdown()

    # ── Events ──────────────────────────────────────────────────────────
    process_btn.click(
        fn=full_process,
        inputs=[input_image],
        outputs=[cleaned_img, corrected, raw_ocr, entities_output, status],
    )

    save_btn.click(
        fn=save_to_hf,
        inputs=[corrected, raw_ocr, entities_output, category],
        outputs=[status],
    )

    copy_btn.click(
        fn=copy_to_clipboard,
        inputs=[corrected],
        outputs=[copy_status],
    )

    jais_btn.click(
        fn=jais_proofread_only,
        inputs=[jais_input],
        outputs=[jais_output],
    )

    jais_copy_btn.click(
        fn=copy_to_clipboard,
        inputs=[jais_output],
        outputs=[jais_status],
    )

    def _fill_comparison(raw: str, corr: str) -> tuple[str, str, str]:
        """Fill before/after textboxes and generate diff summary."""
        before_text_out = raw or "(لا يوجد نص خام)"
        after_text_out = corr or "(لا يوجد نص مصحح)"
        summary = "### ملخص المقارنة\n"
        if raw and corr and raw != corr:
            from rapidfuzz import fuzz
            ratio = fuzz.ratio(raw, corr) / 100.0
            summary += f"- نسبة التطابق: **{ratio:.1%}**\\n"
            summary += f"- عدد الأحرف (قبل): {len(raw)} | (بعد): {len(corr)}\n"
        elif raw and corr and raw == corr:
            summary = "### ✅ النصان متطابقان — لا تغييرات"
        else:
            summary = "### ⚠️ شغّل المعالجة الكاملة أولاً لملء المقارنة"
        return before_text_out, after_text_out, summary

    compare_btn.click(
        fn=_fill_comparison,
        inputs=[raw_ocr, corrected],
        outputs=[before_text, after_text, compare_output],
    )

    dict_btn.click(
        fn=update_medical_dictionary,
        outputs=[dict_status],
    )

    retrain_btn.click(
        fn=retrain_now,
        outputs=[retrain_status],
    )

    translate_btn.click(
        fn=translate_text,
        inputs=[translate_input, translate_direction, translate_correct],
        outputs=[translate_output],
    )

    metrics_btn.click(
        fn=calculate_metrics,
        inputs=[metrics_ref, metrics_hyp],
        outputs=[metrics_output],
    )


if __name__ == "__main__":
    logger.info("Starting Omni Medical OCR Gradio on port 7860")
    demo.launch(server_name="0.0.0.0", server_port=7860)
