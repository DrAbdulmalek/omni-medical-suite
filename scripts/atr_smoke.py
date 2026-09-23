#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATR-06 — سكربت الدخان التكاملي المستقل (بيانات اصطناعية، صفر PHI).

يشغّل خط الأنابيب كاملًا خارج pytest ويطبع أرقامًا حقيقية:
    PDF اصطناعي → segment_batch → merge_batches → تصحيحات وهمية
    → تدريب smoke (نموذج dry_run صغير، بلا تنزيل أوزان)

الاستخدام:
    python scripts/atr_smoke.py [--workdir /tmp/atr-smoke]

لا يلمس بيانات طبية حقيقية ولا ينزّل أي أوزان. عند النجاح يطبع SMOKE: PASS.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

# السماح بالتشغيل من جذر المستودع
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import fitz  # noqa: E402
import pandas as pd  # noqa: E402

from ahw.train_trocr import TrainConfig, load_corrections, run_training  # noqa: E402
from merge_batches import merge_all  # noqa: E402
from segment_batch import segment_pdf  # noqa: E402

WORDS = ["alpha", "beta", "gamma", "delta", "epsilon"]
FAKE_LABELS = ["المريض", "ألم", "ضغط", "الدواء", "الجراحة"]


def make_pdf(path: Path, pages: int = 3) -> None:
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=595, height=842)
        y = 90.0
        for _ in range(4):
            x = 70.0
            for w in WORDS:
                page.insert_text(fitz.Point(x, y), w, fontsize=14, fontname="helv")
                x += fitz.get_text_length(w, fontname="helv", fontsize=14) + 10.0
            y += 34.0
    doc.save(str(path))
    doc.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workdir", default=None,
                    help="مجلد عمل مؤقت (افتراضيًا يُنشأ ثم يُحذف)")
    ap.add_argument("--keep", action="store_true",
                    help="عدم حذف مجلد العمل بعد الانتهاء")
    args = ap.parse_args(argv)

    tmp = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="atr-smoke-"))
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"🔬 ATR SMOKE — workdir={tmp}")

    # 1) PDF اصطناعي
    pdf = tmp / "scan.pdf"
    make_pdf(pdf, pages=3)
    print(f"1) PDF اصطناعي: 3 صفحات، {pdf.stat().st_size} bytes (بلا PHI)")

    # 2) دفعات
    out_dir = tmp / "output" / "SMOKE"
    summary = segment_pdf(str(pdf), sample="SMOKE", out=str(out_dir),
                          pages_per_batch=1, dpi=150)
    print(f"2) segment_batch: {summary['batches_done']} دفعات ناجحة، "
          f"{summary['batches_failed']} فاشلة، {summary['total_words']} كلمة، "
          f"sha256={summary['pdf_sha256'][:12]}…")
    assert summary["batches_done"] == 3 and summary["batches_failed"] == 0

    # 3) دمج
    csv_path, xlsx_path, n_rows = merge_all(str(out_dir))
    merged = pd.read_csv(csv_path)
    print(f"3) merge_batches: {n_rows} صف → metadata_all.csv/.xlsx، "
          f"عمود batch بقيم {sorted(merged['batch'].unique())}")
    assert "batch" in merged.columns

    # 4) تصحيحات وهمية
    merged["text"] = [FAKE_LABELS[i % len(FAKE_LABELS)] for i in range(len(merged))]
    merged["status"] = "CORRECTED"
    merged["source_page"] = merged["page"].astype(str)
    merged.to_excel(out_dir / "corrections.xlsx", index=False, engine="openpyxl")
    loaded = load_corrections(out_dir)
    print(f"4) corrections وهمية: {len(loaded)} تصحيحًا قابلًا للتحميل")
    assert len(loaded) == n_rows

    # 5) تدريب smoke (نموذج dry_run — بلا تنزيل)
    model_out = tmp / "models" / "smoke"
    result = run_training(TrainConfig(
        mode="full", dry_run_model=True, data_dir=str(out_dir),
        output_dir=str(model_out), epochs=1, batch=2, lr=5e-4))
    print(f"5) تدريب smoke: mode={result['mode']} "
          f"train={result['train_samples']} val={result['val_samples']} "
          f"final_loss={result['final_loss']:.4f} "
          f"duration={result['duration_s']}s")
    assert result["train_samples"] > 0 and result["final_loss"] > 0.0

    dt = time.time() - t0
    if not args.keep and not args.workdir:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n✅ SMOKE: PASS — خط الأنابيب كامل في {dt:.1f}s "
          f"(0 تنزيل أوزان، 0 شبكة، 0 PHI)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
