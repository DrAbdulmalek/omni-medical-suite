#!/usr/bin/env python3
"""TASK 011 (PHASE 2) — Segmentation validation against GT588.

GT588 reality check (PROVEN at base a8f829a):
  - packages/gt_core/ground_truth_588.txt = TEXT-ONLY ground truth
    (25 raw lines, 23 non-empty, Arabic medical TOC "جدول المحتويات").
  - The source page image "Scanned Document-588.jpg" (2550x4200, per
    BENCHMARK_REPORT_588.md) is NOT in the repository (0 images under
    packages/gt_core/). => pixel-level IoU vs the real scan = BLOCKED.
  - Therefore this run uses a REPRODUCIBLE SYNTHETIC-RENDER PROXY:
    the GT text itself is rendered to a page image with known line
    bands, and the repo's real segmenters are measured against those
    bands (1-D interval IoU on the y-axis + word-count agreement).
    Per DATASETS_POLICY / brief §54 this is labelled SYNTHETIC-RENDER
    and must NOT be read as real-scan accuracy.

Metrics (proxy):
  - line_count_detected vs line_count_expected (GT non-empty lines)
  - band IoU (1-D y-interval IoU, best match per expected band)
  - band precision / recall at IoU >= 0.5
  - word segmentation: words detected per matched line vs GT tokens

Usage:
  python3 scripts/eval_segmentation_gt588.py [--out docs/portfolio/SEGMENTATION_VALIDATION]
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "hf-space"))

GT_TXT = REPO / "packages" / "gt_core" / "ground_truth_588.txt"


def load_gt_lines() -> list[str]:
    lines = [ln.strip() for ln in GT_TXT.read_text(encoding="utf-8").splitlines()]
    return [ln for ln in lines if ln]


def pick_arabic_font() -> str | None:
    try:
        out = subprocess.run(
            ["fc-list", ":lang=ar", "--format=%{file}\n"],
            capture_output=True, text=True, timeout=20,
        )
        fonts = [f for f in out.stdout.splitlines() if f.strip()]
        for f in fonts:
            if "amiri" in f.lower() and "italic" not in f.lower():
                return f
        return fonts[0] if fonts else None
    except Exception:
        return None


def render_page(gt_lines: list[str], font_path: str | None):
    """Render GT lines onto a white page; return (PIL image, expected bands)."""
    from PIL import Image, ImageDraw, ImageFont

    import arabic_reshaper
    from bidi.algorithm import get_display

    width, line_h, margin, gap = 1400, 72, 60, 46
    height = margin * 2 + line_h * len(gt_lines) + gap * (len(gt_lines) - 1)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, 44) if font_path else ImageFont.load_default()

    bands = []
    y = margin
    for ln in gt_lines:
        txt = get_display(arabic_reshaper.reshape(ln))
        draw.text((margin, y), txt, font=font, fill="black")
        bands.append((y, y + line_h))
        y += line_h + gap

    # Measure the ACTUAL ink band per line slot from the rendered page
    # (a slot is the padded region; the ink is the dark rows inside it).
    import numpy as np

    g = np.array(img.convert("L"))
    ink_bands = []
    for (y0, y1) in bands:
        region = g[y0:y1, :]
        dark_rows = np.where((region < 128).any(axis=1))[0]
        if len(dark_rows):
            ink_bands.append((int(y0 + dark_rows[0]), int(y0 + dark_rows[-1] + 1)))
        else:
            ink_bands.append((y0, y1))
    return img, ink_bands


def interval_iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union else 0.0


def match_bands(detected, expected, thr=0.5):
    """Greedy best-match of detected y-bands to expected bands."""
    matches, used = [], set()
    for exp in expected:
        best, best_iou = None, 0.0
        for i, det in enumerate(detected):
            if i in used:
                continue
            iou = interval_iou(exp, det)
            if iou > best_iou:
                best, best_iou = i, iou
        if best is not None and best_iou >= thr:
            used.add(best)
            matches.append((exp, detected[best], best_iou))
        else:
            matches.append((exp, None, 0.0))
    return matches


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "docs/portfolio/SEGMENTATION_VALIDATION"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from packages.vision.htr.line_segmenter import ContourLineSegmenter, ProjectionProfileSegmenter
    from packages.vision.htr.word_segmenter import ArabicWordSegmenter

    gt_lines = load_gt_lines()
    font = pick_arabic_font()
    page, expected_bands = render_page(gt_lines, font)  # bands = actual ink rows per line
    gt_tokens = [len(ln.replace("\u00a0", " ").split()) for ln in gt_lines]

    import numpy as np  # noqa: F401  (segmenters depend on it)

    gray = np.array(page.convert("L"))
    results = {}

    for name, seg in (
        ("projection", ProjectionProfileSegmenter()),
        ("contour", ContourLineSegmenter()),
    ):
        info = seg.segment_with_info(gray)
        det_bands = [(d["y_start"], d["y_end"]) for _, d in info]
        matches = match_bands(det_bands, expected_bands)
        ious = [m[2] for m in matches]
        matched = [m for m in matches if m[1] is not None]
        precision = len(matched) / len(det_bands) if det_bands else 0.0
        recall = len(matched) / len(expected_bands) if expected_bands else 0.0

        # word segmentation on matched lines (profile strategy default)
        word_seg = ArabicWordSegmenter()
        word_rows, word_ok = [], 0
        for (exp, det, iou), gt_line, n_gt in zip(matches, gt_lines, gt_tokens):
            if det is None:
                word_rows.append({"gt_line": gt_line, "gt_words": n_gt, "detected_words": None, "match": "NO_LINE"})
                continue
            line_img = page.crop((0, exp[0], page.width, exp[1]))
            n_det = len(word_seg.segment(line_img))
            ok = abs(n_det - n_gt) <= 1
            word_ok += int(ok)
            word_rows.append({"gt_line": gt_line, "gt_words": n_gt, "detected_words": n_det, "match": "OK" if ok else "DIFF"})

        results[name] = {
            "detected_lines": len(det_bands),
            "expected_lines": len(expected_bands),
            "matched_at_iou05": len(matched),
            "mean_band_iou": round(sum(ious) / len(ious), 4) if ious else 0.0,
            "band_precision": round(precision, 4),
            "band_recall": round(recall, 4),
            "word_lines_agree": word_ok,
            "word_lines_total": len(matches),
            "det_bands_sample": det_bands[:5],
        }

        with open(out / f"gt588_lines_{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["gt_index", "gt_text", "expected_y0", "expected_y1", "detected_y0", "detected_y1", "iou"])
            for idx, ((exp, det, iou), gt_line) in enumerate(zip(matches, gt_lines)):
                w.writerow([idx, gt_line, exp[0], exp[1], det[0] if det else "", det[1] if det else "", iou])
        with open(out / f"gt588_words_{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["gt_line", "gt_words", "detected_words", "match"])
            w.writeheader()
            w.writerows(word_rows)

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": "a8f829add290132287bfcc26b087772606108898",
        "branch": "feat/seg-eval-gt588",
        "gt_file": str(GT_TXT.relative_to(REPO)),
        "gt_lines_nonempty": len(gt_lines),
        "page_image_in_repo": False,
        "method": "SYNTHETIC-RENDER PROXY (GT text rendered with known bands; 1-D interval IoU)",
        "font": font,
        "results": results,
        "disclaimer": "SYNTHETIC-RENDER proxy — NOT real-scan accuracy. Real-scan IoU BLOCKED (page image absent from repo).",
    }
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    md = ["# Segmentation validation — GT588 (PHASE 2 / TASK 011)", "",
          f"Generated: {payload['generated_utc']} · branch `{payload['branch']}` · base `{payload['base_commit'][:7]}`",
          "", "## Reality check (PROVEN)", "",
          f"- GT = text-only (`{payload['gt_file']}`): **{len(gt_lines)} non-empty lines** (25 raw lines).",
          "- The scanned page `Scanned Document-588.jpg` is **NOT in the repo** (0 images in packages/gt_core/) → real-scan IoU = **BLOCKED**.",
          "- Method: **SYNTHETIC-RENDER proxy** — GT text rendered with known line bands; repo segmenters measured by 1-D interval IoU + word-count agreement. Must not be read as real-scan accuracy (§54).",
          "", "## Metrics", "",
          "| Metric | ProjectionProfile | Contour |", "|---|---|---|"]
    for k, label in [("detected_lines", "detected lines (expected 23)"), ("matched_at_iou05", "matched bands (IoU≥0.5)"),
                     ("mean_band_iou", "mean band IoU"), ("band_precision", "band precision"),
                     ("band_recall", "band recall"), ("word_lines_agree", "word-count agree (±1) / total")]:
        r0, r1 = results["projection"], results["contour"]
        v0 = f"{r0['word_lines_agree']}/{r0['word_lines_total']}" if "agree" in k else r0[k]
        v1 = f"{r1['word_lines_agree']}/{r1['word_lines_total']}" if "agree" in k else r1[k]
        md.append(f"| {label} | {v0} | {v1} |")
    md += ["", "## LIMITS", "",
           "- Real-scan segmentation IoU: BLOCKED (page image absent).",
           "- Proxy is SYNTHETIC-RENDER; single font, clean background.",
           "- No OCR/HTR engine executed in this run (segmentation only)."]
    (out / "SEGMENTATION_VALIDATION.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
