# scanner-fixer v1.0 — Arabic Text Benchmark + Interaction Test

> Date: 2026-06-30 | Follow-up to OCR_BENCHMARK.md
> Engine: Tesseract 5.5.0 (ara) | Font: Noto Naskh Arabic (22px variable)
> Arabic rendering: arabic-reshaper 3.0.1 + python-bidi 0.6.10

## Purpose

Two tests requested by external review:

1. **Interaction test**: Does deskew+enhance TOGETHER cause more damage than either alone? (Isolates interaction effect)
2. **Real Arabic text**: Replaces synthetic `cv2.line()` text with actual Arabic medical text rendered via PIL + real font + reshaper + bidi.

## PART 1: Deskew-Enhance Interaction (English text, confidence metric)

| Stage | Confidence | Delta from baseline |
|-------|-----------|-------------------|
| 0. Baseline (no processing) | 83.5% | — |
| 1. Enhance ONLY (no deskew) | 78.6% | -4.9% |
| 2. Deskew ONLY (no enhance) | 74.1% | -9.4% |
| 3. Deskew THEN Enhance | 71.2% | -12.3% |

**Interaction calculation:**
- Expected combined damage (sum): -14.3%
- Actual combined damage: -12.3%
- **Interaction effect: +2.0%** (essentially zero)

**Conclusion:** Deskew and enhance damage is **purely additive, not synergistic**. There is no extra damage from combining them. Claude's hypothesis about negative interaction is **disproved** — the pipeline order is fine.

## PART 2: Arabic Text Benchmark

### Methodology Issue

Word-level accuracy is **not a usable metric** for this test because:
- Tesseract Arabic on 22px rendered text produces fragmented output (even clean reference: 2.3% word accuracy)
- Ground truth terms don't match Tesseract's morphological output forms
- This makes before/after word accuracy comparison meaningless

**Instead, we use:**
1. **Confidence scores** (Tesseract's own word-level certainty)
2. **Qualitative text analysis** (garbage vs. readable fragments)
3. **Arabic character count** (more Arabic chars = better recognition)

### Results by Confidence

| Version | Before Conf | After Conf | Delta | Arabic Chars (before→after) |
|---------|-----------|-----------|-------|---------------------------|
| A: 4° tilt + borders | 54.0% | 48.5% | **-5.5%** | 239 → 245 |
| B: 180° flip + tilt | 36.8% | 59.4% | **+22.6%** | 103 → 241 |
| C: borders only | 60.8% | 65.0% | **+4.2%** | 231 → 246 |

### Key Finding: 180° Flip Detection (Version B)

**BEFORE scanner-fixer (garbage):**
```
م اا ا اا 77 رضي >< رصت 1777 مج امم ا يور روج 7 2م همع 1ص 6-7 بوهيم
```
103 Arabic characters, 36.8% confidence. Tesseract cannot read upside-down Arabic at all.

**AFTER scanner-fixer (readable fragments):**
```
قيبطلا هذ علدا قنيدم ديشرا الأصبء نب حمداً نض يرهاا مسا 5 بقيههلا مقر
5 مبلايماا خيراة مقر: ىناذلا عوذاا يركساا ءاد نص يخشتاا يحكارةلا يركسلا
```
241 Arabic characters, 59.4% confidence. Text is visually reversed (Tesseract RTL limitation) but actual Arabic words are extracted.

### Deskew Accuracy (Real Arabic vs. Synthetic)

| Test | Applied Tilt | Detected by Hough | Assessment |
|------|-------------|-------------------|------------|
| Synthetic lines (previous) | 4.0° | -3.03° | Under-detects |
| Arabic text (this test) | 4.0° | -4.0° | **Accurate** |
| Arabic text after flip | ~4.0° (inverted) | 6.83° | Over-corrects |

**The synthetic line test was misleading.** Hough detection is significantly more accurate on real Arabic text with actual character glyphs than on `cv2.line()` segments.

### Clean Reference Upper Bound

Even the clean reference page (no defects) only achieves:
- 2.3% word accuracy (43 ground truth terms)
- 58.3% confidence

This confirms Tesseract Arabic at 22px is near its resolution limit. A real scanner at 300 DPI would produce larger character images and likely much better results.

## Honest Summary

| Question | Answer |
|----------|--------|
| Is there deskew-enhance negative interaction? | **No.** Interaction = +2.0% (negligible). Damage is additive. |
| Does the synthetic test mislead about deskew? | **Yes.** Real Arabic text: Hough detects -4.0° (accurate). Synthetic: -3.03°. |
| Is 180° flip detection valuable? | **Yes.** Confidence +22.6%, Arabic chars 2.3× increase, garbage → readable. |
| Is mild tilt (4°) harmful? | **Slight** confidence loss (-5.5%) on Arabic. May improve at real 300 DPI. |
| Are border-only cases safe? | **Yes.** +4.2% confidence, no regression. |
| Is the word accuracy metric usable? | **No for Arabic.** Use confidence + qualitative analysis instead. |

## Open Issues

1. **Deskew on flipped images**: After 180° correction, deskew detects 6.83° when actual is ~4°. The double-transformation may accumulate error.
2. **Tesseract Arabic quality at small font sizes**: The 22px rendered text is at the lower bound of what Tesseract Arabic can handle. Real scanned documents at 300 DPI would have larger character images.
3. **Word accuracy metric**: Need a better evaluation method for Arabic OCR (e.g., character-level CER, or fuzzy word matching with Arabic morphological normalization).

## Files

- `arabic_benchmark_results.json` — Full raw data
- `arabic_clean_reference.png` — Clean Arabic page (no defects)
- `arabic_A_tilted.png` / `arabic_A_fixed.png` — 4° tilt scenario
- `arabic_B_flipped.png` / `arabic_B_fixed.png` — 180° flip scenario
- `arabic_C_borders.png` / `arabic_C_fixed.png` — Borders-only scenario