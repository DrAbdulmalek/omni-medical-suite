# scanner-fixer v1.0 — OCR Benchmark (Honest Results)

> Date: 2026-06-30 | Engine: Tesseract 5.5.0 (eng, PSM 6)
> Environment: Python 3.13.5, Ubuntu, no GPU

## TL;DR

| Scenario | Before Fix | After Fix | Delta |
|----------|-----------|-----------|-------|
| **A: 4° tilt** | 71.4% | 59.2% | **-12.2%** ⚠️ |
| **B: 180° flip + 4° tilt** | 0.0% | 55.1% | **+55.1%** ✅ |
| **C: dark borders only** | 77.6% | 77.6% | 0.0% = |

## What This Proves

1. **180° flip detection is genuinely valuable.** A flipped page goes from complete garbage (0% — Tesseract outputs random characters) to 55.1% word accuracy. This is not marginal — it's the difference between "OCR fails entirely" and "OCR works."

2. **The enhance step (CLAHE + denoise) partially compensates for deskew damage.** Isolated testing shows CLAHE adds +8.2% and denoise adds +8.2% when applied after crop+deskew.

3. **The deskew step is the weak link for mildly tilted images.** For a 4° tilt on synthetic text, deskew DETECTS -3.03° but the correction introduces artifacts that confuse Tesseract more than the original tilt.

## Root Cause Analysis (Version A Regression)

Step-by-step OCR accuracy tracking:

| Stage | Accuracy | Delta |
|-------|----------|-------|
| 0. Original (no processing) | 71.4% | — |
| 1. Crop only | 71.4% | +0.0% |
| 2. Crop + Rotate | 71.4% | +0.0% |
| 3. Crop + Rotate + **Deskew** | 55.1% | **-16.3%** |
| 4. Full pipeline | 59.2% | +4.1% |

**The deskew step alone causes the entire regression.** Crop and rotate are neutral. Enhance partially recovers.

### Why Deskew Hurts

The Hough line detection is **inaccurate on this type of text.** Validation test:

| Applied Tilt | Detected by Hough | Corrected to |
|-------------|-------------------|-------------|
| 0.5° | -5.92° | -5.92° |
| 1.0° | -4.98° | -4.98° |
| 2.0° | -5.95° | -5.95° |
| 3.0° | -6.07° | -6.07° |

The detector reports ~6° even for images with 0.5° tilt. This means it's picking up noise from the rendered text lines, not actual page skew. The subsequent "correction" introduces a NEW tilt of ~2-3° in the wrong direction.

**Note:** This may be specific to synthetic line-rendered text. Real scanned text (with actual character glyphs) may produce more reliable Hough line detection.

## Honest Assessment

| Feature | Verdict | Evidence |
|---------|---------|----------|
| 180° flip detection | **Proven value** | 0% → 55.1% on flipped pages |
| Border cropping | **Neutral/safe** | No accuracy loss on clean images |
| CLAHE + denoise | **Positive** | +8.2% each when isolated |
| Sharpen | **Neutral** | No measurable effect |
| Deskew (Hough) | **Needs fix** | -16.3% regression on mild tilt |

## What Needs Attention

1. **Deskew threshold**: The `< 0.3°` skip threshold is too low. With Hough detecting ~6° on straight images, we need either:
   - A confidence metric for the detected angle (e.g., number of lines, agreement between lines)
   - A higher skip threshold or maximum correction limit
   - Using projection method as validation (cross-check Hough vs projection)

2. **Real scan testing**: These tests use OpenCV-rendered text lines, not actual scanned text with character glyphs. Real scans may produce different Hough line results. This benchmark should be repeated with real medical documents.

3. **NLM denoise performance**: Not tested here at scale. For production batch processing of 300 DPI images, `fastNlMeansDenoisingColored` may be slow (seconds per page).

## Raw OCR Output Samples

### Version B (180° flip) — BEFORE
```
Aug PoueS bum juawyodeg euisipan POWWOUON 40 sujuow ¢ fyop 2ouo - Susie
"¥ ewypeq yo — 6woz Ayop 2ouo - °~ Ayop eo — BwOOS Ye22ND syww ogi
```
*(Complete garbage — Tesseract cannot read upside-down text)*

### Version B (180° flip) — AFTER
```
cm FAHAD MEDICAL CITY Patient Nome: AI-Rashid Dote of Birth: 15/03/1965
potient 10: MMRN-2024-00847 Diagnosis: TyPe 2 Diabetes Mellitus HbAte:
8-2% (Torget: < 7.0%) Fasting Glucose 480 mg/dl Blood Pressure 445/92
mmHg Current Medications: 4. Metformin ~ twice daily 2. Lisinopril 10m9
```
*(Readable — patient name, diagnosis, medications all extracted despite some OCR errors)*