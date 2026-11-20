#!/usr/bin/env python3
"""ATR-F4 — دمج دفعات batch_*/metadata.csv -> metadata_all.csv/.xlsx (مع عمود batch).

الاستخدام:
    python merge_batches.py --out output/S002
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from typing import List, Optional, Tuple

import pandas as pd

REQUIRED_COL = "batch"


def merge_all(out_dir: str) -> Tuple[str, str, int]:
    """يدمج كل batch_*/metadata.csv في out/metadata_all.csv + .xlsx.

    يضمن وجود عمود batch (يُشتق من اسم مجلد الدفعة إن غاب).
    يعيد (csv_path, xlsx_path, n_rows).
    """
    pattern = os.path.join(out_dir, "batch_*", "metadata.csv")
    csv_files = sorted(glob.glob(pattern))
    if not csv_files:
        raise SystemExit(f"no batch metadata found under {out_dir} (pattern: {pattern})")
    frames: List[pd.DataFrame] = []
    for path in csv_files:
        batch_name = os.path.basename(os.path.dirname(path))
        df = pd.read_csv(path, encoding="utf-8-sig")
        if REQUIRED_COL not in df.columns:
            df[REQUIRED_COL] = batch_name
        df[REQUIRED_COL] = df[REQUIRED_COL].fillna(batch_name)
        frames.append(df)
    all_df = pd.concat(frames, ignore_index=True)
    # الترتيب المستقر: دفعة -> صفحة -> سطر -> كلمة
    sort_cols = [c for c in ("batch", "page", "line", "word") if c in all_df.columns]
    all_df = all_df.sort_values(sort_cols).reset_index(drop=True)
    csv_path = os.path.join(out_dir, "metadata_all.csv")
    xlsx_path = os.path.join(out_dir, "metadata_all.xlsx")
    all_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    all_df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"merged {len(csv_files)} batches -> {n_rows_label(len(all_df))}")
    print(f"csv : {csv_path}")
    print(f"xlsx: {xlsx_path}")
    return csv_path, xlsx_path, len(all_df)


def n_rows_label(n: int) -> str:
    return f"{n} rows"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="ATR-F4 merge batch metadata")
    ap.add_argument("--out", required=True, help="مجلد مخرجات sample يحوي batch_*/")
    args = ap.parse_args(argv)
    merge_all(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
