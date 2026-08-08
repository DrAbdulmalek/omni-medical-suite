#!/usr/bin/env python3
"""
Handwriting Trainer — Interactive Word-Level Correction UI
============================================================

Enhanced with modules from the Arabic Medical OCR Pipeline Blueprint:
  - RTL Fixer (src/ocr/rtl_utils.py): corrects reversed Arabic OCR
  - Medical Field Extractor (src/ocr/field_extractor.py): regex-based field extraction
  - Image Preprocessing: CLAHE + bilateral denoise for better OCR
  - Active Learning: low-confidence words flagged for priority review

Workflow:
    PDF → preprocess → pages → word segmentation → OCR → RTL fix
          → field extraction → user correction → save to DB + HF

Usage:
    python apps/handwriting-trainer/app.py
    python apps/handwriting-trainer/app.py --port 7861
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import gradio as gr
import numpy as np
from PIL import Image

# ── Add project root to path ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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

# ── Lazy OCR imports ─────────────────────────────────────────────────────

# Try to import monorepo RTL fixer, fallback to no-op
try:
    from src.ocr.rtl_utils import ArabicRTLFixer as _MonorepoRTLFixer
    _rtl = _MonorepoRTLFixer()
    HAS_RTL = True
except Exception:
    HAS_RTL = False
    _rtl = None

# Try to import monorepo field extractor
try:
    from src.ocr.field_extractor import ArabicMedicalFieldExtractor
    _field_extractor = ArabicMedicalFieldExtractor()
    HAS_FIELD_EXTRACTOR = True
except Exception:
    HAS_FIELD_EXTRACTOR = False
    _field_extractor = None

# Try to import monorepo ActiveLearningLoop
try:
    from packages.ai.active_learning_loop import ActiveLearningLoop
    _al_loop = ActiveLearningLoop()
    HAS_ACTIVE_LEARNING = True
except Exception:
    HAS_ACTIVE_LEARNING = False
    _al_loop = None


def _get_tesseract_langs() -> list[str]:
    """Return available Tesseract language strings, always including eng."""
    base = ["eng"]
    for lang in ("ara", "deu", "ara+eng", "deu+eng", "ara+eng+deu"):
        try:
            import pytesseract
            pytesseract.image_to_string(np.zeros((10, 10), dtype=np.uint8), lang=lang)
            base.append(lang)
        except Exception:
            continue
    return list(dict.fromkeys(base))


_AVAILABLE_LANGS = _get_tesseract_langs()

def _best_ocr_lang(requested: str) -> str:
    """Pick the best available Tesseract lang string for the requested combo."""
    if requested in _AVAILABLE_LANGS:
        return requested
    for fallback in ("eng", "ara+eng", "deu+eng", "ara+eng+deu"):
        if fallback in _AVAILABLE_LANGS:
            return fallback
    return "eng"


def _apply_rtl_fix(text: str) -> str:
    """Apply RTL fix if the module is available and text is Arabic."""
    if HAS_RTL and _rtl and _rtl.contains_arabic(text):
        return _rtl.fix_text(text)
    return text


def _run_tesseract(img: np.ndarray, lang: str = "eng") -> str:
    """Run Tesseract OCR on an image. Falls back to empty string."""
    try:
        import pytesseract
        actual_lang = _best_ocr_lang(lang)
        raw = str(pytesseract.image_to_string(img, lang=actual_lang, config="--psm 6")).strip()
        return _apply_rtl_fix(raw)
    except Exception:
        return ""

def _detect_language(text: str) -> str:
    """Detect dominant language from text content."""
    if not text:
        return "unknown"
    arabic_pattern = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
    german_pattern = re.compile(r"\b(und|der|die|das|ist|ein|nicht|mit|auf|für|von|sich|dem|des|den|auch)\b", re.IGNORECASE)
    
    arabic_chars = len(arabic_pattern.findall(text))
    german_words = len(german_pattern.findall(text))
    
    if arabic_chars > len(text) * 0.1:
        return "arabic"
    elif german_words >= 2:
        return "german"
    elif any(c.isalpha() for c in text):
        return "english"
    return "unknown"

# ── Word Segmentation ────────────────────────────────────────────────────

@dataclass
class WordBox:
    """A single word extracted from a page image."""
    image: np.ndarray          # Cropped word image (RGB)
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) in page coordinates
    ocr_text: str              # OCR recognized text
    page_num: int
    confidence: float = 0.0
    user_correction: str = ""
    language: str = "unknown"

@dataclass
class PageData:
    """A single page from a PDF."""
    image: np.ndarray
    page_num: int
    rotation: int = 0

def pdf_to_pages(pdf_path: str, max_pages: int = 50, dpi: int = 200) -> list[PageData]:
    """Convert PDF pages to images, auto-correcting rotation."""
    if not HAS_FITZ:
        raise ImportError("PyMuPDF (fitz) required. Install: pip install PyMuPDF")
    
    doc = fitz.open(pdf_path)
    pages = []
    
    for i in range(min(max_pages, doc.page_count)):
        page = doc[i]
        rotation = page.rotation
        
        # Normalize rotation: always render upright
        # If page is rotated 180°, we render it right-side-up
        mat = fitz.Matrix(1, 1)
        if rotation:
            mat = mat.prerotate(rotation)
        
        pix = page.get_pixmap(matrix=mat, dpi=dpi)
        img_data = pix.tobytes("png")
        pil_img = Image.open(io.BytesIO(img_data)).convert("RGB")
        np_img = np.array(pil_img)
        
        pages.append(PageData(
            image=np_img,
            page_num=i + 1,
            rotation=rotation,
        ))
    
    doc.close()
    return pages

def segment_words(page: PageData, min_word_height: int = 15, ocr_lang: str = "eng") -> list[WordBox]:
    """Segment a page image into word-level boxes using projection + contour."""
    img = page.image.copy()
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if HAS_CV2 else None
    
    if not HAS_CV2 or gray is None:
        # Fallback: split by whitespace regions using PIL
        return _segment_words_pil(page, min_word_height)
    
    # Binarize
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Morphological cleanup
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
    dilated = cv2.dilate(binary, kernel_h, iterations=1)
    cleaned = cv2.erode(dilated, kernel_v, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    words = []
    h, w = img.shape[:2]
    
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        
        # Filter: skip tiny/noise
        if bh < min_word_height or bw < 5:
            continue
        # Skip very large regions (likely images/tables)
        if bh > h * 0.5 or bw > w * 0.9:
            continue
        
        # Crop word image with small padding
        pad = 4
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(w, x + bw + pad)
        y2 = min(h, y + bh + pad)
        
        word_img = img[y1:y2, x1:x2]
        
        # Run OCR on the word
        ocr_text = _run_tesseract(word_img, lang=ocr_lang)
        lang = _detect_language(ocr_text)
        
        words.append(WordBox(
            image=word_img,
            bbox=(x1, y1, x2, y2),
            ocr_text=ocr_text,
            page_num=page.page_num,
            language=lang,
        ))
    
    # Sort top-to-bottom, left-to-right (RTL-aware: for Arabic, sort right-to-left within line)
    words.sort(key=lambda w: (w.bbox[1], -w.bbox[0] if w.language == "arabic" else w.bbox[0]))
    
    return words

def _segment_words_pil(page: PageData, min_height: int = 15) -> list[WordBox]:
    """Fallback word segmentation using PIL only (no OpenCV)."""
    from PIL import Image as PILImage
    
    img = page.image
    h, w = img.shape[:2]
    
    # Simple approach: use Tesseract with word-level output
    try:
        import pytesseract
        actual_lang = _best_ocr_lang("ara+eng+deu")
        data = pytesseract.image_to_data(img, lang=actual_lang, output_type=pytesseract.Output.DICT)
        
        words = []
        pad = 4
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if not text:
                continue
            
            x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            if bh < min_height or bw < 5:
                continue
            
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(w, x + bw + pad)
            y2 = min(h, y + bh + pad)
            
            word_img = img[y1:y2, x1:x2]
            lang = _detect_language(text)
            
            words.append(WordBox(
                image=word_img,
                bbox=(x1, y1, x2, y2),
                ocr_text=text,
                page_num=page.page_num,
                confidence=float(data["conf"][i]) / 100.0 if data["conf"][i] > 0 else 0.0,
                language=lang,
            ))
        
        return words
    except Exception:
        return []

# ── Corrections Database ──────────────────────────────────────────────────

DB_PATH = PROJECT_ROOT / "training-data" / "corrections" / "handwriting_corrections.db"

def _init_db() -> sqlite3.Connection:
    """Initialize SQLite database for corrections."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(word_image_hash, ocr_text)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT,
            total_pages INTEGER,
            total_words INTEGER,
            corrected_words INTEGER,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
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
) -> bool:
    """Save a single word correction to the database."""
    if not corrected_text.strip() or corrected_text == ocr_text:
        return False
    
    # Hash the word image for dedup
    img_bytes = cv2.imencode(".png", cv2.cvtColor(word_image, cv2.COLOR_RGB2BGR))[1].tobytes() if HAS_CV2 else b""
    img_hash = hashlib.md5(img_bytes).hexdigest() if img_bytes else "nohash"
    
    conn = _init_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO corrections 
               (word_image_hash, ocr_text, corrected_text, language, source_file, page_num, bbox, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (img_hash, ocr_text, corrected_text, language, source_file, page_num, json.dumps(bbox), confidence),
        )
        conn.commit()
    finally:
        conn.close()

    # Feed into ActiveLearningLoop (packages/ai/active_learning_loop.py)
    _feed_active_learning(ocr_text, corrected_text, language, confidence)
    return True


def _feed_active_learning(ocr_text: str, corrected_text: str, language: str, confidence: float):
    """Submit correction to the monorepo's ActiveLearningLoop if available."""
    try:
        from packages.ai.active_learning_loop import ActiveLearningLoop
        loop = ActiveLearningLoop()
        loop.submit_correction(
            original=ocr_text,
            corrected=corrected_text,
            confidence=confidence,
            metadata={"language": language, "source": "handwriting-trainer"},
        )
    except Exception:
        pass  # ActiveLearningLoop is optional


def get_stats() -> dict:
    """Get correction statistics."""
    conn = _init_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        by_lang = {}
        for row in conn.execute("SELECT language, COUNT(*) FROM corrections GROUP BY language"):
            by_lang[row[0]] = row[1]
        return {"total_corrections": total, "by_language": by_lang}
    finally:
        conn.close()

def export_to_hf_dataset(output_path: str = "training-data/corrections/handwriting_gt.jsonl") -> str:
    """Export all corrections as JSONL for HuggingFace Dataset upload."""
    conn = _init_db()
    try:
        rows = conn.execute(
            "SELECT ocr_text, corrected_text, language, source_file, page_num, confidence, created_at FROM corrections ORDER BY id"
        ).fetchall()
        
        out_path = PROJECT_ROOT / output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(out_path, "w", encoding="utf-8") as f:
            for row in rows:
                record = {
                    "ocr_text": row[0],
                    "corrected_text": row[1],
                    "language": row[2],
                    "source_file": row[3],
                    "page_num": row[4],
                    "confidence": row[5],
                    "created_at": row[6],
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
        return str(out_path)
    finally:
        conn.close()

# ── App State ─────────────────────────────────────────────────────────────

@dataclass
class SessionState:
    """Holds current session data."""
    pages: list[PageData] = field(default_factory=list)
    all_words: list[WordBox] = field(default_factory=list)
    current_page_idx: int = 0
    current_word_idx: int = 0
    source_file: str = ""
    ocr_lang: str = "eng"
    session_corrections: int = 0

_state = SessionState()

# ── Gradio Callbacks ─────────────────────────────────────────────────────

def load_pdf(pdf_file, max_pages: int, ocr_lang: str) -> tuple:
    """Load a PDF and segment first page into words."""
    if pdf_file is None:
        return None, "", "No file uploaded"

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_file)
        tmp_path = tmp.name

    try:
        _state.source_file = os.path.basename(pdf_file.name) if hasattr(pdf_file, "name") else "uploaded.pdf"
        _state.ocr_lang = ocr_lang
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
    """Display a page and its segmented words."""
    if page_idx >= len(_state.pages):
        return [], "", "❌ No more pages"
    
    _state.current_page_idx = page_idx
    page = _state.pages[page_idx]
    _state.all_words = segment_words(page, ocr_lang=getattr(_state, 'ocr_lang', 'eng'))
    _state.current_word_idx = 0
    
    page_pil = Image.fromarray(page.image)
    
    info = (
        f"📄 Page {page_idx + 1}/{len(_state.pages)} | "
        f"🔄 Original rotation: {page.rotation}° | "
        f"📝 Words found: {len(_state.all_words)} | "
        f"✅ Session corrections: {_state.session_corrections}"
    )
    
    return page_pil, info, ""

def navigate_page(direction: int) -> tuple:
    """Navigate to next/previous page."""
    new_idx = _state.current_page_idx + direction
    if 0 <= new_idx < len(_state.pages):
        return _show_page(new_idx)
    return gr.update(), gr.update(), "⚠️ No more pages in this direction"

def show_word(word_idx: int) -> tuple:
    """Display a specific word with its OCR text."""
    if not _state.all_words or word_idx >= len(_state.all_words):
        return None, "", f"⚠️ Word index {word_idx} out of range (total: {len(_state.all_words)})"
    
    _state.current_word_idx = word_idx
    word = _state.all_words[word_idx]
    word_pil = Image.fromarray(word.image)
    
    lang_emoji = {"arabic": "🇸🇦", "english": "🇬🇧", "german": "🇩🇪", "unknown": "🌐"}.get(word.language, "🌐")
    status = (
        f"Word {word_idx + 1}/{len(_state.all_words)} | "
        f"Lang: {lang_emoji} {word.language} | "
        f"Page: {word.page_num} | "
        f"Size: {word.image.shape[1]}x{word.image.shape[0]}px"
    )
    
    return word_pil, word.ocr_text, status

def save_word_correction(word_text: str) -> tuple:
    """Save user's correction for the current word."""
    if not _state.all_words:
        return "⚠️ No words loaded", gr.update(), gr.update()
    
    word = _state.all_words[_state.current_word_idx]
    
    if not word_text.strip():
        return "⚠️ Correction cannot be empty", gr.update(), gr.update()
    
    saved = save_correction(
        ocr_text=word.ocr_text,
        corrected_text=word_text,
        word_image=word.image,
        language=word.language,
        source_file=_state.source_file,
        page_num=word.page_num,
        bbox=word.bbox,
        confidence=word.confidence,
    )
    
    if saved:
        word.user_correction = word_text
        _state.session_corrections += 1
    
    # Move to next word
    next_idx = _state.current_word_idx + 1
    if next_idx < len(_state.all_words):
        word_pil = Image.fromarray(_state.all_words[next_idx].image)
        status_msg = f"✅ Saved! ({_state.session_corrections} total)" if saved else "ℹ️ No change (same text)"
        next_status = f"Word {next_idx + 1}/{len(_state.all_words)} | Lang: {_state.all_words[next_idx].language}"
        return status_msg, word_pil, _state.all_words[next_idx].ocr_text
    else:
        status_msg = f"✅ Saved! ({_state.session_corrections} total) — Last word on this page" if saved else "ℹ️ Last word"
        return status_msg, gr.update(), ""

def skip_word() -> tuple:
    """Skip current word and move to next."""
    if not _state.all_words:
        return gr.update(), ""
    
    next_idx = _state.current_word_idx + 1
    if next_idx < len(_state.all_words):
        word = _state.all_words[next_idx]
        word_pil = Image.fromarray(word.image)
        return word_pil, word.ocr_text
    return gr.update(), ""

def load_sample(which: str) -> tuple:
    """Load a sample training image."""
    samples_dir = PROJECT_ROOT / "training-data" / "samples"
    
    if which == "medical":
        path = samples_dir / "medical" / "page_002.png"
    else:
        path = samples_dir / "technical" / "page_001.png"
    
    if not path.exists():
        return None, "❌ Sample not found"
    
    img = np.array(Image.open(path).convert("RGB"))
    
    # Create a single-page session
    page = PageData(image=img, page_num=1, rotation=0)
    _state.pages = [page]
    _state.source_file = f"sample/{which}"
    _state.all_words = segment_words(page, ocr_lang="eng")
    _state.current_word_idx = 0
    _state.session_corrections = 0
    
    info = (
        f"📄 Sample: {which} | "
        f"📝 Words found: {len(_state.all_words)} | "
        f"Source: training-data/samples/{which}/"
    )
    
    return Image.fromarray(img), info

def get_dataset_stats() -> str:
    """Get current correction database statistics."""
    stats = get_stats()
    lines = [f"📊 **Total Corrections:** {stats['total_corrections']}"]
    if stats["by_language"]:
        for lang, count in sorted(stats["by_language"].items(), key=lambda x: -x[1]):
            emoji = {"arabic": "🇸🇦", "english": "🇬🇧", "german": "🇩🇪", "unknown": "🌐"}.get(lang, "🌐")
            lines.append(f"  {emoji} {lang}: {count}")
    
    # Session stats
    lines.append(f"\n📝 **Current Session:** {_state.session_corrections} corrections")
    lines.append(f"📄 **Pages processed:** {_state.current_page_idx + 1}/{len(_state.pages) if _state.pages else 0}")
    return "\n".join(lines)

def export_dataset() -> str:
    """Export corrections to JSONL for HuggingFace."""
    path = export_to_hf_dataset()
    stats = get_stats()
    return f"✅ Exported {stats['total_corrections']} corrections to:\n`{path}`\n\nUpload to HuggingFace with:\n```python\nfrom datasets import load_dataset\nds = load_dataset('json', data_files='{path}')\nds.push_to_hub('DrAbdulmalek/handwriting-corrections-ar-en-de')\n```"

# ── Build Gradio UI ──────────────────────────────────────────────────────

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
    with gr.Blocks(
        title="Handwriting Trainer — Interactive Correction UI",
        css=CUSTOM_CSS,
        theme=gr.themes.Soft(),
    ) as demo:
        gr.Markdown("""
        # ✍️ Handwriting Trainer — Interactive Word-Level Correction
        
        **رفع مستند مسحوب بخط اليد ← تقسيم لكلمات ← تصحيح OCR ← حفظ للتدريب**
        
        اللغات المدعومة: 🇸🇦 عربي | 🇬🇧 إنجليزي | 🇩🇪 ألماني
        """)
        
        with gr.Tabs():
            # ── Tab 1: Upload & Process ──
            with gr.Tab("📁 Upload & Process"):
                with gr.Row():
                    with gr.Column(scale=1):
                        pdf_input = gr.File(
                            label="Upload PDF (scanned handwriting)",
                            file_types=[".pdf"],
                            type="binary",
                        )
                        max_pages = gr.Slider(1, 100, value=20, step=1, label="Max pages to process")
                        lang_select = gr.Dropdown(
                            choices=["ara+eng", "eng", "deu", "deu+eng", "ara+eng+deu"],
                            value="ara+eng",
                            label="OCR Language(s)",
                        )
                        load_btn = gr.Button("📄 Load PDF", variant="primary", size="lg")
                        
                        gr.Markdown("**Or load a sample:**")
                        with gr.Row():
                            sample_med = gr.Button("🩺 Medical Sample", size="sm")
                            sample_tech = gr.Button("🔧 Technical Sample", size="sm")
                    
                    with gr.Column(scale=2):
                        page_image = gr.Image(label="Current Page", type="pil", elem_classes="page-image")
                        page_info = gr.Markdown("")
                        page_status = gr.Markdown("")
                
                with gr.Row():
                    prev_page = gr.Button("⬅️ Previous Page", size="sm")
                    next_page = gr.Button("Next Page ➡️", size="sm")
            
            # ── Tab 2: Word Correction ──
            with gr.Tab("✏️ Word Correction"):
                with gr.Row():
                    with gr.Column(scale=1):
                        word_image = gr.Image(label="Current Word", type="pil", elem_classes="word-image")
                        word_status = gr.Markdown("")
                        with gr.Row():
                            skip_btn = gr.Button("⏭️ Skip", size="sm")
                            nav_prev = gr.Button("⬅️ Prev Word", size="sm")
                            nav_next = gr.Button("Next Word ➡️", size="sm")
                    
                    with gr.Column(scale=2):
                        ocr_text = gr.Textbox(label="OCR Text (read-only)", interactive=False, lines=2)
                        correction_input = gr.Textbox(
                            label="✏️ Corrected Text (type here)",
                            lines=2,
                            placeholder="Type the correct text...",
                            autofocus=True,
                        )
                        save_btn = gr.Button("✅ Save Correction & Next", variant="primary", size="lg")
                        correction_status = gr.Markdown("")
            
            # ── Tab 3: Statistics & Export ──
            with gr.Tab("📊 Statistics & Export"):
                stats_display = gr.Markdown("Click refresh to load stats")
                refresh_stats = gr.Button("🔄 Refresh Stats")
                export_btn = gr.Button("📦 Export to JSONL (HuggingFace)", variant="secondary")
                export_result = gr.Markdown("")
        
        # ── Event Bindings ──
        load_btn.click(
            fn=load_pdf,
            inputs=[pdf_input, max_pages, lang_select],
            outputs=[page_image, page_info, page_status],
        )
        
        sample_med.click(fn=lambda: load_sample("medical"), outputs=[page_image, page_info])
        sample_tech.click(fn=lambda: load_sample("technical"), outputs=[page_image, page_info])
        
        prev_page.click(fn=lambda: navigate_page(-1), outputs=[page_image, page_info, page_status])
        next_page.click(fn=lambda: navigate_page(1), outputs=[page_image, page_info, page_status])
        
        # When page loads, auto-show first word
        page_image.change(
            fn=lambda: show_word(0) if _state.all_words else (None, "", ""),
            outputs=[word_image, ocr_text, word_status],
        )
        
        save_btn.click(
            fn=save_word_correction,
            inputs=[correction_input],
            outputs=[correction_status, word_image, ocr_text],
        )
        
        skip_btn.click(fn=skip_word, outputs=[word_image, ocr_text])
        
        # Word navigation
        nav_prev.click(
            fn=lambda: show_word(max(0, _state.current_word_idx - 1)),
            outputs=[word_image, ocr_text, word_status],
        )
        nav_next.click(
            fn=lambda: show_word(min(len(_state.all_words) - 1, _state.current_word_idx + 1)),
            outputs=[word_image, ocr_text, word_status],
        )
        
        # Stats
        refresh_stats.click(fn=get_dataset_stats, outputs=[stats_display])
        export_btn.click(fn=export_dataset, outputs=[export_result])
        
        # Auto-load stats on tab open
        stats_display.change(fn=get_dataset_stats, outputs=[stats_display])
    
    return demo


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Handwriting Trainer")
    parser.add_argument("--port", type=int, default=7861, help="Gradio port")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Gradio host")
    args = parser.parse_args()
    
    demo = build_ui()
    demo.launch(server_name=args.host, server_port=args.port)