# src/ocr/normalization.py
"""
Advanced Arabic Text Normalization for Medical OCR.
Includes: Unicode NFC, diacritics removal, character unification,
Arabic digit conversion, medical dictionary mapping, and optional CAMeL Tools integration.
"""
import re
import unicodedata
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Medical Dictionary (mutable, loaded from JSON) ──────────────────────────
MEDICAL_DICT: dict[str, str] = {
    # Abbreviation expansions (common in prescriptions)
    "مغ": "ملغ",
    "سم": "سم",
    "ص": "صباحا",
    "م": "مساء",
    "Name": "الاسم",
    # Drug forms
    "قرص": "قرص",
    "حبة": "حبة",
    "كبسولة": "كبسولة",
    "شراب": "شراب",
    "حقن": "حقن",
    "مرهم": "مرهم",
    "قطرة": "قطرة",
    "بخاخ": "بخاخ",
    "محلول": "محلول",
    # Common medical terms
    "تشخيص": "تشخيص",
    "التهاب": "التهاب",
    "لوزتين": "اللوزتين",
    # Drug name corrections
    "اموكسيسيلين": "أموكسيسيلين",
    "ايبوبروفين": "إيبوبروفين",
    "باراسيتامول": "باراسيتامول",
    "اموكلاف": "أموكسيسيلين/كلافولانات",
}


def load_medical_dict(dict_path: Optional[str] = None) -> None:
    """Load additional medical dictionary from JSON file and merge into MEDICAL_DICT."""
    global MEDICAL_DICT
    if dict_path is None:
        dict_path = str(Path(__file__).parent.parent.parent / "medical_terms.json")
    p = Path(dict_path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                MEDICAL_DICT.update(loaded)
                logger.info(f"Loaded {len(loaded)} terms from {dict_path}")


# ── Core Normalization ──────────────────────────────────────────────────────

# Pre-compiled patterns for performance
_DIACRITICS_RE = re.compile(r'[\u0617-\u061A\u064B-\u0652]')
_ALEF_RE = re.compile(r'[إأٱآ]')
_TATWEEL_RE = re.compile(r'[ـ]+')
_WHITESPACE_RE = re.compile(r'\s+')
_ARABIC_DIGIT_RE = re.compile(r'[٠-٩]')
_CLEAN_RE = re.compile(r'[^\w\s\.\-\،\؛\؟\:\(\)]')


def arabic_normalize(text: str) -> str:
    """
    Basic Arabic normalization for medical OCR text.
    Steps: NFC → remove diacritics → unify alef/ya/teh → remove tatweel →
           normalize digits → clean special chars.
    """
    if not text:
        return ""
    # 1. Unicode NFC
    text = unicodedata.normalize('NFC', text)
    # 2. Remove diacritics (tashkeel)
    text = _DIACRITICS_RE.sub('', text)
    # 3. Unify hamza/alef variants
    text = _ALEF_RE.sub('ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    # 4. Clean spaces and tatweel
    text = _TATWEEL_RE.sub('', text)
    text = _WHITESPACE_RE.sub(' ', text).strip()
    # 5. Convert Arabic-Indic digits to Western
    text = _ARABIC_DIGIT_RE.sub(lambda m: str(int(m.group(0), 10)), text)
    # 6. Remove unwanted special characters (keep medical-relevant ones)
    text = re.sub(r'[^\w\s\.\-\،\؛]', '', text)
    return text.strip()


def arabic_strong_normalize(text: str, use_medical_dict: bool = True) -> str:
    """
    Advanced Arabic normalization with medical dictionary mapping.
    Includes all steps of arabic_normalize() plus optional medical term correction.

    Args:
        text: Input Arabic medical text (from OCR).
        use_medical_dict: If True, apply medical dictionary corrections.

    Returns:
        Normalized text with medical terms corrected.

    ⚠️ METRIC BIAS WARNING:
        This function converts ة → ه (line below), which is applied to BOTH
        the prediction AND the reference inside compute_metrics. While this
        is methodologically sound (apples-to-apples comparison), it HIDES
        real ة/ه OCR errors from CER/WER scores. In a medical context this
        matters: "صيدلية" (pharmacy) vs "صيدليه" changes grammatical role,
        and some clinical terms have distinct meanings with ة vs ه.

        To see true ة/h error rates, run a separate evaluation WITHOUT
        calling this function, or count ة/ه mismatches separately.
    """
    if not text:
        return ""
    # 1. Unicode NFC
    text = unicodedata.normalize('NFC', text)
    # 2. Remove diacritics
    text = _DIACRITICS_RE.sub('', text)
    # 3. Unify characters
    text = _ALEF_RE.sub('ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    text = _TATWEEL_RE.sub('', text)
    # 4. Clean spaces
    text = _WHITESPACE_RE.sub(' ', text).strip()
    # 5. Convert Arabic digits
    text = _ARABIC_DIGIT_RE.sub(lambda m: str(int(m.group(0), 10)), text)
    # 6. Medical Dictionary Mapping
    if use_medical_dict:
        words = text.split()
        normalized_words = []
        for word in words:
            lower = word.lower()
            if lower in MEDICAL_DICT:
                normalized_words.append(MEDICAL_DICT[lower])
            else:
                normalized_words.append(word)
        text = ' '.join(normalized_words)
    # 7. Final cleanup (keep more medical-relevant chars)
    text = _CLEAN_RE.sub('', text)
    return text.strip()


def normalize_batch(texts: list, use_medical_dict: bool = True) -> list:
    """Apply arabic_strong_normalize to a list of texts."""
    return [arabic_strong_normalize(t, use_medical_dict) for t in texts]


def full_arabic_normalize(text: str) -> str:
    """
    Full normalization pipeline combining CAMeL Tools (if available)
    with our custom medical normalization.

    Falls back to arabic_strong_normalize if CAMeL is not installed.
    """
    try:
        from camel_tools.utils.normalize import normalize_unicode
        text = normalize_unicode(text)
    except ImportError:
        logger.debug("CAMeL Tools not available, using basic NFC")
        text = unicodedata.normalize('NFC', text)
    return arabic_strong_normalize(text)


# ── Load medical dict on import ─────────────────────────────────────────────
try:
    load_medical_dict()
except Exception as e:
    logger.warning(f"Could not load medical_terms.json: {e}")


# ── CLI Test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_texts = [
        "الاسم: أحمد محمد - التشخيص: إلتهاب اللوزتين",
        "المريض يأخذ اموكسيسيلين 500مغ صباحا ومساء",
        "وصفة: ٢ قرص باراسيتامول ٥٠٠ ملغ",
    ]
    for t in test_texts:
        print(f"Original : {t}")
        print(f"Basic    : {arabic_normalize(t)}")
        print(f"Strong   : {arabic_strong_normalize(t)}")
        print(f"Full     : {full_arabic_normalize(t)}")
        print("---")