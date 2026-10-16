#!/usr/bin/env python3
"""B200 benchmark CLI wrapper (S3-T1) — thin shell over omni_medical_suite.benchmark_metrics.

Examples:
  python3 scripts/build_benchmark.py cer refs/ hyps/
  python3 scripts/build_benchmark.py manifest --images-dir data/raw/
  python3 scripts/build_benchmark.py check --manifest manifest.local.json
Skeleton status: pure metrics PROVEN by unit tests; folder plumbing PARTIALLY_PROVEN.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from omni_medical_suite.benchmark_metrics import Manifest, cer, wer


def cmd_cer(args: argparse.Namespace) -> int:
    refs = sorted(Path(args.refs).glob("*.txt"))
    hyps = sorted(Path(args.hyps).glob("*.txt"))
    if len(refs) != len(hyps) or not refs:
        print(f"mismatch/empty: {len(refs)} refs vs {len(hyps)} hyps", file=sys.stderr)
        return 2
    rows = []
    for r, h in zip(refs, hyps):
        rt = r.read_text(encoding="utf-8")
        ht = h.read_text(encoding="utf-8")
        rows.append({"file": r.name, "cer": round(cer(rt, ht), 4),
                     "wer": round(wer(rt, ht), 4)})
    mean_cer = sum(x["cer"] for x in rows) / len(rows)
    print(json.dumps({"n": len(rows), "mean_cer": round(mean_cer, 4),
                      "rows": rows}, ensure_ascii=False, indent=2))
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    images = sorted(p.name for p in Path(args.images_dir).iterdir()) if Path(args.images_dir).exists() else []
    m = Manifest().build(iter(images))
    print(json.dumps(m.entries[:5], ensure_ascii=False, indent=2) + "\n...")
    print(f"total: {len(m.entries)} entries (target 200)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="B200 benchmark helper (skeleton)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cer", help="CER/WER over paired ref/hyp .txt folders")
    c.add_argument("refs")
    c.add_argument("hyps")
    m = sub.add_parser("manifest", help="emit skeleton manifest for an images dir")
    m.add_argument("--images-dir", required=True)
    args = p.parse_args()
    return cmd_cer(args) if args.cmd == "cer" else cmd_manifest(args)


if __name__ == "__main__":
    raise SystemExit(main())
