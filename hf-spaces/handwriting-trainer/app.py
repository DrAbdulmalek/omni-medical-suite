#!/usr/bin/env python3
"""
Handwriting OCR Trainer — Standalone HF Space
==============================================
Interactive word-level correction UI for building ground-truth training data
from scanned handwritten documents. Supports Arabic, English, and German.

Workflow: PDF -> pages -> word segmentation -> OCR -> user correction -> DB + JSONL

Deploy: Push this directory to huggingface.co/spaces/DrAbdulmalek/handwriting-trainer
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import gradio as gr
import numpy as np
from PIL import Image

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

# ── Tesseract Language Detection ─────────────────────────────────────────

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
        return str(
            pytesseract.image_to_string(img, lang=actual_lang, config="--psm 6")
        ).strip()
    except Exception:
        return ""


def _detect_language(text: str) -> str:
    """Detect dominant language from OCR text content."""
    if not text:
        return "unknown"
    arabic_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text))
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


# ── Word Segmentation ────────────────────────────────────────────────────

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
        raise ImportError(
            "PyMuPDF (fitz) required. Install: pip install PyMuPDF"
        )

    doc = fitz.open(pdf_path)
    pages: list[PageData] = []

    for i in range(min(max_pages, doc.page_count)):
        page = doc[i]
        rotation = page.rotation

        # Normalize: always render upright
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
    page: PageData, min_word_height: int = 15, ocr_lang: str = "eng"
) -> list[WordBox]:
    """Segment a page image into word-level boxes using OpenCV or Tesseract fallback."""
    img = page.image.copy()
    h, w = img.shape[:2]

    if HAS_CV2:
        words = _segment_cv2(img, h, w, min_word_height, ocr_lang)
    else:
        words = _segment_tesseract(img, h, w, min_word_height, ocr_lang)

    # Sort top-to-bottom; Arabic words sort right-to-left within a line
    words.sort(
        key=lambda wb: (
            wb.bbox[1],
            -wb.bbox[0] if wb.language == "arabic" else wb.bbox[0],
        )
    )
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
        ocr_text = _run_tesseract(word_img, lang=ocr_lang)
        lang = _detect_language(ocr_text)

        words.append(WordBox(
            image=word_img, bbox=(x1, y1, x2, y2),
            ocr_text=ocr_text, page_num=0, language=lang,
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

        words.append(WordBox(
            image=word_img, bbox=(x1, y1, x2, y2),
            ocr_text=text, page_num=0, confidence=conf, language=lang,
        ))
    return words


# ── Corrections Database ──────────────────────────────────────────────────

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
    """Save a single word correction to the database. Returns True if new/updated."""
    if not corrected_text.strip() or corrected_text == ocr_text:
        return False

    # Hash the word image for dedup
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
                source_file, page_num, bbox, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (img_hash, ocr_text, corrected_text, language,
             source_file, page_num, json.dumps(bbox), confidence),
        )
        conn.commit()
    finally:
        conn.close()
    return True


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
        return {"total_corrections": total, "by_language": by_lang}
    finally:
        conn.close()


def export_to_jsonl() -> str:
    """Export all corrections as JSONL. Returns the file path."""
    conn = _init_db()
    try:
        rows = conn.execute(
            "SELECT ocr_text, corrected_text, language, source_file, "
            "       page_num, confidence, created_at "
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
                    "created_at": row[6],
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return str(EXPORT_PATH)
    finally:
        conn.close()


# ── App State ─────────────────────────────────────────────────────────────

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


_state = SessionState()

# ── Gradio Callbacks ─────────────────────────────────────────────────────

def cb_load_pdf(pdf_file, max_pages: int, ocr_lang: str) -> tuple:
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
    _state.all_words = segment_words(page, ocr_lang=_state.ocr_lang)
    _state.current_word_idx = 0

    page_pil = Image.fromarray(page.image)
    rot_icon = "🔄" if page.rotation else "✅"
    info = (
        f"Page {page_idx + 1}/{len(_state.pages)} | "
        f"{rot_icon} Rotation: {page.rotation}° | "
        f"Words found: {len(_state.all_words)} | "
        f"Session corrections: {_state.session_corrections}"
    )
    return page_pil, info, ""


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
    status = (
        f"Word {word_idx + 1}/{len(_state.all_words)} | "
        f"{lang_emoji} {word.language} | "
        f"Page: {word.page_num} | "
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

    saved = save_correction(
        ocr_text=word.ocr_text,
        corrected_text=correction_text,
        word_image=word.image,
        language=word.language,
        source_file=_state.source_file,
        page_num=word.page_num,
        bbox=word.bbox,
        confidence=word.confidence,
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
        msg = f"Saved! ({_state.session_corrections} total) — Last word on this page" if saved else "Last word"
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
    lines.append(f"\n**Current Session:** {_state.session_corrections} corrections")
    pages_done = _state.current_page_idx + 1 if _state.pages else 0
    pages_total = len(_state.pages)
    lines.append(f"**Pages processed:** {pages_done}/{pages_total}")

    # Available OCR languages
    lines.append(f"\n**Available OCR langs:** {', '.join(_AVAILABLE_OCR_LANGS)}")
    if _MULTILANG_COMBOS:
        lines.append(f"**Multi-lang combos:** {', '.join(_MULTILANG_COMBOS)}")
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
    """Build and return the Gradio Blocks UI."""
    with gr.Blocks(
        title="Handwriting Trainer — Arabic/English/German",
        css=CUSTOM_CSS,
        theme=gr.themes.Soft(),
    ) as demo:
        gr.Markdown("""
        # ✍️ Handwriting OCR Trainer — Interactive Word-Level Correction

        **Upload scanned handwritten PDF → Word segmentation → OCR → Correct → Export for training**

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
                        load_btn = gr.Button(
                            "Load PDF", variant="primary", size="lg"
                        )

                    with gr.Column(scale=2):
                        page_image = gr.Image(
                            label="Current Page", type="pil",
                            elem_classes="page-image",
                        )
                        page_info = gr.Markdown("")
                        page_status = gr.Markdown("")

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
                            label="OCR Text (read-only)",
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

            # ── Tab 3: Statistics & Export ──
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
            inputs=[pdf_input, max_pages, lang_select],
            outputs=[page_image, page_info, page_status],
        )

        prev_page.click(
            fn=lambda: cb_navigate_page(-1),
            outputs=[page_image, page_info, page_status],
        )
        next_page.click(
            fn=lambda: cb_navigate_page(1),
            outputs=[page_image, page_info, page_status],
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


# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Handwriting OCR Trainer")
    parser.add_argument(
        "--port", type=int,
        default=int(os.environ.get("GRADIO_SERVER_PORT", 7860)),
        help="Gradio server port",
    )
    parser.add_argument(
        "--host", type=str,
        default=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
        help="Gradio server host",
    )
    args = parser.parse_args()

    print(f"Available OCR languages: {_AVAILABLE_OCR_LANGS}")
    print(f"Multi-lang combos: {_MULTILANG_COMBOS}")
    print(f"Data directory: {DATA_DIR}")
    print(f"Database: {DB_PATH}")

    demo = build_ui()
    demo.launch(server_name=args.host, server_port=args.port)