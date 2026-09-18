# Segmentation validation — GT588 (PHASE 2 / TASK 011)

Generated: 2026-09-18T15:23:28.908726+00:00 · branch `feat/seg-eval-gt588` · base `a8f829a`

## Reality check (PROVEN)

- GT = text-only (`packages/gt_core/ground_truth_588.txt`): **23 non-empty lines** (25 raw lines).
- The scanned page `Scanned Document-588.jpg` is **NOT in the repo** (0 images in packages/gt_core/) → real-scan IoU = **BLOCKED**.
- Method: **SYNTHETIC-RENDER proxy** — GT text rendered with known line bands; repo segmenters measured by 1-D interval IoU + word-count agreement. Must not be read as real-scan accuracy (§54).

## Metrics

| Metric | ProjectionProfile | Contour |
|---|---|---|
| detected lines (expected 23) | 23 | 23 |
| matched bands (IoU≥0.5) | 23 | 23 |
| mean band IoU | 0.6573 | 0.6478 |
| band precision | 1.0 | 1.0 |
| band recall | 1.0 | 1.0 |
| word-count agree (±1) / total | 1/23 | 1/23 |

## LIMITS

- Real-scan segmentation IoU: BLOCKED (page image absent).
- Proxy is SYNTHETIC-RENDER; single font, clean background.
- No OCR/HTR engine executed in this run (segmentation only).
