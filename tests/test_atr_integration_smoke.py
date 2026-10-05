"""ATR-06 — Integration Smoke Test (تكاملي، بيانات اصطناعية 100%، صفر PHI).

يثبت خط الأنابيب كاملًا من طرف إلى طرف:
    PDF اصطناعي (3 صفحات) → segment_batch (دفعات) → merge_batches (دمج)
    → تصحيحات وهمية (corrections.xlsx) → تدريب smoke (epoch واحد، نموذج
    dry_run صغير — بلا أي تنزيل أوزان)

هذا هو الاختبار الذي يمسك "درز" التكامل بين مخرجات segment_batch الحقيقية
(crop_path نسبي لمجلد الدفعة + عمود batch منفصل) وما تستهلكه نواة التدريب
وخادم التصحيح. يُشغَّل أيضًا كسكريبت مستقل: scripts/atr_smoke.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import pandas as pd
import pytest

from ahw.train_trocr import TrainConfig, load_corrections, run_training
from merge_batches import merge_all
from segment_batch import segment_pdf

WORDS = ["alpha", "beta", "gamma", "delta", "epsilon"]
DPI = 150
# تسميات عربية وهمية (غير طبية حقيقية) لدفعات التدريب الاصطناعية
FAKE_LABELS = ["المريض", "ألم", "ضغط", "الدواء", "الجراحة"]


def _make_pdf(path: Path, pages: int = 3) -> None:
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=595, height=842)
        y = 90.0
        for _ln in range(4):
            x = 70.0
            for w in WORDS:
                page.insert_text(fitz.Point(x, y), w, fontsize=14, fontname="helv")
                x += fitz.get_text_length(w, fontname="helv", fontsize=14) + 10.0
            y += 34.0
    doc.save(str(path))
    doc.close()


def _fake_corrections(sample_dir: Path) -> Path:
    """يحاكي تصحيح بشري: يقرأ metadata_all ويملأ نصًا لكل قصاصة."""
    merged = pd.read_csv(sample_dir / "metadata_all.csv")
    merged["text"] = [FAKE_LABELS[i % len(FAKE_LABELS)]
                      for i in range(len(merged))]
    merged["status"] = "CORRECTED"
    merged["source_page"] = merged["page"].astype(str)
    out = sample_dir / "corrections.xlsx"
    merged.to_excel(out, index=False, engine="openpyxl")
    return out


def test_full_pipeline_end_to_end(tmp_path):
    # حارس CI (ATR-04d): التدريب يتطلب torch+transformers — تُتخطى في بيئات
    # بلا تبعيات ATR بدل الفشل؛ بقية اختبارات الوحدة تعمل أينما وُجد fitz/pandas.
    pytest.importorskip("torch", reason="pipeline training step requires torch")
    pytest.importorskip("transformers",
                        reason="pipeline training step requires transformers")
    work = tmp_path / "work"
    work.mkdir()
    pdf = work / "scan.pdf"
    _make_pdf(pdf, pages=3)

    # 1) دفعات: صفحة لكل دفعة → 3 دفعات
    out_dir = work / "output" / "T001"
    summary = segment_pdf(str(pdf), sample="T001", out=str(out_dir),
                          pages_per_batch=1, dpi=DPI)
    assert summary["batches_done"] == 3
    assert summary["batches_failed"] == 0
    assert summary["total_words"] > 0
    assert (out_dir / "batch_state.json").exists()
    assert (out_dir / "manifest.json").exists()
    man = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(man["pdf_sha256"]) == 64

    # 2) دمج
    csv_path, xlsx_path, n_rows = merge_all(str(out_dir))
    assert Path(csv_path).exists() and Path(xlsx_path).exists()
    assert n_rows == summary["total_words"]
    merged = pd.read_csv(csv_path)
    assert "batch" in merged.columns           # عمود الدفعة مُضاف
    assert merged["batch"].nunique() == 3
    # درز التكامل: المسار الحقيقي للقصاصة = <batch>/<crop_path>
    first = merged.iloc[0]
    true_crop = out_dir / first["batch"] / first["crop_path"]
    assert true_crop.exists(), f"قصاصة غير قابلة للحل: {true_crop}"

    # 3) تصحيحات وهمية
    corr = _fake_corrections(out_dir)
    assert corr.exists()
    loaded = load_corrections(out_dir)
    assert len(loaded) == n_rows
    assert (loaded["text"].str.strip() != "").all()

    # 4) تدريب smoke على القصاصات الحقيقية (نموذج dry_run — بلا تنزيل)
    model_out = tmp_path / "models" / "smoke"
    result = run_training(
        TrainConfig(mode="full", dry_run_model=True,
                    data_dir=str(out_dir), output_dir=str(model_out),
                    epochs=1, batch=2, lr=5e-4),
    )
    assert result["mode"] == "full"
    assert result["train_samples"] > 0
    assert result["final_loss"] > 0.0
    # full mode يحفظ الأوزان (نموذج dry_run صغير)
    assert result["output_dir"] == str(model_out)
    assert model_out.exists()
    # المعالج المحفوظ قابل لإعادة التحميل
    assert (model_out / "tokenizer_config.json").exists() or \
        any(model_out.glob("*token*")) or any(model_out.glob("*.json"))


def test_merge_is_idempotent_and_batch_column_present(tmp_path):
    work = tmp_path / "w2"
    work.mkdir()
    pdf = work / "d.pdf"
    _make_pdf(pdf, pages=2)
    out_dir = work / "out" / "T002"
    segment_pdf(str(pdf), sample="T002", out=str(out_dir),
                pages_per_batch=1, dpi=DPI)
    merge_all(str(out_dir))
    merge_all(str(out_dir))  # تشغيل ثانٍ لا يفسد
    merged = pd.read_csv(out_dir / "metadata_all.csv")
    assert "batch" in merged.columns
    assert set(merged["batch"].unique()) == {"batch_001", "batch_002"}


def test_correction_server_serves_real_batch_crops(tmp_path, monkeypatch):
    """خادم التصحيح يقدّم قصاصة حقيقية من بنية الدفعات (درز المسار)."""
    pytest.importorskip("flask", reason="correction_server requires flask")
    import correction_server

    work = tmp_path / "cs"
    work.mkdir()
    pdf = work / "d.pdf"
    _make_pdf(pdf, pages=1)
    root = work / "output"
    out_dir = root / "T003"
    segment_pdf(str(pdf), sample="T003", out=str(out_dir),
                pages_per_batch=5, dpi=DPI)
    merge_all(str(out_dir))

    monkeypatch.setitem(correction_server._STATE, "sample", "T003")
    monkeypatch.setitem(correction_server._STATE, "root", str(root))
    c = correction_server.app.test_client()

    words = c.get("/api/words").get_json()["words"]
    assert len(words) > 0
    # الخادم يقدّم مسارًا جاهزًا (crop_url) يحل إلى قصاصة موجودة فعلًا
    crop_url = words[0]["crop_url"]
    assert crop_url.startswith("batch_")
    r = c.get(f"/crops/{crop_url}")
    assert r.status_code == 200, f"فشل تقديم {crop_url}"
    assert (out_dir / crop_url).exists()
