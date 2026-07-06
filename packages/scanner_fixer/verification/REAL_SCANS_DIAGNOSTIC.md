# Real Scan Diagnostic — Raw Results

> Date: 2026-06-30 | 5 real Syrian medical/legal documents
> NO code modifications — data collection only per Claude's instructions

## 1. 180° Flip Detection on Originals

| File | Layout | Density R (bot/top) | Votes | Detected? | Correct? |
|------|--------|---------------------|-------|-----------|----------|
| IMG_20260630_001239_035.jpg | form/table | **1.72** | 3/3 | **True** | **FALSE POSITIVE** — page is upright |
| IMG-20260629-WA0010.jpg | memo+header | 0.81 | 0/3 | False | ✅ Correct |
| IMG-20260629-WA0011.jpg | memo (cont.) | 0.61 | 1/3 | False | ✅ Correct |
| IMG-20260629-WA0012.jpg | memo+table+stamps | 0.77 | 0/3 | False | ✅ Correct |
| IMG-20260629-WA0001.jpg | memo+header+table | **2.27** | 3/3 | **True** | **FALSE POSITIVE** — page is upright |

**2 out of 5 upright pages are falsely flagged as flipped.**

The false positives have density ratios of 1.72 and 2.27 — heavy content at the bottom (tables, stamps, or form fields). These are NOT "balanced 50/50" pages. They are the OPPOSITE: heavily bottom-weighted, which triggers votes 1 and 2.

## 2. 180° Flip Detection on Flipped Variants

| File | Original Detected | Flipped Detected | Correctly Identified? |
|------|-------------------|------------------|----------------------|
| IMG_20260630_001239_035.jpg | True (wrong) | **False** | ✗ **MISSED** |
| IMG-20260629-WA0010.jpg | False | True | ✅ Correct |
| IMG-20260629-WA0011.jpg | False | True | ✅ Correct |
| IMG-20260629-WA0012.jpg | False | **False** | ✗ **MISSED** |
| IMG-20260629-WA0001.jpg | True (wrong) | **False** | ✗ **MISSED** |

**Only 2 out of 5 flipped pages are correctly detected.**

- IMG_20260630: Was falsely positive on original (3/3 votes), so flipped version gets 0/3 → missed
- IMG-20260629-WA0012: Density ratio is 0.77 (moderately top-heavy), flipped becomes 1.31 but only gets 1/3 votes → missed
- IMG-20260629-WA0001: Was falsely positive on original (3/3 votes), flipped gets 0/3 → missed

**The heuristic has a fundamental asymmetry problem**: it gives 3/3 votes for heavily bottom-weighted upright pages (false positive), then 0/3 for their flipped versions (missed). The votes are inverted but never cross the threshold correctly in both directions.

## 3. Skew Detection on 5° Tilted Variants

| File | Actual Tilt | Detected | Error | Within ±3°? | Hough Lines | Std Dev |
|------|-------------|----------|-------|-------------|-------------|---------|
| IMG_20260630_001239_035.jpg | 5.0° | **+27.8°** | 22.8° | ✗ | 2464 (162 filtered) | **18.86°** |
| IMG-20260629-WA0010.jpg | 5.0° | -3.2° | 8.2° | ✗ | 1210 (534 filtered) | **17.56°** |
| IMG-20260629-WA0011.jpg | 5.0° | -5.0° | 10.0° | ✗ | 945 (745 filtered) | 1.10° |
| IMG-20260629-WA0012.jpg | 5.0° | -4.7° | 9.7° | ✗ | 971 (802 filtered) | 3.94° |
| IMG-20260629-WA0001.jpg | 5.0° | -5.0° | 10.0° | ✗ | 3733 (864 filtered) | 9.31° |

**0 out of 5 within ±3° tolerance.** The deskew detection is unreliable on real Arabic documents.

Key observation: **high std dev correlates with bad detection.**
- IMG_20260630 (std=18.86°): Wildly wrong (27.8° instead of 5°)
- IMG_20260629-WA0011 (std=1.10°): Closest to correct (-5.0° vs 5.0° — sign error but magnitude good)

The std of detected angles is a strong confidence indicator. When std > 5°, the detection should not be trusted.

## 4. Density Distribution in Real Documents

| File | Ratio | Distribution Type |
|------|-------|-------------------|
| IMG-20260629-WA0010.jpg | 0.81 | Near-balanced, slight top-heavy |
| IMG-20260629-WA0012.jpg | 0.77 | Moderate top-heavy |
| IMG-20260629-WA0011.jpg | 0.61 | Top-heavy |
| IMG_20260630_001239_035.jpg | 1.72 | **Heavy bottom** (form fields/table) |
| IMG-20260629-WA0001.jpg | 2.27 | **Very heavy bottom** (large table) |

**Claude's hypothesis confirmed**: the 50/50 "balanced page" case from the Arabic synthetic test is NOT the common failure mode. The real failure modes are:
- **Bottom-heavy pages** (ratio > 1.5): false positive flip detection
- **Table-dense pages** (IMG_20260630): massive skew detection errors

## 5. Raw Data

Full JSON with all diagnostic details: `real_scans_diagnostic.json`

## Implications (for Claude — NO code changes made)

1. **Flip heuristic is harmful on real data**: 2/5 false positives on upright pages means it should NOT run automatically. A false 180° rotation destroys the document.

2. **Deskew is unreliable on real Arabic text**: 0/5 within tolerance, with one catastrophic failure (22.8° error). The `angles_std` metric is a viable confidence signal.

3. **The "balanced page" concern was a red herring**: The actual problem is the OPPOSITE — heavily asymmetric pages trigger false positives. The heuristic assumes "normal pages are top-heavy" which is not universally true.

4. **Tesseract OSD was not tested here** per Claude's original instructions ("no code fixes"), but it should be the next step before any heuristic modification.