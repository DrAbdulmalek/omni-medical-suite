#!/usr/bin/env python3
"""
Handwriting OCR Trainer — Standalone HF Space (Enhanced)
==========================================================
Integrates modules from the Arabic Medical OCR Pipeline Blueprint:
  - RTL Fixer: detects and corrects reversed Arabic OCR output
  - Medical Field Extractor: regex-based extraction of patient_name, date, etc.
  - Image Preprocessing: deskew, contrast enhancement, denoising
  - Active Learning: low-confidence words flagged for priority review
  - Field-Aware Dedup: prevents saving duplicate corrections

Workflow: PDF -> preprocess -> pages -> word segmentation -> OCR -> RTL fix
         -> field extraction -> user correction -> DB + JSONL

Deploy: Push this directory to huggingface.co/spaces/DrAbdulmalek/handwriting-trainer
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import sqlite3
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import gradio as gr
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── Optional heavy imports (graceful fallback) ────────────────────────────
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# ── Data directory for SQLite + exports ──────────────────────────────────
DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "corrections.db"
EXPORT_PATH = DATA_DIR / "corrections.jsonl"

# ═══════════════════════════════════════════════════════════════════════
# 1. ARABIC RTL FIXER  (from src/ocr/rtl_utils.py — self-contained copy)
# ═══════════════════════════════════════════════════════════════════════

ARABIC_CHAR_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)
ARABIC_TOKEN_RE = re.compile(
    r"^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+$"
)
PRESENTATION_FORM_RE = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")
TOKEN_SPLIT_RE = re.compile(r"\s+")

# Minimal Arabic normalization map (presentation forms → canonical)
_AR_NORM = {
    # Lam-Alef forms
    "\uFEFB": "\u0644\u0627", "\uFEFC": "\u0644\u0627",
    "\uFEF7": "\u0644\u0627", "\uFEF8": "\u0644\u0627",
    "\uFEF5": "\u0644\u0627", "\uFEF6": "\u0644\u0627",
}

COMMON_ARABIC_HINTS = (
    "\u0627\u0644",  # ال
    "\u0627\u0633\u0645",  # اسم
    "\u0627\u0644\u0645",  # الم
    "\u0645\u0631\u064a\u0636",  # مريض
    "\u062a\u0627\u0631\u064a\u062e",  # تاريخ
    "\u0639\u0628\u062f",  # عبد
    "\u0628\u0646",  # بن
)


class ArabicRTLFixer:
    """Fix reversed Arabic OCR output while leaving non-Arabic tokens intact.

    Adapted from ``src/ocr.rtl_utils.ArabicRTLFixer`` in omni-medical-suite.
    Uses heuristic reversal-ratio detection to decide whether to flip Arabic
    tokens and reorder them right-to-left within each line.
    """

    def __init__(self, reversal_threshold: float = 0.30) -> None:
        self.reversal_threshold = reversal_threshold

    # ── public API ──────────────────────────────────────────────────────

    @staticmethod
    def contains_arabic(text: str) -> bool:
        return bool(text and ARABIC_CHAR_RE.search(text))

    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""
        nfk = unicodedata.normalize("NFKC", text)
        return "".join(_AR_NORM.get(ch, ch) for ch in nfk)

    def should_fix(self, text: str) -> bool:
        if not self.contains_arabic(text):
            return False
        normalized = self.normalize(text)
        if PRESENTATION_FORM_RE.search(text):
            return True
        return self._reversal_ratio(normalized) >= self.reversal_threshold

    def fix(self, text: str, *, force: bool = False) -> str:
        """Return RTL-fixed text (or original if no fix needed)."""
        if not text:
            return ""
        normalized = self.normalize(text)
        if not force and not self.should_fix(normalized):
            return normalized
        lines = [self._fix_line(line) for line in normalized.splitlines()]
        return "\n".join(lines).strip()

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _arabic_tokens(text: str) -> list[str]:
        return [
            t for t in TOKEN_SPLIT_RE.split(text.strip())
            if ARABIC_TOKEN_RE.match(t)
        ]

    @staticmethod
    def _hint_score(token: str) -> int:
        score = 0
        if token.startswith("\u0627\u0644"):  # ال
            score += 2
        for hint in COMMON_ARABIC_HINTS:
            if hint in token:
                score += 1
        return score

    def _reversal_ratio(self, text: str) -> float:
        tokens = self._arabic_tokens(text)
        long_tokens = [t for t in tokens if len(t) >= 3]
        if not long_tokens:
            return 0.0
        votes = sum(
            1 for t in long_tokens
            if self._hint_score(t[::-1]) > self._hint_score(t)
        )
        return votes / len(long_tokens)

    def _fix_line(self, line: str) -> str:
        tokens = [t for t in TOKEN_SPLIT_RE.split(line.strip()) if t]
        if not tokens:
            return ""
        normalized = [self.normalize(t) for t in tokens]
        converted = [
            t[::-1] if ARABIC_TOKEN_RE.match(t) else t
            for t in normalized
        ]
        arabic_pos = [
            i for i, t in enumerate(normalized) if ARABIC_TOKEN_RE.match(t)
        ]
        if len(arabic_pos) > 1:
            reversed_ar = [converted[i] for i in arabic_pos][::-1]
            for idx, new_tok in zip(arabic_pos, reversed_ar):
                converted[idx] = new_tok
        return " ".join(converted)


_rtl_fixer = ArabicRTLFixer()

# ═══════════════════════════════════════════════════════════════════════
# 2. MEDICAL FIELD EXTRACTOR  (from src/ocr/field_extractor.py)
# ═══════════════════════════════════════════════════════════════════════

MEDICAL_FIELD_PATTERNS = {
    "patient_name": [
        re.compile(
            r"(?:\u0627\u0633\u0645\s*\u0627\u0644\u0645\u0631\u064a\u0636"
            r"|\u0627\u0644\u0645\u0631\u064a\u0636"
            r"|Patient\s*Name)\s*[:：\-]?\s*(.+)",
            re.IGNORECASE,
        ),
    ],
    "patient_id": [
        re.compile(
            r"(?:\u0631\u0642\u0645\s*(?:\u0627\u0644\u0645\u0644\u0641"
            r"|\u0627\u0644\u0645\u0631\u064a\u0636|\u0627\u0644\u0647\u0648\u064a\u0629)"
            r"|Patient\s*ID|MRN|ID)\s*[:：\-]?\s*([A-Z0-9\-/]{3,})",
            re.IGNORECASE,
        ),
    ],
    "date": [
        re.compile(
            r"(?:\u0627\u0644\u062a\u0627\u0631\u064a\u062e"
            r"|\u062a\u0627\u0631\u064a\u062e\s*\u0627\u0644\u0632\u064a\u0627\u0631\u0629"
            r"|Date)\s*[:：\-]?\s*([0-9\u0660-\u0669\-/]{6,})",
            re.IGNORECASE,
        ),
    ],
    "doctor_name": [
        re.compile(
            r"(?:\u0627\u0633\u0645\s*\u0627\u0644\u0637\u0628\u064a\u0628"
            r"|\u0627\u0644\u0637\u0628\u064a\u0628"
            r"|Doctor)\s*[:：\-]?\s*(.+)",
            re.IGNORECASE,
        ),
    ],
    "diagnosis": [
        re.compile(
            r"(?:\u0627\u0644\u062a\u0634\u062e\u064a\u0635"
            r"|Diagnosis)\s*[:：\-]?\s*(.+)",
            re.IGNORECASE,
        ),
    ],
    "medications": [
        re.compile(
            r"(?:\u0627\u0644\u0623\u062f\u0648\u064a\u0629"
            r"|\u0627\u0644\u0639\u0644\u0627\u062c"
            r"|Rx|Medication[s]?)\s*[:：\-]?\s*(.+)",
            re.IGNORECASE,
        ),
    ],
}

MEDICATION_SPLIT_RE = re.compile(r"\s*[،,؛;\n]\s*")


@dataclass
class ExtractedFields:
    """Lightweight container for extracted medical fields."""
    patient_name: str = ""
    patient_id: str = ""
    date: str = ""
    doctor_name: str = ""
    diagnosis: str = ""
    medications: list[str] = field(default_factory=list)
    raw_text: str = ""

    def as_markdown(self) -> str:
        lines = []
        if self.patient_name:
            lines.append(f"**Patient:** {self.patient_name}")
        if self.patient_id:
            lines.append(f"**ID:** {self.patient_id}")
        if self.date:
            lines.append(f"**Date:** {self.date}")
        if self.doctor_name:
            lines.append(f"**Doctor:** {self.doctor_name}")
        if self.diagnosis:
            lines.append(f"**Diagnosis:** {self.diagnosis}")
        if self.medications:
            lines.append(f"**Medications:** {', '.join(self.medications)}")
        return "\n".join(lines) if lines else "No medical fields detected"


def extract_medical_fields(text: str) -> ExtractedFields:
    """Regex-first extraction of medical document fields from OCR text.

    Adapted from ``src/ocr.field_extractor.ArabicMedicalFieldExtractor``.
    """
    fields = ExtractedFields(raw_text=text or "")
    for field_name, patterns in MEDICAL_FIELD_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(text or "")
            if match:
                value = match.group(1).strip()
                if field_name == "medications":
                    fields.medications = [
                        p.strip() for p in MEDICATION_SPLIT_RE.split(value) if p.strip()
                    ]
                else:
                    setattr(fields, field_name, value)
                break
    return fields

# ═══════════════════════════════════════════════════════════════════════
# 3. IMAGE PREPROCESSING  (deskew, contrast, denoise)
# ═══════════════════════════════════════════════════════════════════════

def preprocess_image(img: np.ndarray) -> np.ndarray:
    """Apply preprocessing pipeline to improve OCR quality.

    Steps (when OpenCV is available):
      1. Grayscale conversion
      2. CLAHE contrast enhancement
      3. Mild denoising (bilateral filter)
      4. Otsu binarization (returned as 3-channel for consistency)

    From the Grok blueprint ImagePreprocessor concept.
    """
    if not HAS_CV2:
        return img  # No preprocessing without OpenCV

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Bilateral filter (denoise while preserving edges)
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)

    # Convert back to RGB for consistency with Tesseract
    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)

# ═══════════════════════════════════════════════════════════════════════
# 4. TESSERACT LANGUAGE DETECTION
# ═══════════════════════════════════════════════════════════════════════

def _get_available_ocr_langs() -> list[str]:
    """Probe which Tesseract language packs are installed."""
    available = []
    for lang in ("eng", "ara", "deu"):
        try:
            import pytesseract
            pytesseract.image_to_string(
                np.zeros((10, 10), dtype=np.uint8), lang=lang
            )
            available.append(lang)
        except Exception:
            continue
    return available if available else ["eng"]


_AVAILABLE_OCR_LANGS = _get_available_ocr_langs()
_MULTILANG_COMBOS = []
for combo in ("ara+eng", "deu+eng", "ara+eng+deu"):
    parts = combo.split("+")
    if all(p in _AVAILABLE_OCR_LANGS for p in parts):
        _MULTILANG_COMBOS.append(combo)


def _best_ocr_lang(requested: str) -> str:
    """Pick the best available Tesseract lang string."""
    if requested in _MULTILANG_COMBOS or requested in _AVAILABLE_OCR_LANGS:
        return requested
    if "ara" in requested and "ara" in _AVAILABLE_OCR_LANGS and "eng" in _AVAILABLE_OCR_LANGS:
        return "ara+eng"
    if "deu" in requested and "deu" in _AVAILABLE_OCR_LANGS and "eng" in _AVAILABLE_OCR_LANGS:
        return "deu+eng"
    return "eng"


def _run_tesseract(img: np.ndarray, lang: str = "eng") -> str:
    """Run Tesseract OCR. Falls back to empty string on any error."""
    try:
        import pytesseract
        actual_lang = _best_ocr_lang(lang)
        raw = str(
            pytesseract.image_to_string(img, lang=actual_lang, config="--psm 6")
        ).strip()
        # Apply RTL fix for Arabic text
        if _rtl_fixer.contains_arabic(raw):
            raw = _rtl_fixer.fix(raw)
        return raw
    except Exception:
        return ""


def _run_tesseract_with_confidence(img: np.ndarray, lang: str = "eng") -> tuple[str, float]:
    """Run Tesseract OCR and also return per-word confidence."""
    try:
        import pytesseract
        actual_lang = _best_ocr_lang(lang)
        data = pytesseract.image_to_data(
            img, lang=actual_lang, output_type=pytesseract.Output.DICT,
        )
        texts, confs = [], []
        for i, t in enumerate(data["text"]):
            t = t.strip()
            if t:
                texts.append(t)
                confs.append(float(data["conf"][i]) / 100.0)
        raw = " ".join(texts)
        if _rtl_fixer.contains_arabic(raw):
            raw = _rtl_fixer.fix(raw)
        avg_conf = float(np.mean(confs)) if confs else 0.0
        return raw, avg_conf
    except Exception:
        return "", 0.0


def _detect_language(text: str) -> str:
    """Detect dominant language from OCR text content."""
    if not text:
        return "unknown"
    arabic_chars = len(ARABIC_CHAR_RE.findall(text))
    german_words = len(re.findall(
        r"\b(und|der|die|das|ist|ein|nicht|mit|auf|fur|von|sich|dem|des|den|auch)\b",
        text, re.IGNORECASE,
    ))
    if arabic_chars > len(text) * 0.1:
        return "arabic"
    if german_words >= 2:
        return "german"
    if any(c.isalpha() for c in text):
        return "english"
    return "unknown"

# ═══════════════════════════════════════════════════════════════════════
# 5. WORD SEGMENTATION
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class WordBox:
    """A single word extracted from a page image."""
    image: np.ndarray
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    ocr_text: str
    page_num: int
    confidence: float = 0.0
    user_correction: str = ""
    language: str = "unknown"
    rtl_fixed: bool = False


@dataclass
class PageData:
    """A single page from a PDF."""
    image: np.ndarray
    page_num: int
    rotation: int = 0


def pdf_to_pages(
    pdf_path: str, max_pages: int = 50, dpi: int = 200
) -> list[PageData]:
    """Convert PDF pages to images, auto-correcting rotation."""
    if not HAS_FITZ:
        raise ImportError("PyMuPDF (fitz) required. Install: pip install PyMuPDF")

    doc = fitz.open(pdf_path)
    pages: list[PageData] = []

    for i in range(min(max_pages, doc.page_count)):
        page = doc[i]
        rotation = page.rotation

        mat = fitz.Matrix(1, 1)
        if rotation:
            mat = mat.prerotate(rotation)

        pix = page.get_pixmap(matrix=mat, dpi=dpi)
        img_data = pix.tobytes("png")
        pil_img = Image.open(io.BytesIO(img_data)).convert("RGB")
        np_img = np.array(pil_img)

        pages.append(PageData(image=np_img, page_num=i + 1, rotation=rotation))

    doc.close()
    return pages


def segment_words(
    page: PageData, min_word_height: int = 15, ocr_lang: str = "eng",
    apply_preprocess: bool = True,
) -> list[WordBox]:
    """Segment a page image into word-level boxes."""
    img = page.image.copy()

    # Apply preprocessing for better OCR
    if apply_preprocess:
        img = preprocess_image(img)

    h, w = img.shape[:2]

    if HAS_CV2:
        words = _segment_cv2(img, h, w, min_word_height, ocr_lang)
    else:
        words = _segment_tesseract(img, h, w, min_word_height, ocr_lang)

    # Sort: top-to-bottom; Arabic words right-to-left within a line
    words.sort(
        key=lambda wb: (
            wb.bbox[1],
            -wb.bbox[0] if wb.language == "arabic" else wb.bbox[0],
        )
    )

    # Flag low-confidence words for active learning priority
    for w in words:
        if w.confidence > 0 and w.confidence < 0.5:
            w.ocr_text = f"[LOW-CONF] {w.ocr_text}"

    return words


def _segment_cv2(
    img: np.ndarray, h: int, w: int, min_h: int, ocr_lang: str
) -> list[WordBox]:
    """Word segmentation via OpenCV morphological operations + contour detection."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
    dilated = cv2.dilate(binary, kernel_h, iterations=1)
    cleaned = cv2.erode(dilated, kernel_v, iterations=1)

    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    words: list[WordBox] = []
    pad = 4
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bh < min_h or bw < 5:
            continue
        if bh > h * 0.5 or bw > w * 0.9:
            continue

        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
        word_img = img[y1:y2, x1:x2]

        ocr_text, conf = _run_tesseract_with_confidence(word_img, lang=ocr_lang)
        # Strip the [LOW-CONF] prefix for language detection
        clean_text = ocr_text.replace("[LOW-CONF] ", "")
        lang = _detect_language(clean_text)

        words.append(WordBox(
            image=word_img, bbox=(x1, y1, x2, y2),
            ocr_text=ocr_text, page_num=0, confidence=conf, language=lang,
            rtl_fixed=_rtl_fixer.contains_arabic(clean_text),
        ))
    return words


def _segment_tesseract(
    img: np.ndarray, h: int, w: int, min_h: int, ocr_lang: str
) -> list[WordBox]:
    """Fallback word segmentation using Tesseract word-level output."""
    try:
        import pytesseract
        actual_lang = _best_ocr_lang(ocr_lang)
        data = pytesseract.image_to_data(
            img, lang=actual_lang, output_type=pytesseract.Output.DICT
        )
    except Exception:
        return []

    words: list[WordBox] = []
    pad = 4
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        if bh < min_h or bw < 5:
            continue

        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
        word_img = img[y1:y2, x1:x2]
        lang = _detect_language(text)
        conf = float(data["conf"][i]) / 100.0 if data["conf"][i] > 0 else 0.0

        # Apply RTL fix per word
        fixed_text = text
        if _rtl_fixer.contains_arabic(text):
            fixed_text = _rtl_fixer.fix(text)

        words.append(WordBox(
            image=word_img, bbox=(x1, y1, x2, y2),
            ocr_text=fixed_text, page_num=0, confidence=conf, language=lang,
            rtl_fixed=(fixed_text != text),
        ))
    return words

# ═══════════════════════════════════════════════════════════════════════
# 6. CORRECTIONS DATABASE  (with dedup + active learning fields)
# ═══════════════════════════════════════════════════════════════════════

def _init_db() -> sqlite3.Connection:
    """Initialize or connect to the SQLite corrections database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_image_hash TEXT NOT NULL,
            ocr_text TEXT NOT NULL,
            corrected_text TEXT NOT NULL,
            language TEXT DEFAULT 'unknown',
            source_file TEXT,
            page_num INTEGER,
            bbox TEXT,
            confidence REAL DEFAULT 0.0,
            rtl_fixed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(word_image_hash, ocr_text)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT,
            total_pages INTEGER DEFAULT 0,
            total_words INTEGER DEFAULT 0,
            corrected_words INTEGER DEFAULT 0,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS page_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT,
            page_num INTEGER,
            fields_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def save_correction(
    ocr_text: str,
    corrected_text: str,
    word_image: np.ndarray,
    language: str,
    source_file: str = "",
    page_num: int = 0,
    bbox: tuple = (0, 0, 0, 0),
    confidence: float = 0.0,
    rtl_fixed: bool = False,
) -> bool:
    """Save a single word correction. Returns True if new/updated (dedup by hash)."""
    if not corrected_text.strip() or corrected_text == ocr_text:
        return False

    img_hash = "nohash"
    if HAS_CV2:
        try:
            img_bytes = cv2.imencode(".png", cv2.cvtColor(word_image, cv2.COLOR_RGB2BGR))[1].tobytes()
            img_hash = hashlib.md5(img_bytes).hexdigest()
        except Exception:
            pass

    conn = _init_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO corrections
               (word_image_hash, ocr_text, corrected_text, language,
                source_file, page_num, bbox, confidence, rtl_fixed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (img_hash, ocr_text, corrected_text, language,
             source_file, page_num, json.dumps(bbox), confidence, int(rtl_fixed)),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def save_page_fields(source_file: str, page_num: int, fields: ExtractedFields):
    """Save extracted medical fields for a page (for later dedup/review)."""
    conn = _init_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO page_fields (source_file, page_num, fields_json)
               VALUES (?, ?, ?)""",
            (source_file, page_num, json.dumps({
                "patient_name": fields.patient_name,
                "patient_id": fields.patient_id,
                "date": fields.date,
                "doctor_name": fields.doctor_name,
                "diagnosis": fields.diagnosis,
                "medications": fields.medications,
            }, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats() -> dict:
    """Get correction statistics from the database."""
    conn = _init_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        by_lang: dict[str, int] = {}
        for row in conn.execute(
            "SELECT language, COUNT(*) FROM corrections GROUP BY language"
        ):
            by_lang[row[0]] = row[1]

        rtl_count = conn.execute(
            "SELECT COUNT(*) FROM corrections WHERE rtl_fixed = 1"
        ).fetchone()[0]
        low_conf = conn.execute(
            "SELECT COUNT(*) FROM corrections WHERE confidence > 0 AND confidence < 0.5"
        ).fetchone()[0]
        field_pages = conn.execute(
            "SELECT COUNT(*) FROM page_fields"
        ).fetchone()[0]

        return {
            "total_corrections": total,
            "by_language": by_lang,
            "rtl_fixed_count": rtl_count,
            "low_confidence_count": low_conf,
            "pages_with_fields": field_pages,
        }
    finally:
        conn.close()


def export_to_jsonl() -> str:
    """Export all corrections as JSONL. Returns the file path."""
    conn = _init_db()
    try:
        rows = conn.execute(
            "SELECT ocr_text, corrected_text, language, source_file, "
            "       page_num, confidence, rtl_fixed, created_at "
            "FROM corrections ORDER BY id"
        ).fetchall()

        with open(EXPORT_PATH, "w", encoding="utf-8") as f:
            for row in rows:
                record = {
                    "ocr_text": row[0],
                    "corrected_text": row[1],
                    "language": row[2],
                    "source_file": row[3],
                    "page_num": row[4],
                    "confidence": row[5],
                    "rtl_fixed": bool(row[6]),
                    "created_at": row[7],
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return str(EXPORT_PATH)
    finally:
        conn.close()

# ═══════════════════════════════════════════════════════════════════════
# 7. APP STATE
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SessionState:
    """Holds current session data (in-memory, per Gradio instance)."""
    pages: list[PageData] = field(default_factory=list)
    all_words: list[WordBox] = field(default_factory=list)
    current_page_idx: int = 0
    current_word_idx: int = 0
    source_file: str = ""
    ocr_lang: str = "eng"
    session_corrections: int = 0
    apply_preprocess: bool = True


_state = SessionState()

# ═══════════════════════════════════════════════════════════════════════
# 8. GRADIO CALLBACKS
# ═══════════════════════════════════════════════════════════════════════

def cb_load_pdf(pdf_file, max_pages: int, ocr_lang: str, do_preprocess: bool) -> tuple:
    """Load a PDF file and segment the first page into words."""
    if pdf_file is None:
        return None, "", "No file uploaded"

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_file)
        tmp_path = tmp.name

    try:
        _state.source_file = (
            os.path.basename(pdf_file.name) if hasattr(pdf_file, "name")
            else "uploaded.pdf"
        )
        _state.ocr_lang = ocr_lang
        _state.apply_preprocess = do_preprocess
        _state.pages = pdf_to_pages(tmp_path, max_pages=max_pages)
        _state.current_page_idx = 0
        _state.session_corrections = 0

        if not _state.pages:
            return None, "", "No pages found in PDF"

        return _show_page(0)
    except Exception as e:
        return None, "", f"Error: {e}"
    finally:
        os.unlink(tmp_path)


def _show_page(page_idx: int) -> tuple:
    """Render a page image and segment it into words."""
    if page_idx >= len(_state.pages):
        return None, "", "No more pages"

    _state.current_page_idx = page_idx
    page = _state.pages[page_idx]
    _state.all_words = segment_words(
        page, ocr_lang=_state.ocr_lang, apply_preprocess=_state.apply_preprocess,
    )
    _state.current_word_idx = 0

    # Extract medical fields from full-page OCR
    full_text = " ".join(w.ocr_text.replace("[LOW-CONF] ", "") for w in _state.all_words)
    fields = extract_medical_fields(full_text)
    save_page_fields(_state.source_file, page.page_num, fields)

    page_pil = Image.fromarray(page.image)
    rot_icon = "ROTATED" if page.rotation else "OK"
    preprocess_icon = "+Preprocess" if _state.apply_preprocess else "Raw"
    low_conf_count = sum(1 for w in _state.all_words if w.confidence > 0 and w.confidence < 0.5)
    rtl_count = sum(1 for w in _state.all_words if w.rtl_fixed)

    info = (
        f"Page {page_idx + 1}/{len(_state.pages)} | "
        f"Rotation: {rot_icon} ({page.rotation}deg) | "
        f"Words: {len(_state.all_words)} | "
        f"RTL-fixed: {rtl_count} | "
        f"Low-conf: {low_conf_count} | "
        f"{preprocess_icon}"
    )
    return page_pil, info, fields.as_markdown()


def cb_navigate_page(direction: int) -> tuple:
    """Navigate to next/previous page."""
    new_idx = _state.current_page_idx + direction
    if 0 <= new_idx < len(_state.pages):
        return _show_page(new_idx)
    return gr.update(), gr.update(), "No more pages in this direction"


def cb_show_word(word_idx: int) -> tuple:
    """Display a specific word with its OCR text."""
    if not _state.all_words or word_idx >= len(_state.all_words) or word_idx < 0:
        return None, "", f"Word index {word_idx} out of range (total: {len(_state.all_words)})"

    _state.current_word_idx = word_idx
    word = _state.all_words[word_idx]
    word_pil = Image.fromarray(word.image)

    lang_emoji = {"arabic": "🇸🇦", "english": "🇬🇧", "german": "🇩🇪", "unknown": "🌐"}.get(
        word.language, "🌐"
    )
    rtl_tag = " [RTL-fixed]" if word.rtl_fixed else ""
    conf_pct = f"{word.confidence:.0%}" if word.confidence > 0 else "N/A"
    status = (
        f"Word {word_idx + 1}/{len(_state.all_words)} | "
        f"{lang_emoji} {word.language}{rtl_tag} | "
        f"Conf: {conf_pct} | "
        f"Size: {word.image.shape[1]}x{word.image.shape[0]}px"
    )
    return word_pil, word.ocr_text, status


def cb_save_correction(correction_text: str) -> tuple:
    """Save user's correction for the current word, then advance."""
    if not _state.all_words:
        return "No words loaded", gr.update(), gr.update()

    word = _state.all_words[_state.current_word_idx]

    if not correction_text.strip():
        return "Correction cannot be empty", gr.update(), gr.update()

    # Strip [LOW-CONF] prefix before saving
    clean_ocr = word.ocr_text.replace("[LOW-CONF] ", "")

    saved = save_correction(
        ocr_text=clean_ocr,
        corrected_text=correction_text,
        word_image=word.image,
        language=word.language,
        source_file=_state.source_file,
        page_num=word.page_num,
        bbox=word.bbox,
        confidence=word.confidence,
        rtl_fixed=word.rtl_fixed,
    )

    if saved:
        word.user_correction = correction_text
        _state.session_corrections += 1

    # Advance to next word
    next_idx = _state.current_word_idx + 1
    if next_idx < len(_state.all_words):
        next_word = _state.all_words[next_idx]
        msg = f"Saved! ({_state.session_corrections} total)" if saved else "No change (same text)"
        return msg, Image.fromarray(next_word.image), next_word.ocr_text
    else:
        msg = f"Saved! ({_state.session_corrections} total) -- Last word on this page" if saved else "Last word"
        return msg, gr.update(), ""


def cb_skip_word() -> tuple:
    """Skip current word and move to next."""
    if not _state.all_words:
        return gr.update(), ""
    next_idx = _state.current_word_idx + 1
    if next_idx < len(_state.all_words):
        word = _state.all_words[next_idx]
        return Image.fromarray(word.image), word.ocr_text
    return gr.update(), ""


def cb_get_stats() -> str:
    """Get current correction database statistics as Markdown."""
    stats = get_stats()
    lines = [f"**Total Corrections:** {stats['total_corrections']}"]
    if stats["by_language"]:
        for lang, count in sorted(stats["by_language"].items(), key=lambda x: -x[1]):
            emoji = {"arabic": "🇸🇦", "english": "🇬🇧", "german": "🇩🇪", "unknown": "🌐"}.get(lang, "🌐")
            lines.append(f"  {emoji} {lang}: {count}")
    lines.append(f"\n**RTL-fixed words:** {stats['rtl_fixed_count']}")
    lines.append(f"**Low-confidence words:** {stats['low_confidence_count']}")
    lines.append(f"**Pages with extracted fields:** {stats['pages_with_fields']}")
    lines.append(f"\n**Current Session:** {_state.session_corrections} corrections")
    pages_done = _state.current_page_idx + 1 if _state.pages else 0
    pages_total = len(_state.pages)
    lines.append(f"**Pages processed:** {pages_done}/{pages_total}")
    lines.append(f"\n**Available OCR langs:** {', '.join(_AVAILABLE_OCR_LANGS)}")
    if _MULTILANG_COMBOS:
        lines.append(f"**Multi-lang combos:** {', '.join(_MULTILANG_COMBOS)}")
    lines.append(f"**OpenCV (preprocessing):** {'Yes' if HAS_CV2 else 'No'}")
    lines.append(f"**PyMuPDF (PDF):** {'Yes' if HAS_FITZ else 'No'}")
    return "\n".join(lines)


def cb_export() -> str:
    """Export corrections to JSONL for HuggingFace Datasets."""
    path = export_to_jsonl()
    stats = get_stats()
    return (
        f"Exported {stats['total_corrections']} corrections to:\n`{path}`\n\n"
        "Upload to HuggingFace:\n"
        "```python\n"
        "from datasets import load_dataset\n"
        "ds = load_dataset('json', data_files='corrections.jsonl')\n"
        "ds.push_to_hub('DrAbdulmalek/handwriting-corrections-ar-en-de')\n"
        "```"
    )


# ═══════════════════════════════════════════════════════════════════════
# 9. BUILD GRADIO UI
# ═══════════════════════════════════════════════════════════════════════

CUSTOM_CSS = """
.word-image img {
    max-height: 120px;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
}
.page-image img {
    max-height: 600px;
    border: 1px solid #ccc;
    border-radius: 4px;
}
.correction-input textarea {
    font-size: 20px !important;
    direction: auto;
}
"""


def build_ui() -> gr.Blocks:
    """Build and return the Gradio Blocks UI."""
    with gr.Blocks(
        title="Handwriting Trainer — Arabic/English/German",
        css=CUSTOM_CSS,
        theme=gr.themes.Soft(),
    ) as demo:
        gr.Markdown("""
        # ✍️ Handwriting OCR Trainer — Enhanced with RTL Fix + Field Extraction

        **Upload scanned handwritten PDF → Preprocess → Word segmentation → OCR → RTL fix → Correct → Export**

        Integrated modules from Arabic Medical OCR Pipeline:
        🔄 RTL Fixer | 🏥 Medical Field Extractor | 🖼️ Image Preprocessing | 📊 Active Learning

        Supported: 🇸🇦 Arabic | 🇬🇧 English | 🇩🇪 German
        """)

        with gr.Tabs():
            # ── Tab 1: Upload & Process ──
            with gr.Tab("Upload & Process"):
                with gr.Row():
                    with gr.Column(scale=1):
                        pdf_input = gr.File(
                            label="Upload PDF (scanned handwriting)",
                            file_types=[".pdf"],
                            type="binary",
                        )
                        max_pages = gr.Slider(
                            1, 100, value=20, step=1,
                            label="Max pages to process",
                        )
                        lang_select = gr.Dropdown(
                            choices=_MULTILANG_COMBOS + _AVAILABLE_OCR_LANGS,
                            value=_best_ocr_lang("ara+eng"),
                            label="OCR Language(s)",
                        )
                        preprocess_cb = gr.Checkbox(
                            value=True,
                            label="Apply preprocessing (CLAHE + denoise)",
                        )
                        load_btn = gr.Button(
                            "Load PDF", variant="primary", size="lg"
                        )

                    with gr.Column(scale=2):
                        page_image = gr.Image(
                            label="Current Page", type="pil",
                            elem_classes="page-image",
                        )
                        page_info = gr.Markdown("")
                        page_fields_display = gr.Markdown("")

                with gr.Row():
                    prev_page = gr.Button("← Previous Page", size="sm")
                    next_page = gr.Button("Next Page →", size="sm")

            # ── Tab 2: Word Correction ──
            with gr.Tab("Word Correction"):
                with gr.Row():
                    with gr.Column(scale=1):
                        word_image = gr.Image(
                            label="Current Word", type="pil",
                            elem_classes="word-image",
                        )
                        word_status = gr.Markdown("")
                        with gr.Row():
                            skip_btn = gr.Button("Skip", size="sm")
                            nav_prev = gr.Button("← Prev Word", size="sm")
                            nav_next = gr.Button("Next Word →", size="sm")

                    with gr.Column(scale=2):
                        ocr_text = gr.Textbox(
                            label="OCR Text (read-only, RTL-fixed if Arabic)",
                            interactive=False,
                            lines=2,
                        )
                        correction_input = gr.Textbox(
                            label="Corrected Text (type here)",
                            lines=2,
                            placeholder="Type the correct text...",
                            autofocus=True,
                            elem_classes="correction-input",
                        )
                        save_btn = gr.Button(
                            "Save Correction & Next →",
                            variant="primary",
                            size="lg",
                        )
                        correction_status = gr.Markdown("")

            # ── Tab 3: Medical Fields ──
            with gr.Tab("Medical Fields"):
                gr.Markdown("""
                ### Extracted Medical Fields (per page)
                Automatically detected from OCR text using regex patterns.
                Fields: Patient Name, ID, Date, Doctor, Diagnosis, Medications.
                """)
                fields_overview = gr.Markdown("Load a PDF to see extracted fields")

            # ── Tab 4: Statistics & Export ──
            with gr.Tab("Statistics & Export"):
                stats_display = gr.Markdown("Click refresh to load stats")
                refresh_stats = gr.Button("Refresh Stats")
                export_btn = gr.Button(
                    "Export to JSONL (HuggingFace)", variant="secondary"
                )
                export_result = gr.Markdown("")

        # ── Event Bindings ──
        load_btn.click(
            fn=cb_load_pdf,
            inputs=[pdf_input, max_pages, lang_select, preprocess_cb],
            outputs=[page_image, page_info, page_fields_display],
        )

        prev_page.click(
            fn=lambda: cb_navigate_page(-1),
            outputs=[page_image, page_info, page_fields_display],
        )
        next_page.click(
            fn=lambda: cb_navigate_page(1),
            outputs=[page_image, page_info, page_fields_display],
        )

        # Auto-show first word when page changes
        page_image.change(
            fn=lambda: cb_show_word(0) if _state.all_words else (None, "", ""),
            outputs=[word_image, ocr_text, word_status],
        )

        save_btn.click(
            fn=cb_save_correction,
            inputs=[correction_input],
            outputs=[correction_status, word_image, ocr_text],
        )

        skip_btn.click(fn=cb_skip_word, outputs=[word_image, ocr_text])

        # Word navigation
        nav_prev.click(
            fn=lambda: cb_show_word(max(0, _state.current_word_idx - 1)),
            outputs=[word_image, ocr_text, word_status],
        )
        nav_next.click(
            fn=lambda: cb_show_word(
                min(len(_state.all_words) - 1, _state.current_word_idx + 1)
            ),
            outputs=[word_image, ocr_text, word_status],
        )

        # Stats & Export
        refresh_stats.click(fn=cb_get_stats, outputs=[stats_display])
        export_btn.click(fn=cb_export, outputs=[export_result])

    return demo


# ═══════════════════════════════════════════════════════════════════════
# 10. MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Handwriting OCR Trainer")
    parser.add_argument(
        "--port", type=int,
        default=int(os.environ.get("GRADIO_SERVER_PORT", 7860)),
    )
    parser.add_argument(
        "--host", type=str,
        default=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
    )
    args = parser.parse_args()

    print(f"Available OCR languages: {_AVAILABLE_OCR_LANGS}")
    print(f"Multi-lang combos: {_MULTILANG_COMBOS}")
    print(f"OpenCV (preprocessing): {HAS_CV2}")
    print(f"PyMuPDF (PDF): {HAS_FITZ}")
    print(f"RTL Fixer: ready")
    print(f"Field Extractor: ready")
    print(f"Data directory: {DATA_DIR}")

    demo = build_ui()
    demo.launch(server_name=args.host, server_port=args.port)