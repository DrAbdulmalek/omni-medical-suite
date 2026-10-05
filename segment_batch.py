#!/usr/bin/env python3
"""ATR-F4 — معالجة PDF متعدد الصفحات بحفظ دفعات (word crops + metadata).

يحول PDF (ممسوح/نصي) إلى دفعات قصاصات كلمات مع جدول metadata يقابل كل قصاصة
بنصها (draft_text) ليصححه المالك ثم يُدرَّب عليه (راجع train_server.py).

البنية لكل دفعة:
    batch_NNN/{crops/, preview/, metadata.csv, metadata.xlsx, manifest.json}
مركزيًا:
    batch_state.json  (done/failed لكل دفعة — فشل دفعة لا يوقف الباقي)
    manifest.json     (نهائي، يحوي sha256 للـPDF)

الاستخدام:
    python segment_batch.py --pdf samples/S002.pdf --sample S002 \
        --pages-per-batch 5 --dpi 300 --out output/S002 \
        [--start-page 1] [--end-page 17] [--gt-dir data/handwriting-ar/ground_truth/S001]

ملاحظة إعادة بناء: يستورد preprocess/detect_layout/extract_words من
ahw.segment (إعادة بناء موثقة — راجع ahw/segment.py). التنفيذ عبر PyMuPDF.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
import time
import traceback
from typing import Callable, Dict, List, Optional

import cv2
import fitz  # PyMuPDF
import numpy as np
import pandas as pd

from ahw.segment import crop_save, detect_layout, extract_words, preview_with_boxes, preprocess

META_COLUMNS = [
    "word_id", "sample_id", "page", "batch", "line", "word", "crop_path",
    "box_x0", "box_y0", "box_x1", "box_y1", "width", "height",
    "draft_text", "corrected_text", "gt_state", "reviewer", "notes",
]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def render_page_fitz(doc: fitz.Document, page_no: int, dpi: int = 300) -> np.ndarray:
    """تصيير صفحة (1-based) إلى رمادي عبر PyMuPDF."""
    page = doc[page_no - 1]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY,
                          alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width).copy()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# GT prefill (best-effort DRAFT — يصححه المالك)
# ---------------------------------------------------------------------------
def load_gt_text(gt_dir: str, page: int) -> Optional[str]:
    path = os.path.join(gt_dir, f"page{page:02d}.txt")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def align_gt_tokens(gt_text: str, n_lines: int, order: str = "rtl"):
    """محاذاة أسطر GT مع الأسطر المكتشفة (best-effort).

    order="rtl": أول token منطقي ↔ أول صندوق RTL (أقصى اليمين) — العربي.
    ترجع None إذا عدد الأسطر لا يطابق (لا تفضيل خاطئ بصمت).
    """
    lines = [ln.strip() for ln in (gt_text or "").splitlines() if ln.strip()]
    if len(lines) != n_lines:
        return None
    out = []
    for ln in lines:
        toks = ln.split()
        out.append(toks if order == "rtl" else list(reversed(toks)))
    return out


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------
def process_page(doc, page_no: int, batch_id: str, sample: str, dpi: int,
                 crops_dir: str, preview_dir: str,
                 gt_text: Optional[str] = None, gt_order: str = "rtl",
                 render_fn: Callable = render_page_fitz) -> List[dict]:
    """معالجة صفحة واحدة: تصيير -> تجزئة -> قصاصات -> صفوف metadata."""
    gray = render_fn(doc, page_no, dpi)
    ink = preprocess(gray)
    lines, graphics = detect_layout(ink)
    gt_tokens = align_gt_tokens(gt_text, len(lines), order=gt_order) \
        if gt_text is not None else None
    rows: List[dict] = []
    word_idx = 0
    for li, lb in enumerate(lines, start=1):
        wboxes = extract_words(gray, lb, ink=ink)
        line_toks = gt_tokens[li - 1] if gt_tokens and li - 1 < len(gt_tokens) else None
        tok_mismatch = (line_toks is not None and len(line_toks) != len(wboxes))
        for wi, wb in enumerate(wboxes, start=1):
            word_idx += 1
            fname = f"p{page_no:02d}_l{li:02d}_w{word_idx:03d}.png"
            size = crop_save(gray, wb, os.path.join(crops_dir, fname))
            if size is None:
                word_idx -= 1
                continue
            draft = ""
            notes = ""
            if line_toks is not None and not tok_mismatch and wi <= len(line_toks):
                draft = line_toks[wi - 1]
                notes = "gt_prefill"
            elif tok_mismatch:
                notes = "gt_token_mismatch"
            rows.append({
                "word_id": f"{sample}_p{page_no:02d}_w{word_idx:03d}",
                "sample_id": sample,
                "page": page_no,
                "batch": batch_id,
                "line": li,
                "word": word_idx,
                "crop_path": f"crops/{fname}",
                "box_x0": int(wb[0]), "box_y0": int(wb[1]),
                "box_x1": int(wb[2]), "box_y1": int(wb[3]),
                "width": int(size[0]), "height": int(size[1]),
                "draft_text": draft,
                "corrected_text": "",
                "gt_state": "DRAFT",
                "reviewer": "",
                "notes": notes,
            })
    vis = preview_with_boxes(gray, [tuple(r[k] for k in
              ("box_x0", "box_y0", "box_x1", "box_y1")) for r in rows], graphics)
    cv2.imwrite(os.path.join(preview_dir, f"p{page_no:02d}_preview.png"), vis)
    gc.collect()  # بين الصفحات (متطلب ATR-F4)
    return rows


def _write_batch_files(batch_dir: str, rows: List[dict], manifest: dict) -> None:
    df = pd.DataFrame(rows, columns=META_COLUMNS)
    df.to_csv(os.path.join(batch_dir, "metadata.csv"), index=False,
              encoding="utf-8-sig")
    df.to_excel(os.path.join(batch_dir, "metadata.xlsx"), index=False,
                engine="openpyxl")
    with open(os.path.join(batch_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)


def _update_state(out_dir: str, state: dict) -> None:
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    tmp = os.path.join(out_dir, "batch_state.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(out_dir, "batch_state.json"))


def segment_pdf(pdf_path: str, sample: str, out: str, pages_per_batch: int = 5,
                dpi: int = 300, start_page: Optional[int] = None,
                end_page: Optional[int] = None, gt_dir: Optional[str] = None,
                gt_order: str = "rtl",
                render_fn: Optional[Callable] = None) -> dict:
    """ATR-F4 core API — يعيد ملخص التنفيذ (قابل للاختبار مباشرة)."""
    if pages_per_batch < 1:
        raise ValueError("pages_per_batch must be >= 1")
    doc = fitz.open(pdf_path)
    n_pages = doc.page_count
    p0 = max(1, start_page or 1)
    p1 = min(n_pages, end_page or n_pages)
    if p0 > p1:
        raise ValueError(f"empty page range [{p0},{p1}] (pdf has {n_pages} pages)")
    pages = list(range(p0, p1 + 1))
    render_fn = render_fn or render_page_fitz

    os.makedirs(out, exist_ok=True)
    state: Dict = {"sample_id": sample, "pdf": os.path.abspath(pdf_path),
                   "pdf_sha256": sha256_file(pdf_path), "batches": {}}
    batches_done, batches_failed, total_words = 0, 0, 0

    for bi, chunk_start in enumerate(range(0, len(pages), pages_per_batch), start=1):
        batch_id = f"batch_{bi:03d}"
        chunk = pages[chunk_start:chunk_start + pages_per_batch]
        batch_dir = os.path.join(out, batch_id)
        crops_dir = os.path.join(batch_dir, "crops")
        preview_dir = os.path.join(batch_dir, "preview")
        os.makedirs(crops_dir, exist_ok=True)
        os.makedirs(preview_dir, exist_ok=True)
        state["batches"][batch_id] = {"status": "running", "pages": chunk}
        _update_state(out, state)
        try:
            rows: List[dict] = []
            page_word_counts: Dict[int, int] = {}
            for page_no in chunk:
                gt_text = load_gt_text(gt_dir, page_no) if gt_dir else None
                prows = process_page(doc, page_no, batch_id, sample, dpi,
                                     crops_dir, preview_dir,
                                     gt_text=gt_text, gt_order=gt_order,
                                     render_fn=render_fn)
                rows.extend(prows)
                page_word_counts[page_no] = len(prows)
            manifest = {
                "sample": sample, "batch": batch_id, "pages": chunk,
                "dpi": dpi, "pages_per_batch": pages_per_batch,
                "n_words": len(rows), "words_per_page": page_word_counts,
                "engine": "ahw.segment reconstructed v1 (S001-v7 lineage)",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            _write_batch_files(batch_dir, rows, manifest)
            state["batches"][batch_id] = {
                "status": "done", "pages": chunk, "n_words": len(rows),
            }
            batches_done += 1
            total_words += len(rows)
        except Exception:  # فشل دفعة لا يوقف الباقي (متطلب ATR-F4)
            state["batches"][batch_id] = {
                "status": "failed", "pages": chunk,
                "error": traceback.format_exc(limit=3),
            }
            batches_failed += 1
        _update_state(out, state)

    final_manifest = {
        "sample": sample, "pdf": os.path.abspath(pdf_path),
        "pdf_sha256": state["pdf_sha256"], "pdf_pages_total": n_pages,
        "pages_requested": pages, "pages_per_batch": pages_per_batch, "dpi": dpi,
        "batches_done": batches_done, "batches_failed": batches_failed,
        "total_words": total_words,
        "batches": {k: v["status"] for k, v in state["batches"].items()},
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(final_manifest, fh, ensure_ascii=False, indent=1)
    doc.close()
    return final_manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="ATR-F4 batch PDF -> word crops")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--pages-per-batch", type=int, default=5)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--start-page", type=int, default=None)
    ap.add_argument("--end-page", type=int, default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gt-dir", default=None,
                    help="مجلد ground_truth يحوي pageNN.txt لتعبئة draft_text (DRAFT)")
    ap.add_argument("--gt-order", choices=["rtl", "ltr"], default="rtl")
    args = ap.parse_args(argv)
    summary = segment_pdf(args.pdf, args.sample, args.out,
                          pages_per_batch=args.pages_per_batch, dpi=args.dpi,
                          start_page=args.start_page, end_page=args.end_page,
                          gt_dir=args.gt_dir, gt_order=args.gt_order)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    # كل الدفعات فشلت -> إشارة خطأ (فشل جزئي = نجاح مع تسجيل الحالة)
    return 0 if summary["batches_done"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
