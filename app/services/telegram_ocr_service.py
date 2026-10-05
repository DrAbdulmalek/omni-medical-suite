# app/services/telegram_ocr_service.py
"""Telegram OCR Pipeline — خط معالجة التعرف الضوئي

Local (no-cloud) OCR pipeline for channel files:
    image/pdf -> preprocess -> Tesseract (ara+eng) -> word/line boxes
              -> pattern-store refinement (ABBYY-style learned 字模)
              -> structured result

Engine notes:
    * Tesseract data dir defaults to /home/z/my-project/data/tessdata which
      bundles ara + eng + osd (override with OMNI_TESSDATA_PREFIX).
    * PDFs are rasterized page-by-page with PyMuPDF (first 5 pages).
    * Pattern refinement: when a word-shape matches a learned pattern with
      high confidence, the pattern's label (human-verified text) wins and the
      pattern usage counter is incremented — the system literally improves
      with every annotated slice.

Result contract (kept JSON-serializable):
    {"engine": {...}, "text": str, "pages": [{...}], "lines": [...],
     "words": [...], "pattern_hits": [...], "stats": {...}}
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_SRC_OCR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src", "ocr"))
if _SRC_OCR_DIR not in sys.path:
    sys.path.insert(0, _SRC_OCR_DIR)

DEFAULT_TESSDATA = "/home/z/my-project/data/tessdata"
SUPPORTED_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
MAX_OCR_PAGES = 5


def _tessdata_prefix() -> str:
    return os.getenv("OMNI_TESSDATA_PREFIX", DEFAULT_TESSDATA)


def engine_status() -> Dict[str, Any]:
    """Availability report for UI/health endpoints."""
    import shutil
    tesseract_bin = shutil.which("tesseract")
    prefix = _tessdata_prefix()
    langs = []
    if tesseract_bin and os.path.isdir(prefix):
        try:
            out = os.popen(f"TESSDATA_PREFIX={prefix} tesseract --list-langs 2>/dev/null").read()
            langs = [ln.strip() for ln in out.splitlines()[1:] if ln.strip()]
        except Exception:
            pass
    fitz_ok = False
    try:
        import fitz  # noqa: F401
        fitz_ok = True
    except Exception:
        pass
    return {
        "tesseract": bool(tesseract_bin),
        "tessdata_prefix": prefix,
        "languages": langs,
        "arabic": "ara" in langs,
        "pdf": fitz_ok,
        "cloud": False,  # this pipeline is intentionally local-only
    }


# --------------------------------------------------------------------- io
def load_image(path: str) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)  # handles unicode paths on all OSes
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"cannot decode image: {path}")
    return img


def pdf_to_images(path: str, max_pages: int = MAX_OCR_PAGES) -> List[np.ndarray]:
    import fitz
    doc = fitz.open(path)
    pages: List[np.ndarray] = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        pages.append(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    doc.close()
    if not pages:
        raise ValueError("PDF has no rasterizable pages")
    return pages


def is_pdf(path: str) -> bool:
    return path.lower().endswith(".pdf")


# ------------------------------------------------------------ preprocess
def preprocess(img: np.ndarray) -> np.ndarray:
    """Light document-oriented preprocessing (kept conservative to protect
    thin Arabic diacritics): grayscale, optional upscale, fast denoise."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape[:2]
    if max(h, w) < 1400:
        scale = 1600.0 / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, h=9, templateWindowSize=7, searchWindowSize=21)
    return gray


# ------------------------------------------------------------------- ocr
def _image_to_data(gray: np.ndarray, lang: str, psm: int) -> Dict[str, Any]:
    import pytesseract
    cfg = f"--oem 3 --psm {psm}"
    os.environ.setdefault("TESSDATA_PREFIX", _tessdata_prefix())
    # pytesseract reads TESSDATA_PREFIX from env at call time:
    os.environ["TESSDATA_PREFIX"] = _tessdata_prefix()
    data = pytesseract.image_to_data(gray, lang=lang, config=cfg,
                                     output_type=pytesseract.Output.DICT)
    return data


def _group_lines(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    words: List[Dict[str, Any]] = []
    n = len(data.get("text", []))
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        conf = float(data["conf"][i]) if str(data["conf"][i]) not in ("-1", "") else -1.0
        if not txt:
            continue
        words.append({
            "text": txt, "conf": round(conf, 1),
            "bbox": [int(data["left"][i]), int(data["top"][i]),
                     int(data["width"][i]), int(data["height"][i])],
            "line_key": (data.get("block_num", ["0"])[i], data.get("par_num", ["0"])[i],
                         data.get("line_num", ["0"])[i]),
        })
    lines_map: Dict[Any, List[Dict[str, Any]]] = {}
    for w in words:
        lines_map.setdefault(w["line_key"], []).append(w)
    lines = []
    for key, ws in lines_map.items():
        x0 = min(w["bbox"][0] for w in ws)
        y0 = min(w["bbox"][1] for w in ws)
        x1 = max(w["bbox"][0] + w["bbox"][2] for w in ws)
        y1 = max(w["bbox"][1] + w["bbox"][3] for w in ws)
        text = " ".join(w["text"] for w in ws)
        confs = [w["conf"] for w in ws if w["conf"] >= 0]
        lines.append({"text": text,
                      "conf": round(sum(confs) / len(confs), 1) if confs else -1.0,
                      "bbox": [x0, y0, x1 - x0, y1 - y0]})
    return lines, words


def _pattern_refine(words: List[Dict[str, Any]], page_img: np.ndarray) -> List[Dict[str, Any]]:
    """Replace word text with learned-pattern labels when the shape matches."""
    try:
        from pattern_store import PatternStore  # sibling in src/ocr
    except Exception as exc:  # pattern store is optional sugar
        logger.debug("pattern store unavailable: %s", exc)
        return words
    store = PatternStore()
    if store.count() == 0:
        return words
    refined = []
    for w in words:
        x, y, ww, hh = w["bbox"]
        pad = 2
        crop = page_img[max(0, y - pad):y + hh + pad, max(0, x - pad):x + ww + pad]
        hit = None
        if crop.size:
            hits = store.match(crop, top_k=1, min_score=0.93, level="word")
            if hits:
                hit = hits[0]
        entry = dict(w)
        if hit:
            entry["text_original"] = w["text"]
            entry["text"] = hit["label"]
            entry["pattern_key"] = hit["key"]
            entry["pattern_score"] = hit["score"]
        refined.append(entry)
    return refined


def run_ocr(path: str, lang: str = "ara+eng", psm: int = 6,
            use_patterns: bool = True) -> Dict[str, Any]:
    """Run the full local pipeline on an image or PDF. Returns structured result."""
    started = time.time()
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    if is_pdf(path):
        pages_img = pdf_to_images(path)
        source_kind = "pdf"
    else:
        pages_img = [load_image(path)]
        source_kind = "image"

    all_text: List[str] = []
    pages_out: List[Dict[str, Any]] = []
    words_all: List[Dict[str, Any]] = []
    pattern_hits: List[Dict[str, Any]] = []

    for page_no, img in enumerate(pages_img, start=1):
        gray = preprocess(img)
        data = _image_to_data(gray, lang=lang, psm=psm)
        lines, words = _group_lines(data)
        if use_patterns:
            words = _pattern_refine(words, gray)
            pattern_hits = [w for w in words if w.get("pattern_key")]
            # rebuild line texts from (possibly refined) words
            lines_map: Dict[Any, List[Dict[str, Any]]] = {}
            for w in words:
                lines_map.setdefault(w["line_key"], []).append(w)
            lines = []
            for _key, ws in lines_map.items():
                text = " ".join(w["text"] for w in ws)
                confs = [w["conf"] for w in ws if w["conf"] >= 0]
                x0 = min(w["bbox"][0] for w in ws)
                y0 = min(w["bbox"][1] for w in ws)
                x1 = max(w["bbox"][0] + w["bbox"][2] for w in ws)
                y1 = max(w["bbox"][1] + w["bbox"][3] for w in ws)
                lines.append({"text": text,
                              "conf": round(sum(confs) / len(confs), 1) if confs else -1.0,
                              "bbox": [x0, y0, x1 - x0, y1 - y0]})
        page_text = "\n".join(l["text"] for l in lines)
        all_text.append(page_text)
        pages_out.append({"page": page_no, "text": page_text, "lines": lines,
                          "n_words": len(words)})
        words_all.extend([{**w, "page": page_no} for w in words])

    result = {
        "engine": {"name": "tesseract-local", "lang": lang, "psm": psm,
                   "patterns": use_patterns},
        "source": {"path": os.path.abspath(path), "kind": source_kind,
                   "pages": len(pages_img)},
        "text": "\n\n".join(t for t in all_text if t),
        "pages": pages_out,
        "words": words_all,
        "pattern_hits": pattern_hits,
        "stats": {"elapsed_s": round(time.time() - started, 2),
                  "words": len(words_all),
                  "pattern_refined": len(pattern_hits)},
    }
    return result


def draw_boxes(img: np.ndarray, words: List[Dict[str, Any]],
               highlight_pattern: bool = True) -> np.ndarray:
    """Render detected word boxes on the image for UI review."""
    canvas = img.copy()
    for w in words:
        x, y, ww, hh = w["bbox"]
        color = (0, 165, 255) if w.get("pattern_key") else (40, 160, 60)
        cv2.rectangle(canvas, (x, y), (x + ww, y + hh), color, 2)
    return canvas
