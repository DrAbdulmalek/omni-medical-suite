# src/ocr/normalization.py
"""Arabic Text Normalization for Medical OCR."""
import re
import unicodedata
from pathlib import Path
import json

MEDICAL_DICT = {
    "التهاب": "التهاب", "لوزتين": "اللوزتين", "مغ": "ملغ", "سم": "سم",
    "ص": "صباحا", "م": "مساء", "قرص": "قرص", "حبة": "حبة",
    "كبسولة": "كبسولة", "شراب": "شراب", "حقن": "حقن", "تشخيص": "تشخيص",
}

def load_medical_dict(dict_path=None):
    global MEDICAL_DICT
    if dict_path and Path(dict_path).exists():
        with open(dict_path, encoding="utf-8") as f:
            MEDICAL_DICT.update(json.load(f))

def arabic_normalize(text: str) -> str:
    if not text: return ""
    text = unicodedata.normalize('NFC', text)
    text = re.compile(r'[\u0617-\u061A\u064B-\u0652]').sub('', text)
    text = re.sub(r'[إأٱآ]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[ـ]+', '', text)
    text = re.sub(r'[٠-٩]', lambda m: str(int(m.group(0), 10)), text)
    text = re.sub(r'[^\w\s\.\-\،\؛]', '', text)
    return text.strip()

def arabic_strong_normalize(text: str, use_medical_dict: bool = True) -> str:
    if not text: return ""
    text = unicodedata.normalize('NFC', text)
    text = re.compile(r'[\u0617-\u061A\u064B-\u0652]').sub('', text)
    text = re.sub(r'[إأٱآ]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'[ـ]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[٠-٩]', lambda m: str(int(m.group(0), 10)), text)
    if use_medical_dict:
        words = text.split()
        normalized_words = []
        for word in words:
            lower = word.lower()
            normalized_words.append(MEDICAL_DICT.get(lower, word))
        text = ' '.join(normalized_words)
    text = re.sub(r'[^\w\s\.\-\،\؛\؟]', '', text)
    return text.strip()

def normalize_batch(texts: list, use_medical_dict: bool = True) -> list:
    return [arabic_strong_normalize(t, use_medical_dict) for t in texts]