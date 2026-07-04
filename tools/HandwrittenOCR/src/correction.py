"""
HandwrittenOCR - محرك التصحيح الإملائي وقاموس التصحيح v4.0
===============================================================
المحسنات:
- correction_min_votes=1 (خُفض من 2)
- استخدام defaultdict(Counter) للعد الفعّال
- append_feedback() لتسجيل التصحيحات
- تصحيح SpellChecker كلمة بكلمة (تصحيح #2)
"""

import json
import os
import logging
import pandas as pd
from datetime import datetime
from collections import Counter, defaultdict
from spellchecker import SpellChecker
from langdetect import detect, DetectorFactory

logger = logging.getLogger("HandwrittenOCR")

DetectorFactory.seed = 0

_ar_corrector = None
_en_spellchecker = None


def init_correctors() -> None:
    """تهيئة المدققات الإملائية"""
    global _ar_corrector, _en_spellchecker

    try:
        from ar_corrector.corrector import Corrector
        _ar_corrector = Corrector()
        logger.info("تم تحميل المدقق الإملائي العربي")
    except ImportError:
        logger.warning("ar-corrector غير مثبت. التصحيح العربي لن يكون متاحاً.")

    _en_spellchecker = SpellChecker(language="en")
    logger.info("تم تحميل المدقق الإملائي الإنجليزي")


def correct_text(text: str) -> str:
    """تصحيح إملائي حسب اللغة المكتشفة"""
    if not text or not text.strip():
        return text

    text = text.strip()
    try:
        lang = detect(text)
        if lang == "ar":
            return _correct_arabic(text)
        elif lang == "en":
            return _correct_english(text)
    except Exception:
        pass
    return text


def _correct_arabic(text: str) -> str:
    if _ar_corrector is None:
        return text
    try:
        return _ar_corrector.contextual_correct(text)
    except Exception as e:
        logger.debug(f"خطأ في التصحيح العربي: {e}")
        return text


def _correct_english(text: str) -> str:
    """
    تصحيح الجمل الإنجليزية كلمة بكلمة مع حفظ الترقيم (تصحيح #2).
    SpellChecker.correction() يُستدعى كلمة بكلمة فقط.
    """
    if _en_spellchecker is None:
        return text
    try:
        words = text.split()
        corrected = []
        for word in words:
            clean = word.strip(".,;:!?\"'()-")
            if clean:
                fixed = _en_spellchecker.correction(clean)
                corrected_word = word.replace(clean, fixed) if fixed else word
                corrected.append(corrected_word)
            else:
                corrected.append(word)
        return " ".join(corrected)
    except Exception as e:
        logger.debug(f"خطأ في التصحيح الإنجليزي: {e}")
        return text


def spell_correct_word(text: str) -> str:
    """تصحيح سريع كلمة بكلمة — للمعالجة في الحلقات"""
    text = text.strip()
    if not text:
        return ""
    try:
        lang = detect(text)
        if lang == "ar" and _ar_corrector:
            return _ar_corrector.contextual_correct(text)
        words = text.split()
        return " ".join(
            _en_spellchecker.correction(w) or w for w in words
        )
    except Exception:
        return text


# ===================== قاموس التصحيح المستمر =====================

def build_correction_dict(
    feedback_csv: str,
    correction_dict_path: str,
    min_votes: int = 1,
) -> dict:
    """
    بناء قاموس تصحيح من تصحيحات المستخدم.
    يستخدم defaultdict(Counter) للعد الفعّال.
    """
    if not os.path.exists(feedback_csv):
        return {}

    try:
        df_fb = pd.read_csv(feedback_csv, encoding="utf-8-sig")
        if df_fb.empty:
            return {}

        buckets = defaultdict(Counter)
        for _, row in df_fb.iterrows():
            orig = str(row.get("original_text", "")).strip()
            corr = str(row.get("corrected_text", "")).strip()
            if orig and corr and orig != corr:
                buckets[orig][corr] += 1

        result = {
            orig: cnt.most_common(1)[0][0]
            for orig, cnt in buckets.items()
            if cnt.most_common(1)[0][1] >= min_votes
        }

        os.makedirs(os.path.dirname(correction_dict_path), exist_ok=True)
        with open(correction_dict_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"تم تحديث قاموس التصحيح: {len(result)} كلمة")
        return result

    except Exception as e:
        logger.error(f"خطأ في بناء القاموس: {e}")
        return {}


def load_correction_dict(correction_dict_path: str) -> dict:
    """تحميل قاموس التصحيح من الملف."""
    if not os.path.exists(correction_dict_path):
        return {}
    try:
        with open(correction_dict_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.debug(f"خطأ في تحميل القاموس: {e}")
        return {}


def apply_correction_dict(text: str, correction_dict: dict) -> str:
    """تطبيق قاموس التصحيح على نص."""
    if not correction_dict or not text:
        return text
    words = text.split()
    corrected = [correction_dict.get(w, w) for w in words]
    return " ".join(corrected)


def append_feedback(
    feedback_csv: str,
    image_id: int,
    original: str,
    corrected: str,
    status: str = "verified",
) -> None:
    """تسجيل تصحيح في ملف CSV."""
    os.makedirs(os.path.dirname(feedback_csv), exist_ok=True)
    ts = datetime.now().isoformat()
    record = {
        "timestamp": ts,
        "image_id": image_id,
        "original_text": original,
        "corrected_text": corrected,
        "status": status,
    }
    file_exists = os.path.exists(feedback_csv)
    pd.DataFrame([record]).to_csv(
        feedback_csv, mode="a",
        header=not file_exists,
        index=False, encoding="utf-8-sig",
    )
