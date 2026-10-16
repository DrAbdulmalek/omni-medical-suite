"""ATR-F4 tests — PDF دفعات + دمج. اصطناعية بالكامل، صفر PHI.

يغطي متطلبات الماستر برومبت §5 (test_atr_batch.py):
  - PDF اصطناعي 3 صفحات، pages-per-batch=1
  - بنية الدفعات (crops/preview/metadata.csv/metadata.xlsx/manifest.json)
  - استمرار الفشل (فشل دفعة لا يوقف الباقي) عبر حقن render_fn فاشل
  - الدمج الصحيح (metadata_all.csv/.xlsx مع عمود batch)
  - محاذاة GT بترتيب RTL + نطاق صفحات + sha256
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz
import pandas as pd
import pytest

import segment_batch
from merge_batches import merge_all
from segment_batch import segment_pdf

WORDS_LINE = ["alpha", "beta", "gamma", "delta", "epsilon"]
N_LINES = 4
DPI = 150


def _make_pdf(path: Path, pages: int = 3) -> None:
    """PDF اصطناعي: نص مطبوع أسود على أبيض (كلمات متباعدة 10pt — بلا PHI)."""
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=595, height=842)
        y = 90.0
        for _ln in range(N_LINES):
            x = 70.0
            for w in WORDS_LINE:
                page.insert_text(fitz.Point(x, y), w, fontsize=14, fontname="helv")
                x += fitz.get_text_length(w, fontname="helv", fontsize=14) + 10.0
            y += 34.0
    doc.save(str(path))
    doc.close()


@pytest.fixture()
def synthetic_pdf(tmp_dir: Path) -> Path:
    pdf = tmp_dir / "doc.pdf"
    _make_pdf(pdf, pages=3)
    return pdf


def test_batch_structure_merge_and_sha256(tmp_dir: Path, synthetic_pdf: Path):
    out = tmp_dir / "out"
    summary = segment_pdf(str(synthetic_pdf), sample="T001", out=str(out),
                          pages_per_batch=1, dpi=DPI)
    assert summary["batches_done"] == 3
    assert summary["batches_failed"] == 0
    assert summary["total_words"] > 0

    # بنية كل دفعة
    for b in ("batch_001", "batch_002", "batch_003"):
        bd = out / b
        assert (bd / "crops").is_dir()
        assert (bd / "preview").is_dir()
        assert (bd / "metadata.csv").exists()
        assert (bd / "metadata.xlsx").exists()
        assert (bd / "manifest.json").exists()

    # الحالة المركزية
    state = json.loads((out / "batch_state.json").read_text(encoding="utf-8"))
    assert set(state["batches"]) == {"batch_001", "batch_002", "batch_003"}
    assert all(v["status"] == "done" for v in state["batches"].values())

    # manifest نهائي بـ sha256 للـPDF
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert man["pdf_sha256"] == hashlib.sha256(synthetic_pdf.read_bytes()).hexdigest()
    assert man["pdf_pages_total"] == 3

    # القصاصات تقابل صفوف metadata
    df = pd.read_csv(out / "batch_001" / "metadata.csv", encoding="utf-8-sig")
    crops = list((out / "batch_001" / "crops").glob("*.png"))
    assert len(df) == len(crops)
    assert len(df) >= N_LINES * 2  # كلمات متعددة في كل سطر
    assert set(["word_id", "crop_path", "draft_text", "corrected_text",
                "gt_state", "batch"]).issubset(df.columns)
    assert (df["gt_state"] == "DRAFT").all()
    # القصاصات غير فارغة فعليًا
    import cv2
    for c in crops[:3]:
        img = cv2.imread(str(c), cv2.IMREAD_GRAYSCALE)
        assert img is not None and img.size > 0

    # الدمج الصحيح
    csv_path, xlsx_path, n = merge_all(str(out))
    all_df = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert n == len(all_df) == 3 * len(df)
    assert "batch" in all_df.columns
    assert set(all_df["batch"]) == {"batch_001", "batch_002", "batch_003"}
    xdf = pd.read_excel(xlsx_path)
    assert len(xdf) == len(all_df)


def test_gt_alignment_rtl_prefill(tmp_dir: Path, synthetic_pdf: Path):
    """أول token منطقي ↔ أول صندوق RTL (أقصى اليمين) — دلالة عربية صريحة."""
    gt_dir = tmp_dir / "gt"
    gt_dir.mkdir()
    # السطر مُصيَّر LTR (alpha يسارًا ... epsilon يمينًا)؛ النص المنطقي RTL يعني
    # أول كلمة عربية = أقصى اليمين => "epsilon" هنا.
    line = " ".join(reversed(WORDS_LINE))  # "epsilon delta gamma beta alpha"
    (gt_dir / "page01.txt").write_text("\n".join([line] * N_LINES), encoding="utf-8")
    out = tmp_dir / "out"
    summary = segment_pdf(str(synthetic_pdf), sample="T002", out=str(out),
                          pages_per_batch=3, dpi=DPI, gt_dir=str(gt_dir))
    assert summary["batches_done"] == 1
    df = pd.read_csv(out / "batch_001" / "metadata.csv", encoding="utf-8-sig")
    p1 = df[df["page"] == 1]
    assert (p1["notes"] == "gt_prefill").all(), f"prefill failed: {p1['notes'].unique()}"
    line1 = p1[p1["line"] == 1].sort_values("word")
    first_row = line1.iloc[0]  # word #1 = أقصى اليمين (RTL)
    assert first_row["draft_text"] == "epsilon"
    assert first_row["box_x0"] == line1["box_x0"].max()  # وهو الأيمن هندسيًا
    # صفحات بلا GT تبقى فارغة المسودة دون أعطاب (الحقول الفارغة في CSV تُقرأ NaN)
    p3 = df[df["page"] == 3]
    assert p3["draft_text"].fillna("").eq("").all()


def test_batch_failure_does_not_stop_others(tmp_dir: Path, synthetic_pdf: Path):
    """فشل دفعة لا يوقف الباقي (حقن render_fn فاشل — بلا أي PHI)."""
    out = tmp_dir / "out"
    real_render = segment_batch.render_page_fitz

    def flaky_render(doc, page_no, dpi):
        if page_no == 2:
            raise RuntimeError("synthetic render failure (test)")
        return real_render(doc, page_no, dpi)

    summary = segment_pdf(str(synthetic_pdf), sample="T003", out=str(out),
                          pages_per_batch=1, dpi=DPI, render_fn=flaky_render)
    assert summary["batches_done"] == 2
    assert summary["batches_failed"] == 1
    state = json.loads((out / "batch_state.json").read_text(encoding="utf-8"))
    assert state["batches"]["batch_002"]["status"] == "failed"
    assert "synthetic render failure" in state["batches"]["batch_002"]["error"]
    assert state["batches"]["batch_001"]["status"] == "done"
    assert state["batches"]["batch_003"]["status"] == "done"
    # الدمج يكتفي بالدفعات الناجحة
    csv_path, _xlsx, n = merge_all(str(out))
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert n == len(df) and set(df["batch"]) == {"batch_001", "batch_003"}


def test_page_range_subset(tmp_dir: Path, synthetic_pdf: Path):
    out = tmp_dir / "out"
    summary = segment_pdf(str(synthetic_pdf), sample="T004", out=str(out),
                          pages_per_batch=5, dpi=DPI, start_page=2, end_page=3)
    assert summary["pages_requested"] == [2, 3]
    assert summary["batches_done"] == 1  # صفحتان في دفعة واحدة
    assert summary["batches_failed"] == 0
    bd = out / "batch_001"
    df = pd.read_csv(bd / "metadata.csv", encoding="utf-8-sig")
    assert set(df["page"]) == {2, 3}
