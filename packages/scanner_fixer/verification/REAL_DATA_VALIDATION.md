# Real-Data Validation Report: normalize + phash Dedup Pipeline

**Date:** 2026-07-13
**Pipeline:** deskew → auto_crop → resize (h=1600) → grayscale → phash (64-bit)
**Images:** `packages/scanner_fixer/verification/` — real Arabic medical document scans

## Test Images

| Image | Description | Size | File Size |
|-------|-------------|------|-----------|
| `arabic_clean_reference.png` | Clean reference scan (patient report: HbA1c, medications) | 850×1200 | 1.63 MB |
| `arabic_A_tilted.png` | Same document, ~4° tilt defect | 850×1200 | 1.19 MB |
| `arabic_B_flipped.png` | Same document, 180° flip | 850×1200 | 1.19 MB |
| `arabic_C_borders.png` | Same document, excess scanner borders/margins | 850×1200 | 1.35 MB |
| `test_scan_realistic.png` | **Different document** (false positive control) | 820×1160 | 1.27 MB |

## Results

### Hamming Distances from Reference

| Image | Raw (no norm) | Normalized | Δ | Notes |
|-------|:---:|:---:|:---:|-------|
| `clean_reference` | 0 | 0 | — | Baseline |
| `A_tilted` | 18 | **24** | +6 | ⚠️ Worse after normalization |
| `B_flipped` | 36 | **34** | -2 | ≈ Same (flip not correctable) |
| `C_borders` | 6 | **8** | +2 | ≈ Same |
| `different_doc` | 38 | **30** | -8 | ✅ Correctly far |

### Clustering at Different Thresholds

| Threshold | Same-doc clusters | Different doc separate? | Verdict |
|:---------:|:-----------------:|:------------------------:|---------|
| 5 | 4 (all separate) | ✅ Yes | False negatives |
| 8 | 3 (ref+C_borders grouped) | ✅ Yes | False negatives |
| 10 | 3 | ✅ Yes | False negatives |
| 12 | 3 | ✅ Yes | False negatives |
| 15 | 3 | ✅ Yes | False negatives |
| 20 | 2 (A_tilt+C_borders; ref alone) | ❌ **No** | False positive |
| 25 | 2 (all same-doc + different_doc in B cluster) | ❌ **No** | False positive |

**No threshold successfully groups all 4 same-document variants while keeping the different document separate.**

### Step-by-Step Normalization Analysis

| Image | Skew detected | After crop (w×h) | After resize (w×h) |
|-------|:---:|:---:|:---:|
| clean_reference | +0.00° | **771×934** | **1321×1600** |
| A_tilted | -3.95° | 850×1200 | 1133×1600 |
| B_flipped | -4.03° | 850×1200 | 1133×1600 |
| C_borders | +0.00° | 850×1200 | 1133×1600 |

## Root Cause Analysis

### Why A_tilted (Hamming=24) and C_borders (Hamming=8) underperform expectations

The core issue is **asymmetric cropping**. The clean reference image has detectable whitespace around its content edges, causing `auto_crop()` to aggressively trim it to 771×934. The tilted and bordered variants, due to their defects, have different whitespace patterns — the tilt shifts the content boundaries, and the borders add uniform white space that the crop algorithm treats as content margin.

After cropping to different sizes and resizing to the same height (1600px), the images end up with **different widths**:

- Reference: **1321px** wide
- All others: **1133px** wide
- **Difference: 188px (16.6%)**

This 16.6% width difference fundamentally changes the spatial frequency content that phash analyzes (DCT on 8×8 blocks), producing high Hamming distances even though the actual document content is identical.

**This is NOT a phash weakness — it's a preprocessing gap.** The normalize pipeline preserves aspect ratio (by design), but when `auto_crop` produces different aspect ratios for the same content, the downstream resize creates incompatible images.

### Why B_flipped (Hamming=34) fails

The 180° flip is correctly identified as a known limitation:

1. `deskew()` uses Hough line detection for angles in [-45°, +45°]. A 180° flip is NOT a rotation in this range — it appears as near-horizontal text that happens to be upside down.
2. The skew detector reports -4.03° (a spurious angle from the upside-down text), which gets "corrected" — making the image slightly more wrong.
3. The known project note in `REAL_SCANS_DIAGNOSTIC.md` states: *"180° flip heuristic was harmful as default"* — so no automatic flip detection was implemented.

**A 180° flip requires a dedicated detection step** (e.g., text orientation classification or Arabic script direction detection), not a Hamming threshold adjustment.

### Why normalization made A_tilted WORSE (18 → 24)

The raw phash comparison (Hamming=18) operates on the original 850×1200 images — same dimensions, so the DCT blocks align similarly despite the tilt. After normalization, the crop step changes the dimensions differently for each image (771×934 vs 850×1200), creating a larger effective difference.

## Separation Analysis

| Metric | Value |
|--------|-------|
| Max Hamming among same-doc variants (excl. flip) | 24/64 |
| Hamming to genuinely different document | 30/64 |
| **Separation gap** | **6 bits** |

A gap of only 6 bits (out of 64) is insufficient for reliable classification. Any threshold high enough to catch A_tilted (≥24) would also catch the different document (30), and even then B_flipped (34) would still be excluded.

## Recommendation

### Keep default threshold = 5

**The verification images test a fundamentally different scenario than the dedup use case.**

The dedup pipeline is designed for: *"same document scanned multiple times with slight positional differences (±20px shift, ±2° skew, different DPI)."* The synthetic benchmark (Task B3) validated threshold=5 for exactly this scenario, achieving 100% detection with 0 false positives.

The verification images test: *"same document with different DEFECT TYPES (tilt, flip, borders) that change the effective crop area."* This is a defect-correction validation scenario, not a dedup scenario.

### For the dedup use case (production)

- **Threshold = 5** remains the validated default
- Works for: shift (±30px), resolution (50%-200% DPI), minor skew
- Fails for: 180° flip, significant aspect ratio changes from uneven cropping

### For defect-type detection (NOT the current use case)

Would require additional preprocessing:
1. **Flip detection** — dedicated orientation classifier (separate from phash)
2. **Whitespace normalization** — pad all images to the same aspect ratio BEFORE crop, or use content-aware padding after crop to ensure consistent dimensions
3. **Higher hash size** — `hash_size=16` (256-bit) would provide more granularity at the cost of speed

### Bug Fixed During Validation

`dedup.py` had a bug where the first image in each cluster (the representative) was recorded with `hamming_distance_from_representative = 64` (the max-distance initial value) instead of `0`. This has been fixed and will be committed alongside this report.

## Files Generated

- `/home/z/my-project/download/real_validation_results.csv` — machine-readable results
- This report: `packages/scanner_fixer/verification/REAL_DATA_VALIDATION.md`
